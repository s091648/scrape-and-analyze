# Phase 1 Data Model: SSR Conversion for Public Pages

No database or Redis schema changes. This feature introduces no new backend entities — it only relocates/adds *client-held* preference state so Server Components can read it, and defines one ephemeral, never-persisted server-side credential. Documented here for completeness since the spec's Key Entities section names both.

## Topic Preference (cookie)

Represents a visitor's last-selected topic/category filter.

| Field | Type | Notes |
|---|---|---|
| Cookie name | `selectedTopicId` | Same name as the existing `localStorage` key (`topic-provider.tsx:36`) — deliberately kept identical so both storages are easy to reason about as "the same value, two locations." |
| Value | Topic UUID (string) | Must match an `id` from `GET /topics`; if it doesn't (deleted/deactivated topic — see spec Edge Cases), the server-side render treats it as absent and falls back to the no-topic/first-active-topic default, same as a visitor with no cookie at all. |
| `SameSite` | `Lax` | Sent on top-level navigation from external links (shared `/articles?topic=...` URLs), not sent on cross-site subresource requests. |
| `Path` | `/` | Readable by every route that needs it (`/`, `/articles`, `/graph`, `/tags`). |
| Max-Age | 1 year | Long-lived preference, not a session value. |
| `httpOnly` | `false` | Client code must keep reading the same preference (see research.md). |
| Written by | `topic-provider.tsx`'s `setSelectedTopicId`, in addition to its existing `localStorage.setItem` call. | Additive — `localStorage` behavior is unchanged. |
| Read by | New `lib/server/ssr-fetch.ts` helpers, via `cookies()` (`next/headers`), during each of the 4 routes' server-side render. | Not read by any existing client code (client code continues reading its `TopicContext` state, which itself still initializes from `localStorage` as today). |

**Validation rule**: A cookie value that doesn't correspond to any topic returned by `GET /topics` (or that fails to parse as a UUID) MUST be treated identically to a missing cookie — never surfaced as an error.

## Language Preference (cookie)

Represents a visitor's last-resolved or last-chosen display language.

| Field | Type | Notes |
|---|---|---|
| Cookie name | `locale` | Same name as the existing `localStorage` key (`i18n-provider.tsx:55/66`). |
| Value | Locale code (e.g. `en`, `zh-TW`) | Must be one of `SUPPORTED_LANGUAGES` (`backend/services/language_service.py`); an unrecognized value falls back exactly like a missing cookie (server-side geo-IP resolution via `GET /languages`, per research.md). |
| `SameSite` | `Lax` | Same rationale as topic. |
| `Path` | `/` | Same rationale as topic. |
| Max-Age | 1 year | Same rationale as topic. |
| `httpOnly` | `false` | Same rationale as topic. |
| Written by | `i18n-provider.tsx`'s `setLocale`, in addition to its existing `localStorage.setItem` call; **also** written the first time a true first-ever visitor's language is resolved via geo-IP (client-side, once `I18nProvider`'s existing effect resolves `resolvedLanguage` — see `i18n-provider.tsx:46-62`), so their *second* page load already has a cookie instead of re-resolving via geo-IP every time. | Additive. |
| Read by | `lib/server/ssr-fetch.ts`, same as topic. | Not read by any existing client code. |

## Server-Side Credential (not a new entity — superseded during implementation)

The original design (see this file's earlier revisions) planned a one-time, ephemeral guest credential the server would obtain via `POST /auth/guest` for anonymous visitors. That plan was superseded during implementation (research.md, "Server-side credential resolution reuses session tokens only") once it became clear that would bypass the existing client-side paywall/guest-mode gate. There is now no server-issued credential of any kind for anonymous visitors — `SsrContext.credential` is simply the visitor's existing NextAuth session token (`session.accessToken`, already a real JWT once a session exists — no additional issuance step) or `null`. Nothing new is created, stored, or issued by this feature; this section is retained only to explain why it does not appear as an entity.
