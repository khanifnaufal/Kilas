"""
handlers.py — Command dan callback handler untuk bot Kilas.

Handler (Fase 5):
    /start         → sapaan + inline keyboard 5 genre
    /gaya          → pilih preferensi gaya ringkasan (Singkat, Standar, Detail)
    /digest        → pengaturan langganan digest harian (pilih genre & jam WIB)
    genre_*        → fetch berita terbaru, tampilkan 5 judul sebagai tombol
    art_<id>       → ringkas berita (cek rate limit, cache, panggil LLM jika miss)
    chstyle_menu_  → menu ganti gaya ringkasan pada artikel aktif
    chstyle_apply_ → terapkan gaya baru, ringkas ulang artikel & simpan ke cache
    setstyle_      → simpan preferensi gaya global user
    dig_*          → callbacks alur konfigurasi digest harian
    back_genres    → kembali ke daftar genre
"""

import logging

from telegram import Message, Update
from telegram.ext import ContextTypes

from .db import (
    delete_user_subscription,
    get_cached_summary,
    get_user_style,
    get_user_subscription,
    set_cached_summary,
    set_user_style,
    set_user_subscription,
)
from .extractor import extract_article_text
from .keyboards import (
    GENRE_LABEL,
    STYLE_DISPLAY_NAMES,
    digest_genre_keyboard,
    digest_time_keyboard,
    genre_keyboard,
    news_list_keyboard,
    style_keyboard,
    summary_keyboard,
)
from .ratelimit import summary_rate_limiter
from .rss import get_article, get_news_by_genre, store_article
from .scheduler import remove_user_digest, schedule_user_digest
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

    try:
        await message.edit_text(
            clean_text,
            parse_mode=None,
            disable_web_page_preview=True,
        )
    except Exception as exc3:
        logger.error("Semua upaya edit pesan gagal: %s", exc3)


# ---------------------------------------------------------------------------
# Perintah Utama: /start, /gaya, /digest
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — kirim pesan sambutan beserta keyboard pilihan genre."""
    user = update.effective_user
    logger.info("User %s (%s) menjalankan /start", user.id, user.first_name)

    await update.message.reply_text(
        f"Halo, {user.first_name}! 👋\n\n"
        "Selamat datang di *Kilas* — ringkasan berita Indonesia terkini.\n\n"
        "Perintah yang tersedia:\n"
        "• /start — Baca berita terkini berdasarkan genre\n"
        "• /gaya — Atur preferensi gaya ringkasanmu\n"
        "• /digest — Atur jadwal kirim ringkasan harian otomatis\n\n"
        "Pilih genre berita yang ingin kamu baca sekarang:",
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


async def cmd_digest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/digest — tampilkan menu pengaturan langganan digest harian."""
    user = update.effective_user
    sub = get_user_subscription(user.id)

    logger.info("User %s membuka menu /digest", user.id)

    if sub:
        genre_label = GENRE_LABEL.get(sub["genre"], sub["genre"])
        text = (
            "🔔 *Pengaturan Digest Berita Harian*\n\n"
            "Status saat ini: *Aktif* ✅\n"
            f"• Genre: *{genre_label}*\n"
            f"• Jam Kirim: *{sub['send_time']} WIB*\n\n"
            "Kamu bisa memilih genre lain untuk mengubah jadwal, atau matikan langganan:"
        )
    else:
        text = (
            "🔔 *Langganan Digest Berita Harian*\n\n"
            "Status saat ini: *Nonaktif* ⚪\n\n"
            "Dapatkan ringkasan top 5 berita setiap hari secara otomatis sesuai gaya pilihanmu!\n\n"
            "Langkah 1: *Pilih genre berita yang ingin kamu terima:*"
        )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=digest_genre_keyboard(has_active_sub=bool(sub)),
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
# Callback Ringkasan Artikel (dengan Rate Limiter, Cache & Preferensi Gaya)
# ---------------------------------------------------------------------------

