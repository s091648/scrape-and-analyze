# --- 階段 1：構建階段 ---
FROM python:3.11-slim as builder

# 設置環境變數，防止 Python 產生 pyc 檔並確保輸出即時顯示
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 安裝構建依賴（如果需要編譯某些套件）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 先複製並安裝依賴項，利用 Docker 層緩存
# 同時安裝根目錄和 backend 的依賴，因為 backend 會用到 src 中的模型
COPY requirements.txt ./requirements_root.txt
COPY backend/requirements.txt ./requirements_backend.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements_root.txt && \
    pip install --no-cache-dir -r requirements_backend.txt

# --- 階段 2：執行階段 ---
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000

WORKDIR /app

# 從構建階段複製已安裝的套件
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# 複製應用程式代碼
# backend 需要 src (models, database 等) 才能運作
COPY src/ ./src/
COPY backend/ ./backend/
COPY providers.toml ./providers.toml

# 建立並切換到非 root 用戶以提高安全性
RUN addgroup --system appuser && adduser --system --group appuser
RUN chown -R appuser:appuser /app
USER appuser

# 暴露端口
EXPOSE 8000

# 啟動命令
# 在生產環境中移除 --reload
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
