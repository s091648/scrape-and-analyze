---
title: Frontend Architecture
aside: false
---

# Frontend Architecture

Two views of the frontend architecture:

**Module Graph** — 左側選擇模組類型（app / components / lib），點擊節點查看 imports 與 imported-by。切換 File / Directory 層級。循環依賴紅色標示，方向違規（如 lib import app）橘色虛線。

**Provider / Context Chain** — 顯示 React Context 嵌套層級、消費者分布、跨 Context 依賴。

執行 `make uml-frontend` 重新生成資料。

<DepGraphViewer />
