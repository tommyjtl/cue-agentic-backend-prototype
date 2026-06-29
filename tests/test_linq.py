import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock

import pytest

from cue_mark.linq.parser import parse_message_received_event
from cue_mark.linq.verify import WebhookHeaders, verify_webhook_signature


MESSAGE_RECEIVED_V3 = {
    "api_version": "v3",
    "webhook_version": "2026-02-03",
    "event_type": "message.received",
    "event_id": "2915e81c-5068-4796-ace2-21d2c94ad298",
    "data": {
        "chat": {"id": "chat-123"},
        "direction": "inbound",
        "sender_handle": {"handle": "+12025559876", "is_me": False},
        "parts": [
            {"type": "text", "value": "Saving this MLX post"},
            {"type": "link", "value": "https://example.com/mlx"},
        ],
    },
}


def test_parse_message_received_event():
    inbound = parse_message_received_event(MESSAGE_RECEIVED_V3)
    assert inbound is not None
    assert inbound.chat_id == "chat-123"
    assert inbound.sender_handle == "+12025559876"
    assert inbound.text == "Saving this MLX post"
    assert inbound.urls == ["https://example.com/mlx"]


def test_parse_media_part_prefers_attachment_id_over_direct_url():
    payload = {
        **MESSAGE_RECEIVED_V3,
        "data": {
            **MESSAGE_RECEIVED_V3["data"],
            "parts": [
                {
                    "type": "media",
                    "url": "https://cdn.example.com/image.png",
                    "attachment_id": "att-123",
                }
            ],
        },
    }

    inbound = parse_message_received_event(payload)
    assert inbound is not None
    assert inbound.media_urls == []
    assert inbound.attachment_ids == ["att-123"]


def test_parse_ignores_outbound():
    payload = {
        **MESSAGE_RECEIVED_V3,
        "data": {
            **MESSAGE_RECEIVED_V3["data"],
            "direction": "outbound",
            "sender_handle": {"handle": "+12025551234", "is_me": True},
        },
    }
    assert parse_message_received_event(payload) is None


def test_verify_legacy_signature():
    secret = "test-secret"
    body = json.dumps({"hello": "world"}).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.".encode("utf-8") + body,
        hashlib.sha256,
    ).hexdigest()

    verify_webhook_signature(
        body=body,
        secret=secret,
        headers=WebhookHeaders(
            webhook_id=None,
            webhook_timestamp=timestamp,
            webhook_signature=signature,
            x_webhook_timestamp=timestamp,
            x_webhook_signature=signature,
        ),
    )


def test_handler_accepts_and_processes(monkeypatch, tmp_path):
    from cue.config import settings
    from cue_mark.linq.handler import LinqWebhookHandler
    from cue_mark.models import MarkResponse

    monkeypatch.setattr(settings, "mark_vault_root", str(tmp_path / "vault"))
    monkeypatch.setattr(settings, "linq_allowed_senders", "+12025559876")

    mark_service = MagicMock()
    mark_service.capture.return_value = MarkResponse(
        title="MLX Agents",
        file_path=str(tmp_path / "vault/2026-06-11/mlx-agents.md"),
        mode="page",
    )

    linq_client = MagicMock()
    handler = LinqWebhookHandler(
        mark_service=mark_service,
        linq_client=linq_client,
        event_store=__import__("cue_mark.linq.store", fromlist=["LinqEventStore"]).LinqEventStore(
            tmp_path / "jobs.sqlite3"
        ),
    )

    status, inbound = handler.accept_payload_dict(MESSAGE_RECEIVED_V3)
    assert status["status"] == "accepted"
    assert inbound is not None

    handler.process_inbound(inbound)
    mark_service.capture.assert_called_once()
    linq_client.start_typing.assert_called_once_with("chat-123")
    linq_client.send_text_message.assert_called_once()


