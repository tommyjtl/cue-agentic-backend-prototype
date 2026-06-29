from __future__ import annotations

import json
import re
from dataclasses import dataclass

JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", re.IGNORECASE)

JSON_RETRY_USER_MESSAGE = (
    "Your previous reply was not valid JSON. Respond with ONLY one JSON object and nothing else:\n"
    '{"title":"Short plain-text title","body":"Markdown note body"}\n'
    "Keep ## Highlights concise (3-5 bullets max). Escape newlines in the JSON string values."
)


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
        raise MarkParseError(
            "Model response did not contain valid JSON. "
            f"Preview: {_preview_text(normalized)}"
        )

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
    candidates: list[str] = []
    fence_match = JSON_FENCE_RE.search(text)
    if fence_match:
        candidates.append(fence_match.group(1).strip())

    balanced = _extract_balanced_json_object(text)
    if balanced:
        candidates.append(balanced)

    if text.startswith("{"):
        candidates.append(text.strip())

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload

    return None


def _extract_balanced_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return None


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


def _preview_text(text: str, limit: int = 160) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."
