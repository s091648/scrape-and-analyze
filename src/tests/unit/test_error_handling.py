# record_failure was removed in the DDD migration.
# Error recording is handled inside use cases via structured logging.
# Integration-level failure persistence is tested in src/tests/integration/.