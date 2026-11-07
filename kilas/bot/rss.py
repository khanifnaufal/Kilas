"""
rss.py — Async RSS feed fetcher untuk Kilas Bot.

Arsitektur:
- feedparser (sync/blocking) dijalankan di thread executor agar tidak
  memblokir event loop utama Telegram.
- Semua feed dalam satu genre di-fetch secara paralel (asyncio.gather).
- Feed yang gagal di-skip; sumber lain tetap dikembalikan.
- Artikel disimpan sementara di dict memori dengan ID pendek 8-hex.
"""

import asyncio
import calendar
import html as html_module
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser

from .feeds import GENRE_FEEDS

logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<[^>]+>")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NewsItem:
    """Satu artikel berita dari RSS feed."""
    title: str
    source: str
    published: datetime
    link: str
    description: str


# ---------------------------------------------------------------------------
# In-memory article store
# key: ID pendek (8 hex char) → value: NewsItem
# ---------------------------------------------------------------------------

_article_store: dict[str, NewsItem] = {}


def store_article(item: NewsItem) -> str:
    """
    Simpan NewsItem ke memori dan kembalikan ID pendek (8 karakter hex).
    callback_data = 'art_' + art_id = 12 byte (aman di bawah batas 64 byte Telegram).
    """
    art_id = uuid.uuid4().hex[:8]
    _article_store[art_id] = item
    return art_id


def get_article(art_id: str) -> NewsItem | None:
    """Ambil NewsItem berdasarkan ID pendek. Kembalikan None jika tidak ada."""
    return _article_store.get(art_id)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _strip_html(text: str) -> str:
    """Hapus semua tag HTML dan unescape HTML entities dari teks."""
    text = _HTML_TAG_RE.sub("", text)
    return html_module.unescape(text).strip()


def _parse_time(entry) -> datetime:
    """
    Konversi published_parsed / updated_parsed dari feedparser ke datetime UTC.
    feedparser mengembalikan time.struct_time dalam UTC; gunakan calendar.timegm
    (bukan time.mktime) agar tidak terpengaruh timezone lokal.
    Kembalikan datetime.min UTC jika tidak ada timestamp.
    """
    t = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if t:
        try:
            return datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            pass
    return datetime.min.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Feed fetching
# ---------------------------------------------------------------------------

async def _fetch_one_feed(source: str, url: str) -> list[NewsItem]:
    """
    Ambil satu RSS feed secara async.
    feedparser.parse() (sync/blocking) dijalankan di thread executor.

    Return list kosong jika feed:
    - gagal diakses (network error, timeout)
    - tidak dapat di-parse (bozo=True dan entries kosong)
    Tidak melempar exception — kesalahan hanya di-log sebagai WARNING.
    """
    loop = asyncio.get_running_loop()
    try:
        feed = await loop.run_in_executor(None, feedparser.parse, url)
    except Exception as exc:
        logger.warning("Gagal mengambil feed [%s] %s: %s", source, url, exc)
        return []

    # feedparser.bozo = True berarti feed bermasalah (XML error, dsb.)
    # Masih lanjut jika ada entries; buang jika kosong.
    if feed.get("bozo") and not feed.entries:
        exc_msg = feed.get("bozo_exception", "unknown")
        logger.warning("Feed rusak/kosong [%s] %s: %s", source, url, exc_msg)
        return []

    items: list[NewsItem] = []
    for entry in feed.entries:
        title = _strip_html(entry.get("title", "(tanpa judul)"))
        # 'summary' adalah field standar, 'description' adalah alias lama
        raw_desc = entry.get("summary", entry.get("description", ""))
        desc = _strip_html(raw_desc)[:300]  # batasi deskripsi 300 karakter
        link = entry.get("link", "")

        items.append(NewsItem(
            title=title,
            source=source,
            published=_parse_time(entry),
            link=link,
            description=desc,
        ))

    logger.debug("Berhasil: %d artikel dari [%s]", len(items), source)
    return items


async def get_news_by_genre(genre_key: str) -> list[NewsItem]:
    """
    Ambil berita untuk satu genre:
    1. Fetch semua feed secara paralel (asyncio.gather + executor per feed).
    2. Gabungkan semua artikel dari semua sumber.
    3. Urutkan dari terbaru ke terlama.
    4. Kembalikan 5 artikel teratas.

    Feed yang gagal diabaikan; tidak melempar exception.
    Kembalikan list kosong jika genre tidak dikenal atau semua feed gagal.
    """
    feed_list = GENRE_FEEDS.get(genre_key, [])
    if not feed_list:
        logger.warning("Tidak ada feed untuk genre: %s", genre_key)
        return []

    # Fetch semua feed secara paralel; return_exceptions=True agar satu
    # kegagalan tidak membatalkan seluruh gather
    tasks = [_fetch_one_feed(source, url) for source, url in feed_list]
    results: list[list[NewsItem] | BaseException] = await asyncio.gather(
        *tasks, return_exceptions=True
    )

    all_items: list[NewsItem] = []
    for i, result in enumerate(results):
        if isinstance(result, BaseException):
            source_name = feed_list[i][0]
            logger.warning("gather exception dari [%s]: %s", source_name, result)
        else:
            all_items.extend(result)

    # Urutkan dari terbaru ke terlama, ambil 5 teratas
    all_items.sort(key=lambda x: x.published, reverse=True)
    top5 = all_items[:5]

    logger.info(
        "Genre '%s': %d total artikel, dikembalikan %d",
        genre_key, len(all_items), len(top5),
    )
    return top5

