"""
handlers.py — Command dan callback handler untuk bot Kilas.

Handler (Fase 4):
    /start         → sapaan + inline keyboard 5 genre
    /gaya          → pilih preferensi gaya ringkasan (Singkat, Standar, Detail)
    genre_*        → fetch berita terbaru, tampilkan 5 judul sebagai tombol
    art_<id>       → ringkas berita (cek cache dulu, panggil extractor + LLM jika miss)
    chstyle_menu_  → menu ganti gaya ringkasan pada artikel aktif
    chstyle_apply_ → terapkan gaya baru, ringkas ulang artikel & simpan ke cache
    setstyle_      → simpan preferensi gaya global user
    back_genres    → kembali ke daftar genre
"""

import logging

from telegram import Message, Update
from telegram.ext import ContextTypes

from .db import (
    get_cached_summary,
    get_user_style,
    set_cached_summary,
    set_user_style,
)
from .extractor import extract_article_text
from .keyboards import (
    GENRE_LABEL,
    STYLE_DISPLAY_NAMES,
    genre_keyboard,
    news_list_keyboard,
    style_keyboard,
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
    1. Coba format Markdown.
    2. Jika parsing Markdown gagal, coba plain text.
    3. Jika masih gagal (misal link URL tombol bermasalah), coba plain text tanpa keyboard.
    """
    # Upaya 1: Markdown
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

    # Upaya 3: Plain text tanpa keyboard
    try:
        await message.edit_text(
            clean_text,
            parse_mode=None,
            disable_web_page_preview=True,
        )
    except Exception as exc3:
        logger.error("Semua upaya edit pesan gagal: %s", exc3)


# ---------------------------------------------------------------------------
# Perintah /start dan /gaya
# ---------------------------------------------------------------------------

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


async def cmd_gaya(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/gaya — tampilkan menu pemilihan preferensi gaya ringkasan."""
    user = update.effective_user
    current_style = get_user_style(user.id)
    style_label = STYLE_DISPLAY_NAMES.get(current_style, current_style)

    logger.info("User %s membuka menu /gaya (saat ini: %s)", user.id, current_style)

    text = (
        "🎨 *Preferensi Gaya Ringkasan*\n\n"
        "Pilih gaya ringkasan berita favoritmu:\n"
        "• *⚡ Singkat*: 1 kalimat padat dan cepat\n"
        "• *📌 Standar*: 3 poin penting (default)\n"
        "• *📖 Detail*: 1 paragraf pendek komprehensif\n\n"
        f"Gaya aktif saat ini: *{style_label}*"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=style_keyboard(current_style=current_style),
    )


# ---------------------------------------------------------------------------
# Callback Genre & Navigasi
# ---------------------------------------------------------------------------

async def cb_genre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback saat pengguna memilih genre berita."""
    query = update.callback_query
    await query.answer()

    genre_key = query.data                              # e.g. "genre_teknologi"
    genre_label = GENRE_LABEL.get(genre_key, genre_key)

    logger.info("User %s memilih genre: %s", query.from_user.id, genre_key)
    await query.edit_message_text(f"⏳ Mengambil berita {genre_label}…")

    items = await get_news_by_genre(genre_key)

    if not items:
        await query.edit_message_text(
            f"😔 Tidak ada berita {genre_label} yang bisa diambil saat ini.\n\n"
            "Ketik /start untuk mencoba lagi.",
        )
        return

    art_ids = [store_article(item) for item in items]
    keyboard = news_list_keyboard(items, art_ids)

    await query.edit_message_text(
        f"📰 *Berita {genre_label} Terbaru*\n\n"
        "Pilih berita yang ingin kamu baca:",
        parse_mode="Markdown",
        reply_markup=keyboard,
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


# ---------------------------------------------------------------------------
# Callback Ringkasan Artikel (dengan Cache & Preferensi Gaya)
# ---------------------------------------------------------------------------

async def cb_article(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Callback saat pengguna menekan tombol judul artikel.
    1. Ambil preferensi gaya user dari DB.
    2. Cek cache (url, style). Jika ada, langsung tampilkan (Cache Hit).
    3. Jika tidak ada di cache (Cache Miss), ekstrak artikel & ringkas via LLM.
    4. Simpan hasil ringkasan ke cache.
    """
    query = update.callback_query
    await query.answer()

    art_id = query.data[4:]  # strip 'art_'
    article = get_article(art_id)

    if article is None:
        await query.message.reply_text(
            "⚠️ Artikel tidak ditemukan atau sesi telah kedaluwarsa.\n"
            "Silakan pilih genre ulang dengan /start."
        )
        return

    user_id = query.from_user.id
    user_style = get_user_style(user_id)
    style_label = STYLE_DISPLAY_NAMES.get(user_style, user_style)

    logger.info("User %s membuka artikel id=%s dengan gaya=%s", user_id, art_id, user_style)

    # 1. Cek Cache SQLite
    cached_summary = get_cached_summary(article.link, user_style)
    if cached_summary:
        result_text = (
            f"📰 *{article.title}*\n"
            f"🏷️ Sumber: _{article.source}_  •  _{style_label}_\n\n"
            f"{cached_summary}"
        )
        await query.message.reply_text(
            result_text,
            parse_mode="Markdown",
            reply_markup=summary_keyboard(article.link, art_id=art_id),
            disable_web_page_preview=True,
        )
        return

    # 2. Cache Miss: Kirim pesan status loading
    status_msg = await query.message.reply_text(
        f"⏳ Sedang meringkas ({style_label})…",
        reply_to_message_id=query.message.message_id,
    )

    # Ekstraksi teks artikel
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
            reply_markup=summary_keyboard(article.link, art_id=art_id),
        )
        return

    # Peringkasan via LLM
    try:
        summarizer = get_summarizer()
        summary = await summarizer.summarize(
            article.title, article_text, style=user_style
        )
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
            reply_markup=summary_keyboard(article.link, art_id=art_id),
        )
        return

    # Simpan ke cache
    set_cached_summary(article.link, user_style, summary)

    # Tampilkan hasil
    result_text = (
        f"📰 *{article.title}*\n"
        f"🏷️ Sumber: _{article.source}_  •  _{style_label}_\n\n"
        f"{summary}"
    )

    await _safe_edit_message(
        status_msg,
        result_text,
        reply_markup=summary_keyboard(article.link, art_id=art_id),
    )


