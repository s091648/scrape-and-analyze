# Contract: Semantic Scholar Academic Graph API

**Type**: External API（consumed by this system）
**Version**: v1 | **Date**: 2026-06-04

## Endpoint

```
GET https://api.semanticscholar.org/graph/v1/paper/search
```

## Request

### Headers

| Header | Required | Value |
|--------|----------|-------|
| `x-api-key` | Optional | Semantic Scholar API key（env: `SEMANTIC_SCHOLAR_API_KEY`）|

### Query Parameters

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `query` | Yes | string | Keyword search against title + abstract |
| `fields` | Yes | string | Comma-separated field names to return |
| `limit` | No | int | Max results per page（default 10, max 100）|
| `offset` | No | int | Pagination offset（default 0）|
| `sort` | No | string | `PublicationDate:desc` for newest-first |
| `publicationDateOrYear` | No | string | Year range, e.g. `2025-2026` or `2024-` |

### Fields used by this system

```
paperId,title,abstract,authors,publicationDate,year,
openAccessPdf,externalIds,isOpenAccess,citationCount
```

## Response

### Success（HTTP 200）

```json
{
  "total": 1234,
  "offset": 0,
  "next": 10,
  "data": [
    {
      "paperId": "string",
      "title": "string",
      "abstract": "string | null",
      "authors": [{"authorId": "string", "name": "string"}],
      "publicationDate": "YYYY-MM-DD | null",
      "year": 2025,
      "openAccessPdf": {
        "url": "https://...",
        "status": "GREEN | GOLD | BRONZE | HYBRID"
      },
      "externalIds": {
        "ArXiv": "NNNN.NNNNN | null",
        "DOI": "10.xxx/... | null",
        "PubMed": "string | null"
      },
      "isOpenAccess": true,
      "citationCount": 42
    }
  ]
}
```

### Error responses

| Status | Meaning | System behavior |
|--------|---------|-----------------|
| 400 | Bad request（invalid query）| Log error, return empty list |
| 429 | Rate limit exceeded | Log warning, return empty list（no retry） |
| 5xx | Server error | Log error, return empty list |

## Rate Limits

| Tier | Limit |
|------|-------|
| No API key | 1 request per second |
| With API key | Higher（see S2 documentation）|

## Notes

- `abstract` may be `null` for some papers — treat as empty string
- `openAccessPdf` is `null` when not open access — no PDF download attempted
- `publicationDate` is `null` when only year is known — fall back to `year`
- Paper URL normalization: use `https://arxiv.org/abs/{externalIds.ArXiv}` when ArXiv ID present; else `https://www.semanticscholar.org/paper/{paperId}`
