FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY models/ ./models/
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY providers.toml .

CMD ["python", "-m", "src.main"]