def test_handler_routes_search_command(monkeypatch, tmp_path):
    from cue.config import settings
    from cue_mark.linq.handler import LinqWebhookHandler
    from cue_search.models import SearchResponse

    monkeypatch.setattr(settings, "mark_vault_root", str(tmp_path / "vault"))
    monkeypatch.setattr(settings, "linq_allowed_senders", "+12025559876")

    mark_service = MagicMock()
    search_service = MagicMock()
    search_service.search.return_value = SearchResponse(answer="You saved notes about frp.", sources=[])

    linq_client = MagicMock()
    handler = LinqWebhookHandler(
        mark_service=mark_service,
        search_service=search_service,
        linq_client=linq_client,
        event_store=__import__("cue_mark.linq.store", fromlist=["LinqEventStore"]).LinqEventStore(
            tmp_path / "jobs.sqlite3"
        ),
    )

    payload = {
        **MESSAGE_RECEIVED_V3,
        "event_id": "search-event-1",
        "data": {
            **MESSAGE_RECEIVED_V3["data"],
            "parts": [{"type": "text", "value": "search what about frp?"}],
        },
    }
    status, inbound = handler.accept_payload_dict(payload)
    assert status["status"] == "accepted"
    assert inbound is not None

    handler.process_inbound(inbound)
    mark_service.capture.assert_not_called()
    search_service.search.assert_called_once()
    assert search_service.search.call_args.args[0].summary_only is True
    linq_client.send_text_message.assert_called_once_with(
        "chat-123",
        "You saved notes about frp.",
        idempotency_key="search-reply-search-event-1",
    )


def test_handler_empty_search_returns_usage(monkeypatch, tmp_path):
    from cue.config import settings
    from cue_mark.linq.commands import SEARCH_USAGE_MESSAGE
    from cue_mark.linq.handler import LinqWebhookHandler

    monkeypatch.setattr(settings, "mark_vault_root", str(tmp_path / "vault"))
    monkeypatch.setattr(settings, "linq_allowed_senders", "+12025559876")

    linq_client = MagicMock()
    handler = LinqWebhookHandler(
        linq_client=linq_client,
        event_store=__import__("cue_mark.linq.store", fromlist=["LinqEventStore"]).LinqEventStore(
            tmp_path / "jobs.sqlite3"
        ),
    )

    payload = {
        **MESSAGE_RECEIVED_V3,
        "event_id": "search-event-2",
        "data": {
            **MESSAGE_RECEIVED_V3["data"],
            "parts": [{"type": "text", "value": "search"}],
        },
    }
    _, inbound = handler.accept_payload_dict(payload)
    handler.process_inbound(inbound)
    linq_client.send_text_message.assert_called_once_with(
        "chat-123",
        SEARCH_USAGE_MESSAGE,
        idempotency_key="search-usage-search-event-2",
    )


def test_handler_routes_reindex_command(monkeypatch, tmp_path):
    from cue.config import settings
    from cue_mark.linq.handler import LinqWebhookHandler
    from cue_search.models import IndexResponse

    monkeypatch.setattr(settings, "mark_vault_root", str(tmp_path / "vault"))
    monkeypatch.setattr(settings, "linq_allowed_senders", "+12025559876")
    (tmp_path / "vault").mkdir()

    mark_service = MagicMock()
    search_service = MagicMock()
    search_service.sync_index.return_value = IndexResponse(
        files_scanned=3,
        chunks_indexed=42,
        corpus_root=str(tmp_path / "vault"),
    )

    linq_client = MagicMock()
    handler = LinqWebhookHandler(
        mark_service=mark_service,
        search_service=search_service,
        linq_client=linq_client,
        event_store=__import__("cue_mark.linq.store", fromlist=["LinqEventStore"]).LinqEventStore(
            tmp_path / "jobs.sqlite3"
        ),
    )

    payload = {
        **MESSAGE_RECEIVED_V3,
        "event_id": "reindex-event-1",
        "data": {
            **MESSAGE_RECEIVED_V3["data"],
            "parts": [{"type": "text", "value": "reindex"}],
        },
    }
    _, inbound = handler.accept_payload_dict(payload)
    handler.process_inbound(inbound)
    mark_service.capture.assert_not_called()
    search_service.sync_index.assert_called_once()
    linq_client.send_text_message.assert_called_once_with(
        "chat-123",
        "Indexed 42 chunks from 3 files.",
        idempotency_key="reindex-reply-reindex-event-1",
    )
