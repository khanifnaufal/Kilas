"""
summarizer.py — Abstraksi LLM summarizer untuk bot Kilas.

Mendukung berbagai provider (Groq, Gemini, Claude) dengan interface seragam.
Gaya ringkasan: "Standar" (3 poin ringkas, Bahasa Indonesia, anti-halusinasi,
maksimal sekitar 80 kata).
"""

import asyncio
import logging
from abc import ABC, abstractmethod

from .config import (
    CLAUDE_MODEL,
    GEMINI_MODEL,
    GROQ_MODEL,
    LLM_API_KEY,
    LLM_PROVIDER,
    LLM_TIMEOUT,
)

logger = logging.getLogger(__name__)

# Batas aman karakter artikel sebelum diformat ke prompt
MAX_LLM_INPUT_CHARS = 3500

# ---------------------------------------------------------------------------
# Template Prompt Gaya Standar
# ---------------------------------------------------------------------------
STANDARD_SUMMARY_PROMPT = """Tugasmu adalah membuat ringkasan berita dalam gaya Standar untuk bot berita Telegram 'Kilas'.

Aturan ketat yang WAJIB dipatuhi:
1. Tulis ringkasan tepat dalam 3 poin ringkas (gunakan simbol bullet • di awal setiap poin).
2. Gunakan Bahasa Indonesia yang baik, lugas, dan mudah dipahami.
3. Hanya gunakan fakta yang terdapat dalam isi artikel yang diberikan. Jangan pernah mengarang atau menambahkan fakta dari luar (anti-halusinasi).
4. Parafrase dengan kalimatmu sendiri, jangan menyalin kalimat mentah-mentah dari artikel.
5. Panjang total seluruh ringkasan maksimal sekitar 80 kata.
6. Jangan sertakan judul, salam pembuka, atau komentar penutup. Langsung tampilkan 3 poin ringkas.

Judul Artikel: {title}
Isi Artikel:
{text}
"""


class SummarizerError(Exception):
    """Exception umum saat terjadi kegagalan pada proses summarizer."""
    pass


def prepare_prompt(title: str, text: str) -> str:
    """Bersihkan, potong teks ke batas aman, dan susun prompt standar."""
    cleaned_title = (title or "").strip()
    cleaned_text = (text or "").strip()
    if len(cleaned_text) > MAX_LLM_INPUT_CHARS:
        cleaned_text = cleaned_text[:MAX_LLM_INPUT_CHARS] + "…"
    return STANDARD_SUMMARY_PROMPT.format(title=cleaned_title, text=cleaned_text)


# ---------------------------------------------------------------------------
# Base Summarizer Class
# ---------------------------------------------------------------------------
class BaseSummarizer(ABC):
    """Kelas dasar abstrak untuk semua provider LLM summarizer."""

    @abstractmethod
    async def summarize(self, title: str, text: str) -> str:
        """
        Hasilkan ringkasan 3 poin dari judul dan isi artikel.

        Args:
            title: Judul artikel.
            text: Isi teks artikel.

        Returns:
            Teks ringkasan 3 poin.

        Raises:
            SummarizerError: Jika API error, timeout, atau teks kosong.
        """
        pass


# ---------------------------------------------------------------------------
# Groq Implementation
# ---------------------------------------------------------------------------
class GroqSummarizer(BaseSummarizer):
    """Implementasi summarizer menggunakan Groq API dengan auto-discovery model."""

    def __init__(
        self,
        api_key: str,
        model: str = GROQ_MODEL,
        timeout: float = LLM_TIMEOUT,
    ) -> None:
        self.api_key = api_key.strip().strip("'\"")
        self.model = model
        self.timeout = timeout

    async def summarize(self, title: str, text: str) -> str:
        if not text or not text.strip():
            raise SummarizerError("Teks artikel kosong atau tidak tersedia.")

        prompt = prepare_prompt(title, text)
        from groq import AsyncGroq

        client = AsyncGroq(api_key=self.api_key, timeout=self.timeout)

        # 1. Coba request dengan model utama
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            content = response.choices[0].message.content
            if content and content.strip():
                return content.strip()
        except Exception as exc:
            err_str = str(exc).lower()
            logger.warning("Request ke model Groq '%s' gagal: %s", self.model, exc)

            # Jika error 404 / model tidak ditemukan, lakukan auto-discovery model aktif dari akun
            if "not_found" in err_str or "does not exist" in err_str or "404" in err_str or "model_not_found" in err_str:
                logger.info("🔍 Mengambil daftar model aktif yang tersedia di akun Groq kamu...")
                try:
                    models_page = await client.models.list()
                    available_ids = [m.id for m in models_page.data]
                    logger.info("📋 Daftar model aktif di akun Groq kamu: %s", available_ids)

                    # Cari model text-generation yang cocok (hindari whisper, guard, dsb.)
                    candidate = None
                    # Prioritas 1: Llama model
                    for mid in available_ids:
                        low = mid.lower()
                        if "whisper" in low or "guard" in low:
                            continue
                        if "llama" in low:
                            candidate = mid
                            break

                    # Prioritas 2: Qwen, Gemma, Mixtral, Deepseek
                    if not candidate:
                        for mid in available_ids:
                            low = mid.lower()
                            if "whisper" in low or "guard" in low:
                                continue
                            if any(k in low for k in ["qwen", "gemma", "mixtral", "mistral", "deepseek", "gpt"]):
                                candidate = mid
                                break

                    # Prioritas 3: Model apapun yang bukan audio/guard
                    if not candidate:
                        for mid in available_ids:
                            low = mid.lower()
                            if "whisper" not in low and "guard" not in low:
                                candidate = mid
                                break

                    if candidate:
                        logger.info("🚀 Otomatis beralih ke model Groq aktif: '%s'", candidate)
                        self.model = candidate  # simpan untuk request selanjutnya
                        fb_resp = await client.chat.completions.create(
                            model=candidate,
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.2,
                        )
                        fb_content = fb_resp.choices[0].message.content
                        if fb_content and fb_content.strip():
                            return fb_content.strip()
                except Exception as disc_err:
                    logger.error("Auto-discovery model Groq gagal: %s", disc_err)

            raise SummarizerError(f"Groq API error: {exc}") from exc

        raise SummarizerError("Respon dari Groq kosong.")


