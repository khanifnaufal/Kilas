# 📰 Kilas — Bot Ringkasan Berita Indonesia

> Bot Telegram yang merangkum berita terkini dari berbagai sumber RSS Indonesia secara otomatis menggunakan AI.

---

## 🚀 Setup & Menjalankan Bot (Fase 1)

### 1. Prasyarat
- Python **3.11+**
- Token bot Telegram dari [@BotFather](https://t.me/BotFather)

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

Buka `.env` dan isi nilai berikut:

```env
TELEGRAM_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ  # dari @BotFather
LLM_PROVIDER=groq                                        # groq | gemini | claude
LLM_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx                     # API key provider pilihan
```

### 6. Jalankan bot
```bash
python -m kilas.bot.main
```

Output normal:
```
2026-11-07 07:00:00 | INFO     | kilas.bot.main — 🚀 Kilas Bot sedang dimulai...
2026-11-07 07:00:01 | INFO     | kilas.bot.main — ✅ Bot siap. Tekan Ctrl+C untuk berhenti.
```

### 7. Uji di Telegram
1. Buka bot kamu di Telegram
2. Kirim `/start`
3. Tekan salah satu tombol genre — bot akan membalas konfirmasi genre yang dipilih

---

## ⚙️ Variabel Environment

| Variabel | Wajib | Default | Keterangan |
|----------|-------|---------|-----------|
| `TELEGRAM_TOKEN` | ✅ | — | Token dari @BotFather |
| `LLM_PROVIDER` | — | `groq` | Provider AI: `groq`, `gemini`, `claude` |
| `LLM_API_KEY` | — | — | API key provider yang dipilih |

---

## 📂 Struktur Folder

```
Kilas/
├── kilas/
│   └── bot/
│       ├── main.py         # Entry point — jalankan di sini
│       ├── config.py       # Load & validasi .env
│       ├── handlers.py     # Handler /start & callback genre
│       └── keyboards.py    # Definisi InlineKeyboard
├── tests/
├── .env.example            # Template env — salin ke .env
├── requirements.txt        # Dependensi (pin versi)
├── .gitignore
└── README.md
```

---

## 🛠️ Stack

| Library | Versi | Kegunaan |
|---------|-------|---------|
| `python-telegram-bot` | 21.6 | Framework bot async |
| `python-dotenv` | 1.0.1 | Load variabel dari `.env` |

---

## 📜 Lisensi

MIT License
