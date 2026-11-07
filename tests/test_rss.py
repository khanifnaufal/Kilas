"""
tests/test_rss.py — Unit test untuk kilas.bot.rss

Semua test menggunakan fixture RSS XML lokal — tidak ada network request.
feedparser.parse di-mock agar membaca dari memori, bukan dari URL.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import feedparser
import pytest

from kilas.bot.rss import (
    NewsItem,
    _parse_time,
    _strip_html,
    get_article,
    get_news_by_genre,
    store_article,
)

# ---------------------------------------------------------------------------
# Muat fixture RSS dari disk satu kali saat modul di-import
# (feedparser.parse dengan string XML tidak hit network)
# ---------------------------------------------------------------------------

_FIXTURE_DIR = Path(__file__).parent / "fixtures"

FEED_A = feedparser.parse((_FIXTURE_DIR / "sample_feed_a.xml").read_text(encoding="utf-8"))
FEED_B = feedparser.parse((_FIXTURE_DIR / "sample_feed_b.xml").read_text(encoding="utf-8"))

# Verifikasi fixture terbaca dengan benar
assert len(FEED_A.entries) == 7, "sample_feed_a.xml harus punya 7 entries"
assert len(FEED_B.entries) == 3, "sample_feed_b.xml harus punya 3 entries"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Jalankan coroutine secara sinkron di dalam test."""
    return asyncio.run(coro)


def _make_item(title: str = "Judul Test") -> NewsItem:
    return NewsItem(
        title=title,
        source="Sumber Test",
        published=datetime(2026, 11, 7, 10, 0, tzinfo=timezone.utc),
        link="https://example.com/artikel",
        description="Deskripsi singkat",
    )


# ---------------------------------------------------------------------------
# Test: _strip_html
# ---------------------------------------------------------------------------

class TestStripHtml:
    def test_hapus_tag_sederhana(self):
        assert _strip_html("<p>Hello World</p>") == "Hello World"

    def test_hapus_tag_bersarang(self):
        assert _strip_html("<div><b>Tebal</b> dan biasa</div>") == "Tebal dan biasa"

    def test_unescape_html_entities(self):
        assert _strip_html("AT&amp;T &lt;Corp&gt;") == "AT&T <Corp>"

    def test_string_kosong(self):
        assert _strip_html("") == ""

    def test_teks_tanpa_html_tidak_berubah(self):
        assert _strip_html("Teks biasa tanpa tag") == "Teks biasa tanpa tag"

    def test_hapus_tag_dengan_atribut(self):
        result = _strip_html('<a href="https://example.com">Klik di sini</a>')
        assert result == "Klik di sini"


# ---------------------------------------------------------------------------
# Test: _parse_time
# ---------------------------------------------------------------------------

class TestParseTime:
    def test_parse_published_parsed(self):
        """Entry dengan published_parsed → datetime UTC yang valid."""
        import time

        class FakeEntry:
            published_parsed = time.strptime("07 Nov 2026 10:00:00 +0000", "%d %b %Y %H:%M:%S %z")
            updated_parsed = None

        dt = _parse_time(FakeEntry())
        assert dt.year == 2026
        assert dt.month == 11
        assert dt.day == 7
        assert dt.tzinfo == timezone.utc

    def test_fallback_jika_tidak_ada_timestamp(self):
        """Entry tanpa timestamp → datetime.min UTC."""

        class FakeEntry:
            published_parsed = None
            updated_parsed = None

        dt = _parse_time(FakeEntry())
        assert dt == datetime.min.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Test: store_article / get_article
# ---------------------------------------------------------------------------

class TestArticleStore:
    def test_store_mengembalikan_id_8_karakter(self):
        art_id = store_article(_make_item())
        assert len(art_id) == 8
        assert all(c in "0123456789abcdef" for c in art_id)

    def test_store_dan_get_konsisten(self):
        item = _make_item("Judul Unik untuk Test Store")
        art_id = store_article(item)
        retrieved = get_article(art_id)
        assert retrieved is not None
        assert retrieved.title == "Judul Unik untuk Test Store"

    def test_dua_store_menghasilkan_id_berbeda(self):
        id1 = store_article(_make_item("A"))
        id2 = store_article(_make_item("B"))
        assert id1 != id2

    def test_get_id_tidak_ada_mengembalikan_none(self):
        assert get_article("00000000") is None


