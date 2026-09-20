---
title: DB Schema
aside: false
---

# DB Schema

資料庫 schema 圖，顯示每張表所屬的 PostgreSQL schema、欄位、以及外鍵關聯（跨 schema 的關聯以紅色標示）。

<DbSchemaViewer />

## 資料生成方式

圖表由 `scripts/generate_db_schema.py` 在 CI 時透過 AST 靜態解析 `models/*.py` 自動產生，**不需要手動維護**，也不需要安裝 `models/` 的執行期依賴（SQLAlchemy 等）— 純粹解析原始碼語法樹，跟 `scripts/generate_uml.py` 解析 `src/` 的方式一樣是靜態分析，不 import 任何程式碼。

執行 `python scripts/generate_db_schema.py` 可在本機重新產生（純 Python 標準函式庫，不需要 `uv sync`）；也可透過 `make uml-db-schema` 在 `job_service` container 內執行，跟 CI 走的路徑一致。

圖表中每張表的欄位分成三欄：第一欄是 `PK`（primary key）/ `FK`（foreign key）/ `UQ`（unique constraint，涵蓋 `Column(unique=True)`、`UniqueConstraint(...)`、`Index(..., unique=True)` 三種寫法）/ `IDX`（有索引但不是 unique）標記，第二欄是欄位名稱，第三欄是型別。`UQ` 一定隱含有索引（Postgres 的 unique constraint 底層一定是一個 unique index），所以同一個欄位不會同時顯示 `UQ` 又顯示 `IDX`。外鍵關聯線用標準 ERD crow's-foot 記號標示基數：FK 那一端（多）畫成鳥爪（`crow`，若該欄位可為 `NULL` 則加畫空心圓變成 `ocrow`，代表零或多），被參照的 PK 那一端（一）畫成一槓（`tee`）。關聯線會直接指向目標表格中對應欄位的那一列，而不是只指到表格本身；箭頭若能在目標表中找到對應欄位就會精準對齊，找不到（例如目標表未被此腳本解析，見下方「未被此圖表涵蓋的 schema / table」）時才會退回指向整張表。跨 schema 的關聯另外用紅色標示。

## 解析規則的邊界：為什麼偵測不到 trigger / stored procedure / UDF、也偵測不到用 raw SQL 建立的 unique constraint

`scripts/generate_db_schema.py` 能解析的對象，僅限於 `models/*.py` 裡結構化、有固定形狀的 SQLAlchemy 呼叫——`Column(...)`、`Index(...)`、`UniqueConstraint(...)`、`ForeignKey(...)`——這些在 Python AST 裡都是可預期、有限種寫法的 `ast.Call`，可以用一組固定規則可靠地比對出來。

Trigger、stored procedure（PL/pgSQL function）、以及任何寫在 alembic migration 裡透過 `op.execute("CREATE TRIGGER ...")` / `op.execute("CREATE FUNCTION ...")` / `op.execute("CREATE UNIQUE INDEX ...")` 建立的物件，本質上是**一段純文字的原始 SQL，包在 Python 字串常數裡**——AST 分析只能看到「這裡呼叫了 `op.execute()`，參數是一個字串」，沒辦法（也不應該）進一步解析字串內容代表的 SQL 語法。要偵測這些，唯一的做法是對字串內容做正則表達式或真正的 SQL parser——這是質性上完全不同、也脆弱得多的偵測方式：SQL 語法的寫法變化遠比 SQLAlchemy 那幾種固定 call shape 多（`CREATE OR REPLACE`、跨行字串、不同的大小寫/空白排版、`IF NOT EXISTS` 等等），任何一個 migration 作者用稍微不同的方式排版，都可能讓正則規則悄悄漏抓，而且不會有任何錯誤訊息提示——這比「完全不解析、改用手動維護的表格」更危險，因為它會製造一種「這個圖表應該有涵蓋」的錯誤安全感。

因此這類物件維持用下方「未被此圖表涵蓋的 schema / table」表格**手動**記錄，不嘗試自動偵測——這也是這個表格原本就存在的設計：凡是用 raw SQL 建出來、沒有對應 `models/*.py` 的物件，一律手動補一行說明。

## Schema 分類

Schema 分類對照 `src/modules/` 既有的 DDD bounded context，詳見 [016-db-schema-brushup](/specs/016-db-schema-brushup/spec)：

