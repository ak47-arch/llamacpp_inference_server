# Monitoring and Observability

## Status

VERIFIED

## Purpose

Define the repository's first-phase observability capability so the inference service can expose low-privacy, operationally useful telemetry for request latency, readiness behavior, provider failures, and managed local runtime startup behavior before any prompt logging or debug surfaces are added.

## Scope

This spec covers:

- Prometheus-compatible in-process metrics exposed by `GET /metrics`
- HTTP request metrics for service routes relevant to inference and readiness
- aggregate stage timing for request handling and readiness checks
- provider/model-labeled outcome metrics for `POST /v1/chat/completions`
- managed local runtime startup telemetry from `local_server_runtime.py`
- a dedicated instrumentation module that centralizes metric definitions and updates
- the bounded-label rules that additional feature-owned metrics must also respect when they share `monitoring.py`
- dependency and test changes required to support this capability

This spec does not cover:

- raw prompt logging
- metadata request logging
- per-request traces, spans, or stored stage records
- `/debug/*` endpoints
- log retention or persistence
- external collectors, push gateways, or durable metrics storage
- host or container resource monitoring

## Module Ownership

Owning modules and files:

- `monitoring.py` — centralized metric definitions, label normalization, and helper/context APIs for instrumentation
- `service_app.py` — route registration for `GET /metrics` and service-level request instrumentation
- `openai_compatible_provider.py` — provider-call instrumentation for outbound OpenAI-compatible requests and managed warmup entrypoints
- `local_server_runtime.py` — managed local `llama-server` startup attempt, restart, success/failure, and startup duration metrics
- `llama_cpp_provider.py` — provider-call instrumentation for direct subprocess-backed completions when they participate in instrumented request paths
- `requirements.txt` — Prometheus client dependency
- `tests/test_monitoring.py` — acceptance and regression tests for this capability

`monitoring.py` owns metric names, label sets, and helper functions. Existing runtime and provider modules remain thin call sites that emit observations without duplicating metric definitions.

## Current Behavior

The service exposes a Prometheus-compatible `GET /metrics` endpoint by default.

Metrics are in-process and ephemeral. They reset when the service process restarts.

The first implementation is aggregate-only. It records counters, gauges, and histograms, but does not store individual request traces or request bodies.

The `/metrics` endpoint exposes service metrics for:

- request totals by route and outcome
- in-flight request count by route
- end-to-end request duration by route, requested model, resolved provider, and outcome where applicable
- provider execution duration by route, requested model, resolved provider, and outcome where applicable
- readiness probe totals and per-provider readiness duration
- managed local runtime startup attempts, startup successes/failures, startup duration, and restart count

`POST /v1/chat/completions` metrics use the requested `model` from the inbound payload as the `model` label and the resolved provider implementation identity as the `provider` label.

For routes that are not model-specific, metrics use the bounded sentinel values `model="none"` and `provider="none"`.

Metric labels remain low-cardinality and bounded to:

- `route`
- `model`
- `provider`
- `outcome`

No metric label may contain request ids, prompt-derived fields, exception text, or other unbounded user-controlled values.

Additional feature-owned metrics may be exposed from the shared `monitoring.py` module when governed by their own canonical specs, but they must still obey the same bounded-label and low-privacy rules documented here.

The first implementation instruments these routes:

- `GET /health`
- `GET /ready`
- `POST /v1/chat/completions`

`GET /metrics` is exposed but is not itself counted in the service request metrics, so scrape traffic does not distort operational request counts and latency histograms.

`GET /ready` records both:

- overall route-level request metrics for the readiness endpoint, and
- per-provider readiness metrics covering warmup + probe completion duration and outcome

When readiness fails for a provider, the readiness metrics record the provider-specific failure outcome before the route returns a 503.

`POST /v1/chat/completions` records:

- route-level request count and end-to-end duration
- in-flight gauge updates for the route
- provider execution duration for the selected provider call
- outcome classification for success, client error, timeout, unavailable, or server error

Managed local runtime telemetry records startup attempts from `ensure_managed_server()`.

When a managed runtime is already healthy, no startup attempt metric is emitted.

When a tracked managed process exists for a base URL but has exited and a new process must be launched, the restart counter is incremented before the new startup attempt is recorded.

When a managed runtime launch succeeds, the startup success counter and startup duration histogram are updated.

When a managed runtime launch fails after a process spawn attempt, the startup failure counter and startup duration histogram are updated before the exception is re-raised.

## Interfaces

### HTTP endpoints

#### `GET /metrics`

