FROM python:3.11-slim

WORKDIR /app

# Hindari buffering stdout/stderr agar log langsung tampil di console platform
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install dependencies terlebih dahulu (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Salin kode sumber
COPY . .

# Jalankan bot dalam mode polling
CMD ["python", "-m", "kilas.bot.main"]

