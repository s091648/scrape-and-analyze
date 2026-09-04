import asyncio
import httpx
import models  # noqa: F401 — registers all ORM mappers at startup
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from backend.database import get_db, check_db_connection, SessionLocal
from backend.middleware.logging import RequestLoggingMiddleware
from backend.exceptions.handlers import register_exception_handlers
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from backend.routers.articles import router as articles_router
from backend.routers.graph import router as graph_router
from backend.routers.scraper_settings import router as scraper_settings_router
from backend.routers.auth import router as auth_router
from backend.routers.topics import router as topics_router
from backend.routers.scraper_keywords import router as scraper_keywords_router
from backend.routers.languages import router as languages_router
from backend.routers.tags import router as tags_router
from backend.routers.llm_providers import router as llm_providers_router
from backend.routers.grafana import router as grafana_router
from backend.routers.monitoring import router as monitoring_router
from backend.routers.chat import router as chat_router
from backend.routers.user import router as user_router
from backend.routers.weekly_reports import router as weekly_reports_router
from backend.routers.metric_definitions import router as metric_definitions_router
from backend.routers.bootstrap import router as bootstrap_router
from backend.routers.search import router as search_router
from backend.config import FRONTEND_ORIGIN, VIEW_COUNT_FLUSH_INTERVAL, SWAGGER_TRY_IT_OUT_ENABLED, SENTRY_DSN, APP_ENV, GEOIP_DB_PATH
from backend.schemas.error import error_responses
from backend.observability import configure_logging, setup_tracing
from shared.utils.geoip import configure as configure_geoip

if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(dsn=SENTRY_DSN, environment=APP_ENV, include_local_variables=False)

configure_logging(APP_ENV)
_tracer_provider = setup_tracing(APP_ENV)
configure_geoip(GEOIP_DB_PATH)


async def _periodic_view_flush():
    from backend.services.article_service import flush_view_counts
    while True:
        await asyncio.sleep(VIEW_COUNT_FLUSH_INTERVAL)
        db = SessionLocal()
        try:
            await flush_view_counts(db)
        except Exception:
            pass
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.cache_warmup_listener import listen_for_warmup_signals
    # Shared across every /chat/completions request (backend/routers/chat.py) so
    # each chat turn reuses a pooled connection to chatbot-plugin instead of
    # paying a fresh TCP/TLS handshake per request — see ChatCompletionService.
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=30.0, read=120.0, write=10.0, pool=10.0)
    )
    task = asyncio.create_task(_periodic_view_flush())
    warmup_task = asyncio.create_task(listen_for_warmup_signals())
    yield
    task.cancel()
    warmup_task.cancel()
    await app.state.http_client.aclose()
    if _tracer_provider:
        _tracer_provider.shutdown()


app = FastAPI(
    title="Article Analyzer API",
    version="1.0.0",
    lifespan=lifespan,
    swagger_ui_parameters=None if SWAGGER_TRY_IT_OUT_ENABLED else {"supportedSubmitMethods": []},
    responses=error_responses(500),
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

if _tracer_provider:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FastAPIInstrumentor.instrument_app(app, tracer_provider=_tracer_provider, excluded_urls="health")

register_exception_handlers(app)


app.include_router(articles_router)
app.include_router(graph_router)
app.include_router(scraper_settings_router)
app.include_router(auth_router)
app.include_router(topics_router)
app.include_router(scraper_keywords_router)
app.include_router(llm_providers_router)
app.include_router(languages_router)
app.include_router(tags_router)
app.include_router(grafana_router)
app.include_router(monitoring_router)
app.include_router(chat_router)
app.include_router(user_router)
app.include_router(weekly_reports_router)
app.include_router(metric_definitions_router)
app.include_router(bootstrap_router)
app.include_router(search_router)


@app.get("/health", tags=["health"])
def health_check(db: Session = Depends(get_db)):
    db_ok = check_db_connection(db)
    status_code = 200 if db_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok", "db": "ok" if db_ok else "error"}
    )
