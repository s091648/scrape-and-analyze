# Contract: SSR Preference Cookies

Defines the two new cookies this feature introduces, as a contract between client-side writers and the Server Component readers in `lib/server/ssr-fetch.ts`. See `data-model.md` for full field tables.

## `selectedTopicId`

- **Producers**: `frontend/lib/providers/topic-provider.tsx` (`setSelectedTopicId`).
- **Consumers**: `lib/server/ssr-fetch.ts`, read once per server render via `cookies().get('selectedTopicId')`.
- **Format**: raw UUID string, no JSON wrapping, no URL-encoding beyond what `Set-Cookie` requires by default.
- **Absence/invalidity handling**: consumer MUST treat a missing cookie, a malformed value, or a value not present in that render's `GET /topics` response identically — fall back to "no topic filter" or "first active topic" (matching today's client-side default logic in `topic-provider.tsx`'s `loadTopics`).
- **Attributes**: `Path=/; Max-Age=31536000; SameSite=Lax` (not `httpOnly`, not `Secure`-only in local dev — `Secure` should be set in production where the site is HTTPS-only).

## `locale`

- **Producers**: `frontend/lib/providers/i18n-provider.tsx` (`setLocale`, and the first-ever-resolution effect).
- **Consumers**: `lib/server/ssr-fetch.ts`, read once per server render via `cookies().get('locale')`.
- **Format**: raw locale code string (e.g. `en`, `zh-TW`), matching `SUPPORTED_LANGUAGES` in `backend/services/language_service.py`.
- **Absence/invalidity handling**: consumer MUST treat a missing cookie or an unsupported code identically — fall back to calling `GET /languages` server-side for geo-IP resolution (see `research.md`).
- **Attributes**: `Path=/; Max-Age=31536000; SameSite=Lax` (`Secure` in production, same as above).

## Compatibility

Both cookies are purely additive alongside the existing `localStorage` values of the same names — removing either cookie (e.g. a user clears cookies but not site data) degrades that one render to today's server-side default behavior; it does not affect the client-side `localStorage`-backed behavior at all, which is unchanged by this feature.
