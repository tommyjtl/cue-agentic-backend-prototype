from unittest.mock import MagicMock

from cue_search.models import LLMConfig, SearchRequest, SearchResponse
from cue_search.search_service import SearchService


def test_search_summary_only_skips_sources(monkeypatch, tmp_path):
    corpus = tmp_path / "vault"
    corpus.mkdir()
    service = SearchService(store=MagicMock(), indexer=MagicMock())
    monkeypatch.setattr(service.store, "stats", lambda: {"chunk_count": 1})
    monkeypatch.setattr(service.store, "search", lambda query, limit: [{"file_path": str(corpus / "a.md"), "title": "A"}])
    monkeypatch.setattr(
        service,
        "_chat",
        lambda llm, messages, tools: {
            "content": f"Answer text\n```json\n{{\"cited_paths\": [\"{corpus / 'a.md'}\"]}}\n```"
        },
    )

    response = service.search(
        SearchRequest(
            query="test",
            corpus_root=str(corpus),
            llm=LLMConfig(
                provider="ollama",
                base_url="http://localhost:11434",
                model="test",
            ),
            summary_only=True,
        )
    )
    assert response.answer == "Answer text"
    assert response.sources == []
    assert response.debug is None
