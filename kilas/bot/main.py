"""
main.py — Entry point bot Kilas.

Jalankan:
    python -m kilas.bot.main
"""

import logging

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from .config import TELEGRAM_TOKEN
from .db import init_db
from .handlers import (
    cb_article,
    cb_back_genres,
    cb_chstyle_apply,
    cb_chstyle_menu,
    cb_genre,
    cb_set_style,
    cmd_gaya,
    cmd_start,
)


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


def main() -> None:
    """Inisialisasi database dan jalankan bot dalam mode polling."""
    _setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("🚀 Kilas Bot sedang dimulai...")

    # 1. Inisialisasi Database SQLite
    init_db()

    # 2. Bangun Aplikasi Telegram
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    # 3. Daftarkan Handler Perintah
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("gaya", cmd_gaya))

    # 4. Daftarkan Callback Query Handlers (urutan pattern spesifik ke umum)
    app.add_handler(CallbackQueryHandler(cb_genre, pattern=r"^genre_"))
    app.add_handler(CallbackQueryHandler(cb_article, pattern=r"^art_"))
    app.add_handler(CallbackQueryHandler(cb_set_style, pattern=r"^setstyle_"))
    app.add_handler(CallbackQueryHandler(cb_chstyle_menu, pattern=r"^chstyle_menu_"))
    app.add_handler(CallbackQueryHandler(cb_chstyle_apply, pattern=r"^chstyle_apply_"))
    app.add_handler(CallbackQueryHandler(cb_back_genres, pattern=r"^back_genres$"))

    logger.info("✅ Bot siap. Tekan Ctrl+C untuk berhenti.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
