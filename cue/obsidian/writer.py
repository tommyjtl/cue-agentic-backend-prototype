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
MAX_SNAPSHOT_CHARACTERS = 20_000
MIN_SNAPSHOT_TEXT_LENGTH = 400


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


def should_include_snapshot(url: str, extracted_text: str, user_hint: str) -> bool:
    text = extracted_text.strip()
    if not text:
        return False

    hint = user_hint.strip().lower()
    snapshot_triggers = (
        "full article",
        "archive",
        "snapshot",
        "preserve",
        "verbatim",
        "original text",
        "save the post",
        "save this post",
    )
    if any(trigger in hint for trigger in snapshot_triggers):
        return True

    if "youtube.com" in url.lower() or "youtu.be" in url.lower():
        return False

    if len(text) < MIN_SNAPSHOT_TEXT_LENGTH:
        return False

    parsed = urlparse(url)
    path = parsed.path.strip("/").lower()
    if not path or path in {"home", "index.html", "index.htm"}:
        return False

    return True


def build_snapshot_section(url: str, title: str, extracted_text: str, captured_at: datetime) -> str:
    local_time = captured_at.astimezone()
    captured_label = local_time.strftime("%b %d, %Y at %I:%M %p").replace(" 0", " ")
    metadata = f"_Captured from web on {captured_label}. [Original page]({url})._"
    body = truncate_snapshot(extracted_text)
    return f"## Snapshot\n\n{metadata}\n\n{body}"


def truncate_snapshot(extracted_text: str) -> str:
    trimmed = extracted_text.strip()
    if len(trimmed) <= MAX_SNAPSHOT_CHARACTERS:
        return trimmed

    prefix = trimmed[:MAX_SNAPSHOT_CHARACTERS].strip()
    return f"{prefix}\n\n… [Snapshot truncated at capture — {len(trimmed)} characters total.]"


def append_snapshot(body: str, snapshot_section: str) -> str:
    without_snapshot = strip_snapshot_section(body).strip()
    if not without_snapshot:
        return snapshot_section
    return f"{without_snapshot}\n\n{snapshot_section}"


def strip_snapshot_section(body: str) -> str:
    trimmed = body.strip()
    if not trimmed:
        return ""

    lead_lines: list[str] = []
    sections: list[tuple[str, str]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    def flush_section() -> None:
        nonlocal current_heading, current_lines
        if current_heading is None:
            return
        sections.append((current_heading, "\n".join(current_lines)))
        current_heading = None
        current_lines = []

    for line in trimmed.splitlines():
        if line.startswith("## "):
            flush_section()
            current_heading = line[3:].strip()
            continue

        if current_heading is None:
            lead_lines.append(line)
        else:
            current_lines.append(line)

    flush_section()

    kept_sections = [(heading, content) for heading, content in sections if heading.lower() != "snapshot"]
    parts: list[str] = []
    lead = "\n".join(lead_lines).strip()
    if lead:
        parts.append(lead)

    for heading, content in kept_sections:
        section_body = content.strip()
        if section_body:
            parts.append(f"## {heading}\n\n{section_body}")
        else:
            parts.append(f"## {heading}")

    return "\n\n".join(parts)
