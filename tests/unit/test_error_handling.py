# record_failure was removed from src/main.py as part of the DDD migration.
# Error recording is now handled inside the use cases (ProcessArticleUseCase,
# AnalyzeArticleUseCase) via structured logging rather than a FailedTask row.
# Integration-level failure persistence is tested in tests/integration/.
