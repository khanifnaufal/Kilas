"""
keyboards.py — Definisi keyboard markup untuk bot Kilas.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

if TYPE_CHECKING:
    from .rss import NewsItem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Genre keyboard
# ---------------------------------------------------------------------------

GENRES: list[tuple[str, str]] = [
    ("💻 Teknologi", "genre_teknologi"),
    ("💰 Ekonomi",   "genre_ekonomi"),
    ("⚽ Olahraga",  "genre_olahraga"),
    ("🏛️ Politik",   "genre_politik"),
    ("🎬 Hiburan",   "genre_hiburan"),
]

# Mapping callback_data → label tampil
GENRE_LABEL: dict[str, str] = {data: label for label, data in GENRES}


def genre_keyboard() -> InlineKeyboardMarkup:
    """Kembalikan InlineKeyboard dengan 5 tombol genre (satu per baris)."""
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=data)]
        for label, data in GENRES
    ]
    return InlineKeyboardMarkup(buttons)


# ---------------------------------------------------------------------------
# News list keyboard
# ---------------------------------------------------------------------------

def _truncate(text: str, max_len: int) -> str:
    """Potong teks jika melebihi max_len karakter, tambahkan ellipsis."""
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def _format_news_label(title: str, source: str) -> str:
    """
    Format label tombol berita: '<judul dipotong> — <sumber>'
    Total panjang dijaga ≤ 60 karakter.
    """
    source_suffix = f" — {source}"
    max_title = max(10, 60 - len(source_suffix))
    return _truncate(title, max_title) + source_suffix


def news_list_keyboard(
    items: list[NewsItem], art_ids: list[str]
) -> InlineKeyboardMarkup:
    """
    Buat InlineKeyboard dari daftar artikel berita.

    Setiap tombol:
    - Teks: judul dipotong ≤60 char + nama sumber
    - callback_data: 'art_<8hexchar>' (12 byte, aman untuk batas 64 byte Telegram)
    """
    buttons = [
        [
            InlineKeyboardButton(
                text=_format_news_label(item.title, item.source),
                callback_data=f"art_{art_id}",
            )
        ]
        for item, art_id in zip(items, art_ids)
    ]
    return InlineKeyboardMarkup(buttons)


# ---------------------------------------------------------------------------
# Summary keyboard (Fase 3)
# ---------------------------------------------------------------------------

def summary_keyboard(source_url: str) -> InlineKeyboardMarkup:
    """
    Keyboard pada pesan hasil ringkasan:
    - Tombol URL [📖 Baca sumber]
    - Tombol Callback [🔙 Kembali] untuk kembali memilih genre
    """
    action_row: list[InlineKeyboardButton] = []

    cleaned_url = (source_url or "").strip()
    if cleaned_url.startswith(("http://", "https://")):
        # Bersihkan spasi atau karakter kontrol yang merusak URL Telegram
        safe_url = cleaned_url.split()[0]
        try:
            action_row.append(
                InlineKeyboardButton(text="📖 Baca sumber", url=safe_url)
            )
        except Exception as exc:
            logger.warning("URL '%s' tidak valid untuk tombol Telegram: %s", safe_url, exc)

    action_row.append(
        InlineKeyboardButton(text="🔙 Kembali", callback_data="back_genres")
    )

    return InlineKeyboardMarkup([action_row])
