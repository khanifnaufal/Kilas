"""
tests/test_summarizer.py — Unit test untuk kilas.bot.summarizer

Menguji abstraksi LLM summarizer dengan mock provider:
- Validasi 3 prompt gaya: Singkat (1 kalimat), Standar (3 poin), Detail (1 paragraf).
- Pemotongan panjang input aman.
- GroqSummarizer, GeminiSummarizer, ClaudeSummarizer (sukses & error handling).
- Auto-discovery model Groq saat terjadi error 404 / model_not_found.
- Factory function get_summarizer dan validasi API key.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from kilas.bot.summarizer import (
    MAX_LLM_INPUT_CHARS,
    PROMPT_DETAIL,
    PROMPT_SINGKAT,
    PROMPT_STANDAR,
    ClaudeSummarizer,
    GeminiSummarizer,
    GroqSummarizer,
    SummarizerError,
    get_summarizer,
    prepare_prompt,
)


def _run(coro):
    return asyncio.run(coro)


class TestPromptPreparation(unittest.TestCase):
    def test_prompt_rules_singkat(self):
        """Prompt Singkat harus mewajibkan 1 kalimat padat."""
        prompt = PROMPT_SINGKAT.lower()
        self.assertIn("1 (satu) kalimat", prompt)
        self.assertIn("bahasa indonesia", prompt)
        self.assertIn("fakta", prompt)

    def test_prompt_rules_standar(self):
        """Prompt Standar harus mewajibkan 3 poin ringkas."""
        prompt = PROMPT_STANDAR.lower()
        self.assertIn("3 (tiga) poin", prompt)
        self.assertIn("bahasa indonesia", prompt)
        self.assertIn("80 kata", prompt)
        self.assertIn("bullet", prompt)

    def test_prompt_rules_detail(self):
        """Prompt Detail harus mewajibkan 1 paragraf pendek komprehensif."""
        prompt = PROMPT_DETAIL.lower()
        self.assertIn("1 (satu) paragraf", prompt)
        self.assertIn("bahasa indonesia", prompt)
        self.assertIn("120 kata", prompt)

    def test_prepare_prompt_formats_correctly(self):
        """prepare_prompt menyisipkan judul dan teks dengan benar."""
        title = "Inovasi Baru AI di Indonesia"
        text = "Kementerian Kominfo meresmikan program akselerasi AI nasional."
        formatted = prepare_prompt(title, text, style="standar")
        self.assertIn(title, formatted)
        self.assertIn(text, formatted)

    def test_prepare_prompt_selects_style(self):
        """prepare_prompt memilih template sesuai style yang diminta."""
        title = "Judul"
        text = "Isi"
        prompt_s = prepare_prompt(title, text, style="singkat")
        self.assertIn("1 (satu) kalimat", prompt_s.lower())

        prompt_d = prepare_prompt(title, text, style="detail")
        self.assertIn("1 (satu) paragraf", prompt_d.lower())

    def test_prepare_prompt_truncates_oversized_text(self):
        """Teks yang terlalu panjang dipotong ke MAX_LLM_INPUT_CHARS."""
        title = "Judul Berita"
        huge_text = "X" * (MAX_LLM_INPUT_CHARS + 1000)
        formatted = prepare_prompt(title, huge_text)
        self.assertGreater(len(huge_text), MAX_LLM_INPUT_CHARS)
        self.assertIn("…", formatted)
        self.assertNotIn(huge_text, formatted)


class TestGroqSummarizer(unittest.TestCase):
    def test_empty_text_raises_summarizer_error(self):
        summarizer = GroqSummarizer(api_key="mock_key")
        with self.assertRaises(SummarizerError):
            _run(summarizer.summarize("Judul", ""))

    def test_groq_success(self):
        summarizer = GroqSummarizer(api_key="mock_key")
        fake_response = MagicMock()
        fake_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="• Poin satu.\n• Poin dua.\n• Poin tiga."
                )
            )
        ]

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=fake_response)

        with patch("groq.AsyncGroq", return_value=mock_client):
            result = _run(
                summarizer.summarize(
                    "Judul", "Isi teks berita yang memadai.", style="standar"
                )
            )

        self.assertIn("• Poin satu.", result)
        self.assertIn("• Poin tiga.", result)

    def test_groq_api_error_raises_summarizer_error(self):
        summarizer = GroqSummarizer(api_key="mock_key")
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("Rate limit exceeded")
        )

        with patch("groq.AsyncGroq", return_value=mock_client):
            with self.assertRaises(SummarizerError):
                _run(summarizer.summarize("Judul", "Isi teks"))

    def test_groq_404_auto_discovers_active_model(self):
        """Jika model default 404, summarizer mengambil daftar model aktif dan mencoba ulang."""
        summarizer = GroqSummarizer(api_key="mock_key", model="deprecated-model")

        mock_model_item = MagicMock()
        mock_model_item.id = "llama-active-preview"
        mock_page = MagicMock()
        mock_page.data = [mock_model_item]

        fake_success_response = MagicMock()
        fake_success_response.choices = [
            MagicMock(message=MagicMock(content="• Hasil setelah auto-discovery."))
        ]

        mock_client = MagicMock()
        mock_client.models.list = AsyncMock(return_value=mock_page)

        mock_client.chat.completions.create = AsyncMock(
            side_effect=[
                Exception("Error 404: model_not_found"),
                fake_success_response,
            ]
        )

        with patch("groq.AsyncGroq", return_value=mock_client):
            result = _run(
                summarizer.summarize("Judul", "Isi teks berita panjang.")
            )

        self.assertIn("• Hasil setelah auto-discovery.", result)
        self.assertEqual(summarizer.model, "llama-active-preview")


class TestGeminiSummarizer(unittest.TestCase):
    def test_empty_text_raises_summarizer_error(self):
        summarizer = GeminiSummarizer(api_key="mock_key")
        with self.assertRaises(SummarizerError):
            _run(summarizer.summarize("Judul", ""))

    def test_gemini_success(self):
        summarizer = GeminiSummarizer(api_key="mock_key")
        fake_response = MagicMock()
        fake_response.text = "• Ringkasan satu.\n• Ringkasan dua.\n• Ringkasan tiga."

        mock_model = MagicMock()
        mock_model.generate_content.return_value = fake_response

        with patch("google.generativeai.configure"):
            with patch("google.generativeai.GenerativeModel", return_value=mock_model):
                result = _run(
                    summarizer.summarize(
                        "Judul", "Isi artikel ekonomi.", style="standar"
                    )
                )

        self.assertIn("• Ringkasan satu.", result)

    def test_gemini_api_error_raises_summarizer_error(self):
        summarizer = GeminiSummarizer(api_key="mock_key")
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Exception("Quota exceeded")

        with patch("google.generativeai.configure"):
            with patch("google.generativeai.GenerativeModel", return_value=mock_model):
                with self.assertRaises(SummarizerError):
                    _run(summarizer.summarize("Judul", "Isi teks"))


class TestClaudeSummarizer(unittest.TestCase):
    def test_empty_text_raises_summarizer_error(self):
        summarizer = ClaudeSummarizer(api_key="mock_key")
        with self.assertRaises(SummarizerError):
            _run(summarizer.summarize("Judul", ""))

    def test_claude_success(self):
        summarizer = ClaudeSummarizer(api_key="mock_key")
        fake_block = MagicMock(text="• Poin A.\n• Poin B.\n• Poin C.")
        fake_response = MagicMock(content=[fake_block])

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=fake_response)

        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            result = _run(
                summarizer.summarize(
                    "Judul", "Isi berita hiburan.", style="standar"
                )
            )

        self.assertIn("• Poin A.", result)

    def test_claude_api_error_raises_summarizer_error(self):
        summarizer = ClaudeSummarizer(api_key="mock_key")
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("Overloaded"))

        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            with self.assertRaises(SummarizerError):
                _run(summarizer.summarize("Judul", "Isi teks"))


class TestGetSummarizerFactory(unittest.TestCase):
    def test_factory_returns_correct_instance(self):
        groq_s = get_summarizer(provider="groq", api_key="dummy_key")
        self.assertIsInstance(groq_s, GroqSummarizer)

        gemini_s = get_summarizer(provider="gemini", api_key="dummy_key")
        self.assertIsInstance(gemini_s, GeminiSummarizer)

        claude_s = get_summarizer(provider="claude", api_key="dummy_key")
        self.assertIsInstance(claude_s, ClaudeSummarizer)

    def test_missing_api_key_raises_value_error(self):
        with self.assertRaises(ValueError):
            get_summarizer(provider="groq", api_key="")

    def test_invalid_provider_raises_value_error(self):
        with self.assertRaises(ValueError):
            get_summarizer(provider="unsupported_provider", api_key="key")


if __name__ == "__main__":
    unittest.main()
