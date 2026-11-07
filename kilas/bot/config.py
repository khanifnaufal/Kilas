"""
config.py — Loader dan validator konfigurasi dari .env

Semua variabel diakses sebagai atribut modul:
    from kilas.bot.config import TELEGRAM_TOKEN, LLM_PROVIDER, LLM_API_KEY
"""

import logging
import os

from dotenv import load_dotenv

# Muat .env dari direktori kerja (root project)
load_dotenv()

logger = logging.getLogger(__name__)


def _require(key: str) -> str:
    """Ambil env var; raise ValueError dengan pesan jelas jika kosong."""
    value = os.getenv(key, "").strip().strip("'\"")
    if not value:
        raise ValueError(
            f"\n\n❌  Variabel '{key}' tidak ditemukan atau kosong!\n"
            f"    Langkah:\n"
            f"      1. Salin .env.example  →  .env\n"
            f"      2. Isi nilai '{key}' di file .env\n"
            f"      3. Jalankan ulang bot.\n"
        )
    return value


def _optional(key: str, default: str = "") -> str:
    """Ambil env var opsional; kembalikan default jika tidak ada."""
    return os.getenv(key, default).strip().strip("'\"")


# ---------------------------------------------------------------------------
# Variabel konfigurasi — tersedia setelah modul diimpor
# ---------------------------------------------------------------------------

TELEGRAM_TOKEN: str = _require("TELEGRAM_TOKEN")
LLM_PROVIDER: str = _optional("LLM_PROVIDER", "groq").lower()
LLM_API_KEY: str = _optional("LLM_API_KEY")

# Model pilihan per provider
GROQ_MODEL: str = _optional("GROQ_MODEL", "llama-3.1-8b-instant")
GEMINI_MODEL: str = _optional("GEMINI_MODEL", "gemini-1.5-flash")
CLAUDE_MODEL: str = _optional("CLAUDE_MODEL", "claude-3-haiku-20240307")

# Timeout LLM call (detik)
try:
    LLM_TIMEOUT: float = float(_optional("LLM_TIMEOUT", "30"))
except ValueError:
    LLM_TIMEOUT = 30.0

# Validasi LLM_PROVIDER
_VALID_PROVIDERS = {"groq", "gemini", "claude"}
if LLM_PROVIDER not in _VALID_PROVIDERS:
    raise ValueError(
        f"❌  LLM_PROVIDER='{LLM_PROVIDER}' tidak valid.\n"
        f"    Pilihan yang tersedia: {', '.join(sorted(_VALID_PROVIDERS))}"
    )

logger.debug(
    "Config dimuat — provider: %s, token: %s…",
    LLM_PROVIDER,
    TELEGRAM_TOKEN[:8],
)