| Schema | 對應 Bounded Context / 用途 | 建立方式 |
|---|---|---|
| `core` | `src/shared/domain/entities/`（shared kernel：article、topic 等核心實體） | Migration 24（`DbSchema` enum 成員） |
| `collection` | `src/modules/collection/`（爬蟲設定、抓取任務、metric 原始數值） | Migration 24（`DbSchema` enum 成員） |
| `intelligence` | `src/modules/intelligence/`（LLM 分析結果、標籤、週報） | Migration 24（`DbSchema` enum 成員） |
| `ai_infra` | 跨情境的 LLM / metrics 供應商設定 | Migration 24（`DbSchema` enum 成員） |
| `user_prefs` | 讀者個人設定（訂閱、通知、收藏） | Migration 24（`DbSchema` enum 成員） |
| `auth` | 使用者帳號，`app_user` 對此 schema 沒有讀取權限 | Migration 01（raw SQL，早於 `DbSchema` enum，見下方） |
| `vectors` | pgvector 嵌入儲存（RAG 用的文章分塊） | Migration 21（raw SQL，早於 `DbSchema` enum，見下方） |
| `public` | 沒有對應 SQLAlchemy model 的雜項表 | 各自獨立 migration，見下方 |

## 未被此圖表涵蓋的 schema / table

`scripts/generate_db_schema.py` 只解析 `models/*.py` 中的 SQLAlchemy model，以下 schema／table 是直接在 alembic migration 中用 raw SQL 建立、**沒有對應 model**，因此不會出現在上方的圖表中：

| 對象 | 建立於 | 說明 |
|---|---|---|
| `auth` schema | Migration `01_4f2e59c8650f_create_auth_schema` | `CREATE SCHEMA` + `REVOKE ALL ON SCHEMA auth FROM PUBLIC`；schema 本身早於 `DbSchema` enum，但 `auth.users` 有對應的 `models/auth.py::User`，所以該表仍會出現在圖表中 |
| `vectors` schema | Migration `21_add_vectors_schema_and_article_chunks` | `CREATE SCHEMA` + `CREATE EXTENSION vector`；schema 本身早於 `DbSchema` enum |
| `vectors.articles` | Migration `21_add_vectors_schema_and_article_chunks` | Raw SQL 建立的去正規化 parent table（供 search 結果 join 用），沒有對應 model，**不會出現在圖表中** |
| `vectors.article_chunks` | Migration `21_add_vectors_schema_and_article_chunks` | 存放 dense/sparse embedding 的 chunk table；讀寫皆透過 `chatbot-plugin-sdk`／raw SQL 進行（pgvector 的 vector/sparsevec 型別當時缺乏可用的 ORM 支援），沒有對應 model，**不會出現在圖表中**（原本的 `models/article_chunk.py::ArticleChunk` 因欄位定義與實際 table 早已不同步而被移除，見 `023-article-search`） |
| `public.data_migrations` | Migration `18_add_data_migrations_table` | 資料遷移執行紀錄的 ledger 表，沒有對應 model，**不會出現在圖表中** |
| `public.arxiv_metadata` | Migration `22_add_correlation_id_and_rag_providers` | 沒有對應 model，**不會出現在圖表中** |
| `intelligence.search_terms` | Migration `26_add_search_terms_and_pg_trgm` | Autocomplete 的精簡 term 清單（Redis cache-aside fallback 用），讀寫皆透過 `shared/search_index/search_term_repo_impl.py` 的 raw SQL 進行——跟 `vectors.article_chunks` 同樣的理由，沒有對應 model，**不會出現在圖表中**（見 `023-article-search`） |
| `intelligence.tag_article_counts` | Migration `28_add_tag_article_counts_mv` | 預先算好每個 tag 在每個 topic 下的文章數量的 **materialized view**（見 `backend/services/tag_service.py`），不是普通 table，也沒有對應 model——`Base.metadata.create_all()` 的 checkfirst DDL 不適合拿來管理 materialized view 這種 relkind，理由跟 `vectors.article_chunks` 一樣，**不會出現在圖表中** |
| `public.sync_article_has_vectors()`（function）+ `vectors.articles` 上的 `trg_sync_article_has_vectors`（trigger） | Migration `21_add_vectors_schema_and_article_chunks`，schema 修正於 `25_add_article_merge_tombstone`，寫入去重複邏輯修正於 `28_add_tag_article_counts_mv` | 每次 RAG 寫入/刪除 `vectors.articles` 時，同步維護 `core.articles.has_vectors` 這個反正規化旗標。Trigger/function 都是用 `op.execute()` 寫的 raw SQL，AST 分析器只看得到「這裡呼叫了 `op.execute()`」，沒辦法（也不該嘗試用正則表達式去）解析字串內容代表的 SQL 語法——見上方「解析規則的邊界」——**這個 trigger 本身完全不會出現在圖表裡，只能像這樣手動記錄** |
