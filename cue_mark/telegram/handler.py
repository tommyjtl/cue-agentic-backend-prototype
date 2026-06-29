from __future__ import annotations

import logging
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from cue.config import settings
from cue_mark.models import CaptureRequest
from cue_mark.service import MarkService
from cue_mark.telegram.client import TelegramClient
from cue_mark.telegram.commands import (
    SEARCH_USAGE_MESSAGE,
    ParsedTextCommand,
    parse_text_command,
)
from cue_mark.page_gates import PageFetchBlockedError
from cue_mark.telegram.formatting import format_search_reply
from cue_mark.telegram.parser import InboundMessage, TelegramParseError, parse_update
from cue_mark.telegram.store import TelegramEventStore
from cue_search.models import SearchRequest
from cue_search.search_service import SearchService

logger = logging.getLogger(__name__)

TYPING_REFRESH_INTERVAL_SECONDS = 4.0

IMAGE_SUFFIXES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
}


class TelegramUpdateHandler:
    def __init__(
        self,
        *,
        mark_service: MarkService | None = None,
        search_service: SearchService | None = None,
        telegram_client: TelegramClient | None = None,
        event_store: TelegramEventStore | None = None,
    ) -> None:
        self.search_service = search_service or SearchService()
        self.mark_service = mark_service or MarkService(search_service=self.search_service)
        self.telegram_client = telegram_client
        self.event_store = event_store or TelegramEventStore(settings.telegram_jobs_db_file)

    def accept_update(self, update: dict[str, Any]) -> tuple[dict[str, str], InboundMessage | None]:
        inbound = parse_update(update)
        if inbound is None:
            return {"status": "ignored", "reason": "not_a_message_update"}, None

        if parse_text_command(inbound.text).kind == "ping":
            client = self.telegram_client or TelegramClient()
            self._process_ping(client, inbound)
            return {"status": "ping", "event_id": inbound.event_id}, None

        if not self._sender_allowed(inbound.sender_id):
            logger.info("Ignoring Telegram message from unauthorized sender: %s", inbound.sender_id)
            return {"status": "ignored", "reason": "sender_not_allowed"}, None

        if not self.event_store.try_begin(
            inbound.event_id,
            chat_id=inbound.chat_id,
            sender_id=inbound.sender_id,
        ):
            return {"status": "duplicate", "event_id": inbound.event_id}, None

        return {"status": "accepted", "event_id": inbound.event_id}, inbound

    def process_inbound(self, inbound: InboundMessage) -> None:
        client = self.telegram_client or TelegramClient()
        command = parse_text_command(inbound.text)

        action = chat_action_for_inbound(inbound)
        with self._typing_indicator(client, inbound.chat_id, action=action):
            try:
                if command.kind == "search":
                    self._process_search(client, inbound, command)
                elif command.kind == "reindex":
                    self._process_reindex(client, inbound)
                else:
                    self._process_mark(client, inbound)
            except PageFetchBlockedError as exc:
                logger.info("Blocked page fetch for Telegram update %s: %s", inbound.event_id, exc)
                self.event_store.mark_failed(inbound.event_id, error=str(exc))
                self._send_reply(client, inbound, str(exc))
            except Exception as exc:
                logger.exception("Failed to process Telegram update %s", inbound.event_id)
                self.event_store.mark_failed(inbound.event_id, error=str(exc))
                self._send_reply(client, inbound, f"Could not process message: {exc}")

    def _process_mark(self, client: TelegramClient, inbound: InboundMessage) -> None:
        image_paths: list[Path] = []
        try:
            image_paths = self._download_images(client, inbound)
            result = self.mark_service.capture(
                CaptureRequest(
                    text=inbound.text,
                    urls=inbound.urls,
                    image_paths=[str(path) for path in image_paths],
                    sync_index=True,
                )
            )
            self._send_reply(client, inbound, f"Saved: {result.title}")
            self.event_store.mark_completed(
                inbound.event_id,
                title=result.title,
                file_path=result.file_path,
            )
        finally:
            self._cleanup_downloads(image_paths)

    def _process_search(
        self,
        client: TelegramClient,
        inbound: InboundMessage,
        command: ParsedTextCommand,
    ) -> None:
        if not command.search_query:
            self._send_reply(client, inbound, SEARCH_USAGE_MESSAGE)
            self.event_store.mark_completed(
                inbound.event_id,
                title="search",
                file_path="",
            )
            return

        corpus_root = str(settings.mark_vault_dir)
        response = self.search_service.search(
            SearchRequest(
                query=command.search_query,
                corpus_root=corpus_root,
                llm=settings.search_llm_config(),
                summary_only=True,
            )
        )
        self._send_reply(
            client,
            inbound,
            response.answer,
            html=True,
        )
        self.event_store.mark_completed(
            inbound.event_id,
            title=f"search: {command.search_query[:80]}",
            file_path="",
        )

    def _process_ping(self, client: TelegramClient, inbound: InboundMessage) -> None:
        if self._sender_allowed(inbound.sender_id):
            reply = f"pong — you're allowed (user id: {inbound.sender_id})"
        else:
            reply = (
                f"Not allowed. Your user id is {inbound.sender_id}. "
                "Add it to CUE_TELEGRAM_ALLOWED_USERS."
            )
        self._send_reply(client, inbound, reply)

    def _process_reindex(self, client: TelegramClient, inbound: InboundMessage) -> None:
        corpus_root = str(settings.mark_vault_dir)
        result = self.search_service.sync_index(corpus_root)
        reply = f"Indexed {result.chunks_indexed} chunks from {result.files_scanned} files."
        self._send_reply(client, inbound, reply)
        self.event_store.mark_completed(
            inbound.event_id,
            title="reindex",
            file_path=corpus_root,
        )

    def _send_reply(
        self,
        client: TelegramClient,
        inbound: InboundMessage,
        text: str,
        *,
        html: bool = False,
    ) -> None:
        if html:
            client.send_message(
                inbound.chat_id,
                format_search_reply(text),
                parse_mode="HTML",
                fallback_text=text,
            )
        else:
            client.send_message(inbound.chat_id, text)

    @contextmanager
    def _typing_indicator(
        self,
        client: TelegramClient,
        chat_id: str,
        *,
        action: str = "typing",
    ) -> Iterator[None]:
        stop_event = threading.Event()
        thread = threading.Thread(
            target=_refresh_chat_action,
            args=(client, chat_id),
            kwargs={"action": action, "stop_event": stop_event},
            daemon=True,
        )
        thread.start()
        try:
            yield
        finally:
            stop_event.set()
            thread.join(timeout=1.0)

    def _download_images(self, client: TelegramClient, inbound: InboundMessage) -> list[Path]:
        if not inbound.photo_file_ids:
            return []

        temp_dir = Path(tempfile.mkdtemp(prefix="cue-telegram-"))
        downloaded: list[Path] = []

        for index, file_id in enumerate(inbound.photo_file_ids):
            metadata = client.get_file(file_id)
            file_path = str(metadata.get("file_path") or "").strip()
            if not file_path:
                continue
            suffix = Path(file_path).suffix.lower() or ".jpg"
            target = temp_dir / f"photo-{index}{suffix}"
            target.write_bytes(client.download_file(file_path))
            downloaded.append(target)

        return downloaded

    @staticmethod
    def _cleanup_downloads(image_paths: list[Path]) -> None:
        for path in image_paths:
            path.unlink(missing_ok=True)
        if image_paths:
            temp_dir = image_paths[0].parent
            try:
                temp_dir.rmdir()
            except OSError:
                pass

    def _sender_allowed(self, sender_id: str) -> bool:
        allowed = settings.telegram_allowed_user_set
        if not allowed:
            return True
        return sender_id in allowed


def chat_action_for_inbound(inbound: InboundMessage) -> str:
    if inbound.photo_file_ids:
        return "upload_photo"
    return "typing"


def _refresh_chat_action(
    client: TelegramClient,
    chat_id: str,
    *,
    action: str,
    stop_event: threading.Event,
) -> None:
    while not stop_event.is_set():
        try:
            client.send_chat_action(chat_id, action=action)
        except Exception:
            logger.exception("Failed to refresh Telegram chat action for chat %s", chat_id)
        if stop_event.wait(TYPING_REFRESH_INTERVAL_SECONDS):
            break


__all__ = ["TelegramUpdateHandler", "TelegramParseError", "chat_action_for_inbound"]
