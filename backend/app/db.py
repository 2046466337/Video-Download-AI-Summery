"""SQLite 持久化。

只存任务终态与累计统计，实时进度走内存（高频写不碰磁盘）。
每次调用开独立连接，避免线程安全问题。
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS download_records (
    id          TEXT PRIMARY KEY,
    url         TEXT NOT NULL,
    title       TEXT,
    platform    TEXT,
    option_id   TEXT,
    quality     TEXT,
    status      TEXT NOT NULL,
    filename    TEXT,
    filesize    INTEGER,
    error       TEXT,
    created_at  TEXT NOT NULL,
    finished_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_records_created ON download_records(created_at DESC);

CREATE TABLE IF NOT EXISTS counters (
    key   TEXT PRIMARY KEY,
    value INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memberships (
    user_id           TEXT PRIMARY KEY,
    plan              TEXT NOT NULL,
    status            TEXT NOT NULL,
    starts_at         TEXT NOT NULL,
    expires_at        TEXT NOT NULL,
    stripe_session_id TEXT UNIQUE,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memberships_expires ON memberships(expires_at);

CREATE TABLE IF NOT EXISTS webhook_events (
    event_id     TEXT PRIMARY KEY,
    processed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usage_counters (
    subject   TEXT NOT NULL,
    date      TEXT NOT NULL,
    downloads INTEGER NOT NULL DEFAULT 0,
    summaries INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (subject, date)
);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT INTO counters(key, value) VALUES('total_downloads', 0) "
            "ON CONFLICT(key) DO NOTHING"
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_record(task_id: str, url: str, title: str, platform: str, option_id: str, quality: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO download_records"
            "(id, url, title, platform, option_id, quality, status, created_at)"
            " VALUES(?,?,?,?,?,?,'queued',?)",
            (task_id, url, title, platform, option_id, quality, _now()),
        )


def finish_record(task_id: str, status: str, filename: str = "", filesize: int | None = None, error: str = "") -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE download_records SET status=?, filename=?, filesize=?, error=?, finished_at=? WHERE id=?",
            (status, filename, filesize, error, _now(), task_id),
        )
        if status == "success":
            conn.execute("UPDATE counters SET value = value + 1 WHERE key='total_downloads'")


def get_total_downloads() -> int:
    with connect() as conn:
        row = conn.execute("SELECT value FROM counters WHERE key='total_downloads'").fetchone()
    return int(row["value"]) if row else 0


def recent_records(limit: int = 20) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM download_records ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]
