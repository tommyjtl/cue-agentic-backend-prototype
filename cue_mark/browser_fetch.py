from __future__ import annotations

import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

HOST_CONTENT_SELECTORS: dict[str, str] = {
    "mp.weixin.qq.com": "#js_content",
}


def browser_fetch_available() -> bool:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    return True


def host_from_url(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def content_selector_for_url(url: str) -> str | None:
    host = host_from_url(url)
    return HOST_CONTENT_SELECTORS.get(host)


def fetch_html_with_browser(url: str, *, timeout_ms: int = 30_000) -> str:
    if not browser_fetch_available():
        raise RuntimeError(
            "Playwright is not installed. Run: pip install -e \".[browser]\" && playwright install chromium"
        )

    from playwright.sync_api import sync_playwright

    selector = content_selector_for_url(url)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                user_agent=BROWSER_USER_AGENT,
                locale="en-US",
                viewport={"width": 1280, "height": 720},
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if selector:
                page.wait_for_selector(selector, timeout=timeout_ms)
            else:
                page.wait_for_load_state("networkidle", timeout=timeout_ms)
            return page.content()
        finally:
            browser.close()
