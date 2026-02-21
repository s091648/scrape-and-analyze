# backend/Dockerfile
FROM python:3.11-slim
WORKDIR /app

# Install backend dependencies only
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy source model definitions (backend queries existing tables via SQLAlchemy)
COPY src/ ./src/
COPY backend/ ./backend/

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
