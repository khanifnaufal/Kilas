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

---

## 💡 Fitur Utama

- **/start**: Pilih dari 5 genre berita terpopuler (Teknologi, Ekonomi, Olahraga, Politik, Hiburan).
- **/gaya**: Pilih preferensi gaya ringkasan kamu:
  - **⚡ Singkat**: 1 kalimat padat dan informatif.
  - **📌 Standar**: 3 poin penting (default).
  - **📖 Detail**: 1 paragraf pendek komprehensif.
- **🎨 Ganti Gaya Interaktif**: Tombol `[🎨 Ganti gaya]` langsung pada pesan berita untuk meringkas ulang artikel dengan gaya lain.
- **⚡ SQLite Caching**: Ringkasan yang sudah pernah di-generate disimpan ke SQLite. Artikel dan gaya yang sama langsung dimuat instan tanpa memanggil ulang LLM.

---

## ⚙️ Variabel Environment

| Variabel | Wajib | Default | Keterangan |
|----------|-------|---------|-----------|
| `TELEGRAM_TOKEN` | ✅ | — | Token bot Telegram dari @BotFather |
| `LLM_PROVIDER` | — | `groq` | Provider AI: `groq`, `gemini`, `claude` |
| `LLM_API_KEY` | ✅ | — | API key untuk provider yang dipilih |
| `DATABASE_PATH` | — | `kilas.db` | File database SQLite lokal |
| `GROQ_MODEL` | — | `llama-3.1-8b-instant` | Model Groq (auto-fallback aktif) |
| `GEMINI_MODEL` | — | `gemini-1.5-flash` | Model Gemini |
| `CLAUDE_MODEL` | — | `claude-3-haiku-20240307` | Model Claude |
| `LLM_TIMEOUT` | — | `30` | Batas waktu respon LLM (detik) |

---

## 📂 Struktur Folder

```
Kilas/
├── kilas/
│   └── bot/
│       ├── main.py         # Entry point — inisialisasi DB & jalankan bot
│       ├── config.py       # Load & validasi .env
│       ├── db.py           # SQLite: users, subscriptions, summaries_cache
│       ├── feeds.py        # Mapping sumber RSS per genre
│       ├── rss.py          # Fetch & parse feed RSS secara async
│       ├── extractor.py    # Ekstraksi full-text artikel via trafilatura
│       ├── summarizer.py   # LLM summarizer (3 gaya: Singkat, Standar, Detail)
│       ├── handlers.py     # Command & callback handler Telegram
│       └── keyboards.py    # Definisi InlineKeyboard
├── tests/
│   ├── fixtures/           # Fixture data feed XML untuk unit test
│   ├── test_rss.py         # Unit test modul RSS
│   ├── test_extractor.py   # Unit test modul extractor
│   ├── test_summarizer.py  # Unit test modul summarizer (3 gaya & auto-discovery)
│   └── test_db.py          # Unit test SQLite cache & preferensi user
├── .env.example            # Template env — salin ke .env
├── requirements.txt        # Dependensi terkunci (pin versi)
├── .gitignore
└── README.md
```

---

## 📜 Lisensi

MIT License
