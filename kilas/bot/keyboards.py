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
# Style Selection Keyboard (Fase 4)
# ---------------------------------------------------------------------------

STYLES_INFO: list[tuple[str, str, str]] = [
    ("singkat", "⚡ Singkat", "1 kalimat"),
    ("standar", "📌 Standar", "3 poin"),
    ("detail",  "📖 Detail",  "1 paragraf"),
]

STYLE_DISPLAY_NAMES: dict[str, str] = {
    "singkat": "⚡ Singkat (1 Kalimat)",
    "standar": "📌 Standar (3 Poin)",
    "detail":  "📖 Detail (1 Paragraf)",
}


def style_keyboard(
    current_style: str = "standar", art_id: str | None = None
) -> InlineKeyboardMarkup:
    """
    Keyboard pilihan 3 gaya ringkasan.

    Args:
        current_style: Gaya yang sedang aktif (diberi tanda centang ✓).
        art_id: Jika diklik dari pesan ringkasan, sertakan art_id untuk re-summarize.
    """
    buttons = []
    for code, label, hint in STYLES_INFO:
        mark = " ✓" if code == current_style else ""
        text = f"{label} ({hint}){mark}"

        if art_id:
            cb_data = f"chstyle_apply_{code}_{art_id}"
        else:
            cb_data = f"setstyle_{code}"

        buttons.append([InlineKeyboardButton(text=text, callback_data=cb_data)])

    if art_id:
        buttons.append(
            [InlineKeyboardButton(text="🔙 Batal", callback_data=f"art_{art_id}")]
        )

    return InlineKeyboardMarkup(buttons)


# ---------------------------------------------------------------------------
# Summary keyboard (Fase 3 & 4)
# ---------------------------------------------------------------------------

def summary_keyboard(source_url: str, art_id: str = "") -> InlineKeyboardMarkup:
    """
    Keyboard pada pesan hasil ringkasan:
    - Tombol URL [📖 Baca sumber]
    - Tombol [🎨 Ganti gaya] (Fase 4)
    - Tombol [🔙 Kembali] ke daftar genre
    """
    buttons = []

    # Row 1: Tombol URL baca sumber
    cleaned_url = (source_url or "").strip()
    if cleaned_url.startswith(("http://", "https://")):
        safe_url = cleaned_url.split()[0]
        try:
            buttons.append(
                [InlineKeyboardButton(text="📖 Baca sumber", url=safe_url)]
            )
        except Exception as exc:
            logger.warning("URL '%s' tidak valid untuk tombol Telegram: %s", safe_url, exc)

    # Row 2: Tombol Ganti Gaya & Kembali
    action_row = []
    if art_id:
        action_row.append(
            InlineKeyboardButton(
                text="🎨 Ganti gaya", callback_data=f"chstyle_menu_{art_id}"
            )
        )
    action_row.append(
        InlineKeyboardButton(text="🔙 Kembali", callback_data="back_genres")
    )

    buttons.append(action_row)
    return InlineKeyboardMarkup(buttons)


# ---------------------------------------------------------------------------
# Digest Keyboards (Fase 5)
# ---------------------------------------------------------------------------

DIGEST_HOURS: list[tuple[str, str]] = [
    ("🌅 06:00", "06:00"),
    ("☕ 07:00", "07:00"),
    ("☀️ 08:00", "08:00"),
    ("🥪 12:00", "12:00"),
    ("🌇 18:00", "18:00"),
    ("🌙 20:00", "20:00"),
]


def digest_genre_keyboard(has_active_sub: bool = False) -> InlineKeyboardMarkup:
    """
    Keyboard pemilihan genre untuk langganan digest harian.
    Menyediakan tombol opsi matikan digest jika user sudah berlangganan.
    """
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"dig_genre_{code}")]
        for label, code in GENRES
    ]

    action_row = []
    if has_active_sub:
        action_row.append(
            InlineKeyboardButton(text="🔕 Matikan Digest", callback_data="dig_off")
        )
    action_row.append(
        InlineKeyboardButton(text="❌ Tutup", callback_data="dig_close")
    )

    buttons.append(action_row)
    return InlineKeyboardMarkup(buttons)


def digest_time_keyboard(genre_code: str) -> InlineKeyboardMarkup:
    """
    Keyboard pemilihan jam pengiriman digest harian (WIB).
    Opsi jam: 06:00, 07:00, 08:00, 12:00, 18:00, 20:00.
    """
    buttons = [
        [
            InlineKeyboardButton(
                text=label, callback_data=f"dig_time_{genre_code}_{time_val}"
            )
            for label, time_val in DIGEST_HOURS[:3]
        ],
        [
            InlineKeyboardButton(
                text=label, callback_data=f"dig_time_{genre_code}_{time_val}"
            )
            for label, time_val in DIGEST_HOURS[3:]
        ],
        [
            InlineKeyboardButton(text="🔙 Ganti Genre", callback_data="dig_back_genre"),
            InlineKeyboardButton(text="❌ Batal", callback_data="dig_close"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)
