from __future__ import annotations

import logging
from typing import Literal

import httpx

from cue.config import settings
from cue_mark.browser_fetch import (
    BROWSER_USER_AGENT,
    browser_fetch_available,
    fetch_html_with_browser,
    host_from_url,
)

logger = logging.getLogger(__name__)

FetchMode = Literal["auto", "http", "browser"]

GATE_MARKERS = (
    "请在微信客户端打开",
    "请在微信中打开",
    "环境异常",
    "完成验证后即可继续访问",
    "verify_user",
    "captcha",
)

MIN_USABLE_TEXT_CHARS = 120


def parse_browser_hosts(value: str) -> set[str]:
    return {item.strip().lower() for item in value.split(",") if item.strip()}


def browser_hosts() -> set[str]:
    return parse_browser_hosts(settings.mark_browser_fetch_hosts)


def should_use_browser_first(url: str, mode: FetchMode) -> bool:
    if mode == "browser":
        return True
    if mode == "http":
        return False
    return host_from_url(url) in browser_hosts()


def is_gated_html(html: str) -> bool:
    lowered = html.lower()
    return any(marker.lower() in lowered for marker in GATE_MARKERS)


def is_usable_extracted_text(text: str) -> bool:
    return len(text.strip()) >= MIN_USABLE_TEXT_CHARS


def fetch_html_http(url: str) -> str:
    with httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers={
            "User-Agent": BROWSER_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        },
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def fetch_page_html(url: str, *, mode: FetchMode | None = None) -> tuple[str, str]:
    normalized_url = url.strip()
    if not normalized_url:
        raise ValueError("URL cannot be empty.")

    fetch_mode = mode or settings.mark_fetch_mode
    browser_enabled = settings.mark_browser_fetch_enabled and browser_fetch_available()

    if should_use_browser_first(normalized_url, fetch_mode):
        if not browser_enabled:
            logger.warning(
                "Browser fetch requested for %s but Playwright is unavailable; falling back to HTTP.",
                normalized_url,
            )
        else:
            html = fetch_html_with_browser(
                normalized_url,
                timeout_ms=settings.mark_browser_fetch_timeout_ms,
            )
            return html, "browser"

    html = fetch_html_http(normalized_url)
    if fetch_mode == "auto" and browser_enabled and _should_retry_with_browser(html):
        logger.info("HTTP fetch looked gated or empty for %s; retrying with browser.", normalized_url)
        html = fetch_html_with_browser(
            normalized_url,
            timeout_ms=settings.mark_browser_fetch_timeout_ms,
        )
        return html, "browser"

    return html, "http"


def _should_retry_with_browser(html: str) -> bool:
    if is_gated_html(html):
        return True
    return not is_usable_extracted_text(_quick_text_probe(html))


def _quick_text_probe(html: str) -> str:
    import re

    without_scripts = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    without_tags = re.sub(r"(?is)<[^>]+>", " ", without_scripts)
    return re.sub(r"\s+", " ", without_tags).strip()
