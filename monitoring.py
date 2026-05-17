"""Prometheus metrics for the generic inference server."""

from contextlib import contextmanager
from contextvars import ContextVar
from time import monotonic

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest

_REQUEST_CONTEXT: ContextVar[dict | None] = ContextVar("llm_request_context", default=None)

_registry: CollectorRegistry | None = None
_requests_total = None
_in_flight_requests = None
_request_duration_seconds = None
_provider_duration_seconds = None
_readiness_checks_total = None
_readiness_duration_seconds = None
_managed_server_startups_total = None
_managed_server_startup_duration_seconds = None
_managed_server_restarts_total = None


REQUEST_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
STARTUP_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0)
ALLOWED_OUTCOMES = {"success", "client_error", "timeout", "unavailable", "server_error"}


def reset_metrics() -> None:
    global _registry
    global _requests_total
    global _in_flight_requests
    global _request_duration_seconds
    global _provider_duration_seconds
    global _readiness_checks_total
    global _readiness_duration_seconds
    global _managed_server_startups_total
    global _managed_server_startup_duration_seconds
    global _managed_server_restarts_total

    _registry = CollectorRegistry(auto_describe=True)
    _requests_total = Counter(
        "llm_service_requests_total",
        "Total instrumented service requests by route, model, provider, and outcome.",
        labelnames=("route", "model", "provider", "outcome"),
        registry=_registry,
    )
    _in_flight_requests = Gauge(
        "llm_service_in_flight_requests",
        "Current in-flight instrumented service requests by route.",
        labelnames=("route",),
        registry=_registry,
    )
    _request_duration_seconds = Histogram(
        "llm_service_request_duration_seconds",
        "End-to-end instrumented service request duration in seconds.",
        labelnames=("route", "model", "provider", "outcome"),
        buckets=REQUEST_BUCKETS,
        registry=_registry,
    )
    _provider_duration_seconds = Histogram(
        "llm_service_provider_duration_seconds",
        "Provider execution duration in seconds for instrumented chat requests.",
        labelnames=("route", "model", "provider", "outcome"),
        buckets=REQUEST_BUCKETS,
        registry=_registry,
    )
    _readiness_checks_total = Counter(
        "llm_service_readiness_checks_total",
        "Per-provider readiness check totals by model, provider, and outcome.",
        labelnames=("model", "provider", "outcome"),
        registry=_registry,
    )
    _readiness_duration_seconds = Histogram(
        "llm_service_readiness_duration_seconds",
        "Per-provider readiness check duration in seconds.",
        labelnames=("model", "provider", "outcome"),
        buckets=REQUEST_BUCKETS,
        registry=_registry,
    )
    _managed_server_startups_total = Counter(
        "llm_service_managed_server_startups_total",
        "Managed server startup attempts by model, base_url, and outcome.",
        labelnames=("model", "base_url", "outcome"),
        registry=_registry,
    )
    _managed_server_startup_duration_seconds = Histogram(
        "llm_service_managed_server_startup_duration_seconds",
        "Managed server startup duration in seconds by model, base_url, and outcome.",
        labelnames=("model", "base_url", "outcome"),
        buckets=STARTUP_BUCKETS,
        registry=_registry,
    )
    _managed_server_restarts_total = Counter(
        "llm_service_managed_server_restarts_total",
        "Managed server replacement launches after an exited tracked process.",
        labelnames=("model", "base_url"),
        registry=_registry,
    )
    _REQUEST_CONTEXT.set(None)


reset_metrics()


def metrics_response() -> tuple[bytes, str]:
    return generate_latest(_registry), CONTENT_TYPE_LATEST


@contextmanager
def request_context(route: str) -> dict:
    context = {"route": route, "model": "none", "provider": "none"}
    token = _REQUEST_CONTEXT.set(context)
    try:
        yield context
    finally:
        _REQUEST_CONTEXT.reset(token)


@contextmanager
def track_in_flight(route: str):
    _in_flight_requests.labels(route=route).inc()
    try:
        yield
    finally:
        _in_flight_requests.labels(route=route).dec()


@contextmanager
def timer():
    start = monotonic()
    try:
        yield lambda: monotonic() - start
    finally:
        pass


def current_request_labels() -> tuple[str, str]:
    context = _REQUEST_CONTEXT.get() or {}
    return context.get("model", "none"), context.get("provider", "none")


def clear_request_context() -> None:
    _REQUEST_CONTEXT.set(None)


def set_resolved_model(model: str | None) -> None:
    context = _REQUEST_CONTEXT.get()
    if context is not None:
        context["model"] = _normalize_label(model)


def set_resolved_provider(provider: str | None) -> None:
    context = _REQUEST_CONTEXT.get()
    if context is not None:
        context["provider"] = _normalize_label(provider)


def provider_identity(provider, fallback: str | None = None) -> str:
    return _normalize_label(
        fallback
        or getattr(provider, "provider_name", None)
        or getattr(provider, "provider", None)
        or provider.__class__.__name__.replace("Provider", "").replace("_", "").lower()
    )


def classify_exception(exc: Exception) -> str:
    from .provider_base import ProviderTimeoutError, ProviderUnavailableError

    if isinstance(exc, ValueError):
        return "client_error"
    if isinstance(exc, ProviderTimeoutError):
        return "timeout"
    if isinstance(exc, (ProviderUnavailableError, RuntimeError, KeyError)):
        return "unavailable"
    return "server_error"


def observe_request(route: str, outcome: str, model: str = "none", provider: str = "none", duration_seconds: float = 0.0) -> None:
    outcome = _normalize_outcome(outcome)
    model = _normalize_label(model)
    provider = _normalize_label(provider)
    labels = {"route": route, "model": model, "provider": provider, "outcome": outcome}
    _requests_total.labels(**labels).inc()
    _request_duration_seconds.labels(**labels).observe(duration_seconds)


def observe_provider_duration(route: str, outcome: str, model: str, provider: str, duration_seconds: float) -> None:
    outcome = _normalize_outcome(outcome)
    labels = {
        "route": route,
        "model": _normalize_label(model),
        "provider": _normalize_label(provider),
        "outcome": outcome,
    }
    _provider_duration_seconds.labels(**labels).observe(duration_seconds)


def observe_readiness(model: str, provider: str, outcome: str, duration_seconds: float) -> None:
    outcome = _normalize_outcome(outcome)
    labels = {
        "model": _normalize_label(model),
        "provider": _normalize_label(provider),
        "outcome": outcome,
    }
    _readiness_checks_total.labels(**labels).inc()
    _readiness_duration_seconds.labels(**labels).observe(duration_seconds)


def observe_managed_server_startup(model: str, base_url: str, outcome: str, duration_seconds: float) -> None:
    outcome = _normalize_outcome(outcome)
    labels = {
        "model": _normalize_label(model),
        "base_url": _normalize_label(base_url),
        "outcome": outcome,
    }
    _managed_server_startups_total.labels(**labels).inc()
    _managed_server_startup_duration_seconds.labels(**labels).observe(duration_seconds)


def increment_managed_server_restart(model: str, base_url: str) -> None:
    _managed_server_restarts_total.labels(
        model=_normalize_label(model),
        base_url=_normalize_label(base_url),
    ).inc()


def _normalize_label(value: str | None) -> str:
    normalized = str(value or "").strip()
    return normalized or "none"


def _normalize_outcome(outcome: str) -> str:
    normalized = _normalize_label(outcome)
    if normalized not in ALLOWED_OUTCOMES:
        return "server_error"
    return normalized
