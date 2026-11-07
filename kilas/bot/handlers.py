"""
handlers.py — Command dan callback handler untuk bot Kilas.

Handler (Fase 2):
    /start      → sapaan + inline keyboard 5 genre
    genre_*     → fetch berita terbaru, tampilkan 5 judul sebagai tombol
    art_<id>    → reply pesan baru: judul lengkap + link sumber
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from .keyboards import GENRE_LABEL, genre_keyboard, news_list_keyboard
from .rss import get_article, get_news_by_genre, store_article

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
    """
    Callback saat pengguna memilih genre.
    Fetch berita terbaru secara async, lalu tampilkan sebagai daftar tombol.
    """
    query = update.callback_query
    await query.answer()

    genre_key = query.data                              # e.g. "genre_teknologi"
    genre_label = GENRE_LABEL.get(genre_key, genre_key)

    logger.info("User %s memilih genre: %s", query.from_user.id, genre_key)

    # Tampilkan pesan loading sementara fetch berjalan
    await query.edit_message_text(f"⏳ Mengambil berita {genre_label}…")

    # Fetch berita (feedparser di thread executor, paralel antar sumber)
    items = await get_news_by_genre(genre_key)

    if not items:
        await query.edit_message_text(
            f"😔 Tidak ada berita {genre_label} yang bisa diambil saat ini.\n\n"
            "Ketik /start untuk mencoba lagi.",
        )
        return

    # Simpan ke memori, buat ID pendek untuk tiap artikel
    art_ids = [store_article(item) for item in items]
    keyboard = news_list_keyboard(items, art_ids)

    await query.edit_message_text(
        f"📰 *Berita {genre_label} Terbaru*\n\n"
        "Pilih berita yang ingin kamu baca:",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def cb_article(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Callback saat pengguna menekan tombol artikel.
    Reply pesan BARU (bukan edit) agar news list tetap terlihat.
    """
    query = update.callback_query
    await query.answer()

    # callback_data format: "art_<8hexchar>" → strip 4 karakter prefix "art_"
    art_id = query.data[4:]
    article = get_article(art_id)

    logger.info(
        "User %s membuka artikel id=%s", query.from_user.id, art_id
    )

    if article is None:
        await query.message.reply_text(
            "⚠️ Artikel tidak ditemukan. Silakan pilih genre ulang dengan /start."
        )
        return

    await query.message.reply_text(
        f"📄 *{article.title}*\n\n"
        f"🏷️ Sumber: _{article.source}_\n"
        f"🔗 {article.link}",
        parse_mode="Markdown",
    )

