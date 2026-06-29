from unittest.mock import MagicMock, patch
import threading
import time

from cue_mark.telegram.handler import TelegramUpdateHandler
from cue_mark.telegram.store import TelegramEventStore

TEXT_UPDATE = {
    "update_id": 10001,
    "message": {
        "message_id": 42,
        "from": {"id": 123456789, "is_bot": False, "first_name": "Tommy"},
        "chat": {"id": 123456789, "type": "private"},
        "date": 1718000000,
        "text": "Saving this MLX post https://example.com/mlx",
        "entities": [
            {"offset": 21, "length": 23, "type": "url"},
        ],
    },
}


def test_chat_action_for_inbound():
    from cue_mark.telegram.handler import chat_action_for_inbound
    from cue_mark.telegram.parser import InboundMessage

    text_only = InboundMessage(
        event_id="1",
        chat_id="123",
        sender_id="456",
        text="hello",
    )
    assert chat_action_for_inbound(text_only) == "typing"

    with_photo = InboundMessage(
        event_id="2",
        chat_id="123",
        sender_id="456",
        text="",
        photo_file_ids=["file-1"],
    )
    assert chat_action_for_inbound(with_photo) == "upload_photo"


def test_refresh_chat_action_sends_until_stopped():
    from cue_mark.telegram.handler import _refresh_chat_action

    client = MagicMock()
    stop_event = threading.Event()

    def stop_after_two_sends():
        for _ in range(2):
            if client.send_chat_action.call_count >= 2:
                stop_event.set()
                return
            time.sleep(0.01)
        stop_event.set()

    helper = threading.Thread(target=stop_after_two_sends, daemon=True)
    helper.start()

    with patch("cue_mark.telegram.handler.TYPING_REFRESH_INTERVAL_SECONDS", 0.01):
        _refresh_chat_action(client, "123", action="typing", stop_event=stop_event)

    helper.join(timeout=1.0)
    assert client.send_chat_action.call_count >= 2


def test_handler_accepts_and_processes(monkeypatch, tmp_path):
    from cue.config import settings
    from cue_mark.models import MarkResponse

    monkeypatch.setattr(settings, "mark_vault_root", str(tmp_path / "vault"))
    monkeypatch.setattr(settings, "telegram_allowed_users", "123456789")

    mark_service = MagicMock()
    mark_service.capture.return_value = MarkResponse(
        title="MLX Agents",
        file_path=str(tmp_path / "vault/2026-06-11/mlx-agents.md"),
        mode="page",
    )

    telegram_client = MagicMock()
    handler = TelegramUpdateHandler(
        mark_service=mark_service,
        telegram_client=telegram_client,
        event_store=TelegramEventStore(tmp_path / "jobs.sqlite3"),
    )

    status, inbound = handler.accept_update(TEXT_UPDATE)
    assert status["status"] == "accepted"
    assert inbound is not None

    handler.process_inbound(inbound)
    mark_service.capture.assert_called_once()
    telegram_client.send_chat_action.assert_called_once_with("123456789", action="typing")
    telegram_client.send_message.assert_called_once()


def test_handler_ping_allowed(monkeypatch, tmp_path):
    from cue.config import settings

    monkeypatch.setattr(settings, "telegram_allowed_users", "123456789")
    telegram_client = MagicMock()
    handler = TelegramUpdateHandler(telegram_client=telegram_client)

    update = {
        **TEXT_UPDATE,
        "message": {
            **TEXT_UPDATE["message"],
            "text": "ping",
            "entities": [],
        },
    }
    status, inbound = handler.accept_update(update)
    assert status["status"] == "ping"
    assert inbound is None
    telegram_client.send_message.assert_called_once_with(
        "123456789",
        "pong — you're allowed (user id: 123456789)",
    )


def test_handler_ping_not_allowed(monkeypatch, tmp_path):
    from cue.config import settings

    monkeypatch.setattr(settings, "telegram_allowed_users", "999999999")
    telegram_client = MagicMock()
    handler = TelegramUpdateHandler(telegram_client=telegram_client)

    update = {
        **TEXT_UPDATE,
        "message": {
            **TEXT_UPDATE["message"],
            "text": "/ping",
            "entities": [],
        },
    }
    status, inbound = handler.accept_update(update)
    assert status["status"] == "ping"
    assert inbound is None
    telegram_client.send_message.assert_called_once_with(
        "123456789",
        "Not allowed. Your user id is 123456789. Add it to CUE_TELEGRAM_ALLOWED_USERS.",
    )


