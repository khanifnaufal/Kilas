"""
main.py — Entry point bot Kilas.

Jalankan:
    python -m kilas.bot.main
"""

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from .config import TELEGRAM_TOKEN
from .db import init_db
from .handlers import (
    cb_article,
    cb_back_genres,
    cb_chstyle_apply,
    cb_chstyle_menu,
    cb_digest_back_genre,
    cb_digest_close,
    cb_digest_genre,
    cb_digest_off,
    cb_digest_time,
    cb_genre,
    cb_set_style,
    cmd_digest,
    cmd_gaya,
    cmd_start,
)
from .scheduler import start_scheduler

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    """Konfigurasi logging ke stdout dengan format yang mudah dibaca."""
    logging.basicConfig(
        format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )
    # Kurangi log noise dari library pihak ketiga
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler error global untuk python-telegram-bot.
    Mencatat exception ke log dan mencegah bot berhenti / crash saat terjadi error.
    """
    logger.error(
        "Exception tidak tertangani saat memproses update %s: %s",
        update, context.error, exc_info=context.error,
    )


def main() -> None:
    """Inisialisasi database, scheduler, dan jalankan bot dalam mode polling."""
    _setup_logging()
    logger.info("🚀 Kilas Bot sedang dimulai...")

    # 1. Inisialisasi Database SQLite
    init_db()

    # 2. Bangun Aplikasi Telegram
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    # 3. Daftarkan Perintah (Commands)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("gaya", cmd_gaya))
    app.add_handler(CommandHandler("digest", cmd_digest))

    # 4. Daftarkan Callbacks (urutan spesifik ke umum)
    app.add_handler(CallbackQueryHandler(cb_genre, pattern=r"^genre_"))
    app.add_handler(CallbackQueryHandler(cb_article, pattern=r"^art_"))
    app.add_handler(CallbackQueryHandler(cb_set_style, pattern=r"^setstyle_"))
    app.add_handler(CallbackQueryHandler(cb_chstyle_menu, pattern=r"^chstyle_menu_"))
    app.add_handler(CallbackQueryHandler(cb_chstyle_apply, pattern=r"^chstyle_apply_"))

    # Callbacks alur digest
    app.add_handler(CallbackQueryHandler(cb_digest_genre, pattern=r"^dig_genre_"))
    app.add_handler(CallbackQueryHandler(cb_digest_time, pattern=r"^dig_time_"))
    app.add_handler(CallbackQueryHandler(cb_digest_off, pattern=r"^dig_off$"))
    app.add_handler(CallbackQueryHandler(cb_digest_back_genre, pattern=r"^dig_back_genre$"))
    app.add_handler(CallbackQueryHandler(cb_digest_close, pattern=r"^dig_close$"))

    # Navigasi umum
    app.add_handler(CallbackQueryHandler(cb_back_genres, pattern=r"^back_genres$"))

    # 5. Daftarkan Global Error Handler
    app.add_error_handler(global_error_handler)

    # 6. Inisialisasi & Jalankan Scheduler (APScheduler Asia/Jakarta)
    start_scheduler(app.bot)

    logger.info("✅ Bot siap. Tekan Ctrl+C untuk berhenti.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
