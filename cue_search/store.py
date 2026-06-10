from __future__ import annotations

from pathlib import Path

import lancedb

from cue_search.chunking import NoteChunk
from cue_search.config import settings
from cue_search.embeddings import EmbeddingClient

TABLE_NAME = "note_chunks"


class NoteStore:
    def __init__(
        self,
        lancedb_dir: Path | None = None,
        embedding_client: EmbeddingClient | None = None,
    ) -> None:
        self.lancedb_dir = lancedb_dir or settings.lancedb_dir
        self.embedding_client = embedding_client or EmbeddingClient()
        self._db = lancedb.connect(str(self.lancedb_dir))
        self._table = self._ensure_table()

    def _ensure_table(self):
        if TABLE_NAME in self._db.table_names():
            return self._db.open_table(TABLE_NAME)
        return None

    @property
    def table(self):
        if self._table is None:
            raise RuntimeError("Note index is empty. Rebuild the index first.")
        return self._table

    def stats(self) -> dict[str, int | str]:
        if self._table is None:
            return {"chunk_count": 0, "table": TABLE_NAME}
        count = self._table.count_rows()
        return {"chunk_count": count, "table": TABLE_NAME}

    def replace_corpus_chunks(self, chunks: list[NoteChunk], corpus_root: Path) -> int:
        if not chunks:
            if self._table is not None:
                self._db.drop_table(TABLE_NAME)
                self._table = None
            return 0

        vectors = self.embedding_client.embed_texts([chunk.text for chunk in chunks])
        rows = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            rows.append(
                {
                    "id": chunk.id,
                    "file_path": chunk.file_path,
                    "title": chunk.title,
                    "section": chunk.section,
                    "text": chunk.text,
                    "source_url": chunk.source_url or "",
                    "modified_at": chunk.modified_at,
                    "vector": vector,
                }
            )

        if self._table is None:
            self._table = self._db.create_table(TABLE_NAME, data=rows)
        else:
            self._table = self._db.create_table(
                TABLE_NAME,
                data=rows,
                mode="overwrite",
            )
        return len(rows)

    def search(self, query: str, limit: int = 8) -> list[dict]:
        if self._table is None or self._table.count_rows() == 0:
            return []

        query_vector = self.embedding_client.embed_query(query)
        results = (
            self.table.search(query_vector)
            .limit(limit)
            .to_list()
        )
        return results
