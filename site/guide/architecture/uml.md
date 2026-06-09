---
title: Pipeline
aside: false
---

# Pipeline

點擊同心圓環進入各 Clean Architecture 層，再點資料夾查看該子群組的 class 關係圖。點擊節點查看屬性／方法／依賴關係。

<UmlViewer />

## 資料生成方式

所有 UML 資料（class 清單、屬性、方法、docstring、pipeline 流程）都在 CI 時由 `scripts/generate_uml.py` 自動產生，**不需要手動維護**。執行 `make uml-backend` 可在本機重新產生。

### 兩階段解析

資料生成分兩個獨立的解析階段，最終合併為一份 `uml-data.json`：

#### 1. pyreverse — 靜態依賴圖

[pyreverse](https://pylint.readthedocs.io/en/stable/pyreverse.html)（pylint 內建工具）掃描 `src/` 所有 Python 原始碼，輸出 Graphviz DOT 格式的 class 關係圖（`classes.dot`）。DOT 檔記錄了每個 class 的 node ID（dotted module path）以及 inheritance / composition / aggregation / dependency 等邊型別。

#### 2. Python AST — 型別與語意資訊

`ast` 模組直接解析原始碼語法樹，萃取 pyreverse 沒有的語意資訊：

| 資料 | 萃取方式 |
|---|---|
| **Class docstring** | `ast.get_docstring(class_node)` |
| **類別層級型別標注** | class body 裡的 `AnnAssign`，例如 `name: str` |
| **`__init__` 屬性（有標注）** | `self.x: Type = ...` → `AnnAssign` on `Attribute` |
| **`__init__` 屬性（無標注）** | `self.x = ...` → `Assign` on `Attribute` |
| **Method 簽名** | `ast.FunctionDef.args`，含參數型別、回傳型別，格式化為 `name(arg: Type) → ReturnType` |
| **Method docstring** | `ast.get_docstring(method_node)` |

### Clean Architecture 分層分類

分層分類完全基於 pyreverse 輸出的 **node ID（dotted module path）**，套用 `LAYER_RULES` 正規表達式列表決定，不需要修改原始碼標記。

```
nodes.modules.collection.domain.entities.article.Article
→ 符合 "domain.entities." → layer = "domain" → CA circle = "entities"
```

四個 CA 同心圓環對應關係：

| CA 層 | 包含的 fine-grained layers |
|---|---|
| Domain / Entities | `domain` |
| Application | `application`, `shared-application` |
| Interface Adapters | `infrastructure-persistence`, `entrypoints` |
| Infrastructure | `infrastructure-collection`, `infrastructure-intelligence`, `infrastructure-shared`, `config` |

子群組分類（folder cards）同樣由 `SUBGROUP_RULES` 正規表達式決定，例如 `_repo_impl` 結尾 → `persistence`、`scrapers.` 前綴 → `scrapers`。

### Pipeline 流程自動推斷

Pipeline Flow 頁籤的各 stage 是由 AST 解析 `src/bootstrap.py` 自動推斷出來的，不需要在設定檔中手動維護流程圖。

推斷步驟：

1. **自動找到 pipeline 建構函式**：掃描 bootstrap.py 中所有 `def` 函式，找出 `event_bus.subscribe(...)` 呼叫數量最多的那個（不需要硬寫函式名稱）
2. **提取變數賦值**：掃描函式中的 `Assign` 節點，建立 `var_name → ClassName` 對應表
3. **提取訂閱關係**：掃描 `event_bus.subscribe(EventClass, handler.handle)` 呼叫，支援 `with_span(...)` 等 decorator 包裝（透過 `ast.walk` 遞迴找 `.handle` attribute）
4. **掃描 publish 呼叫**：對每個 handler class，掃描其 `handle()` 方法中的 `*.publish(EventClass(...))` 呼叫，得出各 handler 會 emit 哪些事件
5. **拓撲切分 main vs terminal**：不依賴事件名稱字串，而是看 entry events 的 handler 是否還有後續 publish — 有的是 main chain，沒有的（純通知/log）是 terminal chain
6. **兩階段 BFS 拓撲排序**：main chain 先展開，terminal chain 後展開（確保通知類 handler 排在文章處理主鏈之後）
7. **Branch 支線**：`*FailedEvent` 被視為 branch，以側欄呈現不打斷主鏈順序

新增一個 handler 並在 `bootstrap.py` 裡 `event_bus.subscribe(...)` 後，下次執行 `make uml-backend` 時 pipeline 圖就會自動更新。新增 `src/modules/` 下的子目錄也會自動出現在 Business Module 分頁，**無需修改任何設定檔**。

## 命名規則（自動解析的前提）

`generate_uml.py` 純粹依賴程式碼結構推斷拓樸，**沒有手動設定檔**，因此以下慣例必須遵守才能讓圖表自動正確生成。

### 目錄結構

| 路徑 | 作用 |
|---|---|
| `src/modules/<module_name>/` | 新增目錄 → 自動出現新的 Business Module context tab |
| `src/modules/*/domain/entities/` 等標準 DDD 子目錄 | 驅動 CA 層分類（domain / application / adapters / infrastructure）|
| `src/infrastructure/<module_name>/` | 基礎設施實作，與對應 module 同名 |
| `src/bootstrap.py` | 必須存在；pipeline 建構函式從這裡自動偵測 |

### 事件類別

- 所有 domain event 類別**結尾必須是 `Event`**（例：`ArticleScrapedEvent`）。DI 樹會自動排除結尾為 `Event` 的類別，避免汙染依賴圖。
- 失敗事件**類別名稱必須含 `Failed`**（例：`AnalysisFailedEvent`）。Pipeline 圖用這個關鍵字識別 error branch，以側欄方式渲染，不打斷主鏈。

### Handler 類別

- Handler 類別名稱必須是 `UpperCamelCase`（首字大寫）。
- 必須實作 **`handle()` 方法**，這是 publish 掃描和事件訂閱解析的入口點。
- 在 `bootstrap.py` 裡的訂閱寫法必須是：

  ```python
  event_bus.subscribe(SomeEvent, handler.handle)
  ```

  `_find_pipeline_func` 選取 subscribe 呼叫數最多的函式作為 pipeline builder，不需要固定函式名稱。

### 事件發布

- 事件必須在 `handle()` 方法內透過 `*.publish(SomeEvent(...))` 發布。
- 拓樸切分邏輯：entry event 的 handler 若還有後續 publish → main chain；若 handler 是葉節點（純通知 / log，不再 publish）→ terminal chain。

### Pipeline 與 Repository 命名

- Pipeline 主類別名稱**必須含 `Pipeline`，不得含 `Stats`**（例：`CollectionPipeline` ✓，`PipelineStats` ✗）。
- Repository 實作**檔名必須以 `_repo_impl` 結尾**（例：`article_repo_impl.py`），才能正確分類到 `infrastructure-persistence` 層。
