"""
Scraper's own continuous CPU profiling — pyroscope-io pushed to Grafana Cloud Profiles.
Mirrors backend/observability.py's setup_profiling()/to_thread_profiled() (fix/profiler_imprv):
backend/ can't import this module (src/ isn't copied into its production Docker image, see
backend/observability.py's own docstring), so this is a deliberate duplication, not a shared
import, same as otel_tracing.py mirrors backend's tracing setup.

No-op throughout if GRAFANA_PROFILES_*/GRAFANA_API_KEY are unset (local dev, tests).
"""
from typing import Callable, TypeVar

from src.config.settings import GRAFANA_API_KEY, GRAFANA_PROFILES_URL, GRAFANA_PROFILES_USER

T = TypeVar("T")

# Set only on setup_profiling()'s own successful pyroscope.configure() — run_tagged_for_profiling()
# checks this before ever touching pyroscope, so local dev / tests skip straight to calling
# `func` directly with no native-lib call at all, instead of relying on tag_wrapper() itself
# to fail gracefully.
_profiling_enabled = False


def setup_profiling(app_env: str) -> None:
    """Start pyroscope-io's background sampling profiler, pushing to Grafana Cloud Profiles.
    No-op if GRAFANA_PROFILES_*/GRAFANA_API_KEY are absent (local dev).

    Complements otel_tracing.py's setup_tracing() the same way backend/observability.py's own
    setup_profiling() complements its setup_tracing(): OTel spans say WHICH instrumented
    boundary (a fetch, a discover task) took the time; this says what the CPU was actually
    doing meanwhile. Unlike the backend (a persistent server whose profiling just runs
    forever), main.py is a finite process — pair this with shutdown_profiling() in its
    `finally` block so the last <upload_interval seconds of samples aren't silently dropped
    on exit."""
    if not all([GRAFANA_PROFILES_URL, GRAFANA_PROFILES_USER, GRAFANA_API_KEY]):
        print("[profiling] Skipping Pyroscope setup, missing GRAFANA_PROFILES_*/GRAFANA_API_KEY")
        return

    try:
        import pyroscope
        from shared.enums.observability import SERVICE_NAME

        pyroscope.configure(
            application_name=SERVICE_NAME,
            server_address=GRAFANA_PROFILES_URL,
            basic_auth_username=GRAFANA_PROFILES_USER,
            basic_auth_password=GRAFANA_API_KEY,
            tags={"env": app_env},
        )
        global _profiling_enabled
        _profiling_enabled = True
        print("[profiling] Pyroscope setup successful")
    except Exception as e:
        print(f"[profiling] Pyroscope setup failed: {e}")


def shutdown_profiling() -> None:
    """Flush and stop the background sampler before process exit. No-op if setup_profiling()
    never ran or never succeeded (mirrors shutdown_tracing()'s own guard shape)."""
    if not _profiling_enabled:
        return
    try:
        import pyroscope
        pyroscope.shutdown()
    except Exception as e:
        print(f"[profiling] Pyroscope shutdown failed: {e}")


def _current_span_tags() -> dict:
    """Best-effort `{"span_id": ...}` for the currently active OTel span. Empty outside a
    span or if tracing itself never initialized; never raises. Mirrors
    backend/observability.py's helper of the same name."""
    try:
        from opentelemetry import trace as _otel_trace
        ctx = _otel_trace.get_current_span().get_span_context()
        if ctx.is_valid:
            return {"span_id": format(ctx.span_id, "016x")}
    except Exception:
        pass
    return {}


def run_tagged_for_profiling(func: Callable[[], T]) -> T:
    """Calls `func()` on the current thread, tagging that thread with the currently active
    OTel span's span_id for pyroscope's native CPU sampler for the call's duration, then
    always untagging again — regardless of whether `func` raised. Tagging failure (e.g. the
    native extension erroring) is swallowed so `func` still runs untagged rather than never
    running at all — a profiling hiccup must never turn into a fetch/discover failure.

    Unlike backend/observability.py's to_thread_profiled() — which exists because FastAPI's
    `async def` routes all share one event-loop thread across concurrent requests, so tagging
    has to be scoped to a dedicated asyncio.to_thread() worker for the call's duration —
    ScrapeExecutor's fetch/discover workers (scrape_executor.py) are already each their own
    persistent OS thread pulled from a fixed ThreadPoolExecutor, and one task fully occupies
    its worker thread for that task's whole duration with no concurrent interleaving. So this
    tags directly around the call, no to_thread bridging needed — call it with the current
    FETCH_TASK/DISCOVER_TASK span already active (i.e. from inside that span's `with` block),
    once per task, not once for the worker's whole lifetime: a persistent worker thread runs
    many different tasks/spans over its life, so the tag must track whichever span is
    currently active for THIS call, same as _run_tagged does per to_thread call in the
    backend."""
    if not _profiling_enabled:
        return func()
    tags = _current_span_tags()
    if not tags:
        return func()
    tag_cm = None
    try:
        import pyroscope
        tag_cm = pyroscope.tag_wrapper(tags)
        tag_cm.__enter__()
    except Exception:
        tag_cm = None
    try:
        return func()
    finally:
        if tag_cm is not None:
            try:
                tag_cm.__exit__(None, None, None)
            except Exception:
                pass
