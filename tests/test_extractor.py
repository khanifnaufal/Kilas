"""
tests/test_extractor.py — Unit test untuk kilas.bot.extractor

Menguji fungsi ekstraksi teks artikel trafilatura dengan mock tanpa network asli:
- Berhasil ekstraksi konten artikel.
- Fallback ke deskripsi RSS jika unduhan/ekstraksi gagal.
- Fallback ke deskripsi RSS jika teks terlalu pendek (<50 karakter).
- Penanganan URL kosong atau saat kedua metode gagal.
- Pemotongan teks melebihi batas karakter aman.
"""

import asyncio
import unittest
from unittest.mock import patch

from kilas.bot.extractor import MAX_ARTICLE_CHARS, extract_article_text


def _run(coro):
    return asyncio.run(coro)


class TestExtractor(unittest.TestCase):
    def test_extract_success(self):
        """Uji saat trafilatura berhasil mengunduh dan mengekstrak teks panjang."""
        sample_html = "<html><body><p>Konten artikel lengkap</p></body></html>"
        extracted_content = "Ini adalah isi artikel berita yang panjang dan valid lebih dari 50 karakter untuk diuji."

        with patch("trafilatura.fetch_url", return_value=sample_html):
            with patch("trafilatura.extract", return_value=extracted_content):
                result = _run(
                    extract_article_text(
                        "https://example.com/berita", fallback_desc="Deskripsi cadangan"
                    )
                )

        self.assertEqual(result, extracted_content)

    def test_download_failure_uses_fallback(self):
        """Jika fetch_url gagal (None), gunakan fallback_desc."""
        fallback = "Ringkasan bawaan dari feed RSS yang cukup jelas."
        with patch("trafilatura.fetch_url", return_value=None):
            result = _run(
                extract_article_text(
                    "https://example.com/berita-gagal", fallback_desc=fallback
                )
            )

        self.assertEqual(result, fallback)

    def test_download_exception_uses_fallback(self):
        """Jika fetch_url memunculkan exception (e.g. timeout), gunakan fallback_desc."""
        fallback = "Ringkasan bawaan RSS tetap aman digunakan."
        with patch("trafilatura.fetch_url", side_effect=Exception("Connection refused")):
            result = _run(
                extract_article_text(
                    "https://example.com/berita-error", fallback_desc=fallback
                )
            )

        self.assertEqual(result, fallback)

    def test_extract_none_uses_fallback(self):
        """Jika fetch_url berhasil tapi extract mengembalikan None, gunakan fallback."""
        fallback = "Deskripsi RSS cadangan."
        with patch("trafilatura.fetch_url", return_value="<html></html>"):
            with patch("trafilatura.extract", return_value=None):
                result = _run(
                    extract_article_text(
                        "https://example.com/kosong", fallback_desc=fallback
                    )
                )

        self.assertEqual(result, fallback)

    def test_extract_too_short_uses_fallback(self):
        """Jika hasil ekstraksi kurang dari 50 karakter, gunakan fallback."""
        short_text = "Teks pendek"
        fallback = "Deskripsi RSS cadangan yang valid dan informatif."
        with patch("trafilatura.fetch_url", return_value="<html></html>"):
            with patch("trafilatura.extract", return_value=short_text):
                result = _run(
                    extract_article_text(
                        "https://example.com/pendek", fallback_desc=fallback
                    )
                )

        self.assertEqual(result, fallback)

    def test_both_fail_returns_empty_string(self):
        """Jika ekstraksi gagal dan fallback juga kosong, kembalikan string kosong."""
        with patch("trafilatura.fetch_url", return_value=None):
            result = _run(
                extract_article_text("https://example.com/kosong", fallback_desc="")
            )

        self.assertEqual(result, "")

    def test_empty_url_uses_fallback(self):
        """Jika URL kosong, gunakan fallback tanpa mencoba mengunduh."""
        fallback = "Deskripsi fallback saat URL kosong"
        result = _run(extract_article_text("", fallback_desc=fallback))
        self.assertEqual(result, fallback)

    def test_truncates_long_article(self):
        """Teks yang melebihi MAX_ARTICLE_CHARS dipotong rapi dengan elipsis."""
        super_long_text = "A" * (MAX_ARTICLE_CHARS + 500)
        with patch("trafilatura.fetch_url", return_value="<html></html>"):
            with patch("trafilatura.extract", return_value=super_long_text):
                result = _run(extract_article_text("https://example.com/panjang"))

        self.assertEqual(len(result), MAX_ARTICLE_CHARS + 1)  # 3500 + '…'
        self.assertTrue(result.endswith("…"))


if __name__ == "__main__":
    unittest.main()
