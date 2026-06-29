from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from cue.config import settings
from cue_mark.telegram.client import TelegramClient
from cue_mark.telegram.handler import TelegramUpdateHandler
from cue_mark.telegram.store import TelegramEventStore

logger = logging.getLogger(__name__)

INITIAL_RETRY_DELAY_SECONDS = 5
MAX_RETRY_DELAY_SECONDS = 60
GET_UPDATES_RETRY_DELAY_SECONDS = 5


def _friendly_network_error(exc: Exception) -> str:
    if isinstance(exc, httpx.ConnectTimeout):
        return (
            "connection timed out reaching api.telegram.org — "
            "check network, VPN, or firewall"
        )
    if isinstance(exc, httpx.ConnectError):
        return f"connection failed — {exc}"
    if isinstance(exc, httpx.TimeoutException):
        return f"request timed out — {exc}"
    return str(exc)


def get_me_with_retry(client: TelegramClient) -> dict[str, Any]:
    delay = INITIAL_RETRY_DELAY_SECONDS
    attempt = 0
    while True:
        attempt += 1
        try:
            return client.get_me()
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            logger.warning(
                "Cannot reach Telegram API (attempt %s): %s Retrying in %s seconds.",
                attempt,
                _friendly_network_error(exc),
                delay,
            )
            time.sleep(delay)
            delay = min(delay * 2, MAX_RETRY_DELAY_SECONDS)


def run_poller(
    *,
    handler: TelegramUpdateHandler | None = None,
    client: TelegramClient | None = None,
    event_store: TelegramEventStore | None = None,
) -> None:
    if not settings.telegram_configured:
        raise SystemExit("CUE_TELEGRAM_BOT_TOKEN is not configured.")

    if not settings.telegram_allowed_user_set:
        raise SystemExit("CUE_TELEGRAM_ALLOWED_USERS must include at least one Telegram user ID.")

    try:
        settings.mark_vault_dir
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    telegram_client = client or TelegramClient()
    store = event_store or TelegramEventStore(settings.telegram_jobs_db_file)
    update_handler = handler or TelegramUpdateHandler(
        telegram_client=telegram_client,
        event_store=store,
    )

    me = get_me_with_retry(telegram_client)
    username = str(me.get("username") or "bot")
    logger.info("Polling Telegram as @%s", username)

    offset = store.get_poll_offset()
    timeout = settings.telegram_poll_timeout_seconds

    while True:
        try:
            updates = telegram_client.get_updates(
                offset=offset,
                timeout=timeout,
                allowed_updates=["message"],
            )
        except Exception as exc:
            logger.warning(
                "Telegram getUpdates failed: %s Retrying in %s seconds.",
                _friendly_network_error(exc),
                GET_UPDATES_RETRY_DELAY_SECONDS,
            )
            time.sleep(GET_UPDATES_RETRY_DELAY_SECONDS)
            continue

        for update in updates:
            update_id = update.get("update_id")
            if isinstance(update_id, int):
                offset = update_id + 1
                store.set_poll_offset(offset)

            status, inbound = update_handler.accept_update(update)
            logger.debug("Update result: %s", status)
            if inbound is None:
                continue

            update_handler.process_inbound(inbound)
