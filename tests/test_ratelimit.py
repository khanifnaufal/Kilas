"""
tests/test_ratelimit.py — Unit test untuk kilas.bot.ratelimit

Menguji:
- Batas maksimal 10 request per jendela waktu (60 detik).
- Penolakan request ke-11.
- Perhitungan sisa waktu tunggu (get_remaining_seconds).
- Mekanisme sliding window seiring bertambahnya waktu.
- Isolasi antar user (user A tidak mempengaruhi kuota user B).
- Fungsi reset rate limiter.
"""

import unittest

from kilas.bot.ratelimit import RateLimiter


class TestRateLimiter(unittest.TestCase):
    def setUp(self):
        self.limiter = RateLimiter(max_requests=10, window_seconds=60.0)

    def test_allows_up_to_max_requests(self):
        """10 request pertama dalam jendela 60 detik harus diizinkan."""
        user_id = 101
        base_time = 1000.0

        for i in range(10):
            allowed = self.limiter.is_allowed(user_id, now=base_time + i)
            self.assertTrue(allowed, f"Request ke-{i+1} seharusnya diizinkan")

    def test_blocks_eleventh_request(self):
        """Request ke-11 dalam jendela waktu yang sama harus ditolak."""
        user_id = 102
        base_time = 1000.0

        for i in range(10):
            self.limiter.is_allowed(user_id, now=base_time + i)

        # Request ke-11 di detik yang sama
        blocked = self.limiter.is_allowed(user_id, now=base_time + 15)
        self.assertFalse(blocked, "Request ke-11 seharusnya ditolak")

    def test_remaining_seconds_calculation(self):
        """Sisa detik harus bernilai positif saat kuota habis, dan 0 saat masih aman."""
        user_id = 103
        base_time = 1000.0

        # Saat baru mulai, sisa waktu tunggu adalah 0
        self.assertEqual(self.limiter.get_remaining_seconds(user_id, now=base_time), 0)

        for i in range(10):
            self.limiter.is_allowed(user_id, now=base_time + i)

        # Di detik ke-10, request terlama adalah di t=1000, kedaluwarsa di t=1060
        wait = self.limiter.get_remaining_seconds(user_id, now=base_time + 10)
        self.assertGreaterEqual(wait, 49)
        self.assertLessEqual(wait, 51)

    def test_sliding_window_allows_requests_after_expiry(self):
        """Setelah 60 detik berlalu dari request tertua, request baru diizinkan kembali."""
        user_id = 104
        base_time = 1000.0

        # 10 request di detik 1000-1009
        for i in range(10):
            self.limiter.is_allowed(user_id, now=base_time + i)

        # Di detik 1010 ditolak
        self.assertFalse(self.limiter.is_allowed(user_id, now=base_time + 10))

        # Di detik 1061 (sudah lewat 60 detik dari t=1000), request tertua sudah hangus
        self.assertTrue(self.limiter.is_allowed(user_id, now=base_time + 61))

    def test_user_isolation(self):
        """Kuota user 1 yang habis tidak boleh memblokir user 2."""
        user_1 = 201
        user_2 = 202
        base_time = 1000.0

        # Habiskan kuota user 1
        for i in range(10):
            self.limiter.is_allowed(user_1, now=base_time + i)
        self.assertFalse(self.limiter.is_allowed(user_1, now=base_time + 10))

        # User 2 harus tetap bisa request
        self.assertTrue(self.limiter.is_allowed(user_2, now=base_time + 10))

    def test_reset(self):
        """Fungsi reset mengosongkan riwayat kuota."""
        user_id = 301
        base_time = 1000.0

        for i in range(10):
            self.limiter.is_allowed(user_id, now=base_time + i)
        self.assertFalse(self.limiter.is_allowed(user_id, now=base_time + 10))

        self.limiter.reset(user_id)
        self.assertTrue(self.limiter.is_allowed(user_id, now=base_time + 10))


if __name__ == "__main__":
    unittest.main()

