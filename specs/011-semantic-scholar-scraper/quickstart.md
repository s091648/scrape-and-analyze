# Quickstart: Semantic Scholar Scraper

**Feature**: 011-semantic-scholar-scraper | **Date**: 2026-06-04

## 設定 Semantic Scholar API Key（可選）

免費層（1 req/sec）無需 API key。若要提高 rate limit，在 `.env` 加入：

```env
SEMANTIC_SCHOLAR_API_KEY=your_key_here
```

## 啟用 Semantic Scholar 來源

1. 前往 `http://localhost:3000/admin/scraper-settings`
2. 選取一個 topic
3. 在 "Semantic Scholar" 區塊點擊「啟用 Semantic Scholar」
4. 填入：
   - **名稱**：識別用名稱，如 `Semantic Scholar - Digital Twins`
   - **頻率**：抓取間隔（小時），建議 24
   - **Max Results**：每次最多論文數，建議 20
   - **Days Back**：只取最近 N 天的論文，建議 7
5. 在關鍵字區塊加入搜尋詞，如 `digital twin`、`cyber-physical systems`
6. 儲存

## 手動觸發測試

```bash
make scrape SOURCE=semantic_scholar LIMIT=5
```

## 驗證結果

查詢最新 semantic_scholar 論文：

```sql
SELECT title, source, published_at, created_at
FROM articles
WHERE source = 'semantic_scholar'
ORDER BY created_at DESC
LIMIT 10;
```

## ArXiv 設定精簡（配套操作）

現有 ArXiv 設定中的 keyword（非 category）在新版本會被系統層忽略。建議將原本 ArXiv keyword 改設定為 Semantic Scholar keyword，ArXiv 保留 category 即可。

## 執行測試

```bash
# Scraper unit tests
make test

# 或直接執行特定測試
docker compose exec test_service uv run pytest src/tests/unit/infrastructure/collection/scrapers/test_semantic_scholar_scraper.py -v
docker compose exec test_service uv run pytest src/tests/unit/infrastructure/collection/clients/test_semantic_scholar_client.py -v

# Frontend unit tests
cd frontend && npm run test
```
