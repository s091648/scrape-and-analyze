---
title: Terraform Services
aside: false
---

# Terraform Services

`infra/terraform/railway/`（[025-iac-provisioning](/specs/025-iac-provisioning/spec)，revision 2）宣告的每個 Railway 服務**環境變數**，以及各自在 staging／production 兩個環境宣告了哪些；下方另外列出透過 `github-ci-config` 模組管理的 GitHub Actions secrets／variables。

::: info Terraform 只管環境變數，不管服務物件
revision 2（2026-08-28 structure reset）**移除了 `railway_service` resource**。這裡的每個 `<service>.tf` 只 instantiate `railway-variables` 模組。

服務物件的部署細節（`dockerfilePath`／`startCommand`／`cronSchedule`／`restartPolicyType`）走 Railway 原生的 config-as-code：`src/` 那五個共用 `src/Dockerfile` 的服務，各有一份 version-controlled 的 `src/railway-<service>.toml`（revision 3，見 [plan.md](/specs/025-iac-provisioning/plan)）。唯一的手動步驟是每個服務在 Railway 上一次性把 **Config File Path** 指到自己的檔（Railway 沒有對應的 service variable，`RAILWAY_CONFIG_PATH` 不存在）。`UV_GROUP` 這個 per-service build ARG 則是 Terraform 管的 service variable（`var.uv_group_<service>`）。
:::

<TerraformServicesViewer />

## 資料生成方式

圖表由 `scripts/generate_terraform_docs.py` 在 CI 時透過 `python-hcl2` 靜態解析 `infra/terraform/railway/` 底下每個服務各自的 `<service>.tf`（外加共用群組 `shared.tf` 與 `github-ci.tf`）自動產生，**不需要手動維護**，也不需要 `terraform init`／provider credentials — 純粹解析 HCL 語法樹（跟 `scripts/generate_db_schema.py` 解析 `models/*.py` 的 AST 是同一種「不執行、只解析原始碼」哲學），不會呼叫 `terraform plan`/`apply`，也不會連線 Railway／GitHub API。

執行 `python scripts/generate_terraform_docs.py` 可在本機重新產生（只需要 `pip install python-hcl2`，不需要 `uv sync`）；也可透過 `make uml-terraform-docs` 在 `job_service` container 內執行，跟 CI 走的路徑一致。

## 如何解讀

- 每個服務卡片顯示 staging／production 各自宣告了幾個環境變數。（`source_repo`／`root_directory`／`cron_schedule` 欄位保留在資料結構裡但恆為 `null` — revision 2 起不再由 Terraform 管理，見上方 info 區塊。）
- 點開服務卡片可看到完整變數表。revision 2 起**每一個宣告的變數都是 Terraform 管理**（不再有 `managed = false` 的 baseline half-state）：值由 Terraform 在每次 apply 時強制寫回；若標記 sensitive，值只會在 apply 時透過 `TF_VAR_*` 注入（FR-004a），此頁面永遠不會顯示實際內容。
- 「GitHub Actions 密鑰／變數」區塊對應 `github-ci-config` 模組的三個實例：一個 repo 層級（`github_ci_repo`）+ 兩個 GitHub Environment 層級（`github_ci_staging`／`github_ci_production`），欄位語意與服務變數表相同。

## 已知限制

此頁面只反映 **宣告**（`infra/terraform/railway/*.tf` 的原始碼），不反映 Terraform 的 **live state** 或 Railway/GitHub 上的即時真實值 — 若要確認宣告與現實是否一致，請用 `make terraform-drift-check ENV=staging|production`（見 `infra/terraform/railway/README.md`）。

## Terraform Modules（module 介面文件）

上面看的是「哪個服務用了哪些變數」；這裡看的是 `infra/terraform/railway/modules/` 兩個 module **自己的介面**（inputs／outputs／resources／requirements）— 兩者互補，不重複。內容由 [terraform-docs](https://terraform-docs.io/) 產生（設定檔：`infra/terraform/railway/.terraform-docs.yml`），跟上面的服務清單一樣是純 build artifact：本機用 `make uml-terraform-modules` 重新產生（跑官方 `quay.io/terraform-docs/terraform-docs` image，不需要 `terraform init`／provider credentials），輸出的 fragment 檔案不進 git，每次 build 都會重新產生。

<details>
<summary>展開查看 railway-variables／github-ci-config 兩個 module 的介面文件</summary>

<!--@include: ./terraform-modules/railway-variables.md-->

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
