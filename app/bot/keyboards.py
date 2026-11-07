"""
keyboards.py — Definisi keyboard markup untuk bot Kilas.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# ---------------------------------------------------------------------------
# Data genre: (label_tampil, callback_data)
# ---------------------------------------------------------------------------
GENRES: list[tuple[str, str]] = [
    ("💻 Teknologi", "genre_teknologi"),
    ("💰 Ekonomi",   "genre_ekonomi"),
    ("⚽ Olahraga",  "genre_olahraga"),
    ("🏛️ Politik",   "genre_politik"),
    ("🎬 Hiburan",   "genre_hiburan"),
]

# Mapping callback_data → label (dipakai di handler)
GENRE_LABEL: dict[str, str] = {data: label for label, data in GENRES}


def genre_keyboard() -> InlineKeyboardMarkup:
    """Kembalikan InlineKeyboard dengan 5 tombol genre (satu per baris)."""
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=data)]
        for label, data in GENRES
    ]
    return InlineKeyboardMarkup(buttons)
