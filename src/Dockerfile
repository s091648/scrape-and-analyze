FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen \
    --group scraper \
    --group observability \
    --no-group backend \
    --no-group dev

# Pre-download fastembed models at build time so the cron job doesn't need to
# re-download on each run. Model names are read from rag_config.toml — no build
# args needed; the same config file drives both build-time prefetch and runtime.
ENV FASTEMBED_CACHE_PATH=/app/.fastembed_cache

RUN mkdir -p /app/src/infrastructure/intelligence/vector_store
COPY src/infrastructure/intelligence/vector_store/rag_config.toml /app/src/infrastructure/intelligence/vector_store/rag_config.toml

RUN /app/.venv/bin/python - <<'EOF'
import tomllib, os
cache = os.environ["FASTEMBED_CACHE_PATH"]
os.makedirs(cache, exist_ok=True)
cfg_path = "/app/src/infrastructure/intelligence/vector_store/rag_config.toml"
with open(cfg_path, "rb") as f:
    cfg = tomllib.load(f)
for role in ("dense", "sparse"):
    section = cfg.get(role, {})
    if section.get("provider_type") == "local" and section.get("model"):
        model = section["model"]
        if role == "dense":
            from fastembed import TextEmbedding
            print(f"Downloading dense model: {model}", flush=True)
            TextEmbedding(model, cache_dir=cache)
        else:
            from fastembed import SparseTextEmbedding
            print(f"Downloading sparse model: {model}", flush=True)
            SparseTextEmbedding(model, cache_dir=cache)
EOF

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    FASTEMBED_CACHE_PATH=/app/.fastembed_cache

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/.fastembed_cache /app/.fastembed_cache

COPY models/ ./models/
COPY shared/ ./shared/
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .

CMD ["/app/.venv/bin/python", "-m", "src.entrypoints.cli.main"]
