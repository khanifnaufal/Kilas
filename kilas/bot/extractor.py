"""
extractor.py — Ekstraksi full-text artikel dari URL menggunakan trafilatura.

trafilatura dijalankan di thread executor dengan timeout ketat (5 detik)
agar tidak memblokir event loop asyncio. Jika ekstraksi gagal, timeout,
atau teks terlalu pendek (<50 karakter), fungsi melakukan fallback otomatis
ke deskripsi bawaan RSS.
"""

import asyncio
import logging

import trafilatura

logger = logging.getLogger(__name__)

# Batas panjang teks aman untuk dikirim ke LLM (karakter)
MAX_ARTICLE_CHARS = 3500
MIN_VALID_LENGTH = 50
FETCH_TIMEOUT = 5.0   # detik


async def extract_article_text(url: str, fallback_desc: str = "") -> str:
    """
    Ekstrak teks artikel dari URL secara async dengan batas timeout ketat.

    1. Download dan ekstrak konten menggunakan trafilatura di thread executor.
    2. Jika proses melebihi FETCH_TIMEOUT (5 detik) atau gagal, segera gunakan fallback_desc.
    3. Potong teks ke batas aman (MAX_ARTICLE_CHARS) agar tidak membebani konteks LLM.

    Args:
        url: URL lengkap artikel berita.
        fallback_desc: Teks deskripsi/ringkasan bawaan RSS sebagai cadangan.

    Returns:
        Teks artikel bersih (atau fallback) yang siap diringkas,
        atau string kosong jika keduanya tidak tersedia.
    """
    cleaned_fallback = (fallback_desc or "").strip()

    if not url:
        logger.warning("extract_article_text dipanggil dengan URL kosong")
        return cleaned_fallback[:MAX_ARTICLE_CHARS]

    loop = asyncio.get_running_loop()

    # Step 1: Download konten via trafilatura.fetch_url dengan timeout 5 detik
    downloaded = None
    try:
        downloaded = await asyncio.wait_for(
            loop.run_in_executor(None, trafilatura.fetch_url, url),
            timeout=FETCH_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning("Timeout download trafilatura (>%.1fs) untuk URL '%s'. Menggunakan fallback.", FETCH_TIMEOUT, url)
    except Exception as exc:
        logger.warning("Gagal mengunduh URL '%s': %s", url, exc)

    # Step 2: Ekstraksi teks bersih via trafilatura.extract
    extracted_text: str | None = None
    if downloaded:
        try:
            extracted_text = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: trafilatura.extract(
                        downloaded,
                        include_comments=False,
                        include_tables=False,
                        favor_precision=True,
                    ),
                ),
                timeout=3.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Timeout ekstraksi trafilatura (>3s) untuk: %s", url)
        except Exception as exc:
            logger.warning("Gagal ekstraksi teks trafilatura dari '%s': %s", url, exc)

    # Step 3: Evaluasi kelayakan teks
    if extracted_text and len(extracted_text.strip()) >= MIN_VALID_LENGTH:
        final_text = extracted_text.strip()
        logger.debug("Berhasil ekstrak %d karakter dari: %s", len(final_text), url)
    else:
        # Fallback ke deskripsi RSS
        if cleaned_fallback:
            logger.info(
                "Ekstraksi teks tidak memadai dari '%s'. Menggunakan deskripsi RSS.",
                url,
            )
            final_text = cleaned_fallback
        else:
            logger.warning("Ekstraksi gagal dan tidak ada fallback untuk '%s'", url)
            return ""

    # Step 4: Potong teks ke batas panjang aman
    if len(final_text) > MAX_ARTICLE_CHARS:
        final_text = final_text[:MAX_ARTICLE_CHARS] + "…"

    return final_text