def test_handler_rejects_unauthorized_sender(monkeypatch, tmp_path):
    from cue.config import settings

    monkeypatch.setattr(settings, "telegram_allowed_users", "999999999")
    handler = TelegramUpdateHandler(
        event_store=TelegramEventStore(tmp_path / "jobs.sqlite3"),
    )

    status, inbound = handler.accept_update(TEXT_UPDATE)
    assert status["status"] == "ignored"
    assert status["reason"] == "sender_not_allowed"
    assert inbound is None


def test_handler_routes_search_command(monkeypatch, tmp_path):
    from cue.config import settings
    from cue_search.models import SearchResponse

    monkeypatch.setattr(settings, "mark_vault_root", str(tmp_path / "vault"))
    monkeypatch.setattr(settings, "telegram_allowed_users", "123456789")

    mark_service = MagicMock()
    search_service = MagicMock()
    search_service.search.return_value = SearchResponse(
        answer="**Saved notes** about frp.",
        sources=[],
    )

    telegram_client = MagicMock()
    handler = TelegramUpdateHandler(
        mark_service=mark_service,
        search_service=search_service,
        telegram_client=telegram_client,
        event_store=TelegramEventStore(tmp_path / "jobs.sqlite3"),
    )

    update = {
        **TEXT_UPDATE,
        "update_id": 10002,
        "message": {
            **TEXT_UPDATE["message"],
            "text": "search what about frp?",
            "entities": [],
        },
    }
    status, inbound = handler.accept_update(update)
    assert status["status"] == "accepted"
    assert inbound is not None

    handler.process_inbound(inbound)
    mark_service.capture.assert_not_called()
    search_service.search.assert_called_once()
    assert search_service.search.call_args.args[0].summary_only is True
    telegram_client.send_message.assert_called_once()
    call = telegram_client.send_message.call_args
    assert call.args[0] == "123456789"
    assert call.kwargs["parse_mode"] == "HTML"
    assert call.kwargs["fallback_text"] == "**Saved notes** about frp."
    assert call.args[1] == "<b>Saved notes</b> about frp."


def test_handler_empty_search_returns_usage(monkeypatch, tmp_path):
    from cue.config import settings
    from cue_mark.telegram.commands import SEARCH_USAGE_MESSAGE

    monkeypatch.setattr(settings, "mark_vault_root", str(tmp_path / "vault"))
    monkeypatch.setattr(settings, "telegram_allowed_users", "123456789")

    telegram_client = MagicMock()
    handler = TelegramUpdateHandler(
        telegram_client=telegram_client,
        event_store=TelegramEventStore(tmp_path / "jobs.sqlite3"),
    )

    update = {
        **TEXT_UPDATE,
        "update_id": 10003,
        "message": {
            **TEXT_UPDATE["message"],
            "text": "search",
            "entities": [],
        },
    }
    _, inbound = handler.accept_update(update)
    handler.process_inbound(inbound)
    telegram_client.send_message.assert_called_once_with("123456789", SEARCH_USAGE_MESSAGE)


def test_handler_routes_reindex_command(monkeypatch, tmp_path):
    from cue.config import settings
    from cue_search.models import IndexResponse

    monkeypatch.setattr(settings, "mark_vault_root", str(tmp_path / "vault"))
    monkeypatch.setattr(settings, "telegram_allowed_users", "123456789")
    (tmp_path / "vault").mkdir()

    mark_service = MagicMock()
    search_service = MagicMock()
    search_service.sync_index.return_value = IndexResponse(
        files_scanned=3,
        chunks_indexed=42,
        corpus_root=str(tmp_path / "vault"),
    )

    telegram_client = MagicMock()
    handler = TelegramUpdateHandler(
        mark_service=mark_service,
        search_service=search_service,
        telegram_client=telegram_client,
        event_store=TelegramEventStore(tmp_path / "jobs.sqlite3"),
    )

    update = {
        **TEXT_UPDATE,
        "update_id": 10004,
        "message": {
            **TEXT_UPDATE["message"],
            "text": "reindex",
            "entities": [],
        },
    }
    _, inbound = handler.accept_update(update)
    handler.process_inbound(inbound)
    mark_service.capture.assert_not_called()
    search_service.sync_index.assert_called_once()
    telegram_client.send_message.assert_called_once_with(
        "123456789",
        "Indexed 42 chunks from 3 files.",
    )
