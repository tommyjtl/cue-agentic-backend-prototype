from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class NoteChunk:
    id: str
    file_path: str
    title: str
    section: str
    text: str
    source_url: str | None
    modified_at: float


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    body = text[match.end() :]
    return metadata, body


def infer_title(metadata: dict[str, str], body: str) -> str:
    if title := metadata.get("title"):
        return title
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped[:120]
        if stripped.startswith("# "):
            return stripped[2:].strip()[:120]
    return "Untitled"


def chunk_markdown_file(path: Path) -> list[NoteChunk]:
    raw = path.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(raw)
    title = infer_title(metadata, body)
    source_url = metadata.get("source")
    modified_at = path.stat().st_mtime

    sections: list[tuple[str, str]] = []
    matches = list(HEADING_RE.finditer(body))
    if not matches:
        trimmed = body.strip()
        if trimmed:
            sections.append(("Body", trimmed))
    else:
        preamble = body[: matches[0].start()].strip()
        if preamble:
            sections.append(("Introduction", preamble))

        for index, match in enumerate(matches):
            section_title = match.group(2).strip()
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
            section_text = body[start:end].strip()
            if section_text:
                sections.append((section_title, section_text))

    if not sections:
        return []

    chunks: list[NoteChunk] = []
    for section_name, section_text in sections:
        chunk_id = f"{path}:{section_name}"
        chunks.append(
            NoteChunk(
                id=chunk_id,
                file_path=str(path.resolve()),
                title=title,
                section=section_name,
                text=section_text,
                source_url=source_url,
                modified_at=modified_at,
            )
        )
    return chunks
