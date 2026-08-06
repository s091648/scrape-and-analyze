---
title: Exception Handling Guideline
aside: false
---

# Exception Handling Guideline

`src/`、`models/`、`backend/` 應該如何 raise、傳遞、並轉換例外為 HTTP response。這是一份手寫的慣例文件 — 它與自動產生的 [Exceptions](./exceptions) 目錄（靜態分析找出的所有 exception class 與 `raise` 位置）互補，而非重複。

## 1. Raise 還是 return

對於**預期內、可復原**的失敗 — 呼叫方（use case、router、API consumer）可以據以採取行動的情況，例如：錯誤輸入、找不到資源、狀態衝突、缺少／無效授權、外部依賴耗盡 — 應該 raise 一個 `DomainError` 子類別。

**不要**為了「違反不變量、代表程式有 bug」的情況特地發明一個 `DomainError` 子類別（「理論上不應該發生」的那種）。讓它以原本自然發生的形式往外拋（`AssertionError`、`KeyError` 等）。它應該以未對應的 500 呈現並送到 Sentry — 把它包裝成一個看起來正常的 typed error，只會把真正的缺陷藏在一個看似正常的 response 底下。

回傳 `None` ／空集合，在「不存在是正常結果，不是失敗」的情境下仍然合適 — 例如 `ResilientLLMService` / `ResilientMetricsService` 在 fallback chain 裡所有 provider 都耗盡時回傳 `None`（見第 5 節）是刻意的設計，本文件並不要求改變這個行為。

## 2. 該用哪種例外型別

每個 domain exception 都屬於以 `DomainError`（`shared/domain/exceptions.py`）為根的階層：

```
DomainError
├── ValidationError            # 400 — 違反業務規則不變量
├── NotFoundError               # 404 — 請求的資源不存在
├── ConflictError                # 409 — 與既有狀態衝突（例如唯一性違反）
├── UnauthorizedError           # 401 — 缺少／無效／過期的身份驗證
├── ForbiddenError                # 403 — 已驗證身份但無權限
├── ExternalDependencyError    # 502 — 必要的外部依賴失敗／耗盡
├── CollectionDomainError       # 各 bounded context 的根類別（既有）
│   └── ...各 leaf class，各自多重繼承上面某一個共用分類
└── IntelligenceDomainError     # 各 bounded context 的根類別（既有）
    └── ...各 leaf class，各自多重繼承上面某一個共用分類
```

新增的 leaf exception 恰好多重繼承**一個**共用分類（供狀態碼對應使用）以及所屬 bounded context 的根類別（供既有的 context 範圍 `except` 區塊使用）：

```python
class TopicNotFoundError(NotFoundError, CollectionDomainError):
    """Raised when a Topic id does not resolve to an existing row."""
```

內建例外（`ValueError` 等）僅在第 1 節所述的「不可復原／程式錯誤」情境下才可接受 — 絕不能用在任何應該產生特定非 500 HTTP 狀態碼的情況。

`backend/` 裡如果某個 router 沒有天然的 DDD 歸屬可以放新的 leaf class（`backend/` 大部分 CRUD router 是直接查 ORM，沒有獨立的 use case 層），可以直接 raise 共用分類 class，例如 `raise NotFoundError("Topic not found")` — 當沒有任何 bounded-context 專屬的東西可以附加時，不強制要求新增 leaf 子類別。

## 3. 跨層傳遞

- **Domain 層**：直接 raise `DomainError` 子類別。
- **Application 層**（use case）：讓 domain exception 原封不動往外傳。不會 catch 一個自己沒有拋出的 `DomainError` 再重新包裝。
- **Infrastructure 層**（DB、HTTP client、外部 API）：catch 特定於函式庫的例外（`sqlalchemy.exc.IntegrityError`、`httpx.HTTPError` 等），並在例外進入 application 層*之前*重新 raise 成對應的 `DomainError` 子類別。Application 層程式碼不應該需要 import `sqlalchemy.exc` 之類的東西來處理失敗。
- **API 邊界**（`backend/`）：從不為每個 endpoint 手動挑選 HTTP 狀態碼。一個統一的中央例外處理器（`backend/exceptions/handlers.py`，註冊於 `backend/main.py`）會自動把任何 `DomainError` 轉換成正確的狀態碼＋body。Router 程式碼只管 raise，不自己建構 `HTTPException`。

## 4. 400 與 422 的分界

FastAPI 自己的 request 格式驗證（缺少必要欄位、JSON 型別錯誤、在 route signature 上未通過 Pydantic 轉型）維持原本的原生 422 response 不變 — 這發生在任何 router 或 domain 程式碼執行之前，所以沒有東西可以讓 `DomainError` 攔截。

`ValidationError`（400）用於只能在 domain 邏輯*內部*才能評估的驗證 — 一個 Pydantic schema 層級檢查無法表達的業務規則不變量（例如「email 或 username 至少要有一個」，當兩者個別都是選填時；或是 value object 自己的不變量，例如 `InvalidUrlHashError`）。如果你在某個 route body 的 `try`/`except` 內手動建構一個 Pydantic model（不是透過 route 自己的參數型別），並 catch 它的 `ValidationError`，那仍然是 domain 層的事情 — 應該轉換成 `shared.domain.exceptions.ValidationError`，而不是自己手刻一個 422。

## 5. 外部依賴失敗

`ResilientLLMService` 和 `ResilientMetricsService` 會走過一個有序的 provider fallback chain，當所有 provider 都耗盡時回傳 `None` — 這是刻意設計、且已經過測試的韌性機制。本文件不要求改變這個 contract。

如果某個呼叫端把這個 `None` 視為需要回應錯誤的不可復原失敗，應該在該呼叫端（而非 resilient service 內部）把它轉換成 `ExternalDependencyError`。對於尚未開始串流的 request，這會經過中央 handler → 502。對於已經開始串流的 response（例如 Server-Sent Events、HTTP 狀態碼已經以 200 提交），應該改用 [Error Response contract](/specs/017-exception-handling-guideline/contracts/error-response) 同一套 `error.code`/`error.message` 詞彙、以 in-band 方式標示失敗，而不是用狀態碼 — 參考 `backend/routers/chat.py` 的 `generate()` 作為範例實作。

## 6. Response 格式

`backend/` 所有非 2xx response 都使用同一種格式：

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Topic 3fae... was not found",
    "request_id": "b6b2b6b2-....-...."
  }
}
```

`request_id` 不是新機制 — 它就是 `RequestLoggingMiddleware` 本來就會為每個 request 產生、並設成 `X-Request-ID` header 的同一個 UUID；handler 只是從 request 的 structlog context 讀回來，而不是另外產生第二個 ID。對於 500/502 response，`error.message` 一律是每個分類固定的通用字串 — 絕不會是例外本身的文字、stack trace、檔案路徑、或原始 SQL — 而真正的細節仍然會寫進結構化 log 與 Sentry（`sentry_sdk.capture_exception`）。

完整的分類 → 狀態碼對照表見 `specs/017-exception-handling-guideline/data-model.md`，`router-audit.md` 記錄了 `backend/routers/` 每個既有 endpoint 是如何被調整成符合這份指引的。