- enabled by default
- returns Prometheus text exposition format generated from in-process metrics
- does not require request payloads or custom authentication in this first phase

### Metric names

This spec directly governs these core metric families:

- `llm_service_requests_total`
- `llm_service_in_flight_requests`
- `llm_service_request_duration_seconds`
- `llm_service_provider_duration_seconds`
- `llm_service_readiness_checks_total`
- `llm_service_readiness_duration_seconds`
- `llm_service_managed_server_startups_total`
- `llm_service_managed_server_startup_duration_seconds`
- `llm_service_managed_server_restarts_total`

### Label schema

#### `llm_service_requests_total`

Labels:

- `route`
- `model`
- `provider`
- `outcome`

#### `llm_service_in_flight_requests`

Labels:

- `route`

#### `llm_service_request_duration_seconds`

Labels:

- `route`
- `model`
- `provider`
- `outcome`

#### `llm_service_provider_duration_seconds`

Labels:

- `route`
- `model`
- `provider`
- `outcome`

#### `llm_service_readiness_checks_total`

Labels:

- `model`
- `provider`
- `outcome`

For readiness checks, `model` is the logical provider id being checked and `provider` is the provider implementation identity.

#### `llm_service_readiness_duration_seconds`

Labels:

- `model`
- `provider`
- `outcome`

#### `llm_service_managed_server_startups_total`

Labels:

- `model`
- `base_url`
- `outcome`

#### `llm_service_managed_server_startup_duration_seconds`

Labels:

- `model`
- `base_url`
- `outcome`

#### `llm_service_managed_server_restarts_total`

Labels:

- `model`
- `base_url`

### Outcome values

Allowed bounded outcome values are:

- `success`
- `client_error`
- `timeout`
- `unavailable`
- `server_error`

Outcome mapping rules:

- 2xx responses map to `success`
- 4xx responses map to `client_error`
- provider timeout failures map to `timeout`
- provider unavailable or runtime unavailable failures map to `unavailable`
- uncaught 5xx responses map to `server_error`

### Dependency interface

`requirements.txt` adds the `prometheus_client` package for metric primitives and text exposition.

## Data Model

### Service route labels

- `route`: one of `/health`, `/ready`, `/v1/chat/completions`
- `model`: requested logical model id for chat completions; otherwise `none`
- `provider`: resolved provider implementation identity for provider-backed requests; otherwise `none`
- `outcome`: one of the bounded outcome values in this spec

### Readiness labels

- `model`: provider id being warmed/probed
- `provider`: provider implementation identity for that provider id
- `outcome`: bounded readiness result classification

### Managed runtime labels

- `model`: logical provider id that triggered the managed startup
- `base_url`: normalized configured base URL for the managed runtime
- `outcome`: `success` or `unavailable`

### Metric semantics

- request counters are monotonically increasing per label set
- in-flight gauge increases at request start and decreases exactly once when request handling finishes
- duration histograms record elapsed wall-clock seconds as floating-point observations
- managed runtime restart counts increase only when a previously tracked process for a base URL has exited and a replacement launch is attempted

Invariants:

- metrics remain aggregate-only and in-process
- metric labels stay low-cardinality and bounded
- `/metrics` is exposed by default
- `/metrics` scrapes do not update service request counters or request latency histograms
- readiness metrics are emitted per provider checked, not only for the aggregate route result
- startup failures are recorded before exceptions are re-raised

## Rules and Invariants

1. The first observability feature must not log raw prompts.
2. The first observability feature must not store per-request traces or spans.
3. `GET /metrics` must expose Prometheus-compatible text output.
4. Metrics must be enabled by default.
5. Metrics must be in-process and ephemeral only.
6. Metric labels must be limited to bounded, low-cardinality values.
7. Request ids, prompt fingerprints, prompt sizes, message content, and exception text must not appear as metric labels.
8. `POST /v1/chat/completions` metrics must preserve the requested model id in the `model` label.
9. Provider-backed chat metrics must record the resolved provider implementation identity in the `provider` label.
10. `GET /ready` must emit per-provider readiness observations in addition to the aggregate route observation.
11. Managed local runtime launches must emit startup attempt outcomes and startup duration.
12. Managed local runtime replacement launches after an exited tracked process must increment the restart counter.
13. `GET /metrics` must not count toward service request totals or request latency histograms.
14. Existing runtime behavior and exception semantics must remain unchanged except for added observability.

## Edge Cases

