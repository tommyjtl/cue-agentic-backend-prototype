from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse


class ExportKind(str, Enum):
    MARK_PAGE = "mark_page"
    MARK_STANDALONE = "mark_standalone"


@dataclass(frozen=True)
class Reference:
    title: str
    url: str


@dataclass(frozen=True)
class WriteInput:
    title: str
    body: str
    source_url: str | None
    references: list[Reference]
    created_at: datetime
    export_folder: Path
    export_kind: ExportKind
    tags: list[str] | None = None


@dataclass(frozen=True)
class WriteResult:
    file_path: Path
    title: str


INVALID_FILENAME_CHARS = set('/\\:?*"<>|`{}')
MARK_SYSTEM_TAG = "cue"


def write_note(input_data: WriteInput) -> WriteResult:
    title = input_data.title.strip()
    if not title:
        raise ValueError("Note title cannot be empty.")

    date_folder = input_data.created_at.astimezone().strftime("%Y-%m-%d")
    date_directory = input_data.export_folder / date_folder
    date_directory.mkdir(parents=True, exist_ok=True)

    file_name = file_name_for_title(title, input_data.export_kind)
    file_path = date_directory / file_name

    collision_index = 2
    base_name = file_path.stem
    while file_path.exists():
        file_path = date_directory / f"{base_name}-{collision_index}.md"
        collision_index += 1

    markdown = build_markdown(input_data)
    file_path.write_text(markdown, encoding="utf-8")
    return WriteResult(file_path=file_path.resolve(), title=title)


def file_name_for_title(title: str, export_kind: ExportKind) -> str:
    sanitized = sanitize_title_base(title)
    if not sanitized:
        return "mark.md"

    limit = 80 if export_kind != ExportKind.MARK_STANDALONE else 80
    return f"{sanitized[:limit]}.md"


def sanitize_title_base(title: str) -> str:
    chars = []
    for char in title:
        chars.append("-" if char in INVALID_FILENAME_CHARS else char)

    sanitized = "".join(chars)
    while "--" in sanitized:
        sanitized = sanitized.replace("--", "-")
    return sanitized.strip(" .-")


def build_markdown(input_data: WriteInput) -> str:
    tag_values = input_data.tags or [MARK_SYSTEM_TAG]
    tags_line = "[" + ", ".join(tag_values) + "]"

    frontmatter_lines = [
        "---",
        f'title: "{yaml_escape(input_data.title)}"',
        f"created: {iso8601(input_data.created_at)}",
        f"tags: {tags_line}",
    ]

    if input_data.source_url:
        frontmatter_lines.append(f'source: "{yaml_escape(input_data.source_url)}"')

    if input_data.export_kind == ExportKind.MARK_PAGE and input_data.source_url:
        host = urlparse(input_data.source_url).hostname or ""
        if host:
            frontmatter_lines.append(f'domain: "{yaml_escape(host)}"')

    frontmatter_lines.append("---")

    body = input_data.body.strip()
    if not body:
        return "\n".join(frontmatter_lines) + "\n"
    return "\n".join(frontmatter_lines) + "\n\n" + body + "\n"


def yaml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def iso8601(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
