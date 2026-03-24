FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen \
    --group scraper \
    --group observability \
    --no-group backend \
    --no-group dev

COPY models/ ./models/
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY providers.toml .

CMD [".venv/bin/python", "-m", "src.main"]