- `POST /v1/chat/completions` with a missing or invalid `model` still records a route-level request outcome with `model="none"`, `provider="none"`, and `outcome="client_error"`.
- `POST /v1/chat/completions` with malformed `messages` still records a client-error route metric.
- If provider resolution fails before a provider is called, the request still records a route outcome, with `provider="none"` when no provider could be resolved.
- If a provider call times out, the route records `outcome="timeout"` and the provider-duration histogram records the timeout duration observation with the resolved provider label.
- If a provider is unavailable, the route records `outcome="unavailable"`.
- If readiness fails on the first failing provider in the loop, metrics for providers already checked remain recorded and the failing provider receives a failure observation before the route returns 503.
- If a managed runtime is already healthy before startup logic begins, no startup attempt metric is emitted.
- If a managed runtime process spawn succeeds but readiness wait fails, the startup attempt is recorded as `unavailable`, the startup duration is observed, and the original exception is re-raised after cleanup.
- If an unexpected unhandled exception produces a 5xx response on an instrumented route, the route request counter and duration histogram still record `outcome="server_error"`.

## Acceptance Criteria

1. The repository contains a new canonical monitoring spec at `specs/monitoring.md` and a new instrumentation module at `monitoring.py`.
2. `requirements.txt` includes `prometheus_client`.
3. The Flask app exposes `GET /metrics` by default.
4. `GET /metrics` returns Prometheus-formatted output containing the metric families defined in this spec.
5. Requests to `GET /health`, `GET /ready`, and `POST /v1/chat/completions` update `llm_service_requests_total` and `llm_service_request_duration_seconds` with bounded labels.
6. `POST /v1/chat/completions` updates `llm_service_in_flight_requests` while a request is active.
7. Successful chat completions record the requested model id and resolved provider identity in route-level metrics.
8. Invalid chat requests record `client_error` metrics without requiring a provider label.
9. Provider-backed chat completions record `llm_service_provider_duration_seconds`.
10. `GET /ready` records aggregate route metrics and per-provider readiness metrics.
11. Managed runtime startup attempts record `llm_service_managed_server_startups_total` and `llm_service_managed_server_startup_duration_seconds`.
12. Managed runtime replacement launches after an exited tracked process increment `llm_service_managed_server_restarts_total`.
13. `GET /metrics` scrapes do not increment `llm_service_requests_total` for `/metrics`.
14. No prompt content or high-cardinality request metadata appears in metric labels or metric names.

## Test Plan

- add tests that create the Flask app and verify `GET /metrics` is registered and returns Prometheus text output
- add tests that perform `GET /health` and confirm service request counters and request duration metrics are emitted for route `/health`
- add tests that perform invalid `POST /v1/chat/completions` requests and confirm `client_error` observations with bounded `model`/`provider` labels
- add tests that perform successful `POST /v1/chat/completions` requests against a stub runtime/provider and confirm route metrics contain the requested model id and resolved provider identity
- add tests that confirm in-flight gauge values rise during an active chat request and settle back afterward
- add tests that simulate provider timeout and unavailable failures and confirm route outcome classification and provider duration observations
- add tests that simulate readiness over one or more stub providers and confirm aggregate `/ready` metrics plus per-provider readiness metrics
- add tests for `ensure_managed_server()` covering successful startup, failed startup after spawn, and restart-after-exited-process behavior
- add tests that confirm `/metrics` scrapes do not create `/metrics` route request observations
- run the relevant Python test suite for the new monitoring capability and existing inference server behavior

## Out of Scope

- structured request logs
- raw prompt capture or redaction policy
- admin or debug observability endpoints other than `/metrics`
- Prometheus alert rules or dashboards
- persistence, retention, or export of metrics beyond scrape-time exposition
- CPU, memory, GPU, or container utilization metrics
- changing provider routing policy

## Traceability

Append only non-traceability commit hashes here. Traceability-only commits do not record themselves.

### Spec Commits

- 2026-05-17 | 297a8299eb0eca77c33cd9118227f818e2b57cf2 | add canonical monitoring and observability spec
- 2026-05-23 | 392b6802de46371885bc9256d805eb17c6ec9240 | allow bounded feature-owned metrics in shared monitoring module

### Implementation Commits

- 2026-05-17 | 99b4ff5d9b49d5220a7860ef52b693be064326b4 | add Prometheus metrics endpoint and runtime telemetry
- 2026-05-18 | b831568f0716154a36070ea8495c1fe95394489c | update monitoring integration and regression coverage alongside service changes
- 2026-05-23 | 241931c51d84ed2c508c233c3830b4ec7ad14c21 | add bounded prompt-capture record metrics to the shared monitoring module
