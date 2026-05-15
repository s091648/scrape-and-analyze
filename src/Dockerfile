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

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY models/ ./models/
COPY shared/ ./shared/
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY providers.toml .

CMD ["/app/.venv/bin/python", "-m", "src.entrypoints.cli.main"]
