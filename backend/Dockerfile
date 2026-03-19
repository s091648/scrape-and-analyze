# --- Stage 1: Build ---
FROM python:3.11-slim as builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements_root.txt
COPY backend/requirements.txt ./requirements_backend.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements_root.txt && \
    pip install --no-cache-dir -r requirements_backend.txt

# Download MaxMind GeoLite2-City database
ARG MAXMIND_LICENSE_KEY
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /app/data && \
    curl -sSL \
      "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key=${MAXMIND_LICENSE_KEY}&suffix=tar.gz" \
    | tar -xz --wildcards --strip-components=1 -C /app/data/ '*.mmdb'

# --- Stage 2: Run ---
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

COPY models/ ./models/
COPY backend/ ./backend/
COPY providers.toml ./providers.toml
COPY --from=builder /app/data/ ./data/

RUN addgroup --system appuser && adduser --system --group appuser
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
