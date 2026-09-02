/**
 * Railway Infrastructure as Code — 025-iac-provisioning "Revision 6".
 * Replaces railway.toml / src/railway-<svc>.toml (deprecated by Railway,
 * hard cutoff 2026-12-01) AND scripts/push_railway_variables.py +
 * railway-services.json.
 *
 * ── v1 (this file): FAITHFUL REPRODUCTION ──────────────────────────────────
 * Merges `railway config pull` from staging + production into one ctx-aware
 * file. Every service `env` var is preserve() — i.e. its value is left exactly
 * as Railway currently has it, NOT managed here yet. Only build config, start
 * commands, networking, replicas, and the handful of genuine staging↔production
 * differences (volume name, cron schedules, backfill_rag `--limit`) are
 * expressed. Goal: `railway config plan` shows 0 changes for BOTH environments.
 *
 * ── v2 (later) ────────────────────────────────────────────────────────────
 * Move each non-secret var to a real literal in `.railway/constants.ts`, each
 * secret to `process.env.X` (injected at `railway config apply` time from the
 * GitHub Actions secrets that `.github/workflows/*` already carry), and each
 * `${{Redis/Postgres.*}}` reference to `Redis.env.* / Postgres.env.*`. One
 * group at a time, `plan`-verified.
 *
 * ── REVIEW markers ────────────────────────────────────────────────────────
 * `// REVIEW:` flags a spot where the two environments disagree in a way that
 * looks like unintentional drift rather than deliberate config. v1 reproduces
 * current reality; decide whether to normalise once `plan` output is in hand.
 */
import {
  defineRailway,
  github,
  postgres,
  preserve,
  project,
  redis,
  service,
  volume,
} from "railway/iac";
import {
  CONTACT_EMAIL,
  GRAFANA_BACKEND_ENV,
  GRAFANA_ENV,
  GRAFANA_URL,
  RAG_CHUNKING_ENV,
  RAG_DENSE_ENV,
  RAG_SPARSE_ENV,
  VECTOR_DB_SCHEMA,
} from "./constants.ts";

type EnvMap = Record<string, ReturnType<typeof preserve>>;
const preserveAll = (...keys: string[]): EnvMap =>
  Object.fromEntries(keys.map((k) => [k, preserve()]));

// Shared env-var GROUPS — v1 lists names only (all preserve()). v2 turns these
// into real values (non-secret, in ./constants.ts) / process.env.* (secret) one
// group at a time, `plan`-verified.
// T6-08a de-preserve()d the non-secret values into ./constants.ts:
//   RAG_DENSE_ENV / RAG_SPARSE_ENV / RAG_CHUNKING_ENV  (RAG tuning)
//   GRAFANA_ENV / GRAFANA_BACKEND_ENV / GRAFANA_URL     (observability endpoints)
//   CONTACT_EMAIL / VECTOR_DB_SCHEMA / appEnv           (misc)
// Still preserve()d here: GRAFANA_API_KEY / GRAFANA_SA_TOKEN / RAG_GEMINI_API_KEY
// (secrets → T6-08c), RAG_SPARSE_ENDPOINT_URL + the VECTOR_DB Postgres refs
// (cross-service refs → T6-08b), and the production-only groups below.
const GRAFANA_PRESERVED = ["GRAFANA_API_KEY"];
const RAG_DENSE_PRESERVED = ["RAG_GEMINI_API_KEY"];
const RAG_SPARSE_PRESERVED = ["RAG_SPARSE_ENDPOINT_URL"];
// Currently set on production only (scrape-and-analyze / dashboard-backend / backfill_rag).
const RAG_SPARSE_LIMITS = ["RAG_SPARSE_RPD", "RAG_SPARSE_RPM", "RAG_SPARSE_TPM"];
const RAG_DENSE_ENDPOINT = ["RAG_DENSE_ENDPOINT_URL"]; // production only
// VECTOR_DB_SCHEMA is a de-preserve()d literal (constants.ts); the other five are
// ${{Postgres.*}} refs still preserve()d until T6-08b.
const VECTOR_DB_PRESERVED = [
  "VECTOR_DB_HOST", "VECTOR_DB_NAME", "VECTOR_DB_PASSWORD", "VECTOR_DB_PORT",
  "VECTOR_DB_USER",
];
const NOTIFICATIONS = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]; // FIXIE_URL is production-only, added per service

