# 📰 Kilas — Bot Ringkasan Berita Indonesia

> Bot Telegram yang merangkum berita terkini dari berbagai sumber RSS Indonesia secara otomatis menggunakan AI.

---

## 🚀 Setup & Menjalankan Bot

### 1. Prasyarat
- Python **3.11+**
- Token bot Telegram dari [@BotFather](https://t.me/BotFather)
- API Key LLM: [Groq](https://console.groq.com) (gratis, sangat cepat) / [Gemini](https://aistudio.google.com) / [Anthropic Claude](https://console.anthropic.com)

### 2. Clone repo & masuk ke folder
```bash
git clone <repo-url>
cd Kilas
```

### 3. Buat dan aktifkan virtual environment
```bash
# Buat venv
python -m venv .venv

# Aktifkan — Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Aktifkan — Windows (CMD)
.venv\Scripts\activate.bat

# Aktifkan — Linux / macOS
source .venv/bin/activate
```

### 4. Install dependensi
```bash
pip install -r requirements.txt
```

### 5. Konfigurasi environment
```bash
# Salin template
cp .env.example .env   # Linux/macOS
# atau
copy .env.example .env  # Windows CMD
```

Buka `.env` dan lengkapi nilainya:

```env
TELEGRAM_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ  # dari @BotFather
LLM_PROVIDER=groq                                        # groq | gemini | claude
LLM_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx                     # API key provider pilihan
```

### 6. Jalankan Unit Test
```bash
pytest -v
# atau tanpa pytest:
python -m unittest discover tests -v
```

### 7. Jalankan bot
```bash
python -m kilas.bot.main
```

Output normal:
```
2026-11-07 10:00:00 | INFO     | kilas.bot.main — 🚀 Kilas Bot sedang dimulai...
2026-11-07 10:00:01 | INFO     | kilas.bot.main — ✅ Bot siap. Tekan Ctrl+C untuk berhenti.
```

---

## ⚙️ Variabel Environment

| Variabel | Wajib | Default | Keterangan |
|----------|-------|---------|-----------|
| `TELEGRAM_TOKEN` | ✅ | — | Token bot Telegram dari @BotFather |
| `LLM_PROVIDER` | — | `groq` | Provider AI: `groq`, `gemini`, `claude` |
| `LLM_API_KEY` | ✅ | — | API key untuk provider yang dipilih |
| `GROQ_MODEL` | — | `llama-3.1-8b-instant` | Model Groq |
| `GEMINI_MODEL` | — | `gemini-1.5-flash` | Model Gemini |
| `CLAUDE_MODEL` | — | `claude-3-haiku-20240307` | Model Claude |
| `LLM_TIMEOUT` | — | `30` | Batas waktu respon LLM (detik) |

---

## 📂 Struktur Folder

```
Kilas/
├── kilas/
│   └── bot/
│       ├── main.py         # Entry point — jalankan bot
│       ├── config.py       # Load & validasi .env
│       ├── feeds.py        # Mapping sumber RSS per genre
│       ├── rss.py          # Fetch & parse feed RSS secara async
│       ├── extractor.py    # Ekstraksi full-text artikel via trafilatura
│       ├── summarizer.py   # Abstraksi LLM summarizer (Groq/Gemini/Claude)
│       ├── handlers.py     # Command & callback handler Telegram
│       └── keyboards.py    # Definisi InlineKeyboard
├── tests/
│   ├── fixtures/           # Fixture data feed XML untuk unit test
│   ├── test_rss.py         # Unit test modul RSS
│   ├── test_extractor.py   # Unit test modul extractor
│   └── test_summarizer.py  # Unit test modul summarizer
├── .env.example            # Template env — salin ke .env
├── requirements.txt        # Dependensi terkunci (pin versi)
├── .gitignore
└── README.md
```

---

## 🛠️ Stack

| Library | Versi | Kegunaan |
|---------|-------|---------|
| `python-telegram-bot` | 21.6 | Framework bot Telegram async |
| `feedparser` | 6.0.11 | Parsing RSS feed |
| `trafilatura` | 1.12.1 | Ekstraksi teks artikel web bersih |
| `groq` | 0.9.0 | Client Groq API (default LLM) |
| `google-generativeai` | 0.7.2 | Client Google Gemini API |
| `anthropic` | 0.34.2 | Client Anthropic Claude API |
| `python-dotenv` | 1.0.1 | Load konfigurasi dari `.env` |
| `pytest` | 8.3.3 | Pengujian otomatis / unit test |

---

## 📜 Lisensi

MIT License
