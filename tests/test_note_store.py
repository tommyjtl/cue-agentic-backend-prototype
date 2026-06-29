import shutil
import tempfile
from pathlib import Path

from cue_search.chunking import chunk_markdown_file
from cue_search.store import NoteStore


def _index_corpus(store: NoteStore, corpus: Path) -> None:
    chunks = []
    for path in sorted(corpus.glob("*.md")):
        chunks.extend(chunk_markdown_file(path))
    store.replace_corpus_chunks(chunks, corpus)


def test_search_refreshes_table_after_external_rebuild():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        corpus = temp_dir / "vault"
        corpus.mkdir()
        lance_dir = temp_dir / "lance"
        (corpus / "note-a.md").write_text(
            "---\ntitle: Alpha\n---\n\nAlpha content about zebras.\n",
            encoding="utf-8",
        )

        search_store = NoteStore(lancedb_dir=lance_dir)
        _index_corpus(search_store, corpus)
        assert search_store.search("zebras", limit=5)

        (corpus / "note-b.md").write_text(
            "---\ntitle: Beta UniqueXYZ123\n---\n\nBeta talks about UniqueXYZ123 keyword.\n",
            encoding="utf-8",
        )
        mark_store = NoteStore(lancedb_dir=lance_dir)
        _index_corpus(mark_store, corpus)

        hits = search_store.search("UniqueXYZ123", limit=5)
        titles = [hit.get("title") for hit in hits]
        assert "Beta UniqueXYZ123" in titles
    finally:
        shutil.rmtree(temp_dir)


def test_telegram_handler_shares_search_service_with_mark_service():
    from cue_mark.telegram.handler import TelegramUpdateHandler

    handler = TelegramUpdateHandler()
    assert handler.mark_service.search_service is handler.search_service
