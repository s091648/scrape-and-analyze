import { defineRailway, github, postgres, preserve, project, redis, service, volume } from "railway/iac";

export default defineRailway(() => {
  const scrapeAndAnalyze = github("s091648/scrape-and-analyze", { branch: "master", checkSuites: false, rootDirectory: "/" });
  const scrapeAndAnalyze2 = github("s091648/scrape-and-analyze", { branch: "master", rootDirectory: "/" });
  const scrapeAndAnalyze3 = github("s091648/scrape-and-analyze", { branch: "master", rootDirectory: "/frontend" });

  const Redis = redis("Redis", { region: "asia-southeast1-eqsg3a" });
  Redis.deploy = { startCommand: "/bin/sh -c \"rm -rf $RAILWAY_VOLUME_MOUNT_PATH/lost+found/ && exec docker-entrypoint.sh redis-server --requirepass $REDIS_PASSWORD --save 60 1 --dir $RAILWAY_VOLUME_MOUNT_PATH --maxmemory 256mb --maxmemory-policy volatile-lru\"" };
  const Postgres = postgres("Postgres", { region: "asia-southeast1-eqsg3a" });
  const redisVolume = volume("redis-volume", { alerts: { usage: { "100": {}, "80": {}, "95": {} } }, allowOnlineResize: true, region: "asia-southeast1-eqsg3a", sizeMB: 5000 });
  const postgresVolume = volume("postgres-volume", { alerts: { usage: { "100": {}, "80": {}, "95": {} } }, allowOnlineResize: true, region: "asia-southeast1-eqsg3a", sizeMB: 5000 });
  const weeklyReport = service("weekly report", {
    source: scrapeAndAnalyze2,
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "/src/Dockerfile" },
    start: "/app/.venv/bin/python -m src.entrypoints.cli.weekly_report",
    replicas: { "asia-southeast1-eqsg3a": 1 },
    deploy: { cronSchedule: "0 0 1 1 1", restartPolicyType: "NEVER" },
    networking: { privateNetworkEndpoint: "weekly-report" },
    env: { APP_ENV: preserve(), CACHE_REDIS_URL: preserve(), CONTACT_EMAIL: preserve(), DATABASE_URL: preserve(), FRONTEND_ORIGIN: preserve(), GEMINI_API_KEY: preserve(), GRAFANA_API_KEY: preserve(), GRAFANA_LOKI_URL: preserve(), GRAFANA_LOKI_USER: preserve(), GRAFANA_OTLP_ENDPOINT: preserve(), GRAFANA_OTLP_USER: preserve(), HF_TOKEN: preserve(), OPENROUTER_API_KEY: preserve(), R2_ACCESS_KEY_ID: preserve(), R2_ACCOUNT_ID: preserve(), R2_BUCKET_NAME: preserve(), R2_PUBLIC_URL: preserve(), R2_SECRET_ACCESS_KEY: preserve(), RESEND_API_KEY: preserve(), RESEND_FROM_EMAIL: preserve(), SENTRY_DSN: preserve(), TELEGRAM_BOT_TOKEN: preserve(), TELEGRAM_CHAT_ID: preserve(), UV_GROUP: preserve() },
  });
  const dedup_reconcile = service("dedup_reconcile", {
    source: scrapeAndAnalyze,
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "/src/Dockerfile" },
    start: "/app/.venv/bin/python -m src.entrypoints.cli.dedup_reconcile",
    replicas: { "asia-southeast1-eqsg3a": 1 },
    deploy: { cronSchedule: "0 0 1 1 1", restartPolicyType: "NEVER" },
    networking: { privateNetworkEndpoint: "dedupreconcile" },
    env: { APP_ENV: preserve(), CONTACT_EMAIL: preserve(), DATABASE_URL: preserve(), GRAFANA_API_KEY: preserve(), GRAFANA_LOKI_URL: preserve(), GRAFANA_LOKI_USER: preserve(), GRAFANA_OTLP_ENDPOINT: preserve(), GRAFANA_OTLP_USER: preserve(), SENTRY_DSN: preserve(), TELEGRAM_BOT_TOKEN: preserve(), TELEGRAM_CHAT_ID: preserve(), UV_GROUP: preserve() },
  });
  const storybookUI = service("storybook UI", {
    source: scrapeAndAnalyze3,
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "/frontend/Dockerfile.storybook" },
    replicas: { "asia-southeast1-eqsg3a": 1 },
    networking: { privateNetworkEndpoint: "satisfied-luck" },
    env: { GITHUB_PACKAGE_TOKEN: preserve() },
  });
  const dashboardFrontend = service("dashboard-frontend", {
    source: scrapeAndAnalyze3,
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "/frontend/Dockerfile" },
    replicas: { "asia-southeast1-eqsg3a": 1 },
    env: { APP_ENV: preserve(), BACKEND_URL: preserve(), CHAT_SERVICE_API_KEY: preserve(), CHAT_SERVICE_URL: preserve(), GITHUB_PACKAGE_TOKEN: preserve(), GOOGLE_CLIENT_ID: preserve(), GOOGLE_CLIENT_SECRET: preserve(), GRAFANA_SA_TOKEN: preserve(), GRAFANA_URL: preserve(), NEXTAUTH_SECRET: preserve(), NEXTAUTH_URL: preserve() },
  });
  const scrapeAndAnalyze = service("scrape-and-analyze", {
    source: scrapeAndAnalyze2,
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "/src/Dockerfile" },
    replicas: { "asia-southeast1-eqsg3a": 1 },
    deploy: { cronSchedule: "0 0 1 1 1", restartPolicyType: "NEVER" },
    env: { APP_ENV: preserve(), CACHE_REDIS_URL: preserve(), CONTACT_EMAIL: preserve(), DATABASE_URL: preserve(), GEMINI_API_KEY: preserve(), GITHUB_PACKAGE_TOKEN: preserve(), GRAFANA_API_KEY: preserve(), GRAFANA_LOKI_URL: preserve(), GRAFANA_LOKI_USER: preserve(), GRAFANA_OTLP_ENDPOINT: preserve(), GRAFANA_OTLP_USER: preserve(), OPENROUTER_API_KEY: preserve(), RAG_CHUNK_OVERLAP: preserve(), RAG_CHUNK_SIZE: preserve(), RAG_DENSE_API_KEY_ENV: preserve(), RAG_DENSE_DIMENSION: preserve(), RAG_DENSE_MODEL: preserve(), RAG_DENSE_PROVIDER: preserve(), RAG_DENSE_RPD: preserve(), RAG_DENSE_RPM: preserve(), RAG_DENSE_TPM: preserve(), RAG_EMBED_BATCH_SIZE: preserve(), RAG_GEMINI_API_KEY: preserve(), RAG_SPARSE_DIMENSION: preserve(), RAG_SPARSE_ENDPOINT_URL: preserve(), RAG_SPARSE_MODEL: preserve(), RAG_SPARSE_PROVIDER: preserve(), SEARCH_AUTOCOMPLETE_MAX_QUERY_LEN: preserve(), SEARCH_INDEX_REDIS_URL: preserve(), SEARCH_MIN_DOC_FREQ: preserve(), SENTRY_DSN: preserve(), TELEGRAM_BOT_TOKEN: preserve(), TELEGRAM_CHAT_ID: preserve(), VECTOR_DB_HOST: preserve(), VECTOR_DB_NAME: preserve(), VECTOR_DB_PASSWORD: preserve(), VECTOR_DB_PORT: preserve(), VECTOR_DB_SCHEMA: preserve(), VECTOR_DB_USER: preserve() },
  });
  const refreshMetrics = service("refresh metrics", {
    source: scrapeAndAnalyze2,
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "/src/Dockerfile" },
    start: "/app/.venv/bin/python -m src.entrypoints.cli.refresh_metrics",
    replicas: { "asia-southeast1-eqsg3a": 1 },
    deploy: { cronSchedule: "0 0 1 1 1", restartPolicyType: "NEVER" },
    networking: { privateNetworkEndpoint: "refresh-metrics" },
    env: { APP_ENV: preserve(), CONTACT_EMAIL: preserve(), DATABASE_URL: preserve(), GRAFANA_API_KEY: preserve(), GRAFANA_LOKI_URL: preserve(), GRAFANA_LOKI_USER: preserve(), GRAFANA_OTLP_ENDPOINT: preserve(), GRAFANA_OTLP_USER: preserve(), SENTRY_DSN: preserve(), TELEGRAM_BOT_TOKEN: preserve(), TELEGRAM_CHAT_ID: preserve(), UV_GROUP: preserve() },
  });
  const fastembed = service("fastembed", {
    source: scrapeAndAnalyze,
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "fastembed/Dockerfile" },
    replicas: { "asia-southeast1-eqsg3a": 1 },
    env: { APP_ENV: preserve(), GRAFANA_API_KEY: preserve(), GRAFANA_LOKI_URL: preserve(), GRAFANA_LOKI_USER: preserve(), GRAFANA_OTLP_ENDPOINT: preserve(), GRAFANA_OTLP_USER: preserve() },
  });
  const dashboardBackend = service("dashboard-backend", {
    source: scrapeAndAnalyze2,
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "/backend/Dockerfile" },
    start: ".venv/bin/uvicorn backend.main:app --host :: --port 8000",
    replicas: { "asia-southeast1-eqsg3a": 1 },
    networking: { privateNetworkEndpoint: "dashboard-backend2" },
    env: { APP_ENV: preserve(), CACHE_REDIS_URL: preserve(), CHAT_SERVICE_API_KEY: preserve(), CHAT_SERVICE_URL: preserve(), DATABASE_URL: preserve(), FRONTEND_ORIGIN: preserve(), GEMINI_API_KEY: preserve(), GRAFANA_API_KEY: preserve(), GRAFANA_LOKI_URL: preserve(), GRAFANA_LOKI_USER: preserve(), GRAFANA_OTLP_ENDPOINT: preserve(), GRAFANA_OTLP_USER: preserve(), GRAFANA_PROMETHEUS_URL: preserve(), GRAFANA_PROMETHEUS_USER: preserve(), GRAFANA_TEMPO_URL: preserve(), GRAFANA_TEMPO_USER: preserve(), MAXMIND_LICENSE_KEY: preserve(), NEXTAUTH_SECRET: preserve(), RAG_DENSE_API_KEY_ENV: preserve(), RAG_DENSE_DIMENSION: preserve(), RAG_DENSE_MODEL: preserve(), RAG_DENSE_PROVIDER: preserve(), RAG_DENSE_RPD: preserve(), RAG_DENSE_RPM: preserve(), RAG_DENSE_TPM: preserve(), RAG_GEMINI_API_KEY: preserve(), RAG_SPARSE_DIMENSION: preserve(), RAG_SPARSE_ENDPOINT_URL: preserve(), RAG_SPARSE_MODEL: preserve(), RAG_SPARSE_PROVIDER: preserve(), REDIS_URL: preserve(), SEARCH_INDEX_REDIS_URL: preserve(), SENTRY_DSN: preserve(), SWAGGER_TRY_IT_OUT_ENABLED: preserve() },
  });
  const chatbotPlugin = service("chatbot-plugin", {
    source: github("s091648/chatbot-plugin", { branch: "master" }),
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "/Dockerfile" },
    replicas: { "asia-southeast1-eqsg3a": 1 },
    env: { APP_ENV: preserve(), CHATBOT_MAX_TOKENS: preserve(), GEMINI_API_KEY: preserve(), GRAFANA_API_KEY: preserve(), GRAFANA_LOKI_URL: preserve(), GRAFANA_LOKI_USER: preserve(), GRAFANA_OTLP_ENDPOINT: preserve(), GRAFANA_OTLP_USER: preserve(), RAG_DENSE_API_KEY_ENV: preserve(), RAG_DENSE_DIMENSION: preserve(), RAG_DENSE_MODEL: preserve(), RAG_DENSE_PROVIDER: preserve(), RAG_DENSE_RPD: preserve(), RAG_DENSE_RPM: preserve(), RAG_DENSE_TPM: preserve(), RAG_GEMINI_API_KEY: preserve(), RAG_SPARSE_DIMENSION: preserve(), RAG_SPARSE_ENDPOINT_URL: preserve(), RAG_SPARSE_MODEL: preserve(), RAG_SPARSE_PROVIDER: preserve(), VECTOR_DB_HOST: preserve(), VECTOR_DB_NAME: preserve(), VECTOR_DB_PASSWORD: preserve(), VECTOR_DB_PORT: preserve(), VECTOR_DB_SCHEMA: preserve(), VECTOR_DB_USER: preserve() },
  });
  const backfill_rag = service("backfill_rag", {
    source: scrapeAndAnalyze2,
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "/src/Dockerfile" },
    start: "/app/.venv/bin/python -m src.entrypoints.cli.backfill_rag --limit 3",
    replicas: { "asia-southeast1-eqsg3a": 1 },
    deploy: { cronSchedule: "0 0 1 1 1", restartPolicyType: "NEVER" },
    networking: { privateNetworkEndpoint: "ragbackfill" },
    env: { APP_ENV: preserve(), CONTACT_EMAIL: preserve(), DATABASE_URL: preserve(), GITHUB_PACKAGE_TOKEN: preserve(), GRAFANA_API_KEY: preserve(), GRAFANA_LOKI_URL: preserve(), GRAFANA_LOKI_USER: preserve(), GRAFANA_OTLP_ENDPOINT: preserve(), GRAFANA_OTLP_USER: preserve(), OPENROUTER_API_KEY: preserve(), RAG_CHUNK_OVERLAP: preserve(), RAG_CHUNK_SIZE: preserve(), RAG_DENSE_API_KEY_ENV: preserve(), RAG_DENSE_DIMENSION: preserve(), RAG_DENSE_MODEL: preserve(), RAG_DENSE_PROVIDER: preserve(), RAG_DENSE_RPD: preserve(), RAG_DENSE_RPM: preserve(), RAG_DENSE_TPM: preserve(), RAG_EMBED_BATCH_SIZE: preserve(), RAG_GEMINI_API_KEY: preserve(), RAG_SPARSE_DIMENSION: preserve(), RAG_SPARSE_ENDPOINT_URL: preserve(), RAG_SPARSE_MODEL: preserve(), RAG_SPARSE_PROVIDER: preserve(), SENTRY_DSN: preserve(), TELEGRAM_BOT_TOKEN: preserve(), TELEGRAM_CHAT_ID: preserve(), UV_GROUP: preserve(), VECTOR_DB_HOST: preserve(), VECTOR_DB_NAME: preserve(), VECTOR_DB_PASSWORD: preserve(), VECTOR_DB_PORT: preserve(), VECTOR_DB_SCHEMA: preserve(), VECTOR_DB_USER: preserve() },
  });

  return project("scraper", {
    resources: [weeklyReport, dedup_reconcile, storybookUI, dashboardFrontend, scrapeAndAnalyze, refreshMetrics, Redis, Postgres, fastembed, dashboardBackend, chatbotPlugin, backfill_rag, redisVolume, postgresVolume],
  });
});
