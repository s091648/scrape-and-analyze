import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from backend.database import get_db, check_db_connection
from backend.middleware.logging import RequestLoggingMiddleware
from backend.routers.articles import router as articles_router
from backend.routers.graph import router as graph_router
from backend.routers.scraper_settings import router as scraper_settings_router

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")

app = FastAPI(title="Scrape Analyzer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)


app.include_router(articles_router)
app.include_router(graph_router)
app.include_router(scraper_settings_router)


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    db_ok = check_db_connection(db)
    status_code = 200 if db_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok", "db": "ok" if db_ok else "error"}
    )
