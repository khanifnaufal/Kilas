"""
handlers.py — Command dan callback handler untuk bot Kilas.

Handler yang tersedia (Fase 1):
    /start  → sapaan + inline keyboard 5 genre
    genre_* → balas dengan teks dummy "Kamu memilih genre X"
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from .keyboards import GENRE_LABEL, genre_keyboard

logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — kirim pesan sambutan beserta keyboard pilihan genre."""
    user = update.effective_user
    logger.info("User %s (%s) menjalankan /start", user.id, user.first_name)

    await update.message.reply_text(
        f"Halo, {user.first_name}! 👋\n\n"
        "Selamat datang di *Kilas* — ringkasan berita Indonesia terkini.\n\n"
        "Pilih genre berita yang ingin kamu baca:",
        parse_mode="Markdown",
        reply_markup=genre_keyboard(),
    )


async def cb_genre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback saat pengguna menekan salah satu tombol genre."""
    query = update.callback_query
    # Wajib dipanggil agar Telegram tahu callback sudah ditangani
    await query.answer()

    genre_data = query.data                          # e.g. "genre_teknologi"
    genre_label = GENRE_LABEL.get(genre_data, genre_data)  # e.g. "💻 Teknologi"

    logger.info(
        "User %s memilih genre: %s",
        query.from_user.id,
        genre_data,
    )

    await query.edit_message_text(
        f"Kamu memilih genre *{genre_label}* 🎯\n\n"
        "_Ringkasan berita untuk genre ini akan hadir segera!_",
        parse_mode="Markdown",
    )
