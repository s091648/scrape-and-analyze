import structlog


def get_logger(name: str):
    """Return a structlog bound logger for *name*.

    configure_logging() must be called once at process startup (entrypoint)
    before any logger is used, so that Loki and other handlers are attached.
    """
    return structlog.get_logger(name)
