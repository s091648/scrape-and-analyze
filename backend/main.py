from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from backend.database import get_db, check_db_connection
from backend.middleware.logging import RequestLoggingMiddleware

app = FastAPI(title="Scrape Analyzer API", version="1.0.0")

app.add_middleware(RequestLoggingMiddleware)


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    db_ok = check_db_connection(db)
    status_code = 200 if db_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok", "db": "ok" if db_ok else "error"}
    )
