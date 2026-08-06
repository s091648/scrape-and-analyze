---
title: Deployment & Multi-Service Releases
aside: false
---

# Deployment & Multi-Service Releases

本 repo 的程式碼 — 以及它的兩個兄弟 repo，`chatbot-plugin`（git submodule，位於 `chatbot-plugin/`）與 `chatbot-plugin-sdk`（外部的、以 git tag 釘住版本的依賴，並未 vendor 進這個 repo 樹裡）— 實際上是怎麼送到 Railway staging 與 production 的。這是根目錄 `CLAUDE.md` 裡 CI/CD 表格的手寫輔助文件；那張表列出每個 workflow 階段*做了什麼*，這頁則說明*三個 repo 是如何串在一起的*，以及要送出一個牽涉不只一個 repo 的變更，需要依什麼順序發生什麼事。

## 1. 三個 repo，一條部署管線

只有 **scrape-analyzer** 自己的 workflow 會呼叫 `railway up`。另外兩個 repo 從不自己部署 — 它們只產生 commit，有時候還有 version tag，讓 scrape-analyzer 的 pipeline 去對它們做反應。

| Repo | 自己的 CI | 自己的 release tag 做的事 | 實際負責部署的是誰 |
|---|---|---|---|
| **scrape-analyzer**（本 repo） | `.github/workflows/ci.yml` | 不適用 — 在這裡 push `v*` 本身*就是* production 的觸發條件 | 自己（staging 用 `ci.yml`，production 用 `release.yml`） |
| **chatbot-plugin**（submodule） | 自己的 `ci.yml` — 只跑測試 | 自己的 `release.yml` — 更新 `pyproject.toml` 並強制移動 tag；**不呼叫 Railway** | scrape-analyzer 的 `ci.yml`/`release.yml`，讀取 submodule pointer |
| **chatbot-plugin-sdk**（外部依賴） | 自己的 `test.yml` — 只跑測試 | 自己的 `ci.yml`（"Release"）— 更新版本、把 MkDocs 發佈到 GitHub Pages；**不呼叫 Railway** | 沒有人 — 它是一個函式庫，不是一個在跑的服務（見第 6 節） |

## 2. 每個 Railway 服務的部署方式

上面的表格是 repo 層級的關係；下表是實際會出現在 Railway 上、`railway up --detach --service <id>` 真正部署的 8 個服務，每一個在 staging（`ci.yml`）與 production（`release.yml`）分別是怎麼觸發的。`postgres`／`redis` 不在其中 — 它們刻意不透過這條 CI/CD 管線部署，永久保持在線（見第 3 節 `close-staging.yml` 的說明）。

| 服務 | 對應原始碼 | Staging（`ci.yml`） | Production（`release.yml`） |
|---|---|---|---|
| `dashboard-backend` | `backend/` | `backend-unit` + `backend-integration` 通過後，`deploy-staging-backend` 部署 PR 分支（<code v-pre>ref: ${{ github.head_ref }}</code>） | `release` job 對打 tag 的 `master` commit 無條件部署 |
| `dashboard-frontend` | `frontend/` | `frontend-unit` + `frontend-e2e` 通過後，`deploy-staging-frontend` 部署 PR 分支 | 無條件部署 |
| `storybook` | `frontend/`（Storybook build） | 同樣依賴 `frontend-unit` + `frontend-e2e`，由 `deploy-staging-storybook` 部署 | 無條件部署 |
| `scrape-and-analyze` | `src/`（主 worker，`docker-compose.yml` 的 `app`） | `src-unit-test` + `src-integration-test` 通過後，`deploy-staging-src` 部署 | 無條件部署 |
| `weekly-report` | `src/`（與 `scrape-and-analyze` 共用程式碼與 Dockerfile，`src/railway.toml` 覆寫成獨立 start command） | 同樣依賴 `src-unit-test` + `src-integration-test`，由 `deploy-staging-weekly-report` 部署 | 無條件部署 |
| `refresh-metrics` | `src/`（同上，`src/railway.toml` 另一組 start command 覆寫） | 同樣依賴 `src-unit-test` + `src-integration-test`，由 `deploy-staging-refresh-metrics` 部署 | 無條件部署 |
| `fastembed` | `services/fastembed/` | 只依賴 `src-unit-test` 通過，由 `deploy-staging-fastembed` 部署 | 無條件部署 |
| `chatbot-plugin` | `chatbot-plugin/`（submodule） | 只依賴 `src-unit-test` 通過，由 `deploy-staging-chatbot` 部署 submodule pointer 目前指向的 commit — 不管有沒有打 tag | **有條件**：只有 submodule 目前 commit 在*`chatbot-plugin` 自己的 repo*裡有對應 `v*` tag 才會部署，否則整個服務被跳過（詳見第 5 節） |

