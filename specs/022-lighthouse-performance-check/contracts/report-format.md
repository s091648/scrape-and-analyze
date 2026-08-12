# Contract: Consolidated Report Format

`lighthouse-reports/<runId>/report.md` — the artifact FR-006/FR-007/FR-011 require. Structure below is normative; exact wording is not.

```markdown
# Lighthouse 效能檢測報告

- **產出時間**：2026-08-09T14:30:00+08:00
- **測試網址**：http://frontend_prod:3000
- **訪客身分**：guest_id=<uuid>（透過 POST /auth/guest 取得）
- **測試路徑數**：4（成功 3，失敗 1）

## 總覽

| 路徑 | Performance 分數 | LCP (ms) | TBT (ms) | CLS | 狀態 |
|---|---|---|---|---|---|
| `/` | 82 | 1820 | 120 | 0.03 | ✅ 成功 |
| `/articles` | 75 | 2400 | 340 | 0.05 | ✅ 成功 |
| `/graph` | — | — | — | — | ❌ 失敗（逾時） |
| `/tags` | 88 | 1500 | 60 | 0.01 | ✅ 成功 |

## 各路徑詳細結果

### `/`

- Performance 分數：82 / 100
- LCP（最大內容繪製）：1820 ms
- TBT（總阻塞時間）：120 ms
- CLS（累計版面配置位移）：0.03
- 原始 Lighthouse 報告：`graph.json`（同目錄）

### `/graph`

- 狀態：❌ 失敗
- 原因：逾時（Lighthouse 在 60 秒內未完成量測）
```

## Required elements

- **Header block**: production timestamp, tested `BASE_URL`, the `guest_id` used, and a success/failure count summary — all labels in Traditional Chinese.
- **Summary table** (FR-006): exactly one row per configured route, in the order routes were specified. Failed routes show `—` for every metric column and a Traditional-Chinese failure status, never an empty/omitted row (FR-010, SC-002).
- **Per-route section**: one `###` heading per route (successful routes show all four metrics + a relative link to that route's raw JSON; failed routes show only status + reason).
- **Language**: every heading, table header, and narrative sentence is Traditional Chinese (SC-003). Metric identifiers (`Performance`, `LCP`, `TBT`, `CLS`) and units (`ms`) stay in their standard technical form, per spec.md User Story 2 Acceptance Scenario 2 — they are not translated/transliterated.
- **Numeric formatting**: `performanceScore` as an integer 0–100; `lcpMs`/`tbtMs` as integers (milliseconds); `cls` to 3 decimal places.
