from cue_mark.enrich import extract_urls


def test_extract_urls_deduplicates():
    text = "Check https://example.com/a and https://example.com/b"
    urls = extract_urls(text, ["https://example.com/a"])
    assert urls == ["https://example.com/a", "https://example.com/b"]
