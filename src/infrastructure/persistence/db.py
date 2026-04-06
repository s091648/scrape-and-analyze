"""
Thin wrapper around src/database.py so infrastructure code can import
session/engine helpers without depending on the top-level module.
"""
from src.database import get_session, get_engine, init_db  # noqa: F401
