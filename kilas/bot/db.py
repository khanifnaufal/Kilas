"""
db.py — Manajemen database SQLite untuk preferensi user, langganan, dan cache ringkasan.

Tabel:
- users(telegram_id PK, style, created_at)
- subscriptions(telegram_id, genre, send_time)
- summaries_cache(url, style, summary, created_at, PK(url, style))
"""

import logging
import sqlite3
from contextlib import contextmanager
from typing import Generator, Optional

from .config import DATABASE_PATH

logger = logging.getLogger(__name__)

DEFAULT_STYLE = "standar"


@contextmanager
def get_db(db_path: str = DATABASE_PATH) -> Generator[sqlite3.Connection, None, None]:
    """Context manager untuk koneksi database SQLite yang selalu ditutup otomatis."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str = DATABASE_PATH) -> None:
    """
    Inisialisasi tabel database SQLite secara otomatis jika belum ada.
    Dipanggil saat bot pertama kali dijalankan.
    """
    logger.info("Menginisialisasi database SQLite: %s", db_path)
    with get_db(db_path) as conn:
        cursor = conn.cursor()

        # 1. Tabel users (preferensi gaya ringkasan per user)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                style TEXT NOT NULL DEFAULT 'standar',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # 2. Tabel subscriptions (untuk fitur langganan/jadwal di fase mendatang)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                telegram_id INTEGER NOT NULL,
                genre TEXT NOT NULL,
                send_time TEXT NOT NULL,
                PRIMARY KEY (telegram_id, genre)
            );
            """
        )

        # 3. Tabel summaries_cache (cache ringkasan per URL dan gaya)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS summaries_cache (
                url TEXT NOT NULL,
                style TEXT NOT NULL,
                summary TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (url, style)
            );
            """
        )
        conn.commit()
    logger.info("Inisialisasi database SQLite berhasil.")


# ---------------------------------------------------------------------------
# Preferensi User (Style)
# ---------------------------------------------------------------------------

def get_user_style(telegram_id: int, db_path: str = DATABASE_PATH) -> str:
    """
    Ambil preferensi gaya ringkasan user ('singkat' | 'standar' | 'detail').
    Default ke 'standar' jika user belum pernah mengatur preferensi.
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT style FROM users WHERE telegram_id = ?;", (telegram_id,)
        )
        row = cursor.fetchone()
        if row and row["style"]:
            return row["style"]
    return DEFAULT_STYLE


def set_user_style(
    telegram_id: int, style: str, db_path: str = DATABASE_PATH
) -> None:
    """
    Simpan atau perbarui preferensi gaya ringkasan user ke database.
    """
    cleaned_style = (style or DEFAULT_STYLE).lower().strip()
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO users (telegram_id, style)
            VALUES (?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET style = excluded.style;
            """,
            (telegram_id, cleaned_style),
        )
        conn.commit()
    logger.info("User %s memperbarui preferensi gaya ke: '%s'", telegram_id, cleaned_style)


# ---------------------------------------------------------------------------
# Cache Ringkasan (summaries_cache)
# ---------------------------------------------------------------------------

def get_cached_summary(
    url: str, style: str, db_path: str = DATABASE_PATH
) -> Optional[str]:
    """
    Cari ringkasan yang sudah tersimpan di cache berdasarkan kombinasi (url, style).
    Mencatat log cache hit / miss.

    Returns:
        Teks ringkasan jika ditemukan (hit), atau None jika belum ada (miss).
    """
    cleaned_url = (url or "").strip()
    cleaned_style = (style or DEFAULT_STYLE).lower().strip()

    if not cleaned_url:
        return None

    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT summary FROM summaries_cache WHERE url = ? AND style = ?;",
            (cleaned_url, cleaned_style),
        )
        row = cursor.fetchone()
        if row and row["summary"]:
            logger.info("CACHE HIT: url=%s, style=%s", cleaned_url, cleaned_style)
            return row["summary"]

    logger.info("CACHE MISS: url=%s, style=%s", cleaned_url, cleaned_style)
    return None


def set_cached_summary(
    url: str, style: str, summary: str, db_path: str = DATABASE_PATH
) -> None:
    """
    Simpan hasil ringkasan baru ke dalam cache database SQLite.
    """
    cleaned_url = (url or "").strip()
    cleaned_style = (style or DEFAULT_STYLE).lower().strip()
    cleaned_summary = (summary or "").strip()

    if not cleaned_url or not cleaned_summary:
        return

    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO summaries_cache (url, style, summary)
            VALUES (?, ?, ?)
            ON CONFLICT(url, style) DO UPDATE SET summary = excluded.summary, created_at = CURRENT_TIMESTAMP;
            """,
            (cleaned_url, cleaned_style, cleaned_summary),
        )
        conn.commit()
    logger.info("CACHE STORED: url=%s, style=%s (%d karakter)", cleaned_url, cleaned_style, len(cleaned_summary))
