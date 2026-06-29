from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from cue_mark.enrich import extract_urls
from cue_mark.telegram.commands import ParsedTextCommand, parse_text_command
from cue_mark.telegram.intent_router import (
    Confidence,
    IntentClassification,
    IntentKind,
    classify_intent,
)
from cue_mark.telegram.parser import InboundMessage

RouteSource = Literal["keyword", "url", "image", "classifier", "default"]

URL_CAPTION_MAX_CHARS = 40

QUESTION_PHRASES = (
    "have i ",
    "did i ",
    "do i ",
    "have we ",
    "did we ",
    "is there ",
    "anything about",
    "anything on",
    "anything i ",
    "what did i save",
    "what do i have",
    "what have i saved",
    "could you check",
    "can you check",
    "could you let me check",
    "search for",
    "look for",
    "show me ",
)


@dataclass(frozen=True)
class RouteDecision:
    command: ParsedTextCommand
    source: RouteSource
    classification: IntentClassification | None = None
    clarification: str | None = None


def resolve_route(
    inbound: InboundMessage,
    *,
    router_enabled: bool,
) -> RouteDecision:
    if inbound.photo_file_ids:
        return RouteDecision(
            command=ParsedTextCommand(kind="mark"),
            source="image",
        )

    keyword_command = parse_text_command(inbound.text)
    if keyword_command.kind in {"search", "reindex"}:
        return RouteDecision(command=keyword_command, source="keyword")

    if is_url_bookmark_request(inbound):
        return RouteDecision(
            command=ParsedTextCommand(kind="mark"),
            source="url",
        )

    if not router_enabled:
        return RouteDecision(
            command=ParsedTextCommand(kind="mark"),
            source="default",
        )

    classification = classify_intent(inbound.text)

    if classification.confidence == "high" and classification.intent == "search":
        return RouteDecision(
            command=ParsedTextCommand(
                kind="search",
                search_query=classification.search_query,
            ),
            source="classifier",
            classification=classification,
        )

    if classification.confidence == "high" and classification.intent == "reindex":
        return RouteDecision(
            command=ParsedTextCommand(kind="reindex"),
            source="classifier",
            classification=classification,
        )

    if classification.confidence != "high":
        return RouteDecision(
            command=ParsedTextCommand(kind="mark"),
            source="classifier",
            classification=classification,
            clarification=format_clarification(classification),
        )

    return RouteDecision(
        command=ParsedTextCommand(kind="mark"),
        source="default",
    )


def message_urls(inbound: InboundMessage) -> list[str]:
    urls = list(inbound.urls)
    for url in extract_urls(inbound.text, []):
        if url not in urls:
            urls.append(url)
    return urls


def text_without_urls(text: str, urls: list[str]) -> str:
    cleaned = text
    for url in urls:
        cleaned = cleaned.replace(url, " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def looks_like_search_or_question(text: str) -> bool:
    if "?" in text:
        return True
    lowered = text.lower()
    return any(phrase in lowered for phrase in QUESTION_PHRASES)


def is_url_bookmark_request(inbound: InboundMessage) -> bool:
    urls = message_urls(inbound)
    if not urls:
        return False

    remaining = text_without_urls(inbound.text, urls)
    if not remaining:
        return True
    if looks_like_search_or_question(remaining):
        return False
    return len(remaining) <= URL_CAPTION_MAX_CHARS


def format_classifier_prefix(
    classification: IntentClassification,
    *,
    html: bool = False,
) -> str:
    if html:
        import html as html_module

        intent = html_module.escape(classification.intent)
        confidence = html_module.escape(classification.confidence)
        reason = html_module.escape(classification.reason)
        return (
            f"<i>Routed as: {intent} ({confidence} confidence)</i>\n"
            f"Reason: {reason}\n\n"
        )

    return (
        f"Routed as: {classification.intent} ({classification.confidence} confidence)\n"
        f"Reason: {classification.reason}\n\n"
    )


def apply_classifier_context(
    text: str,
    decision: RouteDecision,
    *,
    html: bool = False,
) -> str:
    if decision.source != "classifier" or decision.classification is None:
        return text
    return format_classifier_prefix(decision.classification, html=html) + text


def format_clarification(classification: IntentClassification) -> str:
    return "\n".join(
        [
            "I'm not sure what you want to do.",
            "",
            f"Best guess: {classification.intent} ({classification.confidence} confidence)",
            f"Reason: {classification.reason}",
            "",
            "Try:",
            "• search your question here",
            "• send a URL to save a bookmark",
            "• reindex — rebuild the search index",
        ]
    )


def format_route_error(message: str, decision: RouteDecision) -> str:
    if decision.source != "classifier" or decision.classification is None:
        return message

    prefix = format_classifier_prefix(decision.classification)
    return f"{prefix}{message}"


__all__ = [
    "Confidence",
    "IntentKind",
    "RouteDecision",
    "RouteSource",
    "format_classifier_prefix",
    "apply_classifier_context",
    "format_clarification",
    "format_route_error",
    "is_url_bookmark_request",
    "looks_like_search_or_question",
    "message_urls",
    "resolve_route",
    "text_without_urls",
]
