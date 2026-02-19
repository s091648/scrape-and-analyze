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


def log_execution_summary(
    total_articles: int,
    success_count: int,
    failure_count: int,
    duration_seconds: float,
    total_tokens: int = 0
) -> None:
    """Log execution summary metrics for monitoring dashboards"""
    logger = get_logger(__name__)
    logger.info(
        "execution_summary",
        total_articles=total_articles,
        success_count=success_count,
        failure_count=failure_count,
        duration_seconds=round(duration_seconds, 2),
        total_tokens=total_tokens,
        articles_per_second=round(total_articles / max(duration_seconds, 1), 2),
        success_rate=round(success_count / max(total_articles, 1) * 100, 1)
    )


def log_llm_metrics(
    article_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int
) -> None:
    """Log LLM metrics for cost monitoring and performance tracking"""
    logger = get_logger(__name__)
    logger.info(
        "llm_analysis_metrics",
        article_id=article_id,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        latency_ms=latency_ms
    )
