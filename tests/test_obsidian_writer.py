from datetime import datetime, timezone
from pathlib import Path

from cue.obsidian.writer import (
    ExportKind,
    Reference,
    WriteInput,
    build_markdown,
    file_name_for_title,
    sanitize_title_base,
    write_note,
)
from cue_mark.parser import has_substantive_content


def test_sanitize_title_base():
    assert sanitize_title_base('Hello: World / "Test"') == "Hello- World - -Test"


def test_file_name_for_title():
    assert file_name_for_title("Short title", ExportKind.MARK_PAGE) == "Short title.md"


def test_build_markdown_frontmatter():
    created = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)
    markdown = build_markdown(
        WriteInput(
            title="MLX Agents",
            body="## Highlights\n\n- One",
            source_url="https://example.com/post",
            references=[Reference(title="Example", url="https://example.com/post")],
            created_at=created,
            export_folder=Path("/tmp"),
            export_kind=ExportKind.MARK_PAGE,
        )
    )
    assert 'title: "MLX Agents"' in markdown
    assert 'source: "https://example.com/post"' in markdown
    assert 'domain: "example.com"' in markdown
    assert "## Highlights" in markdown


def test_write_note_creates_dated_folder(tmp_path: Path):
    created = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)
    result = write_note(
        WriteInput(
            title="Bookmark",
            body="## Highlights\n\nSaved.",
            source_url="https://example.com",
            references=[],
            created_at=created,
            export_folder=tmp_path,
            export_kind=ExportKind.MARK_PAGE,
        )
    )
    assert result.file_path.exists()
    assert result.file_path.parent.name == "2026-06-11"


def test_has_substantive_content():
    assert has_substantive_content("## Highlights\n\n- item")
    assert not has_substantive_content("## Highlights\n\n")