除了 `chatbot-plugin` 外，以上每一列的 staging／production 部署都只是「測試通過與否」或「有沒有打 tag」的差異 — 沒有例外邏輯；`chatbot-plugin` 是唯一在 staging 與 production 之間部署條件不對稱的服務，這也是第 5 節要特別拆開講的原因。

## 3. Staging：PR 開啟時上線，PR 關閉時下線

`ci.yml` 在每次對 `master` 的 `pull_request`/`push` 時執行。與 staging 相關的 job 全部都加上 `if: github.event_name == 'pull_request'` 這個條件 — post-merge 對 master 的 push 永遠不會重新部署 staging，因為 `close-staging.yml` 正好在同一時間把同一個環境拆掉（見下方），重新部署會跟它互相競爭。

Job 鏈：`check-staging-deployments`（把 Railway 顯示為 `REMOVED` 的服務復活，例如上一次沒跑完的 teardown）→ `migrate`（staging DB）→ 各領域的測試 → 每個服務各自一個 `deploy-staging-*` job，各自依賴自己的測試通過：

| 服務 | 依賴 |
|---|---|
| `dashboard-backend` | `backend-unit`、`backend-integration` |
| `dashboard-frontend` | `frontend-unit`、`frontend-e2e` |
| `storybook` | `frontend-unit`、`frontend-e2e` |
| `scrape-and-analyze`（本 repo 的 `src/`） | `src-unit-test`、`src-integration-test` |
| `chatbot-plugin` | 只依賴 `src-unit-test` |
| `fastembed` | 只依賴 `src-unit-test` |
| `weekly-report` | `src-unit-test`、`src-integration-test` |
| `refresh-metrics` | `src-unit-test`、`src-integration-test` |

每個 `deploy-staging-*` job 都會 checkout <code v-pre>ref: ${{ github.head_ref }}</code>（PR 分支）並帶 `submodules: recursive`，然後執行 `railway up --detach --service <id> --environment staging`。對 `chatbot-plugin` 來說，這代表**部署的是你 PR 裡 submodule pointer 目前指向的那個 commit** — 沒打 tag 也沒關係，staging 是預覽環境，不是正式發布。

`close-staging.yml` 在 `pull_request: closed`（且 `merged == true`）時執行，把上面每個服務都 `railway down`。`postgres`/`redis` 刻意排除在復活與拆除流程之外 — Railway 的 CLI 沒有可靠的方式把一個完全被移除的 DB 服務救回來（`check-staging-deployments` 自己的註解裡記錄過一次驗證此事的事故），所以它們永久保持在線，不會被拆掉。

## 4. Production：只在對 `master` push 一個 `v*` tag 時觸發

`release.yml` 在 `push: tags: ['v*']` 時觸發，並固定 checkout `ref: master` — **tag 必須指向已經在 `master` 上的 commit**，所以任何想上 production 的東西都必須先被 merge；沒辦法直接對一個 feature branch 打 tag 送進 production。

流程：把 `pyproject.toml` 的版本更新成跟 tag 一致 → 記錄 release notes（如果沒有 PR 作者寫的佔位內容，就用 LLM 產生）→ 執行 production DB migration（`alembic upgrade head` + `scripts/run_data_migrations.py`）→ 對 `dashboard-frontend`、`dashboard-backend`、`storybook`、`scrape-and-analyze`、`fastembed`、`weekly-report`、`refresh-metrics` 無條件執行 `railway up --detach --service <id>`（不帶 `--environment`，預設就是 production）。`chatbot-plugin` 是唯一的例外，見第 5 節。

## 5. `chatbot-plugin` 拆分的部署責任

這是最容易搞錯的部分：**光是 push 到 `chatbot-plugin` 自己的 `master` 是不夠的。**

- 在 **staging** 上沒差 — `ci.yml` 會部署 submodule pointer 目前指向的 commit，不管有沒有打 tag（第 3 節）。
- 在 **production** 上，`release.yml` 會拒絕部署一個沒打 tag 的 commit：

  ```bash
  CHATBOT_TAG=$(cd chatbot-plugin && git fetch --tags origin -q && git tag --points-at HEAD | grep '^v' | head -1 || true)
  if [ -n "$CHATBOT_TAG" ]; then
    (cd chatbot-plugin && railway up --detach --service e3a28eae-2765-456e-822c-841598fcf1c2)
  else
    echo "::warning::... has no version tag (v*) — skipping its production deploy."
  fi
  ```

  如果 submodule 目前的 commit 在 `chatbot-plugin` *自己的 repo* 裡沒有對應的 `v*` tag，它的 production 部署會被靜默跳過（只是一個 workflow `::warning::`，不是失敗）— 同一次 release 裡其他所有服務仍然照常上線。

