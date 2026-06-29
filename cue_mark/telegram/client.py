from __future__ import annotations

import logging
from typing import Any

import httpx

from cue.config import settings

logger = logging.getLogger(__name__)


class TelegramClient:
    def __init__(
        self,
        *,
        bot_token: str | None = None,
        base_url: str | None = None,
    ) -> None:
        token = (bot_token if bot_token is not None else settings.telegram_bot_token).strip()
        if not token:
            raise ValueError("CUE_TELEGRAM_BOT_TOKEN is not configured.")
        self.bot_token = token
        self.base_url = (base_url if base_url is not None else settings.telegram_api_base_url).rstrip("/")

    def get_me(self) -> dict[str, Any]:
        return self._call("getMe")

    def get_updates(
        self,
        *,
        offset: int | None = None,
        timeout: int | None = None,
        allowed_updates: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if offset is not None:
            params["offset"] = offset
        if timeout is not None:
            params["timeout"] = timeout
        if allowed_updates is not None:
            params["allowed_updates"] = allowed_updates

        result = self._call("getUpdates", params=params)
        if not isinstance(result, list):
            raise RuntimeError("Unexpected getUpdates response.")
        return result

    def send_message(
        self,
        chat_id: str,
        text: str,
        *,
        parse_mode: str | None = None,
        fallback_text: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode:
            params["parse_mode"] = parse_mode
        try:
            result = self._call("sendMessage", params=params)
        except RuntimeError as exc:
            if parse_mode and _is_parse_mode_error(exc):
                logger.warning(
                    "Telegram rejected %s message; retrying as plain text: %s",
                    parse_mode,
                    exc,
                )
                result = self._call(
                    "sendMessage",
                    params={
                        "chat_id": chat_id,
                        "text": fallback_text if fallback_text is not None else text,
                    },
                )
            else:
                raise
        if not isinstance(result, dict):
            raise RuntimeError("Unexpected sendMessage response.")
        return result

    def send_chat_action(self, chat_id: str, *, action: str = "typing") -> None:
        self._call("sendChatAction", params={"chat_id": chat_id, "action": action})

    def get_file(self, file_id: str) -> dict[str, Any]:
        result = self._call("getFile", params={"file_id": file_id})
        if not isinstance(result, dict):
            raise RuntimeError("Unexpected getFile response.")
        return result

    def download_file(self, file_path: str) -> bytes:
        url = f"{self.base_url}/file/bot{self.bot_token}/{file_path.lstrip('/')}"
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.content

    def _call(self, method: str, *, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}/bot{self.bot_token}/{method}"
        long_poll = method == "getUpdates"
        timeout = self._request_timeout(long_poll=long_poll)
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=params or {})
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, dict):
            raise RuntimeError(f"Unexpected Telegram response for {method}.")
        if not payload.get("ok"):
            description = str(payload.get("description") or "Unknown Telegram API error.")
            raise RuntimeError(description)
        return payload.get("result")

    @staticmethod
    def _request_timeout(*, long_poll: bool) -> httpx.Timeout:
        read_timeout = (
            max(35.0, float(settings.telegram_poll_timeout_seconds + 5))
            if long_poll
            else 30.0
        )
        return httpx.Timeout(connect=15.0, read=read_timeout, write=15.0, pool=15.0)


def _is_parse_mode_error(exc: RuntimeError) -> bool:
    message = str(exc).lower()
    return "can't parse entities" in message or "parse mode" in message