# ---------------------------------------------------------------------------
# Test: get_news_by_genre
# ---------------------------------------------------------------------------

class TestGetNewsByGenre:
    # --- Helpers ---

    def _fetch_genre(self, genre_key: str = "genre_teknologi") -> list[NewsItem]:
        return _run(get_news_by_genre(genre_key))

    # --- Test cases ---

    def test_mengembalikan_maksimal_5_artikel(self):
        """
        FEED_A punya 7 item, 4 feed per genre = 28 combined → top-5 dikembalikan.
        """
        with patch("feedparser.parse", return_value=FEED_A):
            items = self._fetch_genre()
        assert len(items) <= 5

    def test_diurutkan_terbaru_ke_terlama(self):
        """Artikel pertama harus memiliki published >= artikel berikutnya."""
        with patch("feedparser.parse", return_value=FEED_A):
            items = self._fetch_genre()
        assert len(items) >= 2, "Harus ada minimal 2 item untuk uji urutan"
        for i in range(len(items) - 1):
            assert items[i].published >= items[i + 1].published, (
                f"Item [{i}] ({items[i].published}) lebih lama dari "
                f"item [{i+1}] ({items[i+1].published})"
            )

    def test_artikel_pertama_adalah_paling_baru(self):
        """Item pertama harus memiliki published tertinggi."""
        with patch("feedparser.parse", return_value=FEED_A):
            items = self._fetch_genre()
        # Artikel paling baru di feed_a adalah jam 10:00 UTC
        assert items[0].published.hour == 10

    def test_genre_tidak_dikenal_mengembalikan_list_kosong(self):
        items = _run(get_news_by_genre("genre_tidak_ada"))
        assert items == []

    def test_semua_feed_gagal_mengembalikan_list_kosong(self):
        """Jika semua feed raise exception → list kosong, tidak crash."""
        with patch("feedparser.parse", side_effect=Exception("Simulasi network error")):
            items = self._fetch_genre()
        assert items == []

    def test_satu_feed_gagal_sumber_lain_tetap_dikembalikan(self):
        """
        Feed Antara (pertama di GENRE_FEEDS['genre_teknologi']) gagal,
        3 feed lain mengembalikan FEED_B → masih ada artikel yang dikembalikan.
        """
        def mock_parse(url: str):
            if "antaranews" in url:
                raise Exception("Simulasi Antara down")
            return FEED_B

        with patch("feedparser.parse", side_effect=mock_parse):
            items = self._fetch_genre("genre_teknologi")

        # 3 feed berhasil, masing-masing 3 item = 9 combined → top-5
        assert len(items) == 5

    def test_field_wajib_terisi_pada_setiap_item(self):
        """Setiap NewsItem harus memiliki title, source, link yang valid."""
        with patch("feedparser.parse", return_value=FEED_A):
            items = self._fetch_genre()
        for item in items:
            assert isinstance(item, NewsItem)
            assert item.title, "title tidak boleh kosong"
            assert item.source, "source tidak boleh kosong"
            assert isinstance(item.published, datetime)
            assert item.published.tzinfo is not None, "published harus timezone-aware"

    def test_source_diisi_dari_mapping_feed(self):
        """
        Source name harus berasal dari GENRE_FEEDS, bukan dari konten feed.
        Contoh: 'Antara', 'CNN Indonesia', 'Detik', 'Kompas'.
        """
        from kilas.bot.feeds import GENRE_FEEDS
        expected_sources = {src for src, _ in GENRE_FEEDS["genre_teknologi"]}

        with patch("feedparser.parse", return_value=FEED_A):
            items = self._fetch_genre("genre_teknologi")

        for item in items:
            assert item.source in expected_sources, (
                f"Source '{item.source}' tidak ada di GENRE_FEEDS['genre_teknologi']"
            )

    def test_deskripsi_dibersihkan_dari_html(self):
        """Deskripsi artikel tidak boleh mengandung tag HTML."""
        with patch("feedparser.parse", return_value=FEED_A):
            items = self._fetch_genre()
        for item in items:
            assert "<" not in item.description, (
                f"Deskripsi masih mengandung HTML: {item.description[:100]}"
            )

    def test_deskripsi_dibatasi_300_karakter(self):
        """Deskripsi tidak boleh melebihi 300 karakter."""
        with patch("feedparser.parse", return_value=FEED_A):
            items = self._fetch_genre()
        for item in items:
            assert len(item.description) <= 300

