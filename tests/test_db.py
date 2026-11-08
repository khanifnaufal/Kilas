"""
tests/test_db.py — Unit test untuk modul db.py

Menguji:
- Inisialisasi tabel SQLite (users, subscriptions, summaries_cache).
- Preferensi gaya user (default 'standar', get, dan set).
- Cache ringkasan (cache hit, cache miss, pembaruan, dan composite PK url+style).
- Langganan digest harian (get, set, delete, dan get_all).
"""

import os
import tempfile
import unittest

from kilas.bot.db import (
    DEFAULT_STYLE,
    delete_user_subscription,
    get_all_subscriptions,
    get_cached_summary,
    get_db,
    get_user_style,
    get_user_subscription,
    init_db,
    set_cached_summary,
    set_user_style,
    set_user_subscription,
)


class TestDatabase(unittest.TestCase):
    def setUp(self):
        """Buat file database sementara untuk setiap test case."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_file.close()
        self.db_path = self.temp_file.name
        init_db(self.db_path)

    def tearDown(self):
        """Hapus file database sementara setelah test selesai."""
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_tables_created(self):
        """Pastikan tabel users, subscriptions, dan summaries_cache terbentuk."""
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {row["name"] for row in cursor.fetchall()}

        self.assertIn("users", tables)
        self.assertIn("subscriptions", tables)
        self.assertIn("summaries_cache", tables)

    def test_init_db_is_idempotent(self):
        """Memanggil init_db berulang kali tidak menyebabkan error."""
        init_db(self.db_path)
        init_db(self.db_path)

    def test_get_user_style_default(self):
        """User baru yang belum ada di DB harus mengembalikan style default ('standar')."""
        style = get_user_style(12345, db_path=self.db_path)
        self.assertEqual(style, DEFAULT_STYLE)

    def test_set_and_get_user_style(self):
        """Set gaya baru dan pastikan tersimpan dan terbaca dengan benar."""
        user_id = 999
        set_user_style(user_id, "singkat", db_path=self.db_path)
        self.assertEqual(get_user_style(user_id, db_path=self.db_path), "singkat")

        # Perbarui ke gaya lain
        set_user_style(user_id, "detail", db_path=self.db_path)
        self.assertEqual(get_user_style(user_id, db_path=self.db_path), "detail")

    def test_cache_miss_returns_none(self):
        """URL yang belum pernah diringkas mengembalikan None (cache miss)."""
        result = get_cached_summary(
            "https://example.com/berita-baru", "standar", db_path=self.db_path
        )
        self.assertIsNone(result)

    def test_cache_hit_returns_stored_summary(self):
        """URL yang sudah dicache mengembalikan teks ringkasan (cache hit)."""
        url = "https://example.com/artikel-1"
        style = "standar"
        summary = "• Poin satu.\n• Poin dua.\n• Poin tiga."

        set_cached_summary(url, style, summary, db_path=self.db_path)
        cached = get_cached_summary(url, style, db_path=self.db_path)
        self.assertEqual(cached, summary)

    def test_cache_composite_primary_key(self):
        """
        URL yang sama dengan gaya berbeda harus disimpan terpisah.
        (url, 'singkat') != (url, 'standar')
        """
        url = "https://example.com/artikel-multi-gaya"
        sum_singkat = "Satu kalimat ringkas."
        sum_standar = "• Poin A.\n• Poin B.\n• Poin C."
        sum_detail = "Paragraf lengkap artikel berita."

        set_cached_summary(url, "singkat", sum_singkat, db_path=self.db_path)
        set_cached_summary(url, "standar", sum_standar, db_path=self.db_path)
        set_cached_summary(url, "detail", sum_detail, db_path=self.db_path)

        self.assertEqual(get_cached_summary(url, "singkat", db_path=self.db_path), sum_singkat)
        self.assertEqual(get_cached_summary(url, "standar", db_path=self.db_path), sum_standar)
        self.assertEqual(get_cached_summary(url, "detail", db_path=self.db_path), sum_detail)

    def test_cache_update_overwrites_existing(self):
        """Menyimpan ringkasan baru pada (url, style) yang sama memperbarui isinya."""
        url = "https://example.com/artikel-update"
        set_cached_summary(url, "standar", "Ringkasan lama", db_path=self.db_path)
        set_cached_summary(url, "standar", "Ringkasan baru", db_path=self.db_path)

        self.assertEqual(
            get_cached_summary(url, "standar", db_path=self.db_path), "Ringkasan baru"
        )

    # --- Pengujian Langganan Digest (Fase 5) ---

    def test_subscription_lifecycle(self):
        """Uji get, set, delete, dan get_all langganan digest."""
        user_id = 12345
        # 1. Sebelum berlangganan harus None
        self.assertIsNone(get_user_subscription(user_id, db_path=self.db_path))

        # 2. Set langganan baru
        set_user_subscription(user_id, "genre_teknologi", "07:00", db_path=self.db_path)
        sub = get_user_subscription(user_id, db_path=self.db_path)
        self.assertIsNotNone(sub)
        self.assertEqual(sub["genre"], "genre_teknologi")
        self.assertEqual(sub["send_time"], "07:00")

        # 3. Update langganan (ganti jam dan genre)
        set_user_subscription(user_id, "genre_ekonomi", "18:00", db_path=self.db_path)
        sub_updated = get_user_subscription(user_id, db_path=self.db_path)
        self.assertEqual(sub_updated["genre"], "genre_ekonomi")
        self.assertEqual(sub_updated["send_time"], "18:00")

        # 4. get_all_subscriptions
        all_subs = get_all_subscriptions(db_path=self.db_path)
        self.assertEqual(len(all_subs), 1)
        self.assertEqual(all_subs[0]["telegram_id"], user_id)

        # 5. Delete langganan
        delete_user_subscription(user_id, db_path=self.db_path)
        self.assertIsNone(get_user_subscription(user_id, db_path=self.db_path))
        self.assertEqual(len(get_all_subscriptions(db_path=self.db_path)), 0)


if __name__ == "__main__":
    unittest.main()
