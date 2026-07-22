---
title: Exceptions
aside: false
---

# Exceptions

彙整 `backend/`、`src/`、`models/`、`shared/` 中所有出現的 exception：每種 exception 是在哪裡定義的（如果是專案自訂的）、以及所有會 raise 出它的位置（檔案、行號、所在函式）。

<ExceptionViewer />

## 資料生成方式

資料由 `scripts/generate_exceptions.py` 在 CI 時透過 AST 靜態解析自動產生，**不需要手動維護**，也不 import 任何專案程式碼 — 跟 `scripts/generate_db_schema.py` 解析 `models/` 的方式一樣是純靜態分析。執行 `make uml-exceptions` 可在本機重新產生。

### 解析範圍

掃描 `backend/`、`src/`、`models/`、`shared/`（排除任何路徑含 `tests/` 的檔案）：

1. **自訂 exception class**：找出所有繼承自 `Exception`/`BaseException`（或間接繼承，透過鏈式解析）的 class，記錄其 base class、docstring、定義位置。
2. **`raise` 語句**：解析每一個 `raise` 語句實際 raise 出的型別 —
   - `raise X(...)`、`raise X(...) from e` → 直接解析 `X`
   - 裸 `raise`（重新拋出）→ 透過最近的 `except ExcType as e:` 解析出 `ExcType`
   - `raise e`（重新拋出被捕捉的變數）→ 同樣透過最近的 `except ... as e:` 解析
   - 無法解析的情況（`except:` 沒有指定型別、或 `except (A, B):` 有多種型別）→ **該筆 raise 直接排除**，不會被誤歸類到錯誤的 exception 型別
3. 針對 `HTTPException(...)` 額外嘗試擷取 `status_code=` 參數（僅限寫死的整數常數）。

每個 exception 型別分類為：

| 分類 | 定義 |
|---|---|
| `custom` | 在掃描範圍內找到對應 class 定義 |
| `framework` | 來自 framework 的 exception（目前只有 `HTTPException`） |
| `builtin` | Python 內建型別（`ValueError`、`RuntimeError` 等） |

## 涵蓋範圍的限制

這份目錄**只涵蓋專案自己程式碼裡明確寫出 `raise` 的例外**。第三方套件內部丟出、但我們的程式碼從未親自 `raise` 過的例外（例如某個 HTTP client library 內部拋出的連線錯誤）不會出現在這裡 — 純靜態 AST 分析無法追蹤到套件內部的程式碼，這是刻意的範圍限制，不是遺漏。
