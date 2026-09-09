/**
 * Railway Infrastructure as Code — 025-iac-provisioning "Revision 6".
 * Replaces railway.toml / src/railway-<svc>.toml (deprecated by Railway,
 * hard cutoff 2026-12-01) AND scripts/push_railway_variables.py +
 * railway-services.json.
 *
 * ── How each env var's value is expressed ─────────────────────────────────
 *   - non-secret, fixed          → literal in ./constants.ts (T6-08a)
 *   - non-secret, env-specific   → a `ctx`-branch here (APP_ENV)
 *   - ${{Postgres.*}}/${{Redis.*}} single ref  → SDK ref, Postgres.env.* (T6-08b)
 *   - secret, or a ${{...}} interpolation string → need("X") — process.env.X,
 *     injected at `railway config plan|apply` by railway-config.yml's
 *     `scripts/tfvars_to_env.py` step from the TF_TFVARS_RAILWAY_* GitHub
 *     secrets (T6-08c). `need()` throws if unset, so a missing CI step fails
 *     loudly instead of pushing an empty value onto a live service.
 *   - still preserve()           → hand-managed on Railway (OPENROUTER_API_KEY,
 *     RESEND_*), or empty on this env (FIXIE_URL, RAG_DENSE_ENDPOINT_URL,
 *     RAG_SPARSE_*_limits) — Railway stores nothing for an empty var.
 *
 * Gate for every change: `railway config plan` shows 0 changes on BOTH
 * environments (run `scripts/tfvars_to_env.py --env <e>` into the process env
 * first so the need() reads resolve).
 *
 * `// REVIEW:` flags a spot where staging and production disagree in a way that
 * looks like unintentional drift; v2 reproduces current reality.
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
  ASYNC_DB_ENV,
  CACHE_REDIS_URL,
  CONTACT_EMAIL,
  GRAFANA_BACKEND_ENV,
  GRAFANA_ENV,
  GRAFANA_URL,
  RAG_CHUNKING_ENV,
  RAG_DENSE_ENV,
  RAG_SPARSE_ENV,
  SEARCH_INDEX_REDIS_URL,
  UV_GROUP,
  VECTOR_DB_SCHEMA,
} from "./constants.ts";

type EnvMap = Record<string, ReturnType<typeof preserve>>;
const preserveAll = (...keys: string[]): EnvMap =>
  Object.fromEntries(keys.map((k) => [k, preserve()]));

// Secret / ${{...}}-interpolation values — supplied via process.env by
// railway-config.yml's tfvars_to_env.py step (T6-08c). Throw rather than push an
// empty value if the step didn't run.
const need = (key: string): string => {
  const v = process.env[key];
  if (v === undefined || v === "") {
    throw new Error(
      `railway.ts: process.env.${key} is unset — run ` +
        `\`scripts/tfvars_to_env.py --env <env>\` into the environment before ` +
        `\`railway config\` (railway-config.yml does this in CI; T6-08c).`,
    );
  }
  return v;
};
const needAll = (...keys: string[]): Record<string, string> =>
  Object.fromEntries(keys.map((k) => [k, need(k)]));

// Still preserve()d groups: hand-managed on Railway, or empty on some/all envs
// (Railway stores nothing for an empty var).
const RAG_SPARSE_LIMITS = ["RAG_SPARSE_RPD", "RAG_SPARSE_RPM", "RAG_SPARSE_TPM"]; // production only, currently empty
const RAG_DENSE_ENDPOINT = ["RAG_DENSE_ENDPOINT_URL"]; // production only, currently empty

// T6-08e: NEXTAUTH_SECRET / GITHUB_PACKAGE_TOKEN / FRONTEND_ORIGIN / NEXTAUTH_URL
// were briefly held preserve() because production's live value had drifted from
// the tfvars (a placeholder NEXTAUTH_SECRET, an un-rotated GITHUB_PACKAGE_TOKEN,
// a bare-host FRONTEND_ORIGIN/NEXTAUTH_URL). Decision: the tfvars values ARE the
// intended ones — now managed via need() like the rest, so `railway config
// apply` corrects production. NOTE: the NEXTAUTH_SECRET change invalidates every
// existing production session on apply.

export default defineRailway((ctx) => {
  const prod = ctx.environment === "production";
  const region = "asia-southeast1-eqsg3a";
  const replicas = { [region]: 1 };

  // The one genuinely environment-specific non-secret value.
  const appEnv = { APP_ENV: prod ? "production" : "staging" };
  // Grafana: de-preserve()d endpoints (constants.ts) + the secret API key.
  const grafana = { ...GRAFANA_ENV, ...needAll("GRAFANA_API_KEY") };
  // Telegram bot creds (FIXIE_URL is production-only, added per service).
  const notifications = needAll("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID");
  // RAG values still needing process.env: the Gemini key (secret) + the
  // fastembed private-domain URL (a ${{...}} interpolation string).
  const ragSecrets = needAll("RAG_GEMINI_API_KEY", "RAG_SPARSE_ENDPOINT_URL");

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

  // T6-08b: single-value ${{Postgres.*}} / ${{Redis.*}} references as real SDK
  // refs (must come after the Postgres/Redis nodes above).
  const databaseUrl = { DATABASE_URL: Postgres.env.DATABASE_URL };
  const redisUrl = { REDIS_URL: Redis.env.REDIS_URL };
  const vectorDbRef = {
    VECTOR_DB_HOST: Postgres.env.PGHOST,
    VECTOR_DB_NAME: Postgres.env.PGDATABASE,
    VECTOR_DB_PASSWORD: Postgres.env.PGPASSWORD,
    VECTOR_DB_PORT: Postgres.env.PGPORT,
    VECTOR_DB_USER: Postgres.env.PGUSER,
  };

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
      CACHE_REDIS_URL,
      UV_GROUP: UV_GROUP.weekly_report,
      ...databaseUrl,
      ...grafana,
      ...notifications,
      ...needAll(
        "FRONTEND_ORIGIN", "GEMINI_API_KEY", "HF_TOKEN",
        "R2_ACCESS_KEY_ID", "R2_ACCOUNT_ID", "R2_BUCKET_NAME", "R2_PUBLIC_URL",
        "R2_SECRET_ACCESS_KEY", "SENTRY_DSN",
      ),
      // Hand-managed on Railway (see railway-services.json `unmanaged`).
      ...preserveAll("OPENROUTER_API_KEY", "RESEND_API_KEY", "RESEND_FROM_EMAIL"),
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
      UV_GROUP: UV_GROUP.dedup_reconcile,
      ...databaseUrl,
      ...grafana,
      ...notifications,
      ...needAll("SENTRY_DSN"),
      ...(prod ? preserveAll("FIXIE_URL") : {}),
    },
  });

  const storybookUI = service("storybook UI", {
    source: frontendRepo,
    build: df("/frontend/Dockerfile.storybook"),
    replicas,
    networking: { privateNetworkEndpoint: "satisfied-luck" },
    env: needAll("GITHUB_PACKAGE_TOKEN"),
  });

  const dashboardFrontend = service("dashboard-frontend", {
    source: frontendRepo,
    build: df("/frontend/Dockerfile"),
    replicas,
    env: {
      ...appEnv,
      GRAFANA_URL,
      ...needAll(
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
      CACHE_REDIS_URL,
      ...databaseUrl,
      ...vectorDbRef,
      ...grafana,
      ...notifications,
      ...ragSecrets,
      ...RAG_DENSE_ENV,
      ...RAG_SPARSE_ENV,
      ...RAG_CHUNKING_ENV,
      ...ASYNC_DB_ENV,
      ...needAll("GEMINI_API_KEY", "GITHUB_PACKAGE_TOKEN", "SENTRY_DSN"),
      ...preserveAll("OPENROUTER_API_KEY"), // hand-managed on Railway
      // REVIEW: SEARCH_* are set on staging only today — production's
      // scrape-and-analyze has no SEARCH_* vars (likely drift; the rebuild-
      // search-index cron path needs SEARCH_INDEX_REDIS_URL).
      ...(prod ? {} : {
        SEARCH_AUTOCOMPLETE_MAX_QUERY_LEN: "8",
        SEARCH_MIN_DOC_FREQ: "2",
        SEARCH_INDEX_REDIS_URL,
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
      UV_GROUP: UV_GROUP.refresh_metrics,
      ...databaseUrl,
      ...grafana,
      ...notifications,
      ...needAll("SENTRY_DSN"),
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
      CACHE_REDIS_URL,
      SEARCH_INDEX_REDIS_URL,
      ...databaseUrl,
      ...redisUrl,
      ...grafana,
      ...GRAFANA_BACKEND_ENV,
      ...ragSecrets,
      ...RAG_DENSE_ENV,
      ...RAG_SPARSE_ENV,
      ...needAll(
        "CHAT_SERVICE_API_KEY", "CHAT_SERVICE_URL",
        "FRONTEND_ORIGIN", "GEMINI_API_KEY", "MAXMIND_LICENSE_KEY",
        "NEXTAUTH_SECRET", "SENTRY_DSN",
      ),
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
      ...vectorDbRef,
      ...grafana,
      ...ragSecrets,
      ...RAG_DENSE_ENV,
      ...RAG_SPARSE_ENV,
      ...needAll("GEMINI_API_KEY"),
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
      UV_GROUP: UV_GROUP.rag_backfill,
      ...databaseUrl,
      ...vectorDbRef,
      ...grafana,
      ...notifications,
      ...ragSecrets,
      ...RAG_DENSE_ENV,
      ...RAG_SPARSE_ENV,
      ...RAG_CHUNKING_ENV,
      ...needAll("GITHUB_PACKAGE_TOKEN", "SENTRY_DSN"),
      ...preserveAll("OPENROUTER_API_KEY"), // hand-managed on Railway
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
