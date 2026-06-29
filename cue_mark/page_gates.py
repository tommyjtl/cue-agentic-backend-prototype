from __future__ import annotations

from urllib.parse import urlparse

GATE_MARKERS = (
    "请在微信客户端打开",
    "请在微信中打开",
    "环境异常",
    "完成验证后即可继续访问",
    "verify_user",
    "captcha",
)

CAPTCHA_URL_PARTS = (
    "wappoc_appmsgcaptcha",
    "appmsgcaptcha",
    "verify_user",
    "/mp/readtemplate",
)


class PageFetchBlockedError(RuntimeError):
    """The target site blocked automated fetching (captcha, app-only gate, etc.)."""


def host_from_url(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def is_gated_url(url: str) -> bool:
    lowered = url.lower()
    return any(part in lowered for part in CAPTCHA_URL_PARTS)


def is_gated_html(html: str) -> bool:
    lowered = html.lower()
    return any(marker.lower() in lowered for marker in GATE_MARKERS)


def blocked_message_for_url(url: str) -> str:
    if host_from_url(url) == "mp.weixin.qq.com":
        return (
            "WeChat blocked automated fetch (captcha or \"open in WeChat\" gate). "
            "Try sending a screenshot of the article instead."
        )
    return (
        "This page blocked automated fetch. "
        "Try sending a screenshot or paste the text you want saved."
    )
