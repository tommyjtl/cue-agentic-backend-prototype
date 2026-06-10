from __future__ import annotations

import json
from pathlib import Path

from cue_search.sandbox import resolve_corpus_path
from cue_search.store import NoteStore

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_notes",
            "description": "Semantic search across indexed bookmark notes. Returns ranked snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural-language search query.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return.",
                        "minimum": 1,
                        "maximum": 10,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_note",
            "description": "Read a markdown note file from the corpus by absolute path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to a markdown note under the corpus root.",
                    }
                },
                "required": ["file_path"],
            },
        },
    },
]


class AgentTools:
    def __init__(self, store: NoteStore, corpus_root: str) -> None:
        self.store = store
        self.corpus_root = corpus_root

    def execute(self, name: str, arguments: dict) -> str:
        if name == "search_notes":
            return self._search_notes(arguments)
        if name == "read_note":
            return self._read_note(arguments)
        return json.dumps({"error": f"Unknown tool: {name}"})

    def _search_notes(self, arguments: dict) -> str:
        query = str(arguments.get("query", "")).strip()
        limit = int(arguments.get("limit", 5))
        if not query:
            return json.dumps({"error": "query is required"})

        hits = self.store.search(query, limit=limit)
        payload = [
            {
                "file_path": hit.get("file_path"),
                "title": hit.get("title"),
                "section": hit.get("section"),
                "text": str(hit.get("text", ""))[:1200],
            }
            for hit in hits
        ]
        return json.dumps(payload, ensure_ascii=False)

    def _read_note(self, arguments: dict) -> str:
        file_path = str(arguments.get("file_path", "")).strip()
        if not file_path:
            return json.dumps({"error": "file_path is required"})

        try:
            resolved = resolve_corpus_path(self.corpus_root, file_path)
        except Exception as exc:
            return json.dumps({"error": str(exc)})

        if not resolved.exists():
            return json.dumps({"error": f"File not found: {resolved}"})

        text = Path(resolved).read_text(encoding="utf-8")
        return json.dumps(
            {
                "file_path": str(resolved),
                "content": text[:12000],
            },
            ensure_ascii=False,
        )
