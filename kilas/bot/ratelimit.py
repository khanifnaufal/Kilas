"""
ratelimit.py — In-memory rate limiter per user.

Aturan:
- Maksimal 10 ringkasan per menit per user.
- Menggunakan sliding window sederhana berbasis timestamp.
"""

import time
from collections import defaultdict


class RateLimiter:
    """
    Sliding-window rate limiter berbasis memori.

    Attributes:
        max_requests: Jumlah permintaan maksimal dalam satu jendela waktu.
        window_seconds: Panjang jendela waktu dalam detik (default: 60 detik / 1 menit).
    """

    def __init__(self, max_requests: int = 10, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # user_id -> list[timestamp]
        self._history: dict[int, list[float]] = defaultdict(list)

    def is_allowed(self, user_id: int, now: float | None = None) -> bool:
        """
        Periksa apakah user diizinkan melakukan request baru.
        Jika diizinkan, catat timestamp request saat ini.

        Args:
            user_id: ID Telegram user.
            now: Timestamp saat ini (opsional, untuk kemudahan unit test).

        Returns:
            True jika masih di bawah kuota, False jika melebihi batas.
        """
        current_time = time.time() if now is None else now
        cutoff = current_time - self.window_seconds

        # Buang timestamp yang sudah lewat dari window
        valid_timestamps = [t for t in self._history[user_id] if t > cutoff]
        self._history[user_id] = valid_timestamps

        if len(valid_timestamps) < self.max_requests:
            self._history[user_id].append(current_time)
            return True

        return False

    def get_remaining_seconds(self, user_id: int, now: float | None = None) -> int:
        """
        Hitung perkiraan waktu tunggu (dalam detik) sampai user bisa request lagi.
        """
        current_time = time.time() if now is None else now
        cutoff = current_time - self.window_seconds
        valid_timestamps = [t for t in self._history[user_id] if t > cutoff]

        if len(valid_timestamps) < self.max_requests:
            return 0

        # Waktu tunggu dihitung dari timestamp request tertua dalam window
        oldest = valid_timestamps[0]
        wait = int(self.window_seconds - (current_time - oldest))
        return max(1, wait)

    def reset(self, user_id: int | None = None) -> None:
        """Reset riwayat request untuk user tertentu atau seluruh user."""
        if user_id is not None:
            self._history.pop(user_id, None)
        else:
            self._history.clear()


# Instance global untuk membatasi permintaan ringkasan berita
summary_rate_limiter = RateLimiter(max_requests=10, window_seconds=60.0)

