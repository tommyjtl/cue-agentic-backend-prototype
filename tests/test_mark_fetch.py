from cue_mark.enrich import _extract_element_text, fetch_page_context
from cue_mark.fetch import (
    is_gated_html,
    is_usable_extracted_text,
    parse_browser_hosts,
    should_use_browser_first,
)


def test_parse_browser_hosts():
    assert parse_browser_hosts("mp.weixin.qq.com, example.com") == {
        "mp.weixin.qq.com",
        "example.com",
    }


def test_should_use_browser_first_for_weixin_in_auto_mode(monkeypatch):
    monkeypatch.setenv("CUE_MARK_BROWSER_FETCH_HOSTS", "mp.weixin.qq.com")
    from cue.config import Settings

    monkeypatch.setattr("cue_mark.fetch.settings", Settings())
    assert should_use_browser_first("https://mp.weixin.qq.com/s/abc", "auto") is True
    assert should_use_browser_first("https://example.com/post", "auto") is False


def test_is_gated_html_detects_weixin_gate():
    html = "<html><body><p>请在微信客户端打开</p></body></html>"
    assert is_gated_html(html) is True


def test_is_gated_url_detects_weixin_captcha_redirect():
    from cue_mark.page_gates import is_gated_url

    assert is_gated_url(
        "https://mp.weixin.qq.com/mp/wappoc_appmsgcaptcha?target_url=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2Fabc"
    )


def test_fetch_html_with_browser_raises_on_weixin_captcha(monkeypatch):
    from cue_mark.browser_fetch import fetch_html_with_browser
    from cue_mark.page_gates import PageFetchBlockedError

    class FakePage:
        url = "https://mp.weixin.qq.com/mp/wappoc_appmsgcaptcha?target_url=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2Fabc"

        def goto(self, url, wait_until, timeout):
            return None

        def content(self):
            return "<html><body>captcha</body></html>"

    class FakeContext:
        def new_page(self):
            return FakePage()

    class FakeBrowser:
        def new_context(self, **kwargs):
            return FakeContext()

        def close(self):
            return None

    class FakeChromium:
        def launch(self, headless):
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakeSyncPlaywright:
        def __enter__(self):
            return FakePlaywright()

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: FakeSyncPlaywright())

    try:
        fetch_html_with_browser("https://mp.weixin.qq.com/s/example")
        raise AssertionError("Expected PageFetchBlockedError")
    except PageFetchBlockedError as exc:
        assert "WeChat blocked automated fetch" in str(exc)
        assert "screenshot" in str(exc)


def test_is_usable_extracted_text():
    assert is_usable_extracted_text("x" * 119) is False
    assert is_usable_extracted_text("x" * 120) is True


def test_extract_element_text_strips_tags():
    html = '<div id="js_content"><p>Hello</p><p>World</p></div>'
    assert _extract_element_text(html, id="js_content") == "Hello World"


def test_fetch_page_context_uses_browser_for_weixin(monkeypatch):
    monkeypatch.setenv("CUE_MARK_BROWSER_FETCH_HOSTS", "mp.weixin.qq.com")
    from cue.config import Settings

    monkeypatch.setattr("cue_mark.fetch.settings", Settings())

    browser_html = """
    <html><head><title>WeChat Article</title></head>
    <body><div id="js_content"><p>Full article body with enough content to be useful for bookmarking and summarization by the LLM pipeline in Cue mark capture.</p></div></body></html>
    """
    monkeypatch.setattr(
        "cue_mark.fetch.fetch_html_with_browser",
        lambda url, timeout_ms: browser_html,
    )
    monkeypatch.setattr(
        "cue_mark.fetch.browser_fetch_available",
        lambda: True,
    )

    page = fetch_page_context("https://mp.weixin.qq.com/s/example")
    assert page.fetch_method == "browser"
    assert "Full article body" in page.extracted_text


def test_fetch_page_context_retries_browser_on_gated_http(monkeypatch):
    monkeypatch.setenv("CUE_MARK_BROWSER_FETCH_HOSTS", "")
    from cue.config import Settings

    monkeypatch.setattr("cue_mark.fetch.settings", Settings())

    calls: list[str] = []

    def fake_http(url: str) -> str:
        calls.append("http")
        return "<html><body>请在微信客户端打开</body></html>"

    browser_html = """
    <html><head><title>Recovered</title></head>
    <body><article><p>Recovered article text with enough content to pass the usable threshold for mark capture and snapshot generation in the Cue backend pipeline.</p></article></body></html>
    """

    def fake_browser(url: str, timeout_ms: int) -> str:
        calls.append("browser")
        return browser_html

    monkeypatch.setattr("cue_mark.fetch.fetch_html_http", fake_http)
    monkeypatch.setattr("cue_mark.fetch.fetch_html_with_browser", fake_browser)
    monkeypatch.setattr("cue_mark.fetch.browser_fetch_available", lambda: True)

    page = fetch_page_context("https://example.com/article")
    assert calls == ["http", "browser"]
    assert page.fetch_method == "browser"
    assert "Recovered article text" in page.extracted_text
