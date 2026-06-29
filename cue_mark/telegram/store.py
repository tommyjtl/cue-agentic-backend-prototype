from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

OFFSET_KEY = "poll_offset"


class TelegramEventStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS telegram_events (
                    event_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    chat_id TEXT,
                    sender_id TEXT,
                    title TEXT,
                    file_path TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS telegram_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

    def get_poll_offset(self) -> int | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM telegram_state WHERE key = ?",
                (OFFSET_KEY,),
            ).fetchone()
        if row is None:
            return None
        try:
            return int(row["value"])
        except ValueError:
            return None

    def set_poll_offset(self, offset: int) -> None:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO telegram_state (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (OFFSET_KEY, str(offset)),
            )

    def try_begin(self, event_id: str, *, chat_id: str, sender_id: str) -> bool:
        now = _utc_now()
        with self._connect() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO telegram_events (
                        event_id, status, chat_id, sender_id, created_at, updated_at
                    ) VALUES (?, 'processing', ?, ?, ?, ?)
                    """,
                    (event_id, chat_id, sender_id, now, now),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def mark_completed(
        self,
        event_id: str,
        *,
        title: str,
        file_path: str,
    ) -> None:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE telegram_events
                SET status = 'completed',
                    title = ?,
                    file_path = ?,
                    error = NULL,
                    updated_at = ?
                WHERE event_id = ?
                """,
                (title, file_path, now, event_id),
            )

    def mark_failed(self, event_id: str, *, error: str) -> None:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE telegram_events
                SET status = 'failed',
                    error = ?,
                    updated_at = ?
                WHERE event_id = ?
                """,
                (error[:2000], now, event_id),
            )

    def get(self, event_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM telegram_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
        return dict(row) if row else None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