# ---------------------------------------------------------------------------
# Callback Penggantian Gaya Ringkasan
# ---------------------------------------------------------------------------

async def cb_set_style(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback saat memilih gaya dari perintah /gaya (setstyle_<style>)."""
    query = update.callback_query
    await query.answer()

    style = query.data[9:]  # strip 'setstyle_'
    user_id = query.from_user.id
    set_user_style(user_id, style)

    style_label = STYLE_DISPLAY_NAMES.get(style, style)
    logger.info("User %s mengubah preferensi gaya via /gaya ke: %s", user_id, style)

    text = (
        f"✅ Gaya ringkasan berhasil diubah ke *{style_label}*!\n\n"
        "Gaya ini akan digunakan otomatis untuk setiap berita yang kamu baca.\n\n"
        "Silakan pilih genre berita untuk mulai membaca:"
    )

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=genre_keyboard(),
    )


async def cb_chstyle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Callback saat tombol [🎨 Ganti gaya] di pesan ringkasan ditekan (chstyle_menu_<art_id>).
    Tampilkan tombol 3 pilihan gaya.
    """
    query = update.callback_query
    await query.answer()

    art_id = query.data[13:]  # strip 'chstyle_menu_'
    user_id = query.from_user.id
    current_style = get_user_style(user_id)

    logger.info("User %s membuka menu ganti gaya untuk artikel id=%s", user_id, art_id)

    text = (
        "🎨 *Pilih Gaya Baru untuk Artikel Ini:*\n\n"
        "• *⚡ Singkat*: 1 kalimat padat\n"
        "• *📌 Standar*: 3 poin ringkas\n"
        "• *📖 Detail*: 1 paragraf pendek komprehensif"
    )

    await query.edit_message_reply_markup(
        reply_markup=style_keyboard(current_style=current_style, art_id=art_id)
    )


async def cb_chstyle_apply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Callback saat gaya baru dipilih untuk artikel aktif (chstyle_apply_<style>_<art_id>).
    1. Simpan preferensi gaya baru user ke DB.
    2. Cek cache. Jika ada, langsung edit pesan.
    3. Jika tidak ada di cache, minta LLM meringkas ulang dengan gaya baru & simpan cache.
    """
    query = update.callback_query
    await query.answer()

    # format: "chstyle_apply_<style>_<art_id>"
    parts = query.data.split("_")
    if len(parts) < 4:
        logger.error("Callback data chstyle_apply tidak valid: %s", query.data)
        return

    new_style = parts[2]
    art_id = parts[3]
    user_id = query.from_user.id

    # Simpan sebagai preferensi user
    set_user_style(user_id, new_style)
    style_label = STYLE_DISPLAY_NAMES.get(new_style, new_style)

    article = get_article(art_id)
    if article is None:
        await query.edit_message_text(
            "⚠️ Artikel tidak ditemukan atau sesi telah berakhir. Ketik /start."
        )
        return

    logger.info(
        "User %s menerapkan gaya baru '%s' untuk artikel id=%s",
        user_id, new_style, art_id,
    )

    # 1. Cek Cache dulu
    cached_summary = get_cached_summary(article.link, new_style)
    if cached_summary:
        result_text = (
            f"📰 *{article.title}*\n"
            f"🏷️ Sumber: _{article.source}_  •  _{style_label}_\n\n"
            f"{cached_summary}"
        )
        await _safe_edit_message(
            query.message,
            result_text,
            reply_markup=summary_keyboard(article.link, art_id=art_id),
        )
        return

    # 2. Cache Miss: Update pesan jadi loading
    await query.edit_message_text(f"⏳ Meringkas ulang dengan gaya *{style_label}*…", parse_mode="Markdown")

    article_text = await extract_article_text(
        article.link, fallback_desc=article.description
    )

    if not article_text:
        await _safe_edit_message(
            query.message,
            f"📰 *{article.title}*\n\n"
            "Maaf, isi berita tidak dapat dimuat saat ini. 🙏",
            reply_markup=summary_keyboard(article.link, art_id=art_id),
        )
        return

    try:
        summarizer = get_summarizer()
        summary = await summarizer.summarize(
            article.title, article_text, style=new_style
        )
    except Exception as exc:
        logger.error("Gagal meringkas ulang dengan gaya '%s': %s", new_style, exc)
        await _safe_edit_message(
            query.message,
            f"📰 *{article.title}*\n\n"
            "Maaf, ringkasan dengan gaya baru gagal dibuat. 🙏",
            reply_markup=summary_keyboard(article.link, art_id=art_id),
        )
        return

    # Simpan ke cache
    set_cached_summary(article.link, new_style, summary)

    result_text = (
        f"📰 *{article.title}*\n"
        f"🏷️ Sumber: _{article.source}_  •  _{style_label}_\n\n"
        f"{summary}"
    )

    await _safe_edit_message(
        query.message,
        result_text,
        reply_markup=summary_keyboard(article.link, art_id=art_id),
    )
