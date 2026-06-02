# === Stage 1: Build dependencies ===
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# === Stage 2: Runtime ===
FROM python:3.11-slim

# ffmpeg нужен для обработки аудио, node — для code execution sandbox
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 ffmpeg curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g typescript ts-node && \
    rm -rf /var/lib/apt/lists/*

# Безопасность: не-root пользователь
RUN adduser --disabled-password --no-create-home --gecos "" appuser

WORKDIR /app

ENV PYTHONPATH=/app

# Копируем установленные пакеты из builder
COPY --from=builder /install /usr/local

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY seed_fullstack.py seed_shop_items.py _parsed_blocks.json ./

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -sf http://localhost:8000/api/health || exit 1

CMD ["sh", "-c", "alembic upgrade head && exec su -s /bin/sh appuser -c 'uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WORKERS:-1}'"]
