from unittest.mock import MagicMock

import httpx
import pytest

from cue_mark.telegram.poller import (
    INITIAL_RETRY_DELAY_SECONDS,
    _friendly_network_error,
    get_me_with_retry,
)


def test_friendly_network_error_for_connect_timeout():
    message = _friendly_network_error(httpx.ConnectTimeout("SSL handshake timed out"))
    assert "api.telegram.org" in message
    assert "VPN" in message


def test_get_me_with_retry_recovers_after_transient_failure(monkeypatch):
    client = MagicMock()
    client.get_me.side_effect = [
        httpx.ConnectTimeout("SSL handshake timed out"),
        {"username": "cue_bot", "id": 1},
    ]

    sleeps: list[float] = []
    monkeypatch.setattr("cue_mark.telegram.poller.time.sleep", lambda seconds: sleeps.append(seconds))

    me = get_me_with_retry(client)

    assert me["username"] == "cue_bot"
    assert client.get_me.call_count == 2
    assert sleeps == [INITIAL_RETRY_DELAY_SECONDS]


def test_get_me_with_retry_backoff_increases(monkeypatch):
    client = MagicMock()
    client.get_me.side_effect = [
        httpx.ConnectError("failed"),
        httpx.ConnectError("failed"),
        {"username": "cue_bot", "id": 1},
    ]

    sleeps: list[float] = []
    monkeypatch.setattr("cue_mark.telegram.poller.time.sleep", lambda seconds: sleeps.append(seconds))

    get_me_with_retry(client)

    assert sleeps == [INITIAL_RETRY_DELAY_SECONDS, INITIAL_RETRY_DELAY_SECONDS * 2]


def test_get_me_with_retry_propagates_keyboard_interrupt(monkeypatch):
    client = MagicMock()
    client.get_me.side_effect = KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        get_me_with_retry(client)