要真正把一個 `chatbot-plugin` 的變更送上 production：

1. **在 `chatbot-plugin` 裡**：merge 到它的 `master`，然後在那裡 push 一個 `v*` tag（例如 `git tag v0.4.0 && git push origin v0.4.0`）。它自己的 `release.yml` 會更新 `pyproject.toml` 並把 tag 強制移到那個 bump commit 上 — 不會部署任何東西。
2. **在 scrape-analyzer 裡**：把 submodule pointer 更新到那個打了 tag 的 commit（`cd chatbot-plugin && git checkout v0.4.0 && cd .. && git add chatbot-plugin && git commit`），並透過正常的 PR → staging 流程 merge 到 `master`（在 merge 之前 staging 就已經會反映這個變更）。
3. **在 scrape-analyzer 裡**：push scrape-analyzer 自己的 `v*` tag。這時 `release.yml` 就會在 submodule 的 HEAD 上找到對應的 tag，並把 `chatbot-plugin` 跟其他所有服務一起部署。

跳過第 1 步（打 tag）或第 2 步（更新 submodule pointer + merge），結果都一樣：`chatbot-plugin` 悄悄停留在上次部署的版本，而 production 的其他部分則繼續往前推進。

## 6. `chatbot-plugin-sdk`：一個有版本號的依賴，不是一個部署對象

`chatbot-plugin-sdk` 完全沒有 Railway 服務 — 它是一個 Python 套件，`scrape-analyzer/pyproject.toml` 和 `chatbot-plugin/pyproject.toml` 各自透過 `[tool.uv.sources]` 獨立釘住版本：

```toml
[tool.uv.sources]
chatbot-plugin-sdk = { git = "https://github.com/s091648/chatbot-plugin-sdk.git", tag = "v0.15.2" }
```

它自己的 `ci.yml`（名稱是 "Release"，由 push 一個 `v*` tag 到*它自己的* repo 觸發）只會更新它的 `pyproject.toml` 版本、並把它的 MkDocs 網站發佈到 GitHub Pages — 不會通知任何使用它的專案，下游也不會自動重建。

`chatbot-plugin-sdk` 裡的一個變更，只有在以下情況才會真正送到一個在跑的服務：

1. 在 SDK 自己的 repo 裡打上 tag。
2. 每個使用它的專案（`scrape-analyzer`，以及如果變更牽涉到 `chatbot-plugin` 用到的程式碼路徑，還有 `chatbot-plugin`）把上面的 `tag =` 值更新、重新跑 `uv lock`，並把更新後的 `pyproject.toml` + `uv.lock` commit 進去。
3. 那個 commit 會走*那個使用專案自己的* staging/production 流程，跟其他任何程式碼變更完全一樣（第 3–5 節）— 對 `chatbot-plugin` 來說，這還包含在這個更新能送到 production 之前，需要它自己再打一個新的 version tag。

想在打 tag 之前，先在本機測試一個還沒發布的 SDK 變更，可以參考 `docker-compose.yml` 裡 `app` 和 `chatbot_plugin` 服務上的 `../chatbot-plugin-sdk` volume mount 與 editable-install 覆寫設定（每個都標註 `LOCAL DEV ONLY`）— 這會完全繞過上面的 tag-pin 機制，不屬於上述部署管線的一部分。

## 7. 快速參考

| 我改了... | 要讓它上 production 之前需要發生什麼事 |
|---|---|
| `src/`、`backend/`、`frontend/`、`models/`、`shared/`（本 repo，非 submodule） | Merge 到 `master` → push 一個 scrape-analyzer 的 `v*` tag |
| `chatbot-plugin/`（submodule 內容） | 在 *`chatbot-plugin` 自己的 repo* 打一個 release tag → 在 scrape-analyzer 裡更新 submodule pointer 並 merge → push 一個 scrape-analyzer 的 `v*` tag |
| `chatbot-plugin-sdk` | 在 *SDK 自己的 repo* 打一個 release tag → 在每個需要這個變更的使用專案裡更新 `tag =` 釘住值（+ `uv lock`）→ 從那裡開始，各自套用上面對應的那一列 |
