from __future__ import annotations

import re
from dataclasses import dataclass

import trafilatura

from cue_mark.browser_fetch import host_from_url
from cue_mark.fetch import fetch_page_html

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


@dataclass(frozen=True)
class PageContext:
    url: str
    title: str
    extracted_text: str
    fetch_method: str = "http"


def extract_urls(text: str, explicit_urls: list[str]) -> list[str]:
    found = explicit_urls[:]
    for match in URL_RE.findall(text):
        if match not in found:
            found.append(match.rstrip(".,);]"))
    return found


def fetch_page_context(url: str) -> PageContext:
    normalized_url = url.strip()
    html, fetch_method = fetch_page_html(normalized_url)

    extracted = trafilatura.extract(
        html,
        url=normalized_url,
        include_comments=False,
        include_tables=False,
    )
    metadata = trafilatura.extract_metadata(html, default_url=normalized_url)
    title = (metadata.title if metadata and metadata.title else "").strip()
    if not title:
        title = _title_from_html(html) or normalized_url

    extracted_text = (extracted or "").strip()
    if not extracted_text:
        extracted_text = _extract_host_specific_text(html, normalized_url)

    return PageContext(
        url=normalized_url,
        title=title,
        extracted_text=extracted_text,
        fetch_method=fetch_method,
    )


def primary_page_context_message(page: PageContext) -> dict[str, str]:
    text = f"""Primary page context:
Title: {page.title}
URL: {page.url}

Extracted page text:
{page.extracted_text or "(No readable page text was extracted.)"}
"""
    return {"role": "system", "content": text}


def _title_from_html(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


def _extract_host_specific_text(html: str, url: str) -> str:
    host = host_from_url(url)
    if host == "mp.weixin.qq.com":
        return _extract_element_text(html, id="js_content")
    return ""


def _extract_element_text(html: str, *, id: str) -> str:
    from html.parser import HTMLParser

    class _ElementTextParser(HTMLParser):
        def __init__(self, target_id: str) -> None:
            super().__init__()
            self.target_id = target_id
            self.in_target = False
            self.depth = 0
            self.parts: list[str] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            attrs_dict = {key: value for key, value in attrs if value is not None}
            if not self.in_target:
                if attrs_dict.get("id") == self.target_id:
                    self.in_target = True
                    self.depth = 1
                return
            self.depth += 1

        def handle_endtag(self, tag: str) -> None:
            if not self.in_target:
                return
            self.depth -= 1
            if self.depth == 0:
                self.in_target = False

        def handle_data(self, data: str) -> None:
            if not self.in_target:
                return
            text = data.strip()
            if text:
                self.parts.append(text)

    parser = _ElementTextParser(id)
    parser.feed(html)
    return " ".join(parser.parts)


__all__ = ["PageContext", "extract_urls", "fetch_page_context", "host_from_url", "primary_page_context_message"]
