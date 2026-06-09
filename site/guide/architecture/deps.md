---
title: Frontend Architecture
aside: false
---

# Frontend Architecture

Two views of the frontend architecture:

**Module Graph** — 左側選擇模組類型（app / components / lib），點擊節點查看 imports 與 imported-by。切換 File / Directory 層級。循環依賴紅色標示，方向違規（如 lib import app）橘色虛線。

**Provider / Context Chain** — 顯示 React Context 嵌套層級、消費者分布、跨 Context 依賴。

執行 `make uml-frontend` 重新生成所有資料（或個別執行下方指令）。

<DepGraphViewer />

## 資料生成方式

所有資料在 CI 時自動產生並寫入 `site/guide/architecture/`，本機可用下表指令重新產生，**不需要手動維護**。

| 檔案 | 生成指令 | 來源 |
|---|---|---|
| `frontend-deps.json` | `make uml-frontend-deps` | madge 靜態掃描 |
| `frontend-context.json` | `make uml-frontend-context` | 自訂 AST 腳本 |

### Module Graph — `frontend-deps.json`

由 [madge](https://github.com/pahen/madge) 在 `frontend` Docker 容器內掃描原始碼生成：

```sh
npx madge --json --extensions ts,tsx \
  --ts-config tsconfig.json \
  app/ lib/ components/
```

madge 追蹤每個 `.ts` / `.tsx` 檔案的 `import` 語句（包含 path alias 解析），輸出一份 JSON 物件：

```json
{
  "app/page.tsx": ["lib/api-fetch", "components/ui/button"],
  "lib/api-fetch.ts": [],
  ...
}
```

`DepGraphViewer` 讀取這份 JSON 後：

1. **分類**：依路徑前綴分為 `app`、`components`、`lib`、`other` 四個 category
2. **建雙向邊**：每條 `src → tgt` import 同時記錄 `src.deps` 與 `tgt.depended`
3. **目錄聚合**：把 file-level 邊匯總為 directory-level 邊（跨目錄才計入）
4. **循環偵測**：DFS 染色法（white / gray / black）找出 cycle 中的節點與邊
5. **方向違規**：`LAYER_RANK` 定義 `app(0) > components(1) > lib(2) > other(3)`，下層 import 上層視為違規，橘色虛線標示

### Provider Chain — `frontend-context.json`

由 `frontend/scripts/generate-frontend-context.mjs` 掃描原始碼生成，分四個階段：

#### 1. 嵌套層級偵測

讀取 `lib/providers/index.tsx` barrel 檔，以正規表達式掃描 JSX 開標籤出現順序推斷 Provider 嵌套關係（outermost first），**不需要手動設定父子關係**：

```tsx
// lib/providers/index.tsx
<SessionProviderWrapper>     ← level 0
  <TopicProvider>            ← level 1
    <I18nProvider>           ← level 2
      <GuestModeProvider>    ← level 3
```

#### 2. Consumer 掃描

遍歷 `app/`、`components/`、`lib/` 所有 `.tsx` / `.ts` 檔，以正規表達式比對 hook 呼叫：

```
const { ... } = useXxx(...)   ← 有解構
useXxx(...)                   ← 無解構
```

每個命中記錄 `{ file, line, destructured }`。

#### 3. 跨 Context 依賴偵測

掃描各 Provider 本身的原始碼，找出是否在其內部呼叫了其他 Provider 的 hook（例如 `TopicProvider` 內呼叫 `useSession()`），輸出為 `crossContextDeps`。

#### 4. 輸出格式

```json
{
  "providers": [{ "id": "topic", "nestingLevel": 1, "consumerCount": 12, ... }],
  "consumers": [{ "contextId": "topic", "sites": [{ "file": "...", "line": 42 }] }],
  "crossContextDeps": [{ "from": "topic", "to": "session", "evidence": {...} }],
  "summary": { "totalConsumerSites": 38, "mostConsumedContext": "topic", ... }
}
```

## 命名規則（自動解析的前提）

`generate-frontend-context.mjs` 依賴以下慣例：

| 規則 | 說明 |
|---|---|
| Provider 定義列在 `PROVIDER_DEFS` | 新增 Context 需在腳本頂部的 `PROVIDER_DEFS` 陣列補上 `{ id, name, file, hookName, importPath }` |
| barrel 檔路徑固定 | 嵌套偵測讀取 `lib/providers/index.tsx`，Provider 必須在此以 JSX 方式組合 |
| hook 命名 `useXxx` | Consumer 掃描依 `hookName` 字串做正規匹配，命名必須與 `PROVIDER_DEFS` 一致 |
| Provider 原始碼路徑與 `file` 欄位相符 | 跨 Context 依賴偵測依此路徑讀取 Provider 本身的原始碼 |
