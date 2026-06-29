from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cue_mark.enrich import extract_urls


@dataclass(frozen=True)
class InboundMessage:
    event_id: str
    chat_id: str
    sender_id: str
    text: str
    urls: list[str] = field(default_factory=list)
    photo_file_ids: list[str] = field(default_factory=list)


class TelegramParseError(ValueError):
    pass


IMAGE_MIME_PREFIXES = ("image/",)


def parse_update(update: dict[str, Any]) -> InboundMessage | None:
    message = update.get("message")
    if not isinstance(message, dict):
        return None

    update_id = update.get("update_id")
    if update_id is None:
        raise TelegramParseError("Update is missing update_id.")

    chat = message.get("chat")
    if not isinstance(chat, dict):
        raise TelegramParseError("Message is missing chat.")

    chat_id = str(chat.get("id") or "").strip()
    if not chat_id:
        raise TelegramParseError("Message is missing chat id.")

    sender = message.get("from")
    if not isinstance(sender, dict):
        raise TelegramParseError("Message is missing sender.")

    sender_id = str(sender.get("id") or "").strip()
    if not sender_id:
        raise TelegramParseError("Message is missing sender id.")

    text = _message_text(message)
    urls = _message_urls(message, text)
    photo_file_ids = _photo_file_ids(message)

    return InboundMessage(
        event_id=str(update_id),
        chat_id=chat_id,
        sender_id=sender_id,
        text=text,
        urls=urls,
        photo_file_ids=photo_file_ids,
    )


def _message_text(message: dict[str, Any]) -> str:
    text = str(message.get("text") or message.get("caption") or "").strip()
    return text


def _message_urls(message: dict[str, Any], text: str) -> list[str]:
    urls: list[str] = []
    entities = message.get("entities")
    if isinstance(entities, list):
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            if str(entity.get("type") or "") != "url":
                continue
            offset = entity.get("offset")
            length = entity.get("length")
            if isinstance(offset, int) and isinstance(length, int):
                url = text[offset : offset + length].strip()
                if url and url not in urls:
                    urls.append(url)

    for url in extract_urls(text, []):
        if url not in urls:
            urls.append(url)
    return urls


def _photo_file_ids(message: dict[str, Any]) -> list[str]:
    photos = message.get("photo")
    if isinstance(photos, list) and photos:
        largest = photos[-1]
        if isinstance(largest, dict):
            file_id = str(largest.get("file_id") or "").strip()
            if file_id:
                return [file_id]

    document = message.get("document")
    if isinstance(document, dict):
        mime_type = str(document.get("mime_type") or "").lower()
        if mime_type.startswith(IMAGE_MIME_PREFIXES):
            file_id = str(document.get("file_id") or "").strip()
            if file_id:
                return [file_id]

    return []
