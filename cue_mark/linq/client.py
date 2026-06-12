from __future__ import annotations

from typing import Any

import httpx

from cue.config import settings


class LinqClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = (api_key if api_key is not None else settings.linq_api_key).strip()
        self.base_url = (base_url if base_url is not None else settings.linq_api_base_url).rstrip("/")
        if not self.api_key:
            raise ValueError("CUE_LINQ_API_KEY is not configured.")

    def send_text_message(
        self,
        chat_id: str,
        text: str,
        *,
        reply_to_message_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        message: dict[str, Any] = {
            "parts": [{"type": "text", "value": text}],
        }
        if reply_to_message_id:
            message["reply_to"] = {"message_id": reply_to_message_id, "part_index": 0}
        if idempotency_key:
            message["idempotency_key"] = idempotency_key

        payload = {"message": message}
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.base_url}/chats/{chat_id}/messages",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {"raw": data}

    def get_attachment(self, attachment_id: str) -> dict[str, Any]:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{self.base_url}/attachments/{attachment_id}",
                headers=self._headers(),
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise RuntimeError("Unexpected attachment response.")
            return data

    def download_url(self, url: str) -> bytes:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.content

    def start_typing(self, chat_id: str) -> None:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                f"{self.base_url}/chats/{chat_id}/typing",
                headers=self._headers(),
            )
            response.raise_for_status()

    def stop_typing(self, chat_id: str) -> None:
        with httpx.Client(timeout=15.0) as client:
            response = client.delete(
                f"{self.base_url}/chats/{chat_id}/typing",
                headers=self._headers(),
            )
            response.raise_for_status()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
