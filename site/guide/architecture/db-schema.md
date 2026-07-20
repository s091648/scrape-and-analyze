---
title: DB Schema
aside: false
---

# DB Schema

資料庫 schema 圖，顯示每張表所屬的 PostgreSQL schema、欄位、以及外鍵關聯（跨 schema 的關聯以紅色標示）。

<DbSchemaViewer />

## 資料生成方式

圖表由 `scripts/generate_db_schema.py` 在 CI 時透過 AST 靜態解析 `models/*.py` 自動產生，**不需要手動維護**，也不需要安裝 `models/` 的執行期依賴（SQLAlchemy 等）— 純粹解析原始碼語法樹，跟 `scripts/generate_uml.py` 解析 `src/` 的方式一樣是靜態分析，不 import 任何程式碼。

執行 `python scripts/generate_db_schema.py` 可在本機重新產生（純 Python 標準函式庫，不需要 `uv sync`）。

Schema 分類對照 `src/modules/` 既有的 DDD bounded context：`core`（`src/shared/domain/entities/` shared kernel）、`collection`（`src/modules/collection/`）、`intelligence`（`src/modules/intelligence/`）、`ai_infra`（跨情境的 LLM/metrics 供應商設定）、`user_prefs`（讀者個人設定）。詳見 [016-db-schema-brushup](/specs/016-db-schema-brushup/spec)。
