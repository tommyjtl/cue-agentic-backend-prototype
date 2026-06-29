import pytest

from cue_mark.telegram.commands import parse_text_command


@pytest.mark.parametrize(
    ("text", "kind", "query"),
    [
        ("search what did I save about frp?", "search", "what did I save about frp?"),
        ("SEARCH MLX agents", "search", "MLX agents"),
        ("search", "search", ""),
        ("  search   something  ", "search", "something"),
        ("/search what about frp?", "search", "what about frp?"),
        ("/search@cue_bot what about frp?", "search", "what about frp?"),
        ("ping", "ping", ""),
        ("/ping", "ping", ""),
        ("reindex", "reindex", ""),
        ("/reindex", "reindex", ""),
        ("  REINDEX  ", "reindex", ""),
        ("nice tool", "mark", ""),
        ("searching for jobs", "mark", ""),
        ("https://example.com", "mark", ""),
    ],
)
def test_parse_text_command(text, kind, query):
    parsed = parse_text_command(text)
    assert parsed.kind == kind
    assert parsed.search_query == query
