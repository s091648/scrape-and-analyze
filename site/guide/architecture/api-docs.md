---
title: API Docs
aside: false
---

# API Docs

嵌入 backend FastAPI 的 Swagger 文件，唯讀 — 「Try it out」執行功能已在 backend 端全域關閉，不會真的送出請求。

<SwaggerViewer />

## 資料來源

這個頁面直接 iframe 嵌入 `${BACKEND_URL}/docs`（backend 自己的 Swagger UI），不是另外產生的靜態頁面 — API 文件永遠是最新的，不需要重新產生。

`BACKEND_URL` 的來源：

- **CI（GitHub Pages 部署）**：讀取 repo variable `BACKEND_URL`（跟 `STORYBOOK_URL` 同一套機制），在 `npm run generate` 時寫入 `site/.vitepress/config.js` 的 `themeConfig.backendUrl`。
- **本機預覽**：`BACKEND_URL=http://localhost:8000 npm run generate`（需要 `docker compose up backend` 正在跑）。

沒有設定 `BACKEND_URL` 時，這個頁面會顯示提示訊息，不會出現壞掉的 iframe。

## 為什麼不會真的執行

FastAPI 官方支援透過 `swagger_ui_parameters` 客製化 `/docs` 頁面的行為。`backend/main.py` 預設帶入 `swagger_ui_parameters={"supportedSubmitMethods": []}`，這會讓 Swagger UI 對所有 endpoint 都不顯示「Try it out」按鈕 — 這個限制是加在 backend **本身**的 `/docs` endpoint 上，不只是這個 docs 站的嵌入畫面，所以不管是透過這裡瀏覽、還是直接訪問 backend 的 `/docs`，都無法真的送出請求。

這個行為由環境變數 `SWAGGER_TRY_IT_OUT_ENABLED` 控制（預設 `false`）。如果某個部署（例如 staging）想要保留可執行的 Swagger UI，可以明確設成 `true` 開啟 — 這是刻意保留的操作者選項，不是安全漏洞。
