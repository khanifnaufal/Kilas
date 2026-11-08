# 📰 Kilas — Bot Ringkasan Berita Indonesia

> **Kilas** adalah bot Telegram berbasis AI yang mengumpulkan berita terkini dari media terpercaya Indonesia melalui RSS feed dan menyajikannya dalam ringkasan padat, akurat, dan sesuai gaya pilihan pengguna.

---

## 📑 Daftar Isi

- [Fitur Utama](#-fitur-utama)
- [Arsitektur Sistem](#-arsitektur-sistem)
- [Panduan Mendapatkan Token & API Key](#-panduan-mendapatkan-token--api-key)
- [Daftar Environment Variables](#-daftar-environment-variables)
- [Instalasi & Menjalankan Lokal](#-instalasi--menjalankan-lokal)
- [Panduan Deployment](#-panduan-deployment)
  - [Deploy ke Railway](#1-deploy-ke-railway-direkomendasikan)
  - [Deploy ke Render](#2-deploy-ke-render)
  - [Catatan Penting: Persistent Volume SQLite & Mitigasi Sleep Free Tier](#catatan-penting-persistent-volume-sqlite--mitigasi-sleep)
- [Menjalankan Unit Test](#-menjalankan-unit-test)
- [Batasan yang Diketahui (Known Limitations)](#-batasan-yang-diketahui-known-limitations)
- [Tangkapan Layar Demo](#-tangkapan-layar-demo)
- [Checklist Uji Manual End-to-End](#-checklist-uji-manual-end-to-end)

---

## ✨ Fitur Utama

1. **Kompilasi Multi-Sumber Berita**: Mengambil feed RSS secara paralel dan non-blocking dari media nasional (Antara, CNN Indonesia, Detik, Kompas).
2. **5 Genre Berita**: Teknologi, Ekonomi, Olahraga, Politik, dan Hiburan.
3. **Ekstraksi Full-Text Cerdas**: Mengekstrak isi artikel berita dengan `trafilatura` (disertai fallback otomatis ke deskripsi RSS jika artikel terpotong atau gagal diekstrak).
4. **3 Gaya Ringkasan LLM**:
   - ⚡ **Singkat**: 1 kalimat padat dan informatif.
   - 📌 **Standar**: 3 poin utama (default).
   - 📖 **Detail**: 1 paragraf pendek komprehensif.
5. **Multi-Provider AI**: Mendukung **Groq** (sangat cepat & gratis), **Google Gemini**, dan **Anthropic Claude**, lengkap dengan mekanisme *auto-discovery* model fallback.
6. **SQLite Smart Caching**: Ringkasan artikel disimpan di database lokal berdasarkan kombinasi `(URL, Gaya)`, menghemat kuota LLM dan mempercepat respons klik ganda.
7. **Pergantian Gaya Interaktif (`[🎨 Ganti gaya]`)**: Pengguna dapat mengubah gaya ringkasan langsung dari pesan artikel yang sedang dibaca tanpa kembali ke menu utama.
8. **Digest Harian Terjadwal (`/digest`)**: Pengiriman rekap 5 berita teratas setiap hari pada jam pilihan (06:00, 07:00, 08:00, 12:00, 18:00, 20:00 WIB) menggunakan `APScheduler`.
9. **Sliding-Window Rate Limiter**: Membatasi maksimal 10 permintaan per menit per pengguna untuk mencegah spam dan melindungi kuota API.
10. **Resilience & Error Handling Global**: Menangani kegagalan parsing RSS (bozo feed), pemblokiran bot oleh user (otomatis menghapus langganan agar tidak memory-leak), dan sanitasi Markdown Telegram.

---

## 🏗 Arsitektur Sistem

Berikut diagram alur data sederhana:

```text
+-------------------+
|  Pengguna Telegram|
+---------+---------+
          |  Update (Command / Inline Button)
          v
+-------------------+      Ekstraksi teks
|     Bot Kilas     +----------------------------+
|  (Python-Telegram)|                            |
+----+----+----+----+                            v
     |    |    |                          +---------------+
     |    |    |  Cek Cache / Simpan      |  Trafilatura  |
     |    |    +------------------------> |  (Full-Text)  |
     |    |                               +-------+-------+
     |    |                                       |
     |    |  Jadwal Pengiriman                    | Konten artikel
     |    |                                       v
     |    +-----------------> +----------------+  |
     |                        |  APScheduler   |  |
     |                        | (Asia/Jakarta) |  |
     |                        +----------------+  |
     v                                            v
+----------------+                       +-----------------+
|  RSS Aggregator|                       |  LLM Summarizer |
| (Feedparser)   |                       | (Groq / Gemini  |
+-------+--------+                       |   / Claude)     |
        |                                +--------+--------+
        v                                         |
+------------------------------+                  v
| Antara, CNN, Detik, Kompas   |         +-----------------+
+------------------------------+         |  SQLite Cache   |
                                         |    (kilas.db)   |
                                         +-----------------+
```

---

## 🔑 Panduan Mendapatkan Token & API Key

### 1. Token Telegram Bot (@BotFather)
1. Buka aplikasi Telegram dan cari akun **[@BotFather](https://t.me/BotFather)** (pastikan ada centang biru).
2. Kirim perintah `/newbot`.
3. Masukkan nama tampilan bot Anda (contoh: `Kilas Berita Bot`).
4. Masukkan username bot (harus berakhiran `bot`, contoh: `kilas_berita_ai_bot`).
5. Salin token API yang diberikan (format: `1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ`).

### 2. API Key LLM (Pilih Salah Satu)

- **Groq (Sangat Direkomendasikan - Gratis & Cepat)**:
  1. Kunjungi [Groq Console](https://console.groq.com/).
  2. Buat akun / Login dengan GitHub atau Google.
  3. Masuk ke menu **API Keys** -> klik **Create API Key**.
  4. Salin key yang berawalan `gsk_...`.
- **Google Gemini**:
  1. Kunjungi [Google AI Studio](https://aistudio.google.com/).
  2. Klik **Get API key** -> buat key baru di project Google Cloud Anda.
- **Anthropic Claude**:
  1. Kunjungi [Anthropic Console](https://console.anthropic.com/).
  2. Buka menu API Keys dan buat key baru (`sk-ant-...`).

---

## ⚙️ Daftar Environment Variables

| Variabel | Wajib | Default | Deskripsi |
|---|:---:|:---:|---|
| `TELEGRAM_TOKEN` | **Ya** | — | Token API bot Telegram dari @BotFather |
| `LLM_PROVIDER` | Tidak | `groq` | Provider AI yang digunakan: `groq`, `gemini`, atau `claude` |
| `LLM_API_KEY` | **Ya** | — | API key untuk provider yang dipilih |
| `DATABASE_PATH` | Tidak | `kilas.db` | Lokasi file database SQLite lokal |
| `LOG_LEVEL` | Tidak | `INFO` | Tingkat log: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `GROQ_MODEL` | Tidak | `llama-3.1-8b-instant` | Model Groq yang dipakai (otomatis fallback jika 404) |
| `GEMINI_MODEL` | Tidak | `gemini-1.5-flash` | Model Google Gemini |
| `CLAUDE_MODEL` | Tidak | `claude-3-haiku-20240307` | Model Anthropic Claude |
| `LLM_TIMEOUT` | Tidak | `30` | Batas waktu respon LLM dalam detik |

---

## 💻 Instalasi & Menjalankan Lokal

### 1. Clone Repositori
```bash
git clone https://github.com/username/Kilas.git
cd Kilas
```

### 2. Buat Virtual Environment & Install Dependensi
```bash
# Buat venv
python -m venv .venv

# Aktifkan di Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Aktifkan di Linux / macOS
source .venv/bin/activate

# Install dependensi yang dipin
pip install -r requirements.txt
```

### 3. Konfigurasi `.env`
Salin template konfigurasi:
```bash
cp .env.example .env
```
Buka `.env` lalu masukkan `TELEGRAM_TOKEN` dan `LLM_API_KEY` Anda.

### 4. Jalankan Bot
```bash
python -m kilas.bot.main
```

---

## ☁️ Panduan Deployment

Bot ini menggunakan **polling mode**, sehingga tidak membutuhkan domain publik, IP statis, sertifikat SSL, atau webhook HTTPS. Bot dapat langsung dijalankan di cloud container sebagai **Worker Service**.

### 1. Deploy ke Railway (Direkomendasikan)

Railway menyediakan runtime worker yang andal dan mendukung persistent volume:

1. **Fork / Push** repo ini ke akun GitHub Anda.
2. Masuk ke [Railway.app](https://railway.app/) dan buat **New Project** -> **Deploy from GitHub repo**.
3. Pilih repo `Kilas`.
4. Buka tab **Variables** di Railway Dashboard dan tambahkan environment variable:
   - `TELEGRAM_TOKEN`: `<token bot anda>`
   - `LLM_PROVIDER`: `groq`
   - `LLM_API_KEY`: `<api key anda>`
   - `DATABASE_PATH`: `/data/kilas.db` (jika menggunakan persistent volume)
   - `LOG_LEVEL`: `INFO`
5. Railway akan mendeteksi `Procfile` (`worker: python -m kilas.bot.main`) atau `railway.json` secara otomatis dan menjalankan bot.

### 2. Deploy ke Render

Render menyediakan opsi **Background Worker** atau **Web Service**:

1. Buat akun di [Render.com](https://render.com/).
2. Buat service baru -> pilih **Background Worker** (atau **Web Service** jika menggunakan free tier).
3. Sambungkan ke repositori GitHub Anda.
4. Set konfigurasi:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python -m kilas.bot.main`
5. Masukkan variabel environment di menu **Environment**:
   - `TELEGRAM_TOKEN`
   - `LLM_PROVIDER`
   - `LLM_API_KEY`
   - `LOG_LEVEL` = `INFO`

---

### Catatan Penting: Persistent Volume SQLite & Mitigasi Sleep

#### 1. Persistensi Database SQLite
- File SQLite (`kilas.db`) menyimpan preferensi user (`/gaya`), jadwal langganan (`/digest`), dan cache ringkasan berita.
- **Konsekuensi Tanpa Persistent Volume**:
  Pada free tier standar (seperti Render Free atau Railway Ephemeral Disk), setiap kali aplikasi melakukan redeploy atau restart kontainer, file disk lokal akan direset. Akibatnya:
  - Cache ringkasan akan kosong kembali (LLM akan dipanggil ulang saat artikel dibaca).
  - Preferensi gaya user dan langganan digest akan kembali ke nilai default.
- **Solusi**:
  - Di **Railway**: Tambahkan *Volume* pada project settings (mount path `/data`) dan atur `DATABASE_PATH=/data/kilas.db`.
  - Di **Render Paid**: Pasang Disk persistent mount pada service settings.

#### 2. Mitigasi Free Tier Sleep (Spin-Down)
- Pada platform seperti **Render Free Web Service**, instance akan "tertidur" (*spin down*) setelah 15 menit jika tidak menerima traffic HTTP masuk.
- **Mitigasi**:
  1. Gunakan jenis service **Background Worker** (tidak berbasis port HTTP).
  2. Atau jalankan bot pada platform yang tidak memberlakukan sleep pada worker proses aktif (seperti Railway, Fly.io, atau VPS mini).
  3. Jika terpaksa memakai Render Web Service, tambahkan script ping berkala atau scheduler eksternal (misal: Cron-job.org / UptimeKuma) yang memanggil endpoint health check.

---

## 🧪 Menjalankan Unit Test

Untuk menjalankan seluruh test suite:

```bash
# Menggunakan pytest
pytest -v

# Atau menggunakan modul bawaan unittest Python
python -m unittest discover tests -v
```

Cakupan unit test meliputi:
- `test_rss.py`: Pengambilan, parsing, pengurutan waktu, dan limit 5 artikel RSS lokal tanpa hit network eksternal.
- `test_extractor.py`: Ekstraksi konten artikel via Trafilatura beserta fallback ke ringkasan RSS.
- `test_summarizer.py`: Pembentukan prompt 3 gaya dan validasi provider LLM.
- `test_db.py`: Inisialisasi SQLite, CRUD preferensi gaya user, langganan digest, dan caching.
- `test_ratelimit.py`: Sliding window rate limiter (10 req/menit) dan isolasi antar pengguna.
- `test_scheduler.py`: Parsing format waktu, pendaftaran job APScheduler, dan penanganan auto-unsubscribe saat bot diblokir user.

---

## ⚠️ Batasan yang Diketahui (Known Limitations)

1. **Format Feed RSS Pihak Ketiga**: Beberapa portal media sesekali menyajikan tag XML yang tidak standar (mismatched tag). Bot telah dilengkapi *bozo handling* sehingga kegagalan satu feed tidak merusak feed dari portal lain.
2. **SQLite Single-Instance**: SQLite beroperasi berbasis file lokal, sehingga bot dirancang untuk berjalan sebagai *single worker instance*. Jangan menjalankan 2 instance bot secara bersamaan dengan token yang sama (akan menyebabkan Telegram Polling Conflict 409).
3. **Model Availability LLM**: Provider gratis seperti Groq terkadang mempensiunkan checkpoint model tertentu. Bot telah dibekali mekanisme *auto-discovery* yang memeriksa model aktif yang tersedia di akun pengguna secara otomatis jika terjadi error `model_not_found (404)`.
4. **Batas Payload Callback Telegram**: Payload `callback_data` dibatasi maksimal 64 byte oleh Telegram API. Bot Kilas mengatasi ini dengan memetakan URL panjang ke short hash ID in-memory dan database.

---

## 📸 Tangkapan Layar Demo

<!-- TODO: Tambahkan screenshot demo tampilan bot di bawah ini -->
<div align="center">
  <p><i>Menu Utama Pemilihan Genre Berita</i></p>
  <img src="https://via.placeholder.com/600x400.png?text=Demo+Kilas+Bot+Menu+Utama" alt="Menu Utama Kilas Bot" width="500"/>

  <p><i>Hasil Ringkasan Berita dengan Tombol Ganti Gaya & Baca Sumber</i></p>
  <img src="https://via.placeholder.com/600x400.png?text=Demo+Ringkasan+Berita+AI" alt="Ringkasan Berita Kilas Bot" width="500"/>
</div>

---

## ✅ Checklist Uji Manual End-to-End

Gunakan checklist ini untuk menguji seluruh fungsionalitas bot secara menyeluruh dari aplikasi Telegram:

- [ ] **1. Alur `/start` & Pilihan Genre**:
  - Kirim perintah `/start` ke bot.
  - Bot membalas dengan pesan sambutan dan 5 tombol genre (Teknologi, Ekonomi, Olahraga, Politik, Hiburan).
  - Klik salah satu genre (misal: **Teknologi**).
  - Bot menampilkan daftar 5 berita teratas lengkap dengan nama sumber media.

- [ ] **2. Alur Ringkasan Berita**:
  - Klik salah satu tombol judul berita.
  - Pesan berubah menjadi *"Sedang membaca & merangkum berita..."*.
  - Dalam beberapa detik, pesan terupdate menampilkan judul, sumber media, dan ringkasan 3 poin (gaya Standar).
  - Terdapat tombol `[📖 Baca sumber]` dan `[🎨 Ganti gaya]` serta `[🔙 Kembali]`.
  - Klik `[📖 Baca sumber]` dan pastikan link membuka URL berita asli di browser.

- [ ] **3. Alur Pergantian Gaya (`/gaya` & Tombol Interaktif)**:
  - Kirim perintah `/gaya`.
  - Pilih gaya **⚡ Singkat (1 kalimat)**.
  - Buka kembali salah satu berita -> verifikasi ringkasan yang dihasilkan kini berupa 1 kalimat padat.
  - Klik tombol `[🎨 Ganti gaya]` di bawah ringkasan tersebut -> pilih **📖 Detail**.
  - Verifikasi pesan artikel langsung diperbarui menjadi gaya ringkasan 1 paragraf detail tanpa harus kembali ke menu utama.

- [ ] **4. Uji Cache SQLite**:
  - Klik kembali artikel yang sama dengan gaya yang sama.
  - Respon muncul seketika tanpa jeda pemanggilan LLM.
  - Log server menampilkan status: `Cache HIT [url, style]`.

- [ ] **5. Alur Pengaturan Digest Harian (`/digest`)**:
  - Kirim perintah `/digest`.
  - Pilih genre langganan (misal: **Ekonomi**).
  - Pilih jam pengiriman (misal: **07:00**).
  - Bot mengonfirmasi jadwal langganan aktif.
  - Kirim kembali `/digest` dan klik **❌ Matikan Digest** -> pastikan bot mengonfirmasi langganan dinonaktifkan.

- [ ] **6. Uji Sliding-Window Rate Limiter**:
  - Klik tombol ringkasan berita secara cepat berturut-turut lebih dari 10 kali dalam 1 menit.
  - Pada permintaan ke-11, bot menolak dengan pesan ramah peringatan batas kuota dan meminta menunggu beberapa saat.

- [ ] **7. Uji Navigasi & Error Handling**:
  - Klik tombol `[🔙 Kembali]` dari daftar berita dan dari tampilan artikel.
  - Pastikan bot kembali ke menu sebelumnya dengan mulus tanpa menimbulkan error atau unhandled exception pada log.

---

## 📄 Lisensi

Distributed under the MIT License.
