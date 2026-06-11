# Contract: Chat API

**Endpoint**: `POST /chat/completions`
**Router**: `backend/routers/chat.py`
**Frontend calls via**: `POST /api/proxy/chat/completions`（Next.js proxy 轉發）

---

## Request

### Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Content-Type` | Yes | `application/json` |
| `Authorization` | Optional | `Bearer {jwt}` — 登入用戶提供；guest 省略 |
| `X-Topic-Id` | Optional | Topic UUID，縮小 RAG 搜尋範圍；後端注入至轉發 body |

### Body（OpenAI-compatible ChatCompletion Request）

```json
{
  "messages": [
    { "role": "user", "content": "最近有哪些 LLM 效能研究？" },
    { "role": "assistant", "content": "根據最近的研究..." },
    { "role": "user", "content": "這些有什麼實際應用？" }
  ],
  "stream": true
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `messages` | `array` | Yes | 完整對話歷史（含本次問題），role 為 `user` / `assistant` |
| `stream` | `boolean` | Yes | 必須為 `true` |

`topic_id` 不由前端傳送，後端從 `X-Topic-Id` header 取值並注入轉發 body。

---

## Responses

### `200 OK` — OpenAI-compatible SSE Stream

```
Content-Type: text/event-stream
Cache-Control: no-cache

data: {"id":"chatcmpl-abc","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}

data: {"id":"chatcmpl-abc","choices":[{"index":0,"delta":{"content":"根據近期研究，"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc","choices":[{"index":0,"delta":{"content":"[文章標題](https://...)"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc","choices":[{"index":0,"delta":{"content":""},"finish_reason":"stop"}]}

data: [DONE]
```

引用來源以 markdown 超連結格式嵌在回答文字中，前端 `openaiAdapter`（package 內建）直接解析，無需自訂 `StreamAdapter`。

### `429 Too Many Requests` — Rate Limit Exceeded

```json
{
  "detail": "每日問答次數已達上限（訪客：3次/天）",
  "limit": 3,
  "reset_at": "2026-06-12T00:00:00+08:00"
}
```

### `503 Service Unavailable` — Chat Service 無法連線

```json
{
  "detail": "問答服務暫時無法使用，請稍後再試"
}
```

---

## Rate Limiting

| 身份 | 識別方式 | 每日上限 |
|------|---------|---------|
| Admin | JWT `role=admin` | 無限制（bypass Redis） |
| 登入用戶 | JWT `sub`（user_id） | 50 次/天 |
| 訪客（有 cookie） | `__rag_gid` cookie UUID | 3 次/天 |
| 訪客（無 cookie） | `hash(IP + User-Agent)` | 3 次/天 |

**Redis key pattern**:
- User: `rate:user:{user_id}:{YYYY-MM-DD}`
- Guest (cookie): `rate:guest:{cookie_uuid}:{YYYY-MM-DD}`
- Guest (IP fallback): `rate:guest:ip:{hash}:{YYYY-MM-DD}`

**TTL**: 86400 秒（每天午夜自動重置）

**Cookie（guest 首次請求時 set）**:
```
Set-Cookie: __rag_gid=<UUID v4>; HttpOnly; SameSite=Lax; Max-Age=31536000; Path=/
```

---

## Backend → External Chat Service 轉發

後端驗證 rate limit 後，將請求轉發至外部 Chat Service 並原樣 pipe SSE 回前端：

```
POST {CHAT_SERVICE_URL}/v1/chat/completions
Authorization: Bearer {CHAT_SERVICE_API_KEY}
Content-Type: application/json

{
  "messages": [...],       // 前端傳入，原樣轉發
  "stream": true,
  "topic_id": "..."        // 從 X-Topic-Id header 注入
}
```

Response 直接 pipe，不做任何格式轉換。

---

## Frontend Integration

```typescript
// FloatingChatbotWrapper.tsx / InlineQABarWrapper.tsx
const { messages, sendMessage, isLoading } = useChat({
  endpoint: '/api/proxy/chat/completions',
  streamAdapter: openaiAdapter,          // package 內建，解析 OpenAI SSE 格式
  initialMessages: loadSession(),        // 從 sessionStorage 恢復歷史
  headers: {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(topicId ? { 'X-Topic-Id': topicId } : {}),
  },
  onMessage: () => saveSession(messagesRef.current),
})
```

---

## Backend Router 資訊

| 屬性 | 值 |
|------|---|
| Router prefix | （無，直接掛在 app root） |
| Auth | Optional（從 JWT 取 role/user_id 決定 rate limit tier；無 JWT 為 guest） |
| OTel span | 需建立 `chat.completions` span，記錄 user identity tier 與 rate limit 結果 |
| Structured log | 記錄每次請求的 identity tier、rate limit counter、Chat Service 回應狀態 |