# ---------------------------------------------------------------------------
# Gemini Implementation
# ---------------------------------------------------------------------------
class GeminiSummarizer(BaseSummarizer):
    """Implementasi summarizer menggunakan Google Gemini API."""

    def __init__(
        self,
        api_key: str,
        model: str = GEMINI_MODEL,
        timeout: float = LLM_TIMEOUT,
    ) -> None:
        self.api_key = api_key.strip().strip("'\"")
        self.model = model
        self.timeout = timeout

    async def summarize(self, title: str, text: str) -> str:
        if not text or not text.strip():
            raise SummarizerError("Teks artikel kosong atau tidak tersedia.")

        prompt = prepare_prompt(title, text)
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            model_client = genai.GenerativeModel(self.model)

            loop = asyncio.get_running_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, model_client.generate_content, prompt),
                timeout=self.timeout,
            )
            content = getattr(response, "text", "")
            if not content or not content.strip():
                raise SummarizerError("Respon dari Gemini kosong.")
            return content.strip()
        except Exception as exc:
            logger.error("Error pada Gemini summarizer: %s", exc)
            raise SummarizerError(f"Gemini API error: {exc}") from exc


# ---------------------------------------------------------------------------
# Claude Implementation
# ---------------------------------------------------------------------------
class ClaudeSummarizer(BaseSummarizer):
    """Implementasi summarizer menggunakan Anthropic Claude API."""

    def __init__(
        self,
        api_key: str,
        model: str = CLAUDE_MODEL,
        timeout: float = LLM_TIMEOUT,
    ) -> None:
        self.api_key = api_key.strip().strip("'\"")
        self.model = model
        self.timeout = timeout

    async def summarize(self, title: str, text: str) -> str:
        if not text or not text.strip():
            raise SummarizerError("Teks artikel kosong atau tidak tersedia.")

        prompt = prepare_prompt(title, text)
        try:
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(api_key=self.api_key, timeout=self.timeout)
            message = await client.messages.create(
                model=self.model,
                max_tokens=350,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            content = message.content[0].text if message.content else ""
            if not content or not content.strip():
                raise SummarizerError("Respon dari Claude kosong.")
            return content.strip()
        except Exception as exc:
            logger.error("Error pada Claude summarizer: %s", exc)
            raise SummarizerError(f"Claude API error: {exc}") from exc


# ---------------------------------------------------------------------------
# Factory Function
# ---------------------------------------------------------------------------
def get_summarizer(
    provider: str | None = None,
    api_key: str | None = None,
) -> BaseSummarizer:
    """
    Buat instance summarizer berdasarkan konfigurasi atau argumen.

    Args:
        provider: 'groq' | 'gemini' | 'claude' (default dari LLM_PROVIDER).
        api_key: API key provider (default dari LLM_API_KEY).

    Returns:
        Instance BaseSummarizer sesuai provider.
    """
    selected_provider = (provider or LLM_PROVIDER).lower().strip().strip("'\"")
    selected_api_key = api_key if api_key is not None else LLM_API_KEY
    if selected_api_key:
        selected_api_key = selected_api_key.strip().strip("'\"")

    if not selected_api_key:
        raise ValueError(
            f"❌ LLM_API_KEY untuk provider '{selected_provider}' belum diisi di .env."
        )

    if selected_provider == "groq":
        return GroqSummarizer(api_key=selected_api_key)
    elif selected_provider == "gemini":
        return GeminiSummarizer(api_key=selected_api_key)
    elif selected_provider == "claude":
        return ClaudeSummarizer(api_key=selected_api_key)
    else:
        raise ValueError(f"Provider LLM '{selected_provider}' tidak didukung.")
