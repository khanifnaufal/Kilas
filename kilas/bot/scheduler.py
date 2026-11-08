"""
scheduler.py — Penjadwalan digest berita harian menggunakan APScheduler.

Fitur:
- Timezone: Asia/Jakarta (WIB).
- Memuat semua subscription saat bot start.
- Penjadwalan dinamis (tambah, perbarui, dan hapus tanpa restart bot).
- Peringkasan berita top 5 per genre sesuai preferensi gaya user (memanfaatkan cache).
- Penanganan jika user memblokir bot (otomatis hapus langganan).
"""

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot
from telegram.error import Forbidden

from .db import (
    delete_user_subscription,
    get_all_subscriptions,
    get_cached_summary,
    get_user_style,
    get_user_subscription,
    set_cached_summary,
)
from .extractor import extract_article_text
from .keyboards import GENRE_LABEL, STYLE_DISPLAY_NAMES
from .rss import get_news_by_genre
from .summarizer import get_summarizer

logger = logging.getLogger(__name__)

JAKARTA_TZ = ZoneInfo("Asia/Jakarta")

# Instance scheduler global
scheduler = AsyncIOScheduler(timezone=JAKARTA_TZ)
_bot_instance: Bot | None = None


def get_job_id(telegram_id: int) -> str:
    """Format ID pekerjaan scheduler per user."""
    return f"digest_{telegram_id}"


def parse_send_time(send_time: str) -> tuple[int, int]:
    """Parse format 'HH:MM' menjadi tuple (jam, menit)."""
    parts = send_time.strip().split(":")
    return int(parts[0]), int(parts[1])


def schedule_user_digest(telegram_id: int, send_time: str) -> None:
    """
    Jadwalkan atau perbarui job pengiriman digest harian untuk user tertentu
    secara dinamis tanpa perlu restart bot.
    """
    job_id = get_job_id(telegram_id)
    try:
        hour, minute = parse_send_time(send_time)
    except (ValueError, IndexError) as exc:
        logger.error("Format send_time tidak valid '%s' untuk user %s: %s", send_time, telegram_id, exc)
        return

    trigger = CronTrigger(hour=hour, minute=minute, timezone=JAKARTA_TZ)
    scheduler.add_job(
        send_daily_digest,
        trigger=trigger,
        id=job_id,
        args=[telegram_id],
        replace_existing=True,
    )
    logger.info(
        "Job digest dijadwalkan: user=%s pada %02d:%02d WIB (job_id=%s)",
        telegram_id, hour, minute, job_id,
    )


def remove_user_digest(telegram_id: int) -> None:
    """Hapus job pengiriman digest harian user dari scheduler."""
    job_id = get_job_id(telegram_id)
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info("Job digest dihapus: job_id=%s", job_id)


def load_all_subscriptions_to_scheduler() -> None:
    """
    Muat semua subscription dari database SQLite ke APScheduler saat startup.
    """
    subscriptions = get_all_subscriptions()
    logger.info("Memuat %d langganan digest ke scheduler...", len(subscriptions))
    for sub in subscriptions:
        schedule_user_digest(sub["telegram_id"], sub["send_time"])
    logger.info("Semua langganan berhasil dimuat ke scheduler.")


def start_scheduler(bot: Bot) -> None:
    """
    Mulai scheduler dan muat langganan dari database.
    """
    global _bot_instance
    _bot_instance = bot

    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler berjalan dengan timezone: Asia/Jakarta")

    load_all_subscriptions_to_scheduler()


# ---------------------------------------------------------------------------
# Eksekusi Pengiriman Digest Harian
# ---------------------------------------------------------------------------