async def cb_article(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Callback saat pengguna menekan tombol judul artikel.
    1. Cek rate limiter (maks 10 req/menit).
    2. Cek cache (url, style). Jika ada, langsung tampilkan (Cache Hit).
    3. Jika tidak ada di cache (Cache Miss), ekstrak artikel & ringkas via LLM.
    4. Simpan hasil ringkasan ke cache.
    """
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    art_id = query.data[4:]  # strip 'art_'
    article = get_article(art_id)

    if article is None:
        await query.message.reply_text(
            "⚠️ Artikel tidak ditemukan atau sesi telah kedaluwarsa.\n"
            "Silakan pilih genre ulang dengan /start."
        )
        return

    # 1. Cek Rate Limiter
    if not summary_rate_limiter.is_allowed(user_id):
        wait_sec = summary_rate_limiter.get_remaining_seconds(user_id)
        logger.warning("Rate limit terlampaui untuk user %s (tunggu %ds)", user_id, wait_sec)
        await query.message.reply_text(
            f"⏳ *Ups, pelan-pelan ya!* Kamu sudah meminta lebih dari 10 ringkasan dalam 1 menit.\n\n"
            f"Silakan tunggu sekitar *{wait_sec} detik* lagi sebelum membaca artikel berikutnya. 🙏",
            parse_mode="Markdown",
        )
        return

    user_style = get_user_style(user_id)
    style_label = STYLE_DISPLAY_NAMES.get(user_style, user_style)

    logger.info("User %s membuka artikel id=%s dengan gaya=%s", user_id, art_id, user_style)

    # 2. Cek Cache SQLite
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

    # 3. Cache Miss: Kirim status loading
    status_msg = await query.message.reply_text(
        f"⏳ Sedang meringkas ({style_label})…",
        reply_to_message_id=query.message.message_id,
    )

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

    # Tampilkan hasil ringkasan
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
    """Callback tombol [🎨 Ganti gaya] di pesan ringkasan."""
    query = update.callback_query
    await query.answer()

    art_id = query.data[13:]  # strip 'chstyle_menu_'
    user_id = query.from_user.id
    current_style = get_user_style(user_id)

    logger.info("User %s membuka menu ganti gaya untuk artikel id=%s", user_id, art_id)

    await query.edit_message_reply_markup(
        reply_markup=style_keyboard(current_style=current_style, art_id=art_id)
    )


async def cb_chstyle_apply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback saat gaya baru dipilih untuk artikel aktif."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    if len(parts) < 4:
        logger.error("Callback data chstyle_apply tidak valid: %s", query.data)
        return

    new_style = parts[2]
    art_id = parts[3]
    user_id = query.from_user.id

    # 1. Cek Rate Limiter
    if not summary_rate_limiter.is_allowed(user_id):
        wait_sec = summary_rate_limiter.get_remaining_seconds(user_id)
        await query.message.reply_text(
            f"⏳ *Ups, pelan-pelan ya!* Kamu sudah meminta lebih dari 10 ringkasan dalam 1 menit.\n\n"
            f"Silakan tunggu sekitar *{wait_sec} detik* lagi sebelum meringkas ulang. 🙏",
            parse_mode="Markdown",
        )
        return

    set_user_style(user_id, new_style)
    style_label = STYLE_DISPLAY_NAMES.get(new_style, new_style)

    article = get_article(art_id)
    if article is None:
        await query.edit_message_text(
            "⚠️ Artikel tidak ditemukan atau sesi telah berakhir. Ketik /start."
        )
        return

    logger.info("User %s menerapkan gaya baru '%s' untuk artikel id=%s", user_id, new_style, art_id)

    # Cek Cache dulu
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


# ---------------------------------------------------------------------------
# Callbacks Alur Pengaturan Digest Harian (Fase 5)
# ---------------------------------------------------------------------------

async def cb_digest_genre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback setelah user memilih genre untuk digest (dig_genre_<genre>)."""
    query = update.callback_query
    await query.answer()

    genre_code = query.data[10:]  # strip 'dig_genre_'
    genre_label = GENRE_LABEL.get(genre_code, genre_code)

    logger.info("User %s memilih genre digest: %s", query.from_user.id, genre_code)

    text = (
        f"⏰ *Pilih Jam Pengiriman Digest ({genre_label})*\n\n"
        "Pilih waktu pengiriman setiap hari (WIB):\n"
        "Bot akan otomatis mengirimkan top 5 ringkasan berita pilihanmu pada jam ini."
    )

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=digest_time_keyboard(genre_code),
    )


async def cb_digest_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback setelah user memilih jam pengiriman digest (dig_time_<genre>_<time>)."""
    query = update.callback_query
    await query.answer()

    # Format data: 'dig_time_genre_teknologi_07:00'
    payload = query.data[9:]  # strip 'dig_time_'
    genre_code, send_time = payload.rsplit("_", 1)
    user_id = query.from_user.id
    genre_label = GENRE_LABEL.get(genre_code, genre_code)

    # Simpan ke DB & update scheduler dinamis
    set_user_subscription(user_id, genre_code, send_time)
    schedule_user_digest(user_id, send_time)

    logger.info("User %s berhasil berlangganan digest %s jam %s WIB", user_id, genre_code, send_time)

    text = (
        "🎉 *Langganan Digest Berhasil Diaktifkan!*\n\n"
        f"• Genre Berita: *{genre_label}*\n"
        f"• Waktu Pengiriman: *{send_time} WIB* (Setiap Hari)\n\n"
        "Kamu akan otomatis menerima pesan ringkasan top 5 berita sesuai gaya pilihanmu. "
        "Gunakan perintah /digest kapan pun untuk mengubah jadwal atau menonaktifkannya."
    )

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=genre_keyboard(),
    )


async def cb_digest_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback untuk mematikan langganan digest harian (dig_off)."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    delete_user_subscription(user_id)
    remove_user_digest(user_id)

    logger.info("User %s mematikan langganan digest", user_id)

    text = (
        "🔕 *Digest Harian Dinonaktifkan*\n\n"
        "Kamu tidak akan lagi menerima ringkasan berita otomatis setiap hari.\n\n"
        "Ketik /digest kapan saja jika ingin mengaktifkannya kembali!"
    )

    await query.edit_message_text(text, parse_mode="Markdown")


async def cb_digest_back_genre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback kembali ke pemilihan genre digest (dig_back_genre)."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    sub = get_user_subscription(user_id)

    text = (
        "🔔 *Langganan Digest Berita Harian*\n\n"
        "Langkah 1: *Pilih genre berita yang ingin kamu terima:*"
    )

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=digest_genre_keyboard(has_active_sub=bool(sub)),
    )


async def cb_digest_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback menutup menu digest (dig_close)."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "Pengaturan digest ditutup. Ketik /digest untuk membuka kembali.",
    )
