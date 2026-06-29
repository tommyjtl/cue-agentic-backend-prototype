from unittest.mock import patch

import pytest

from cue_mark.telegram.intent_router import IntentClassification
from cue_mark.telegram.parser import InboundMessage
from cue_mark.telegram.routing import (
    format_route_error,
    is_url_bookmark_request,
    looks_like_search_or_question,
    resolve_route,
    text_without_urls,
)


def _inbound(
    *,
    text: str = "",
    urls: list[str] | None = None,
    photo_file_ids: list[str] | None = None,
) -> InboundMessage:
    return InboundMessage(
        event_id="1",
        chat_id="123",
        sender_id="456",
        text=text,
        urls=urls or [],
        photo_file_ids=photo_file_ids or [],
    )


def test_text_without_urls_strips_links():
    text = "have I saved anything? https://www.turing.com/"
    assert text_without_urls(text, ["https://www.turing.com/"]) == "have I saved anything?"


def test_looks_like_search_or_question():
    assert looks_like_search_or_question("have I saved anything about this company?")
    assert not looks_like_search_or_question("great article")


def test_is_url_bookmark_request():
    assert is_url_bookmark_request(_inbound(text="https://example.com"))
    assert is_url_bookmark_request(_inbound(text="check this https://example.com"))
    assert not is_url_bookmark_request(
        _inbound(
            text="have I saved anything about this company? https://www.turing.com/",
            urls=["https://www.turing.com/"],
        )
    )


def test_resolve_route_keyword_search():
    decision = resolve_route(
        _inbound(text="search what about frp?"),
        router_enabled=True,
    )
    assert decision.source == "keyword"
    assert decision.command.kind == "search"
    assert decision.command.search_query == "what about frp?"
    assert decision.clarification is None


def test_resolve_route_url_skips_classifier():
    decision = resolve_route(
        _inbound(text="https://example.com/article"),
        router_enabled=True,
    )
    assert decision.source == "url"
    assert decision.command.kind == "mark"
    assert decision.classification is None


def test_resolve_route_url_with_short_caption_skips_classifier():
    decision = resolve_route(
        _inbound(text="save this https://example.com/article"),
        router_enabled=True,
    )
    assert decision.source == "url"
    assert decision.command.kind == "mark"


@patch("cue_mark.telegram.routing.classify_intent")
def test_resolve_route_url_with_question_uses_classifier(mock_classify):
    mock_classify.return_value = IntentClassification(
        intent="search",
        confidence="high",
        reason="User asked whether they saved notes about a company.",
        search_query="turing company",
    )
    decision = resolve_route(
        _inbound(
            text="have I saved anything about this company? https://www.turing.com/",
            urls=["https://www.turing.com/"],
        ),
        router_enabled=True,
    )
    mock_classify.assert_called_once()
    assert decision.source == "classifier"
    assert decision.command.kind == "search"
    assert decision.command.search_query == "turing company"


def test_resolve_route_image_skips_classifier():
    decision = resolve_route(
        _inbound(text="caption", photo_file_ids=["file-1"]),
        router_enabled=True,
    )
    assert decision.source == "image"
    assert decision.command.kind == "mark"


def test_resolve_route_disabled_defaults_to_mark():
    decision = resolve_route(
        _inbound(text="Is there anything about AI agents?"),
        router_enabled=False,
    )
    assert decision.source == "default"
    assert decision.command.kind == "mark"
    assert decision.classification is None


@patch("cue_mark.telegram.routing.classify_intent")
def test_resolve_route_classifier_high_search(mock_classify):
    mock_classify.return_value = IntentClassification(
        intent="search",
        confidence="high",
        reason="User asked about saved bookmarks.",
        search_query="AI agents",
    )
    decision = resolve_route(
        _inbound(text="Is there anything I bookmarked about AI agents?"),
        router_enabled=True,
    )
    assert decision.source == "classifier"
    assert decision.command.kind == "search"
    assert decision.command.search_query == "AI agents"
    assert decision.clarification is None


@patch("cue_mark.telegram.routing.classify_intent")
def test_resolve_route_classifier_medium_returns_clarification(mock_classify):
    mock_classify.return_value = IntentClassification(
        intent="search",
        confidence="medium",
        reason="The message sounds like a question about saved notes.",
    )
    decision = resolve_route(
        _inbound(text="Anything on MLX?"),
        router_enabled=True,
    )
    assert decision.source == "classifier"
    assert decision.clarification is not None
    assert "Best guess: search (medium confidence)" in decision.clarification
    assert "Reason:" in decision.clarification


@patch("cue_mark.telegram.routing.classify_intent")
def test_resolve_route_classifier_high_reindex(mock_classify):
    mock_classify.return_value = IntentClassification(
        intent="reindex",
        confidence="high",
        reason="User asked to refresh the search index.",
    )
    decision = resolve_route(
        _inbound(text="Refresh my search index"),
        router_enabled=True,
    )
    assert decision.command.kind == "reindex"


@patch("cue_mark.telegram.routing.classify_intent")
def test_resolve_route_classifier_high_unknown_defaults_to_mark(mock_classify):
    mock_classify.return_value = IntentClassification(
        intent="unknown",
        confidence="high",
        reason="Message does not match search or reindex.",
    )
    decision = resolve_route(
        _inbound(text="Remember that Embark uses dynamic documents"),
        router_enabled=True,
    )
    assert decision.source == "default"
    assert decision.command.kind == "mark"
    assert decision.clarification is None
    assert decision.classification is None


def test_format_route_error_includes_classifier_context():
    from cue_mark.telegram.routing import RouteDecision
    from cue_mark.telegram.commands import ParsedTextCommand

    decision = RouteDecision(
        command=ParsedTextCommand(kind="search", search_query="AI agents"),
        source="classifier",
        classification=IntentClassification(
            intent="search",
            confidence="high",
            reason="User asked about saved bookmarks.",
            search_query="AI agents",
        ),
    )
    message = format_route_error("Could not process message: boom", decision)
    assert message.startswith("Routed as: search (high confidence)")
    assert "Reason: User asked about saved bookmarks." in message
    assert "Could not process message: boom" in message


def test_apply_classifier_context_prefixes_success_reply():
    from cue_mark.telegram.routing import RouteDecision, apply_classifier_context
    from cue_mark.telegram.commands import ParsedTextCommand

    decision = RouteDecision(
        command=ParsedTextCommand(kind="reindex"),
        source="classifier",
        classification=IntentClassification(
            intent="reindex",
            confidence="high",
            reason="User asked to refresh the search index.",
        ),
    )
    message = apply_classifier_context("Indexed 42 chunks from 3 files.", decision)
    assert message.startswith("Routed as: reindex (high confidence)")
    assert message.endswith("Indexed 42 chunks from 3 files.")


def test_format_route_error_skips_non_classifier_source():
    from cue_mark.telegram.routing import RouteDecision
    from cue_mark.telegram.commands import ParsedTextCommand

    decision = RouteDecision(
        command=ParsedTextCommand(kind="mark"),
        source="url",
    )
    assert format_route_error("Could not process message: boom", decision) == (
        "Could not process message: boom"
    )
