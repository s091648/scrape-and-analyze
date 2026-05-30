# GitHub Codespaces 開發環境指南

本專案內建 `.devcontainer` 設定，可在 GitHub Codespaces 上一鍵啟動完整的開發環境，包含 PostgreSQL、FastAPI Backend、Next.js Frontend。

## 架構概覽

Codespaces 啟動後會執行三個 Docker 服務：

| 服務 | Port | 說明 |
|---|---|---|
| `postgres` | 5432 | pgvector/pg15 資料庫 |
| `backend` | 8000 | FastAPI REST API |
| `frontend` | 3000 | Next.js 16 開發伺服器 |

---

## 第一步：建立 Codespace

前往 GitHub repo 頁面，點選 **Code → Codespaces → Create codespace on \[branch\]**。

首次建立需要等待約 **5–10 分鐘**，Codespace 會自動：

1. Build 三個 Docker 服務
2. 執行 `postCreateCommand`（`.devcontainer/init-db.sh`）：
   - 執行 `alembic upgrade head`（資料庫 migrations）
   - 建立預設 admin 帳號（`admin` / `admin`）
   - 執行 `seed_db.py` 填入假資料

---

## 第二步：透過瀏覽器查看

Codespace 會自動 forward ports，可用以下 URL 存取：

| 服務 | URL |
|---|---|
| **Frontend** | `https://<codespace-name>-3000.preview.app.github.dev` |
| **Backend API Docs** | `https://<codespace-name>-8000.preview.app.github.dev/docs` |

你也可以在 VS Code 的 **PORTS** 分頁直接點選連結。

### Port Visibility

Ports 預設為 **private**（需登入 GitHub 才能存取）。若要公開分享給外部人員，在 PORTS 分頁右鍵點選對應 port → **Port Visibility → Public**。

---

## 第三步：登入

前端頁面開啟後，點右上角 **Login** 並使用以下帳號登入：

| 欄位 | 值 |
|---|---|
| Username | `admin` |
| Password | `admin` |

> Google OAuth 登入在 Codespaces 上需額外設定 redirect URI，建議直接使用 username/password 登入。

登入後即可在頁面上選擇 Topic（左上角或側欄），選擇 **Digital Twins** 即可看到 seed 的假資料文章。

---

## 第四步：設定 API Keys（選用）

若要啟用 LLM 分析功能，請透過 **Codespaces Secrets** 設定以下 API keys（Repository Settings → Secrets and variables → Codespaces）：

| Secret | 用途 |
|---|---|
| `GEMINI_API_KEY` | Google Gemini LLM |
| `CLAUDE_API_KEY` | Anthropic Claude LLM |
| `OPENROUTER_API_KEY` | OpenRouter 備用 LLM |
| `GOOGLE_CLIENT_ID` | Google OAuth 登入 |
| `GOOGLE_CLIENT_SECRET` | Google OAuth 登入 |

設定後需要重建 Codespace 才會生效。

---

## 常用指令

Codespace 的 terminal 直接開在 `backend` container 內（`/app` 目錄），可直接執行：

```bash
# 跑 backend unit tests
uv run pytest src/tests/unit/

# 跑 alembic migration
alembic upgrade head

# 手動觸發 scrape（需設定 LLM API key）
uv run python -m src.entrypoints.cli.main
```

Frontend 的 log 可在 VS Code 的 **TERMINAL** 分頁切換到 `frontend` container 查看，或在 **PORTS** 分頁觀察服務狀態。

---

## 注意事項

- **重建 Codespace** 會重跑 `init-db.sh`，但 PostgreSQL volume 會保留資料（`postgres_data` volume）。若要完全重置，需先刪除 volume。
- **停用觀測性功能**：`SENTRY_DSN`、`GRAFANA_LOKI_URL`、`GRAFANA_OTLP_ENDPOINT` 預設留空，功能會自動降級為 no-op。
- **Google OAuth** 在 Codespaces 上需要在 Google Console 新增 Codespace URL 為授權的 redirect URI，否則 Google 登入會失敗。

---

## 常見問題

### 頁面開啟後沒有 Topic 可選、沒有文章

前端無法呼叫 backend API，通常是 Codespace 用舊版設定啟動。解決方法：

**Rebuild Codespace**（Command Palette → `Codespaces: Rebuild Container`）

Rebuild 後 `docker-compose.codespaces.yml` 會以正確的 `$CODESPACE_NAME` 展開環境變數，前端才能正確連到 backend。

### Rebuild 後仍沒有資料

手動重跑 seed（terminal 裡直接執行，不需要 docker 指令）：

```bash
uv run python scripts/seed_db.py
```

確認資料筆數：

```bash
uv run python -c "
from sqlalchemy import create_engine, text
import os
e = create_engine(os.environ['DATABASE_URL'])
with e.connect() as c:
    print('topics:', c.execute(text('SELECT COUNT(*) FROM topics')).scalar())
    print('articles:', c.execute(text('SELECT COUNT(*) FROM articles')).scalar())
    print('translations:', c.execute(text('SELECT COUNT(*) FROM analyses_translation')).scalar())
"
```

預期結果：topics: 1、articles: 5、translations: 5。
