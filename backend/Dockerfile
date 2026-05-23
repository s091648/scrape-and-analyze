# --- Stage 1: Build ---
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Download MaxMind GeoLite2-City database
ARG MAXMIND_LICENSE_KEY
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /app/data && \
    curl -sSL \
      "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key=${MAXMIND_LICENSE_KEY}&suffix=tar.gz" \
    | tar -xz --wildcards --strip-components=1 -C /app/data/ '*.mmdb'

COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen \
    --group backend \
    --group observability \
    --no-group scraper \
    --no-group dev

# --- Stage 2: Run ---
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY models/ ./models/
COPY shared/ ./shared/
COPY backend/ ./backend/
COPY src/ ./src/
COPY --from=builder /app/data/ ./data/

RUN addgroup --system appuser && adduser --system --group appuser
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["sh", "-c", ".venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
