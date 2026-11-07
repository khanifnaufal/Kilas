"""
handlers.py — Command dan callback handler untuk bot Kilas.

Handler (Fase 3):
    /start       → sapaan + inline keyboard 5 genre
    genre_*      → fetch berita terbaru, tampilkan 5 judul sebagai tombol
    art_<id>     → status "Sedang meringkas...", ekstrak artikel, panggil LLM,
                   tampilkan ringkasan 3 poin + tombol [Baca sumber] & [Kembali]
    back_genres  → kembali ke daftar genre
"""

import logging

from telegram import Message, Update
from telegram.ext import ContextTypes

from .extractor import extract_article_text
from .keyboards import (
    GENRE_LABEL,
    genre_keyboard,
    news_list_keyboard,
    summary_keyboard,
)
from .rss import get_article, get_news_by_genre, store_article
from .summarizer import SummarizerError, get_summarizer

logger = logging.getLogger(__name__)


async def _safe_edit_message(
    message: Message,
    text: str,
    reply_markup=None,
) -> None:
    """
    Helper untuk edit pesan Telegram dengan proteksi bertingkat:
    1. Coba kirim dengan parse_mode='Markdown'.
    2. Jika parsing Markdown gagal (karakter entitas tidak cocok), coba plain text.
    3. Jika masih gagal (misal link URL pada tombol bermasalah), kirim plain text tanpa keyboard.
    Mencegah bot crash dan memastikan pesan selalu sampai ke pengguna.
    """
    # Upaya 1: Format Markdown
    try:
        await message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
        return
    except Exception as exc1:
        logger.warning("Edit dengan Markdown gagal (%s). Coba plain text.", exc1)

    # Bersihkan markdown agar tidak ada karakter pembuat error
    clean_text = (
        text.replace("*", "")
        .replace("_", "")
        .replace("`", "")
        .replace("[", "")
        .replace("]", "")
    )

    # Upaya 2: Plain text dengan keyboard
    try:
        await message.edit_text(
            clean_text,
            parse_mode=None,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
        return
    except Exception as exc2:
        logger.warning("Edit plain text gagal (%s). Coba tanpa reply_markup.", exc2)

    # Upaya 3: Plain text tanpa keyboard (jika URL button invalid)
    try:
        await message.edit_text(
            clean_text,
            parse_mode=None,
            disable_web_page_preview=True,
        )
    except Exception as exc3:
        logger.error("Semua upaya edit pesan gagal: %s", exc3)


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
    Callback saat pengguna menekan tombol judul artikel.
    1. Kirim pesan status "Sedang meringkas...".
    2. Ekstrak teks artikel (trafilatura -> fallback RSS).
    3. Hasilkan ringkasan via LLM (gaya Standar 3 poin).
    4. Edit pesan status menjadi ringkasan lengkap + tombol aksi.
    """
    query = update.callback_query
    await query.answer()

    # callback_data format: "art_<8hexchar>"
    art_id = query.data[4:]
    article = get_article(art_id)

    logger.info("User %s membuka artikel id=%s", query.from_user.id, art_id)

    if article is None:
        await query.message.reply_text(
            "⚠️ Artikel tidak ditemukan atau sesi telah kedaluwarsa.\n"
            "Silakan pilih genre ulang dengan /start."
        )
        return

    # Kirim pesan status awal
    status_msg = await query.message.reply_text(
        "⏳ Sedang meringkas...",
        reply_to_message_id=query.message.message_id,
    )

    # 1. Ekstraksi teks artikel
    article_text = await extract_article_text(
        article.link, fallback_desc=article.description
    )

    if not article_text:
        logger.warning("Ekstraksi dan fallback gagal untuk '%s'", article.link)
        await _safe_edit_message(
            status_msg,
            f"📰 *{article.title}*\n"
            f"🏷️ Sumber: _{article.source}_\n\n"
            "Maaf, isi berita tidak dapat dimuat saat ini. 🙏\n"
            "Silakan baca berita selengkapnya langsung di sumber resminya.",
            reply_markup=summary_keyboard(article.link),
        )
        return

    # 2. Peringkasan via LLM
    try:
        summarizer = get_summarizer()
        summary = await summarizer.summarize(article.title, article_text)
    except Exception as exc:
        err_msg = str(exc)
        logger.error("Gagal meringkas artikel '%s': %s", article.title, exc, exc_info=True)

        detail = "Maaf, ringkasan sedang tidak dapat dibuat saat ini. 🙏"
        if "api_key" in err_msg.lower() or "unauthorized" in err_msg.lower() or "401" in err_msg:
            detail = "⚠️ API Key LLM belum dikonfigurasi dengan benar di file .env."
        elif "rate limit" in err_msg.lower() or "429" in err_msg:
            detail = "⏳ Batas kuota LLM tercapai sementara (rate limit). Silakan coba lagi beberapa saat lagi."

        await _safe_edit_message(
            status_msg,
            f"📰 *{article.title}*\n"
            f"🏷️ Sumber: _{article.source}_\n\n"
            f"{detail}\n\n"
            "Kamu tetap bisa membaca berita lengkapnya melalui tombol di bawah.",
            reply_markup=summary_keyboard(article.link),
        )
        return

    # 3. Sukses: Tampilkan hasil ringkasan 3 poin
    result_text = (
        f"📰 *{article.title}*\n"
        f"🏷️ Sumber: _{article.source}_\n\n"
        f"{summary}"
    )

    await _safe_edit_message(
        status_msg,
        result_text,
        reply_markup=summary_keyboard(article.link),
    )


async def cb_back_genres(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback tombol [🔙 Kembali] untuk memilih genre kembali."""
    query = update.callback_query
    await query.answer()

    logger.info("User %s menekan tombol kembali ke daftar genre", query.from_user.id)

    await query.edit_message_text(
        "Pilih genre berita yang ingin kamu baca:",
        parse_mode="Markdown",
        reply_markup=genre_keyboard(),
    )
