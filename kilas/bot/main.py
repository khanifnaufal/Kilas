"""
main.py — Entry point bot Kilas.

Jalankan:
    python -m kilas.bot.main
"""

import logging

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from .config import TELEGRAM_TOKEN
from .handlers import cb_article, cb_back_genres, cb_genre, cmd_start


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
    """Inisialisasi dan jalankan bot dalam mode polling."""
    _setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("🚀 Kilas Bot sedang dimulai...")

    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    # --- Daftarkan handler ---
    app.add_handler(CommandHandler("start", cmd_start))
    # Urutan pattern callback
    app.add_handler(CallbackQueryHandler(cb_genre, pattern=r"^genre_"))
    app.add_handler(CallbackQueryHandler(cb_article, pattern=r"^art_"))
    app.add_handler(CallbackQueryHandler(cb_back_genres, pattern=r"^back_genres$"))

    logger.info("✅ Bot siap. Tekan Ctrl+C untuk berhenti.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
