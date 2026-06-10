from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from cue_search.chunking import chunk_markdown_file
from cue_search.config import settings
from cue_search.sandbox import validate_corpus_root
from cue_search.store import NoteStore


@dataclass
class IndexResult:
    files_scanned: int
    chunks_indexed: int
    corpus_root: str


class NoteIndexer:
    def __init__(self, store: NoteStore | None = None) -> None:
        self.store = store or NoteStore()

    def discover_markdown_files(self, corpus_root: Path) -> list[Path]:
        return sorted(corpus_root.rglob("*.md"))

    def rebuild(self, corpus_root: str) -> IndexResult:
        root = validate_corpus_root(corpus_root)
        files = self.discover_markdown_files(root)

        chunks = []
        for file_path in files:
            chunks.extend(chunk_markdown_file(file_path))

        indexed = self.store.replace_corpus_chunks(chunks, root)
        self._write_state(root, files)

        return IndexResult(
            files_scanned=len(files),
            chunks_indexed=indexed,
            corpus_root=str(root),
        )

    def sync(self, corpus_root: str) -> IndexResult:
        return self.rebuild(corpus_root)

    def _write_state(self, corpus_root: Path, files: list[Path]) -> None:
        state = {
            "corpus_root": str(corpus_root),
            "files": {
                str(path.resolve()): path.stat().st_mtime for path in files
            },
        }
        settings.indexer_state_file.write_text(
            json.dumps(state, indent=2),
            encoding="utf-8",
        )
