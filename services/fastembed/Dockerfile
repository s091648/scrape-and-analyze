# --- Stage 1: Build & preload models ---
FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/app/.fastembed_cache

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /usr/local/bin/uv

RUN uv venv .venv && \
    uv pip install fastapi "uvicorn[standard]" "fastembed>=0.3"

ARG EMBED_SPARSE_MODEL=prithivida/Splade_PP_en_v1
ARG EMBED_DENSE_MODEL=

RUN set -eu; \
    cache="$FASTEMBED_CACHE_PATH"; \
    mkdir -p "$cache"; \
    if [ -n "$EMBED_SPARSE_MODEL" ]; then \
        echo "Downloading sparse model: $EMBED_SPARSE_MODEL"; \
        /app/.venv/bin/python -c "from fastembed import SparseTextEmbedding; SparseTextEmbedding('$EMBED_SPARSE_MODEL', cache_dir='$cache')"; \
    fi; \
    if [ -n "$EMBED_DENSE_MODEL" ]; then \
        echo "Downloading dense model: $EMBED_DENSE_MODEL"; \
        /app/.venv/bin/python -c "from fastembed import TextEmbedding; TextEmbedding('$EMBED_DENSE_MODEL', cache_dir='$cache')"; \
    fi

# --- Stage 2: Runtime ---
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/app/.fastembed_cache \
    PATH=/app/.venv/bin:$PATH \
    OMP_NUM_THREADS=1 \
    MALLOC_ARENA_MAX=2

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/.fastembed_cache /app/.fastembed_cache

COPY main.py .
COPY config.py .
COPY observability.py .
COPY routers/ ./routers/
COPY services/ ./services/

RUN addgroup --system appuser && adduser --system --group appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# 單一 worker — ONNX 模型常駐記憶體，多 worker 會讓每個 worker 各自載入一份
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
