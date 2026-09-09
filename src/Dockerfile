FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./

# Which src/ dependency groups this service needs (space-separated).
# Railway auto-injects a same-named service variable into build ARGs — UV_GROUP
# is a Terraform-managed service variable (infra/terraform/github/<service>.tf,
# var.uv_group_<service>), NOT a manual dashboard entry:
#   scrape-and-analyze → (no override; the default below) "scraper llm http-clients"
#   weekly-report      → "llm http-clients"
#   refresh-metrics    → "http-clients metrics"
#   dedup-reconcile    → "http-clients"
#   rag-backfill       → "scraper http-clients"
# NB: the ARG name MUST match the variable name exactly (Railway matches by name).
ARG UV_GROUP="scraper llm http-clients"
RUN set -eu; \
    GROUP_FLAGS=""; \
    for g in $UV_GROUP; do GROUP_FLAGS="$GROUP_FLAGS --group $g"; done; \
    uv sync --frozen $GROUP_FLAGS \
        --group observability \
        --no-group backend \
        --no-group dev

ENV FASTEMBED_CACHE_PATH=/app/.fastembed_cache

ARG RAG_DENSE_PROVIDER=gemini
ARG RAG_DENSE_MODEL=gemini-embedding-001
ARG RAG_SPARSE_PROVIDER=endpoint
ARG RAG_SPARSE_MODEL=prithivida/Splade_PP_en_v1

RUN set -eu; \
    cache="$FASTEMBED_CACHE_PATH"; \
    mkdir -p "$cache"; \
    if [ "$RAG_DENSE_PROVIDER" = "local" ]; then \
        echo "Downloading dense model: $RAG_DENSE_MODEL"; \
        /app/.venv/bin/python -c "from fastembed import TextEmbedding; TextEmbedding('$RAG_DENSE_MODEL', cache_dir='$cache')"; \
    fi; \
    if [ "$RAG_SPARSE_PROVIDER" = "local" ]; then \
        echo "Downloading sparse model: $RAG_SPARSE_MODEL"; \
        /app/.venv/bin/python -c "from fastembed import SparseTextEmbedding; SparseTextEmbedding('$RAG_SPARSE_MODEL', cache_dir='$cache')"; \
    fi

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
