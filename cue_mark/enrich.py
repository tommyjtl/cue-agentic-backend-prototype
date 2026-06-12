from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import trafilatura

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


@dataclass(frozen=True)
class PageContext:
    url: str
    title: str
    extracted_text: str


def extract_urls(text: str, explicit_urls: list[str]) -> list[str]:
    found = explicit_urls[:]
    for match in URL_RE.findall(text):
        if match not in found:
            found.append(match.rstrip(".,);]"))
    return found


def fetch_page_context(url: str) -> PageContext:
    normalized_url = url.strip()
    if not normalized_url:
        raise ValueError("URL cannot be empty.")

    with httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": "CueMarkBot/0.1 (+https://github.com/cue)"},
    ) as client:
        response = client.get(normalized_url)
        response.raise_for_status()
        html = response.text

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

    return PageContext(
        url=normalized_url,
        title=title,
        extracted_text=(extracted or "").strip(),
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


def host_from_url(url: str) -> str:
    return urlparse(url).hostname or ""
