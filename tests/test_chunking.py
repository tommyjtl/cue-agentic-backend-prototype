from pathlib import Path

from cue_search.chunking import chunk_markdown_file, infer_title, parse_frontmatter


SAMPLE = """---
title: "MLX Agents"
source: "https://example.com"
---

Intro paragraph.

## Highlights

- Point one about MLX
- Point two about agents

## Why I saved this

Future reference.
"""


def test_parse_frontmatter_and_chunk(tmp_path: Path):
    note = tmp_path / "note.md"
    note.write_text(SAMPLE, encoding="utf-8")

    metadata, body = parse_frontmatter(SAMPLE)
    assert metadata["title"] == "MLX Agents"
    assert infer_title(metadata, body) == "MLX Agents"

    chunks = chunk_markdown_file(note)
    assert len(chunks) >= 3
    sections = {chunk.section for chunk in chunks}
    assert "Highlights" in sections
    assert "Why I saved this" in sections
