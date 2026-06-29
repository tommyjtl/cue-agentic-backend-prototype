from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cue_mark.enrich import extract_urls


@dataclass(frozen=True)
class InboundMessage:
    event_id: str
    chat_id: str
    sender_handle: str
    text: str
    urls: list[str] = field(default_factory=list)
    media_urls: list[str] = field(default_factory=list)
    attachment_ids: list[str] = field(default_factory=list)


class LinqParseError(ValueError):
    pass


def parse_message_received_event(payload: dict[str, Any]) -> InboundMessage | None:
    event_type = str(payload.get("event_type") or "")
    if event_type != "message.received":
        return None

    event_id = str(payload.get("event_id") or "").strip()
    if not event_id:
        raise LinqParseError("Webhook event is missing event_id.")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise LinqParseError("Webhook event is missing data.")

    if _is_outbound(data):
        return None

    chat_id = _chat_id(data)
    sender_handle = _sender_handle(data)
    parts = _parts(data)

    text_parts: list[str] = []
    urls: list[str] = []
    media_urls: list[str] = []
    attachment_ids: list[str] = []

    for part in parts:
        if not isinstance(part, dict):
            continue

        part_type = str(part.get("type") or "")
        if part_type == "text":
            value = str(part.get("value") or "").strip()
            if value:
                text_parts.append(value)
            continue

        if part_type == "link":
            value = str(part.get("value") or part.get("url") or "").strip()
            if value and value not in urls:
                urls.append(value)
            continue

        if part_type == "media":
            attachment_id = str(part.get("attachment_id") or part.get("id") or "").strip()
            media_url = str(part.get("url") or part.get("download_url") or "").strip()
            if attachment_id:
                if attachment_id not in attachment_ids:
                    attachment_ids.append(attachment_id)
            elif media_url:
                if media_url not in media_urls:
                    media_urls.append(media_url)
            continue

    text = "\n".join(text_parts).strip()
    urls.extend(extract_urls(text, []))
    deduped_urls: list[str] = []
    for url in urls:
        if url not in deduped_urls:
            deduped_urls.append(url)

    return InboundMessage(
        event_id=event_id,
        chat_id=chat_id,
        sender_handle=sender_handle,
        text=text,
        urls=deduped_urls,
        media_urls=media_urls,
        attachment_ids=attachment_ids,
    )


def _is_outbound(data: dict[str, Any]) -> bool:
    direction = str(data.get("direction") or "").lower()
    if direction == "outbound":
        return True

    if data.get("is_from_me") is True:
        return True

    sender_handle = data.get("sender_handle")
    if isinstance(sender_handle, dict) and sender_handle.get("is_me") is True:
        return True

    from_handle = data.get("from_handle")
    if isinstance(from_handle, dict) and from_handle.get("is_me") is True:
        return True

    return False


def _chat_id(data: dict[str, Any]) -> str:
    chat = data.get("chat")
    if isinstance(chat, dict):
        chat_id = str(chat.get("id") or "").strip()
        if chat_id:
            return chat_id

    chat_id = str(data.get("chat_id") or "").strip()
    if chat_id:
        return chat_id

    raise LinqParseError("Webhook event is missing chat id.")


def _sender_handle(data: dict[str, Any]) -> str:
    sender_handle = data.get("sender_handle")
    if isinstance(sender_handle, dict):
        handle = str(sender_handle.get("handle") or "").strip()
        if handle:
            return handle

    from_handle = data.get("from_handle")
    if isinstance(from_handle, dict):
        handle = str(from_handle.get("handle") or "").strip()
        if handle:
            return handle

    handle = str(data.get("from") or "").strip()
    if handle:
        return handle

    raise LinqParseError("Webhook event is missing sender handle.")


def _parts(data: dict[str, Any]) -> list[Any]:
    parts = data.get("parts")
    if isinstance(parts, list):
        return parts

    message = data.get("message")
    if isinstance(message, dict):
        nested_parts = message.get("parts")
        if isinstance(nested_parts, list):
            return nested_parts

    return []
