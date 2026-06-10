import pytest

from cue_search.sandbox import CorpusSandboxError, resolve_corpus_path


def test_resolve_corpus_path_allows_inside_root(tmp_path):
    root = tmp_path / "bookmarks"
    note = root / "2026-06-08" / "note.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Note", encoding="utf-8")

    resolved = resolve_corpus_path(str(root), str(note))
    assert resolved == note.resolve()


def test_resolve_corpus_path_rejects_escape(tmp_path):
    root = tmp_path / "bookmarks"
    outside = tmp_path / "outside.md"
    outside.write_text("# Outside", encoding="utf-8")
    root.mkdir()

    with pytest.raises(CorpusSandboxError):
        resolve_corpus_path(str(root), str(outside))
