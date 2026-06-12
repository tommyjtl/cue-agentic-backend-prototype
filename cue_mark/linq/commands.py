from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

CommandKind = Literal["mark", "search", "reindex"]

REINDEX_RE = re.compile(r"^reindex\s*$", re.IGNORECASE)
SEARCH_EMPTY_RE = re.compile(r"^search\s*$", re.IGNORECASE)
SEARCH_QUERY_RE = re.compile(r"^search\s+(.+)$", re.IGNORECASE | re.DOTALL)

SEARCH_USAGE_MESSAGE = (
    "Type a search query after search, for example:\nsearch what did I save about frp?"
)


@dataclass(frozen=True)
class ParsedTextCommand:
    kind: CommandKind
    search_query: str = ""


def parse_text_command(text: str) -> ParsedTextCommand:
    trimmed = text.strip()
    if not trimmed:
        return ParsedTextCommand(kind="mark")

    if REINDEX_RE.match(trimmed):
        return ParsedTextCommand(kind="reindex")

    query_match = SEARCH_QUERY_RE.match(trimmed)
    if query_match:
        return ParsedTextCommand(kind="search", search_query=query_match.group(1).strip())

    if SEARCH_EMPTY_RE.match(trimmed):
        return ParsedTextCommand(kind="search", search_query="")

    return ParsedTextCommand(kind="mark")