async def send_daily_digest(telegram_id: int, bot: Bot | None = None) -> None:
    """
    Kirim digest harian ke user:
    1. Ambil genre dan preferensi gaya user.
    2. Ambil top 5 berita dari genre tersebut.
    3. Buat ringkasan per berita sesuai gaya user (manfaatkan cache jika ada).
    4. Gabungkan jadi satu pesan rapi dan kirim ke Telegram.
    5. Jika user memblokir bot (Forbidden), hapus langganan otomatis.
    """
    active_bot = bot or _bot_instance
    if not active_bot:
        logger.error("Bot instance belum diinisialisasi di scheduler.")
        return

    # 1. Cek subscription
    sub = get_user_subscription(telegram_id)
    if not sub:
        logger.info("Langganan user %s tidak ditemukan, menghapus job.", telegram_id)
        remove_user_digest(telegram_id)
        return

    genre_key = sub["genre"]
    genre_label = GENRE_LABEL.get(genre_key, genre_key)
    user_style = get_user_style(telegram_id)
    style_label = STYLE_DISPLAY_NAMES.get(user_style, user_style)

    logger.info(
        "Memulai pengiriman digest harian ke user %s: genre=%s, style=%s",
        telegram_id, genre_key, user_style,
    )

    # 2. Ambil top 5 berita
    items = await get_news_by_genre(genre_key)
    if not items:
        logger.warning("Tidak ada berita yang dapat diambil untuk digest user %s", telegram_id)
        return

    # 3. Proses ringkasan untuk tiap berita (manfaatkan cache)
    summarizer = None
    digest_blocks = []

    for idx, item in enumerate(items[:5], start=1):
        # Cek Cache
        summary = get_cached_summary(item.link, user_style)

        if not summary:
            # Cache miss: ekstrak & ringkas
            text = await extract_article_text(item.link, fallback_desc=item.description)
            if not text:
                summary = "Maaf, isi berita tidak dapat dimuat."
            else:
                try:
                    if summarizer is None:
                        summarizer = get_summarizer()
                    summary = await summarizer.summarize(item.title, text, style=user_style)
                    set_cached_summary(item.link, user_style, summary)
                except Exception as exc:
                    logger.error("Gagal meringkas berita digest '%s': %s", item.title, exc)
                    summary = item.description or "Ringkasan gagal dibuat."

        block = (
            f"*{idx}. {item.title}* ({item.source})\n"
            f"{summary}\n"
            f"🔗 {item.link}"
        )
        digest_blocks.append(block)

    # 4. Susun pesan digest lengkap
    now_str = datetime.now(JAKARTA_TZ).strftime("%d %B %Y")
    header = (
        f"🌅 *Kilas Digest Harian — {genre_label}*\n"
        f"📅 _{now_str}_  •  _{style_label}_\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
    )
    body = "\n\n".join(digest_blocks)
    footer = "\n\n━━━━━━━━━━━━━━━━━━\n_Kelola jadwal pengiriman lewat perintah /digest_"
    full_message = header + body + footer

    # 5. Kirim pesan ke Telegram dengan proteksi error
    try:
        await active_bot.send_message(
            chat_id=telegram_id,
            text=full_message,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        logger.info("Berhasil mengirim digest harian ke user %s", telegram_id)
    except Forbidden:
        # User telah memblokir bot / kick bot dari grup
        logger.warning(
            "User %s telah memblokir bot. Menghapus langganan digest secara otomatis.",
            telegram_id,
        )
        delete_user_subscription(telegram_id)
        remove_user_digest(telegram_id)
    except Exception as exc:
        logger.warning("Gagal kirim digest via Markdown (%s). Coba plain text.", exc)
        try:
            # Fallback plain text jika karakter judul berita menyebabkan Markdown parsing error
            clean_message = (
                full_message.replace("*", "")
                .replace("_", "")
                .replace("`", "")
                .replace("[", "")
                .replace("]", "")
            )
            await active_bot.send_message(
                chat_id=telegram_id,
                text=clean_message,
                parse_mode=None,
                disable_web_page_preview=True,
            )
            logger.info("Berhasil mengirim digest (plain text) ke user %s", telegram_id)
        except Forbidden:
            logger.warning("User %s memblokir bot saat fallback kirim digest.", telegram_id)
            delete_user_subscription(telegram_id)
            remove_user_digest(telegram_id)
        except Exception as send_err:
            logger.error("Gagal mengirim digest ke user %s: %s", telegram_id, send_err)

