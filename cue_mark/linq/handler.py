from __future__ import annotations

import json
import logging
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from cue.config import settings
from cue_mark.linq.client import LinqClient
from cue_mark.linq.commands import (
    SEARCH_USAGE_MESSAGE,
    ParsedTextCommand,
    parse_text_command,
)
from cue_mark.linq.parser import InboundMessage, LinqParseError, parse_message_received_event
from cue_mark.linq.store import LinqEventStore
from cue_mark.linq.verify import WebhookHeaders, WebhookVerificationError, verify_webhook_signature
from cue_mark.models import CaptureRequest
from cue_mark.service import MarkService
from cue_search.models import SearchRequest
from cue_search.search_service import SearchService

logger = logging.getLogger(__name__)

IMAGE_SUFFIXES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
}


class LinqWebhookHandler:
    def __init__(
        self,
        *,
        mark_service: MarkService | None = None,
        search_service: SearchService | None = None,
        linq_client: LinqClient | None = None,
        event_store: LinqEventStore | None = None,
    ) -> None:
        self.mark_service = mark_service or MarkService()
        self.search_service = search_service or SearchService()
        self.linq_client = linq_client
        self.event_store = event_store or LinqEventStore(settings.linq_jobs_db_file)

    def accept_webhook(
        self,
        *,
        body: bytes,
        headers: WebhookHeaders,
    ) -> dict[str, str]:
        verify_webhook_signature(
            body=body,
            secret=settings.linq_webhook_secret,
            headers=headers,
            max_age_seconds=settings.linq_webhook_max_age_seconds,
        )

        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise LinqParseError("Webhook payload must be a JSON object.")

        inbound = parse_message_received_event(payload)
        if inbound is None:
            return {"status": "ignored", "reason": "not_an_inbound_message_received_event"}

        if not self._sender_allowed(inbound.sender_handle):
            logger.info("Ignoring Linq message from unauthorized sender: %s", inbound.sender_handle)
            return {"status": "ignored", "reason": "sender_not_allowed"}

        if not self.event_store.try_begin(
            inbound.event_id,
            chat_id=inbound.chat_id,
            sender_handle=inbound.sender_handle,
        ):
            return {"status": "duplicate", "event_id": inbound.event_id}

        return {"status": "accepted", "event_id": inbound.event_id, "_inbound": inbound}

    def accept_payload_dict(self, payload: dict[str, Any]) -> tuple[dict[str, str], InboundMessage | None]:
        inbound = parse_message_received_event(payload)
        if inbound is None:
            return {"status": "ignored", "reason": "not_an_inbound_message_received_event"}, None
        if not self._sender_allowed(inbound.sender_handle):
            return {"status": "ignored", "reason": "sender_not_allowed"}, None
        if not self.event_store.try_begin(
            inbound.event_id,
            chat_id=inbound.chat_id,
            sender_handle=inbound.sender_handle,
        ):
            return {"status": "duplicate", "event_id": inbound.event_id}, None
        return {"status": "accepted", "event_id": inbound.event_id}, inbound

    def process_inbound(self, inbound: InboundMessage) -> None:
        client = self.linq_client or LinqClient()
        command = parse_text_command(inbound.text)

        with self._typing_indicator(client, inbound.chat_id):
            try:
                if command.kind == "search":
                    self._process_search(client, inbound, command)
                elif command.kind == "reindex":
                    self._process_reindex(client, inbound)
                else:
                    self._process_mark(client, inbound)
            except Exception as exc:
                logger.exception("Failed to process Linq inbound message %s", inbound.event_id)
                self.event_store.mark_failed(inbound.event_id, error=str(exc))
                self._send_reply(
                    client,
                    inbound,
                    f"Could not process message: {exc}",
                    idempotency_key=f"error-{inbound.event_id}",
                )

    def _process_mark(self, client: LinqClient, inbound: InboundMessage) -> None:
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
            self._send_reply(
                client,
                inbound,
                f"Saved: {result.title}",
                idempotency_key=f"mark-reply-{inbound.event_id}",
            )
            self.event_store.mark_completed(
                inbound.event_id,
                title=result.title,
                file_path=result.file_path,
            )
        finally:
            self._cleanup_downloads(image_paths)

    def _process_search(
        self,
        client: LinqClient,
        inbound: InboundMessage,
        command: ParsedTextCommand,
    ) -> None:
        if not command.search_query:
            self._send_reply(
                client,
                inbound,
                SEARCH_USAGE_MESSAGE,
                idempotency_key=f"search-usage-{inbound.event_id}",
            )
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
            idempotency_key=f"search-reply-{inbound.event_id}",
        )
        self.event_store.mark_completed(
            inbound.event_id,
            title=f"search: {command.search_query[:80]}",
            file_path="",
        )

    def _process_reindex(self, client: LinqClient, inbound: InboundMessage) -> None:
        corpus_root = str(settings.mark_vault_dir)
        result = self.search_service.sync_index(corpus_root)
        reply = f"Indexed {result.chunks_indexed} chunks from {result.files_scanned} files."
        self._send_reply(
            client,
            inbound,
            reply,
            idempotency_key=f"reindex-reply-{inbound.event_id}",
        )
        self.event_store.mark_completed(
            inbound.event_id,
            title="reindex",
            file_path=corpus_root,
        )

    def _send_reply(
        self,
        client: LinqClient,
        inbound: InboundMessage,
        text: str,
        *,
        idempotency_key: str,
    ) -> None:
        client.send_text_message(
            inbound.chat_id,
            text,
            idempotency_key=idempotency_key,
        )

    @contextmanager
    def _typing_indicator(self, client: LinqClient, chat_id: str) -> Iterator[None]:
        try:
            client.start_typing(chat_id)
        except Exception:
            logger.exception("Failed to start Linq typing indicator for chat %s", chat_id)
        try:
            yield
        finally:
            try:
                client.stop_typing(chat_id)
            except Exception:
                logger.exception("Failed to stop Linq typing indicator for chat %s", chat_id)

    def _download_images(self, client: LinqClient, inbound: InboundMessage) -> list[Path]:
        downloaded: list[Path] = []
        if not inbound.media_urls and not inbound.attachment_ids:
            return downloaded

        temp_dir = Path(tempfile.mkdtemp(prefix="cue-linq-"))

        for index, media_url in enumerate(inbound.media_urls):
            suffix = _suffix_from_url(media_url, default=".jpg")
            target = temp_dir / f"media-{index}{suffix}"
            target.write_bytes(client.download_url(media_url))
            downloaded.append(target)

        for index, attachment_id in enumerate(inbound.attachment_ids):
            metadata = client.get_attachment(attachment_id)
            download_url = str(metadata.get("download_url") or "").strip()
            if not download_url:
                continue
            content_type = str(metadata.get("content_type") or "")
            suffix = IMAGE_SUFFIXES.get(content_type.lower(), _suffix_from_filename(metadata.get("filename")))
            target = temp_dir / f"attachment-{index}{suffix}"
            target.write_bytes(client.download_url(download_url))
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

    def _sender_allowed(self, sender_handle: str) -> bool:
        allowed = settings.linq_allowed_sender_set
        if not allowed:
            return True
        return sender_handle in allowed


def headers_from_request_headers(raw_headers: dict[str, str]) -> WebhookHeaders:
    normalized = {key.lower(): value for key, value in raw_headers.items()}
    return WebhookHeaders(
        webhook_id=normalized.get("webhook-id"),
        webhook_timestamp=normalized.get("webhook-timestamp"),
        webhook_signature=normalized.get("webhook-signature"),
        x_webhook_timestamp=normalized.get("x-webhook-timestamp"),
        x_webhook_signature=normalized.get("x-webhook-signature"),
    )


def _suffix_from_url(url: str, *, default: str) -> str:
    path = url.split("?", 1)[0]
    suffix = Path(path).suffix
    return suffix if suffix else default


def _suffix_from_filename(filename: Any) -> str:
    if not filename:
        return ".jpg"
    suffix = Path(str(filename)).suffix
    return suffix if suffix else ".jpg"


__all__ = [
    "LinqWebhookHandler",
    "WebhookHeaders",
    "WebhookVerificationError",
    "headers_from_request_headers",
]