export default defineRailway((ctx) => {
  const prod = ctx.environment === "production";
  const region = "asia-southeast1-eqsg3a";
  const replicas = { [region]: 1 };

  // The one genuinely environment-specific non-secret value.
  const appEnv = { APP_ENV: prod ? "production" : "staging" };
  // Grafana core endpoints + the still-preserve()d API key, in one spread.
  const grafana = { ...preserveAll(...GRAFANA_PRESERVED), ...GRAFANA_ENV };

  // GitHub sources. Monorepo `s091648/scrape-and-analyze` at two roots, plus the
  // separate chatbot-plugin repo. (The raw pull emitted 3 near-duplicate
  // bindings per environment with inconsistent `branch`/`checkSuites` — these
  // are the canonical two + one.)
  const srcRepo = github("s091648/scrape-and-analyze", { branch: "master", rootDirectory: "/" });
  const frontendRepo = github("s091648/scrape-and-analyze", { branch: "master", rootDirectory: "/frontend" });
  const chatbotRepo = github("s091648/chatbot-plugin", { branch: "master" });

  const df = (dockerfilePath: string) =>
    ({ buildEnvironment: "V3", builder: "DOCKERFILE" as const, dockerfilePath });

  // ── Managed databases — FR-014: these stay MANUALLY managed. Declared here
  //    only so the whole-project `railway config` does not propose deleting
  //    them; nothing about them is managed. If `railway config plan` shows ANY
  //    change to Redis / Postgres / the volumes, STOP and pull them out of
  //    `resources` — do not apply. ────────────────────────────────────────────
  const Redis = redis("Redis", { region });
  Redis.deploy = {
    startCommand:
      '/bin/sh -c "rm -rf $RAILWAY_VOLUME_MOUNT_PATH/lost+found/ && exec docker-entrypoint.sh redis-server --requirepass $REDIS_PASSWORD --save 60 1 --dir $RAILWAY_VOLUME_MOUNT_PATH --maxmemory 256mb --maxmemory-policy volatile-lru"',
  };
  const Postgres = postgres("Postgres", { region });
  // Live Postgres carries no image pin (source: null); the `postgres()` helper
  // injects `ghcr.io/railwayapp-templates/postgres-ssl:18` by default, which
  // `plan` then wants to write onto the DB. Null it back out to match live —
  // FR-014 keeps managed databases hands-off. (Live Redis *is* pinned to
  // railwayapp/redis:8.2, which equals the helper default, so it needs nothing.)
  Postgres.source = null;
  const volAlerts = { usage: { "80": {}, "95": {}, "100": {} } };
  // REVIEW: the Redis volume has a different name per environment (a past recreate).
  const redisVolume = volume(prod ? "redis-volume-t232" : "redis-volume", {
    region, sizeMB: 5000, allowOnlineResize: true, alerts: volAlerts,
  });
  const postgresVolume = volume("postgres-volume", {
    region, sizeMB: 5000, allowOnlineResize: true, alerts: volAlerts,
  });

  // Cron: staging keeps "0 0 1 1 1" (an effectively-never placeholder — staging
  // services are torn down / revived per-PR); production runs the real schedule.
  const cron = (real: string) => (prod ? real : "0 0 1 1 1");

  const weeklyReport = service("weekly report", {
    source: srcRepo,
    build: df("/src/Dockerfile"),
    start: "/app/.venv/bin/python -m src.entrypoints.cli.weekly_report",
    replicas,
    deploy: { cronSchedule: cron("0 0 * * 1"), restartPolicyType: "NEVER" },
    networking: { privateNetworkEndpoint: "weekly-report" },
    env: {
      ...appEnv,
      CONTACT_EMAIL,
      ...preserveAll(
        "CACHE_REDIS_URL", "DATABASE_URL",
        "FRONTEND_ORIGIN", "GEMINI_API_KEY", "HF_TOKEN", "OPENROUTER_API_KEY",
        "R2_ACCESS_KEY_ID", "R2_ACCOUNT_ID", "R2_BUCKET_NAME", "R2_PUBLIC_URL",
        "R2_SECRET_ACCESS_KEY", "RESEND_API_KEY", "RESEND_FROM_EMAIL",
        "SENTRY_DSN", "UV_GROUP",
      ),
      ...grafana,
      ...preserveAll(...NOTIFICATIONS),
      ...(prod ? preserveAll("FIXIE_URL") : {}),
    },
  });

  const dedupReconcile = service("dedup_reconcile", {
    source: srcRepo,
    build: df("/src/Dockerfile"),
    start: "/app/.venv/bin/python -m src.entrypoints.cli.dedup_reconcile",
    replicas,
    deploy: { cronSchedule: cron("0 20 * * *"), restartPolicyType: "NEVER" },
    networking: { privateNetworkEndpoint: "dedupreconcile" },
    env: {
      ...appEnv,
      CONTACT_EMAIL,
      ...preserveAll("DATABASE_URL", "SENTRY_DSN", "UV_GROUP"),
      ...grafana,
      ...preserveAll(...NOTIFICATIONS),
      ...(prod ? preserveAll("FIXIE_URL") : {}),
    },
  });

  const storybookUI = service("storybook UI", {
    source: frontendRepo,
    build: df("/frontend/Dockerfile.storybook"),
    replicas,
    networking: { privateNetworkEndpoint: "satisfied-luck" },
    env: preserveAll("GITHUB_PACKAGE_TOKEN"),
  });

  const dashboardFrontend = service("dashboard-frontend", {
    source: frontendRepo,
    build: df("/frontend/Dockerfile"),
    replicas,
    env: {
      ...appEnv,
      GRAFANA_URL,
      ...preserveAll(
        "BACKEND_URL", "CHAT_SERVICE_API_KEY", "CHAT_SERVICE_URL",
        "GITHUB_PACKAGE_TOKEN", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
        "GRAFANA_SA_TOKEN", "NEXTAUTH_SECRET", "NEXTAUTH_URL",
      ),
    },
  });

  const scrapeAndAnalyze = service("scrape-and-analyze", {
    source: srcRepo,
    build: df("/src/Dockerfile"),
    replicas,
    deploy: { cronSchedule: cron("0 8 * * *"), restartPolicyType: "NEVER" },
    env: {
      ...appEnv,
      CONTACT_EMAIL,
      VECTOR_DB_SCHEMA,
      ...preserveAll(
        "CACHE_REDIS_URL", "DATABASE_URL",
        "GEMINI_API_KEY", "GITHUB_PACKAGE_TOKEN", "OPENROUTER_API_KEY", "SENTRY_DSN",
      ),
      ...grafana,
      ...preserveAll(
        ...RAG_DENSE_PRESERVED, ...RAG_SPARSE_PRESERVED,
        ...VECTOR_DB_PRESERVED, ...NOTIFICATIONS,
      ),
      ...RAG_DENSE_ENV,
      ...RAG_SPARSE_ENV,
      ...RAG_CHUNKING_ENV,
      // REVIEW: these three are set on staging only today — production's
      // scrape-and-analyze has no SEARCH_* vars (likely drift; the rebuild-
      // search-index cron path needs SEARCH_INDEX_REDIS_URL).
      ...(prod ? {} : {
        SEARCH_AUTOCOMPLETE_MAX_QUERY_LEN: "8",
        SEARCH_MIN_DOC_FREQ: "2",
        ...preserveAll("SEARCH_INDEX_REDIS_URL"),
      }),
      ...(prod ? preserveAll("FIXIE_URL", ...RAG_DENSE_ENDPOINT, ...RAG_SPARSE_LIMITS) : {}),
    },
  });

  const refreshMetrics = service("refresh metrics", {
    source: srcRepo,
    build: df("/src/Dockerfile"),
    start: "/app/.venv/bin/python -m src.entrypoints.cli.refresh_metrics",
    replicas,
    // REVIEW: production's refresh-metrics currently has NO cronSchedule set
    // (staging has the "0 0 1 1 1" placeholder). Per src/railway-refresh-metrics
    // .toml the intended production schedule is "0 20 * * *" — confirm & set.
    deploy: prod
      ? { restartPolicyType: "NEVER" }
      : { cronSchedule: "0 0 1 1 1", restartPolicyType: "NEVER" },
    networking: { privateNetworkEndpoint: "refresh-metrics" },
    env: {
      ...appEnv,
      CONTACT_EMAIL,
      ...preserveAll("DATABASE_URL", "SENTRY_DSN", "UV_GROUP"),
      ...grafana,
      ...preserveAll(...NOTIFICATIONS),
      ...(prod ? preserveAll("FIXIE_URL") : {}),
    },
  });

  const fastembed = service("fastembed", {
    source: srcRepo,
    build: df("fastembed/Dockerfile"),
    replicas,
    env: { ...appEnv, ...grafana },
  });

  const dashboardBackend = service("dashboard-backend", {
    source: srcRepo,
    build: df("/backend/Dockerfile"),
    start: ".venv/bin/uvicorn backend.main:app --host :: --port 8000",
    replicas,
    networking: { privateNetworkEndpoint: "dashboard-backend2" },
    env: {
      ...appEnv,
      SWAGGER_TRY_IT_OUT_ENABLED: "false",
      ...preserveAll(
        "CACHE_REDIS_URL", "CHAT_SERVICE_API_KEY", "CHAT_SERVICE_URL",
        "DATABASE_URL", "FRONTEND_ORIGIN", "GEMINI_API_KEY", "MAXMIND_LICENSE_KEY",
        "NEXTAUTH_SECRET", "REDIS_URL", "SEARCH_INDEX_REDIS_URL", "SENTRY_DSN",
      ),
      ...grafana,
      ...GRAFANA_BACKEND_ENV,
      ...preserveAll(...RAG_DENSE_PRESERVED, ...RAG_SPARSE_PRESERVED),
      ...RAG_DENSE_ENV,
      ...RAG_SPARSE_ENV,
      ...(prod ? preserveAll(...RAG_DENSE_ENDPOINT, ...RAG_SPARSE_LIMITS) : {}),
    },
  });

  const chatbotPlugin = service("chatbot-plugin", {
    source: chatbotRepo,
    build: df("/Dockerfile"),
    replicas,
    env: {
      ...appEnv,
      CHATBOT_MAX_TOKENS: "8192",
      VECTOR_DB_SCHEMA,
      ...preserveAll(
        "GEMINI_API_KEY",
        ...RAG_DENSE_PRESERVED, ...RAG_SPARSE_PRESERVED, ...VECTOR_DB_PRESERVED,
      ),
      ...grafana,
      ...RAG_DENSE_ENV,
      ...RAG_SPARSE_ENV,
    },
  });

  const backfillRag = service("backfill_rag", {
    source: srcRepo,
    build: df("/src/Dockerfile"),
    // REVIEW: staging pins `--limit 3`, production runs unbounded.
    start: prod
      ? "/app/.venv/bin/python -m src.entrypoints.cli.backfill_rag"
      : "/app/.venv/bin/python -m src.entrypoints.cli.backfill_rag --limit 3",
    replicas,
    deploy: { cronSchedule: cron("0 20 * * *"), restartPolicyType: "NEVER" },
    networking: { privateNetworkEndpoint: "ragbackfill" },
    env: {
      ...appEnv,
      CONTACT_EMAIL,
      VECTOR_DB_SCHEMA,
      ...preserveAll(
        "DATABASE_URL", "GITHUB_PACKAGE_TOKEN",
        "OPENROUTER_API_KEY", "SENTRY_DSN", "UV_GROUP",
      ),
      ...grafana,
      ...preserveAll(
        ...RAG_DENSE_PRESERVED, ...RAG_SPARSE_PRESERVED,
        ...VECTOR_DB_PRESERVED, ...NOTIFICATIONS,
      ),
      ...RAG_DENSE_ENV,
      ...RAG_SPARSE_ENV,
      ...RAG_CHUNKING_ENV,
      ...(prod ? preserveAll("FIXIE_URL", ...RAG_DENSE_ENDPOINT, ...RAG_SPARSE_LIMITS) : {}),
    },
  });

  return project("scraper", {
    resources: [
      Redis, Postgres, redisVolume, postgresVolume,
      weeklyReport, dedupReconcile, storybookUI, dashboardFrontend,
      scrapeAndAnalyze, refreshMetrics, fastembed, dashboardBackend,
      chatbotPlugin, backfillRag,
    ],
  });
});
