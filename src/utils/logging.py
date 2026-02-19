import structlog
from contextvars import ContextVar

correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='')


def bind_correlation_id(correlation_id: str) -> None:
    """Bind correlation_id to current context"""
    correlation_id_var.set(correlation_id)


def get_correlation_id() -> str:
    """Get current correlation_id"""
    return correlation_id_var.get()


def add_correlation_id(logger, method_name, event_dict):
    """Processor to add correlation_id to log events"""
    corr_id = correlation_id_var.get()
    if corr_id:
        event_dict['correlation_id'] = corr_id
    return event_dict


def configure_logging() -> None:
    """Configure structlog for JSON output"""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            add_correlation_id,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str):
    """Get configured structlog logger"""
    return structlog.get_logger(name)
