"""
feeds.py — Mapping genre ke daftar RSS feed Indonesia.

Setiap genre memiliki list (nama_sumber, url_feed).
Feed yang gagal dibuang otomatis saat runtime tanpa merusak sumber lain.
"""

# genre_key → [(nama_sumber, url_feed), ...]
GENRE_FEEDS: dict[str, list[tuple[str, str]]] = {
    "genre_teknologi": [
        ("Antara",        "https://www.antaranews.com/rss/teknologi"),
        ("CNN Indonesia", "https://www.cnnindonesia.com/teknologi/rss"),
        ("Detik",         "https://inet.detik.com/rss/"),
        ("Kompas",        "https://rss.kompas.com/tekno"),
    ],
    "genre_ekonomi": [
        ("Antara",        "https://www.antaranews.com/rss/ekonomi"),
        ("CNN Indonesia", "https://www.cnnindonesia.com/ekonomi/rss"),
        ("Detik",         "https://finance.detik.com/rss/"),
        ("Kompas",        "https://rss.kompas.com/money"),
    ],
    "genre_olahraga": [
        ("Antara",        "https://www.antaranews.com/rss/olahraga"),
        ("CNN Indonesia", "https://www.cnnindonesia.com/olahraga/rss"),
        ("Detik",         "https://sport.detik.com/rss/"),
        ("Kompas",        "https://rss.kompas.com/sports"),
    ],
    "genre_politik": [
        ("Antara",        "https://www.antaranews.com/rss/politik"),
        ("CNN Indonesia", "https://www.cnnindonesia.com/nasional/rss"),
        ("Detik",         "https://news.detik.com/rss/"),
        ("Kompas",        "https://rss.kompas.com/nasional"),
    ],
    "genre_hiburan": [
        ("Antara",        "https://www.antaranews.com/rss/hiburan"),
        ("CNN Indonesia", "https://www.cnnindonesia.com/hiburan/rss"),
        ("Detik",         "https://hot.detik.com/rss/"),
        ("Kompas",        "https://rss.kompas.com/entertainment"),
    ],
}

