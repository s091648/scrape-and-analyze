---
title: Infra — Services & CI Secrets
aside: false
---

# Infra — Services & CI Secrets

自 [025-iac-provisioning](/specs/025-iac-provisioning/spec) **Revision 6** 起，基礎設施由兩個引擎分工，本頁把兩邊的宣告攤在一起：

| 範圍 | 由誰管 | 宣告在 | CI |
|---|---|---|---|
| 每個 Railway 服務的**部署設定**（`cronSchedule`／`startCommand`／`restartPolicyType`／`replicas`／`source`／networking）＋**環境變數** | `railway config apply`（Railway 原生 IaC，**不是** Terraform） | [`.railway/railway.ts`](https://github.com/s091648/scrape-and-analyze/blob/master/.railway/railway.ts) | `.github/workflows/railway-config.yml` |
| `ci.yml`／`release.yml` 讀的 **GitHub Actions secrets／variables** | Terraform（`github` provider、HCP backend） | `infra/terraform/github/github-ci.tf` ＋ `modules/github-ci-config` | `.github/workflows/terraform.yml` |

::: warning Revision 4→6 的變化（舊文件可能還這樣寫）
- Revision 4 曾用 `terraform-community-providers/railway` 的 `railway_variable*` resource 管環境變數 → 在這個規模不可靠，改用 `scripts/push_railway_variables.py` ＋ `railway-services.json`。
- **Revision 6** 再進一步：整個 Railway 半邊（服務物件 ＋ 環境變數）移到 `.railway/railway.ts` ＋ `railway config`。`push_railway_variables.py`、`pull_railway_variables.py`、`src/railway-<svc>.toml`、`railway_service`／`railway-variables` module、每個服務的 `<svc>.tf`／`shared.tf` **都已刪除**（T6-09）。
- `railway-services.json` **保留**，但只當 `scripts/tfvars_to_env.py` 的變數名／tfvars-key 對照表 ＋ 本頁的資料來源，**不再是路由權威**（權威是 `railway.ts`）。
- `UV_GROUP` 從 Terraform service variable 變成 `.railway/constants.ts` 的 literal（`UV_GROUP.<service>`）。
:::

<TerraformServicesViewer />

## 資料生成方式

`scripts/generate_terraform_docs.py` 在 CI（`speckit-github-pages.yml`）與 `make uml-terraform-docs`（`job_service` container）產生 `site/public/guide/architecture/terraform-services-data.json`，三個來源各對應一個引擎，**都不執行 `terraform`／`railway`、不需要任何 credentials、不連線 Railway／GitHub API**：

| 來源 | 取什麼 | 怎麼取 |
|---|---|---|
| `.railway/railway.ts` | 每個服務的 production 部署設定（cron／start／restart／endpoint） | 正則掃描 `service("…", { … })` 區塊（best-effort：沒 match 到的欄位留 `null`，例如用 Dockerfile CMD、無 cron 的服務） |
| `infra/terraform/github/railway-services.json` | 每個服務有哪些環境變數名稱、哪些是 `preserve()`（Railway 手動管理） | 直接讀 JSON |
| `infra/terraform/github/github-ci.tf` | `github-ci-config` module 的三個實例各自的 secrets／variables 名稱 | `python-hcl2` 靜態解析 HCL 語法樹（跟 `generate_db_schema.py` 解析 `models/*.py` AST 同一種「不執行、只解析原始碼」哲學） |

本機重新產生：`python scripts/generate_terraform_docs.py`（只需 `pip install python-hcl2`），或 `make uml-terraform-docs`（走 CI 同一條路徑）。

## 如何解讀

- **服務卡片**：顯示 production 的 `cron` / `start` / `endpoint`（來自 `.railway/railway.ts`），以及 staging／production 各自宣告了幾個環境變數。點開看完整變數表。
  - staging 的 cron 一律是 `0 0 1 1 1`（等同「永不執行」的佔位——staging 服務隨 PR 開關拆除／復活），所以卡片只顯示 production 值。
  - 變數「來源」欄：**railway.ts 宣告**＝值由 `railway config apply` 每次強制寫回；**Railway 手動管理（preserve）**＝`railway.ts` 用 `preserve()` 保留現值、不覆寫（對照 `railway-services.json` 的 `unmanaged`）。sensitive 變數的實際值在 apply 時注入，本頁永遠不顯示。
- **GitHub Actions 密鑰／變數**：對應 `github-ci-config` module 的三個實例——一個 repo 層級（`github_ci_repo`）＋ 兩個 GitHub Environment 層級（`github_ci_env` × staging／production）。這半邊**仍是 Terraform 管理**，來源欄的「Terraform 管理」在這裡才成立。

## 已知限制

- 本頁只反映**宣告**（`.railway/railway.ts` ＋ `github-ci.tf` 的原始碼），不反映 live state 或 Railway／GitHub 上的即時真實值。
- 對帳方式：Railway 半邊用 `make railway-config-plan ENV=staging|production`（plan 乾淨＝無 drift，見 [`.railway/README.md`](https://github.com/s091648/scrape-and-analyze/blob/master/.railway/README.md)）；GitHub 半邊用 `make terraform-drift-check ENV=staging|production`（見 `infra/terraform/github/README.md`）。
- 部署設定為正則掃描——若 `railway.ts` 的寫法改變，最壞情況是某服務少顯示一個欄位（不會顯示錯的值）；`generate_terraform_docs.py` 會在有服務完全對不到 `service()` 區塊時直接報錯。
- 每個服務 staging／production 顯示同一份變數**名稱**集合；per-env 的差異（`railway.ts` 裡的 `prod ? … : …`）與實際值差異落在 tfvars，不在此圖。

## Terraform Module 介面文件

上面看的是「哪個服務用了哪些變數」；這裡看的是 `infra/terraform/github/modules/` 底下唯一的 module——`github-ci-config`——**自己的介面**（inputs／outputs／resources／requirements）。內容由 [terraform-docs](https://terraform-docs.io/) 產生（設定檔：`infra/terraform/github/.terraform-docs.yml`），跟上面的服務清單一樣是純 build artifact：本機用 `make uml-terraform-modules` 重新產生（跑官方 `quay.io/terraform-docs/terraform-docs` image，不需要 `terraform init`／credentials），輸出的 fragment 檔不進 git。

<details>
<summary>展開查看 github-ci-config module 的介面文件</summary>

<!--@include: ./terraform-modules/github-ci-config.md-->

</details>

<style>
.tf-module {
  border: 1px solid var(--vp-c-border);
  border-radius: 8px;
  padding: 10px 14px;
  margin: 12px 0;
  background: var(--vp-c-bg-soft);
}
.tf-module > summary {
  cursor: pointer;
  font-weight: 700;
  font-family: monospace;
  font-size: 15px;
}
.tf-module-section {
  border-left: 3px solid var(--vp-c-border);
  padding: 4px 0 4px 14px;
  margin: 10px 0 10px 4px;
}
.tf-module-section > summary {
  cursor: pointer;
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--vp-c-text-2);
}
</style>
