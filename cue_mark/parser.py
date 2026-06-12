from __future__ import annotations

import json
import re
from dataclasses import dataclass

JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


@dataclass(frozen=True)
class ParsedNote:
    title: str
    body: str


class MarkParseError(ValueError):
    pass


def parse_generated_note(response_text: str, *, fallback_title: str = "") -> ParsedNote:
    normalized = _strip_markdown_fences(response_text.strip())
    if not normalized:
        raise MarkParseError("Model returned an empty response.")

    payload = _extract_json_payload(normalized)
    if payload is None:
        raise MarkParseError("Model response did not contain valid JSON.")

    title = str(payload.get("title", "")).strip()
    body = str(payload.get("body", "")).strip()
    resolved_title = title or fallback_title.strip()
    if not resolved_title:
        raise MarkParseError("Model response did not include a title.")

    if not has_substantive_content(body):
        raise MarkParseError("Model response did not include substantive note body content.")

    return ParsedNote(title=resolved_title, body=body)


def has_substantive_content(body: str) -> bool:
    for line in body.splitlines():
        trimmed = line.strip()
        if not trimmed:
            continue
        if re.match(r"^#{1,6}\s", trimmed):
            continue
        return True
    return False


def _extract_json_payload(text: str) -> dict | None:
    json_text = text
    match = JSON_FENCE_RE.search(text)
    if match:
        json_text = match.group(1).strip()
    elif "{" in text and "}" in text:
        start = text.find("{")
        end = text.rfind("}")
        json_text = text[start : end + 1]

    if not json_text.startswith("{"):
        return None

    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError:
        return None

    return payload if isinstance(payload, dict) else None


def _strip_markdown_fences(text: str) -> str:
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    if lines and lines[0].strip().lower() in {"markdown", "md", "json"}:
        lines = lines[1:]
    return "\n".join(lines).strip()
