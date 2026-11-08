"""
tests/test_scheduler.py — Unit test untuk kilas.bot.scheduler

Menguji logika penjadwalan tanpa menunggu waktu nyata:
- Parsing waktu 'HH:MM'.
- Penambahan dan penghapusan job scheduler secara dinamis.
- Pemuatan seluruh langganan dari DB ke scheduler.
- Eksekusi pengiriman digest harian (mock bot, format pesan, pemanfaatan cache).
- Penanganan otomatis jika user memblokir bot (Forbidden).
"""

import asyncio
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from telegram.error import Forbidden

from kilas.bot.rss import NewsItem
from kilas.bot.scheduler import (
    get_job_id,
    load_all_subscriptions_to_scheduler,
    parse_send_time,
    remove_user_digest,
    schedule_user_digest,
    scheduler,
    send_daily_digest,
)


def _run(coro):
    return asyncio.run(coro)


class TestSchedulerLogic(unittest.TestCase):
    def setUp(self):
        # Bersihkan semua job di scheduler sebelum tiap test
        for job in scheduler.get_jobs():
            job.remove()

    def tearDown(self):
        for job in scheduler.get_jobs():
            job.remove()

    def test_parse_send_time(self):
        """Format 'HH:MM' harus diparsing ke tuple (int, int)."""
        self.assertEqual(parse_send_time("07:00"), (7, 0))
        self.assertEqual(parse_send_time("18:30"), (18, 30))
        self.assertEqual(parse_send_time("00:15"), (0, 15))

    def test_get_job_id(self):
        """Format job id harus konsisten: digest_<telegram_id>."""
        self.assertEqual(get_job_id(12345), "digest_12345")

    def test_schedule_and_remove_user_digest(self):
        """schedule_user_digest mendaftarkan job, remove_user_digest menghapusnya."""
        user_id = 55555
        job_id = get_job_id(user_id)

        self.assertIsNone(scheduler.get_job(job_id))

        schedule_user_digest(user_id, "08:00")
        job = scheduler.get_job(job_id)
        self.assertIsNotNone(job)
        self.assertEqual(job.id, job_id)

        # Menghapus job
        remove_user_digest(user_id)
        self.assertIsNone(scheduler.get_job(job_id))

    def test_load_all_subscriptions_to_scheduler(self):
        """load_all_subscriptions_to_scheduler memuat seluruh langganan dari DB."""
        fake_subs = [
            {"telegram_id": 1001, "genre": "genre_teknologi", "send_time": "06:00"},
            {"telegram_id": 1002, "genre": "genre_ekonomi", "send_time": "18:00"},
        ]

        with patch("kilas.bot.scheduler.get_all_subscriptions", return_value=fake_subs):
            load_all_subscriptions_to_scheduler()

        self.assertIsNotNone(scheduler.get_job("digest_1001"))
        self.assertIsNotNone(scheduler.get_job("digest_1002"))


class TestSendDailyDigest(unittest.TestCase):
    def test_send_daily_digest_success_uses_cache(self):
        """Digest harian terkirim rapi menggunakan ringkasan cache tanpa error."""
        user_id = 777
        fake_sub = {"telegram_id": user_id, "genre": "genre_teknologi", "send_time": "07:00"}
        fake_items = [
            NewsItem(
                title="Peluncuran Satelit Baru",
                source="Kompas",
                published=datetime(2026, 11, 8, tzinfo=timezone.utc),
                link="https://example.com/satelit",
                description="Deskripsi singkat",
            )
        ]

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        with patch("kilas.bot.scheduler.get_user_subscription", return_value=fake_sub):
            with patch("kilas.bot.scheduler.get_user_style", return_value="standar"):
                with patch("kilas.bot.scheduler.get_news_by_genre", return_value=fake_items):
                    with patch("kilas.bot.scheduler.get_cached_summary", return_value="• Poin satelit."):
                        _run(send_daily_digest(user_id, bot=mock_bot))

        mock_bot.send_message.assert_called_once()
        sent_kwargs = mock_bot.send_message.call_args.kwargs
        self.assertEqual(sent_kwargs["chat_id"], user_id)
        self.assertIn("Peluncuran Satelit Baru", sent_kwargs["text"])
        self.assertIn("• Poin satelit.", sent_kwargs["text"])

    def test_send_daily_digest_handles_forbidden_by_deleting_subscription(self):
        """Jika bot diblokir user (Forbidden), langganan dan job otomatis dihapus."""
        user_id = 888
        fake_sub = {"telegram_id": user_id, "genre": "genre_teknologi", "send_time": "07:00"}
        fake_items = [
            NewsItem(
                title="Judul Berita",
                source="Detik",
                published=datetime(2026, 11, 8, tzinfo=timezone.utc),
                link="https://example.com/berita",
                description="Deskripsi",
            )
        ]

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(side_effect=Forbidden("Forbidden: bot was blocked by the user"))

        with patch("kilas.bot.scheduler.get_user_subscription", return_value=fake_sub):
            with patch("kilas.bot.scheduler.get_user_style", return_value="standar"):
                with patch("kilas.bot.scheduler.get_news_by_genre", return_value=fake_items):
                    with patch("kilas.bot.scheduler.get_cached_summary", return_value="• Poin."):
                        with patch("kilas.bot.scheduler.delete_user_subscription") as mock_delete_sub:
                            with patch("kilas.bot.scheduler.remove_user_digest") as mock_remove_job:
                                _run(send_daily_digest(user_id, bot=mock_bot))

        mock_delete_sub.assert_called_once_with(user_id)
        mock_remove_job.assert_called_once_with(user_id)


if __name__ == "__main__":
    unittest.main()

