from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

CommandKind = Literal["mark", "search", "reindex", "ping"]

PING_RE = re.compile(r"^ping\s*$", re.IGNORECASE)
REINDEX_RE = re.compile(r"^reindex(?:\s+.*)?$", re.IGNORECASE)
SEARCH_EMPTY_RE = re.compile(r"^search\s*$", re.IGNORECASE)
SEARCH_QUERY_RE = re.compile(r"^search\s+(.+)$", re.IGNORECASE | re.DOTALL)

SEARCH_USAGE_MESSAGE = (
    "Type a search query after search, for example:\nsearch what did I save about frp?"
)


@dataclass(frozen=True)
class ParsedTextCommand:
    kind: CommandKind
    search_query: str = ""


def normalize_command_text(text: str) -> str:
    trimmed = text.strip()
    if not trimmed.startswith("/"):
        return trimmed

    parts = trimmed.split(maxsplit=1)
    command = parts[0].split("@", 1)[0].lower()
    rest = parts[1].strip() if len(parts) > 1 else ""

    if command == "/search":
        return f"search {rest}".strip()
    if command == "/reindex":
        return "reindex"
    if command == "/ping":
        return "ping"
    if command in {"/mark", "/start"}:
        return rest
    return trimmed


def parse_text_command(text: str) -> ParsedTextCommand:
    trimmed = normalize_command_text(text)
    if not trimmed:
        return ParsedTextCommand(kind="mark")

    if PING_RE.match(trimmed):
        return ParsedTextCommand(kind="ping")

    if REINDEX_RE.match(trimmed):
        return ParsedTextCommand(kind="reindex")

    query_match = SEARCH_QUERY_RE.match(trimmed)
    if query_match:
        return ParsedTextCommand(kind="search", search_query=query_match.group(1).strip())

    if SEARCH_EMPTY_RE.match(trimmed):
        return ParsedTextCommand(kind="search", search_query="")

    return ParsedTextCommand(kind="mark")
