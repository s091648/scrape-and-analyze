import asyncio
import models  # noqa: F401 — registers all ORM mappers at startup
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from backend.database import get_db, check_db_connection, SessionLocal
from backend.middleware.logging import RequestLoggingMiddleware
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
from backend.config import FRONTEND_ORIGIN, VIEW_COUNT_FLUSH_INTERVAL


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
    task = asyncio.create_task(_periodic_view_flush())
    yield
    task.cancel()


app = FastAPI(title="Article Analyzer API", version="1.0.0", lifespan=lifespan)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")


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


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    db_ok = check_db_connection(db)
    status_code = 200 if db_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok", "db": "ok" if db_ok else "error"}
    )
