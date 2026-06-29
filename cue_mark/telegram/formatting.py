from __future__ import annotations

import html
import re

TELEGRAM_MESSAGE_LIMIT = 4096

HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$")
CODE_RE = re.compile(r"`([^`\n]+)`")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+?)\*(?!\*)")
_PLACEHOLDER = "\x00{}\x00"


def markdown_to_telegram_html(text: str) -> str:
    lines = []
    for line in text.splitlines():
        heading = HEADING_RE.match(line)
        if heading:
            lines.append(f"<b>{_inline_html(heading.group(1))}</b>")
        else:
            lines.append(_inline_html(line))
    return "\n".join(lines)


def truncate_for_telegram(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> str:
    if len(text) <= limit:
        return text
    suffix = "…"
    return text[: max(0, limit - len(suffix))] + suffix


def format_search_reply(text: str) -> str:
    return truncate_for_telegram(markdown_to_telegram_html(text.strip()))


def _inline_html(text: str) -> str:
    tokens: list[str] = []

    def substitute(pattern: re.Pattern[str], build) -> None:
        nonlocal text

        def repl(match: re.Match[str]) -> str:
            tokens.append(build(match))
            return _PLACEHOLDER.format(len(tokens) - 1)

        text = pattern.sub(repl, text)

    substitute(CODE_RE, lambda match: f"<code>{html.escape(match.group(1))}</code>")
    substitute(
        LINK_RE,
        lambda match: (
            f'<a href="{html.escape(match.group(2), quote=True)}">'
            f"{html.escape(match.group(1))}</a>"
        ),
    )
    substitute(BOLD_RE, lambda match: f"<b>{html.escape(match.group(1))}</b>")
    substitute(ITALIC_RE, lambda match: f"<i>{html.escape(match.group(1))}</i>")

    escaped = html.escape(text)
    for index, token in enumerate(tokens):
        escaped = escaped.replace(_PLACEHOLDER.format(index), token)
    return escaped


__all__ = [
    "TELEGRAM_MESSAGE_LIMIT",
    "format_search_reply",
    "markdown_to_telegram_html",
    "truncate_for_telegram",
]
