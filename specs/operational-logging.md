# Operational Logging

## Status

APPROVED

## Purpose

Define safe operational logging for the inference service so container logs provide actionable request, provider-failure, and managed-runtime lifecycle diagnostics without logging raw prompts, message content, image/audio payloads, request bodies, or other sensitive high-cardinality inputs.

## Scope

This spec covers:

- `service_app.py` request/access and failure-summary logging
- `local_server_runtime.py` managed local `llama-server` lifecycle logging and child-process log forwarding
- `Dockerfile` default Gunicorn logging configuration for container stdout/stderr
- `docker-compose.yml` runtime behavior insofar as the service is expected to emit logs to container output by default
- log sanitization rules for service and managed-runtime logging
- regression tests for safe logging behavior

This spec does not cover:

- metrics or Prometheus exposition
- raw prompt logging or request-body logging
- structured log shipping to external systems
- durable log retention
- audit/compliance logging
- browser/client-side logging
- changing provider routing policy

## Module Ownership

Owning modules and files:

- `service_app.py` — request/access logging hooks and failure-summary logging for HTTP routes
- `local_server_runtime.py` — managed `llama-server` start/stop/restart/failure logging and sanitized subprocess log forwarding
- `Dockerfile` — default Gunicorn stdout/stderr and access-log enablement for containerized deployment
- `tests/test_operational_logging.py` — acceptance and regression tests for logging behavior
- `README.md` — operational notes for container log visibility when needed

`service_app.py` owns service-level request/failure log emission. `local_server_runtime.py` owns managed-runtime lifecycle events and child-process log sanitization. Container log plumbing must remain thin and route logs to stdout/stderr without introducing separate in-repo retention.

## Current Behavior

The service emits operational logs to container stdout/stderr by default.

Containerized Gunicorn runs with access logging enabled so successful and failed HTTP requests produce access-log lines that include:

- request method
- request path
- response status
- request duration

Service-side request failure summaries are logged without including raw request bodies or message content. Failure summaries are limited to operational metadata such as route, HTTP status, and coarse error class such as `client_error`, `timeout`, `unavailable`, or `server_error`.

Managed local `llama-server` lifecycle events are logged when a runtime:

- is launched
- becomes ready
- is restarted after an exited tracked process
- fails to become ready
- is terminated during cleanup

Managed-runtime lifecycle logs may include low-cardinality operational identifiers such as configured model id and base URL.

Managed child-process stdout/stderr is not blindly mirrored to container logs. Instead, `local_server_runtime.py` captures child output and forwards only sanitized lifecycle/error lines that do not contain prompt text, request bodies, message content, media URLs, inline base64 payloads, API keys, or authorization headers.

Lines that appear to contain sensitive request content are dropped rather than partially echoed.

The repository does not retain logs beyond process/container output.

## Interfaces

### Service access logging

Container-visible access logs are enabled by default for the service runtime.

Access logs must expose at least:

- HTTP method
- request path
- status code
- duration

Exact formatting may be Gunicorn-native or service-generated, but the information above must be present in container logs.

### Service failure-summary logging

For handled request failures on instrumented routes, the service emits sanitized summaries containing only operational metadata such as:

- route
- status code
- coarse error class

Allowed coarse error classes are:

- `client_error`
- `timeout`
- `unavailable`
- `server_error`

### Managed-runtime lifecycle logging

Managed local runtime lifecycle logs may include:

- event type (`launch`, `ready`, `restart`, `failure`, `terminate`)
- logical model id
- base URL
- elapsed startup duration when available
- coarse failure class

### Child-process log forwarding

`local_server_runtime.py` may forward child stdout/stderr lines only after sanitization.

Forwarded child lines must be prefixed with enough operational context to identify:

- source runtime/model
- stream (`stdout` or `stderr`)

### Sanitization rules

No emitted log line may contain any of the following request-derived content:

- prompt text
- chat message text
- raw request JSON bodies
- `messages` payload dumps
- image URLs
- audio URLs
- inline `data:` URLs
- base64 media payloads
- authorization headers
- bearer tokens
- API keys

If a child-process line appears to contain request content or sensitive payload material, the line must be dropped.

## Data Model

Service access log fields:

- `method`: HTTP method
- `path`: route path
- `status`: HTTP status code
- `duration`: elapsed request handling time

Service failure-summary fields:

- `route`: service route
- `status`: returned HTTP status
- `error_class`: one of the allowed coarse error classes

Managed-runtime lifecycle fields:

- `event`: lifecycle event name
- `model`: logical provider/model id
- `base_url`: configured managed runtime URL
- `duration_seconds`: optional startup or failure duration
- `error_class`: optional coarse failure class

Sanitization invariants:

- log content remains low-risk and operational only
- dropped child-process lines are not rewritten with request content excerpts
- no in-repo buffering or durable retention is added

## Rules and Invariants

1. Container logs must be enabled by default for service access and operational failures.
2. Access logs must include method, path, status, and duration.
3. The service must not log raw prompts, message content, request bodies, image/audio payloads, or media URLs.
4. The service must not log authorization headers, bearer tokens, or API keys.
5. Failure-summary logs must use only coarse operational error classes.
6. Managed local runtime lifecycle events must be visible in container logs.
7. Managed child-process stdout/stderr must not be blindly mirrored to container logs.
8. Child-process lines that appear to contain request or payload content must be dropped.
9. Logging must remain stdout/stderr based and in-process; no durable log store is added.
10. Logging changes must not alter inference request semantics beyond adding operational visibility.

## Edge Cases

- Successful text-only inference still produces an access log line.
- A handled `400 invalid_request` produces an access log line and a sanitized `client_error` summary without body content.
- A provider timeout produces an access log line and a sanitized `timeout` summary.
- A provider unavailable error produces an access log line and a sanitized `unavailable` summary.
- An unexpected unhandled exception produces an access log line and a sanitized `server_error` summary.
- If a managed runtime exits and must be relaunched, both restart and launch/ready or launch/failure lifecycle events are logged.
- If a child-process line contains a `data:` URL, prompt dump, or body-like JSON content, it is dropped.
- If a child-process line is safe lifecycle text, it may be forwarded with operational context.
- If the service runs outside Docker, logging still goes to stdout/stderr without requiring an external log sink.

## Acceptance Criteria

1. Containerized service startup enables access logging to stdout/stderr by default.
2. Successful requests emit access logs that include method, path, status, and duration.
3. Handled request failures emit sanitized failure-summary logs using only coarse error classes.
4. No request body, prompt text, message content, image/audio URL, inline media payload, authorization header, bearer token, or API key appears in emitted service logs.
5. Managed local runtime launch, ready, restart, failure, and termination events are logged to stdout/stderr.
6. Managed child-process stdout/stderr is captured and sanitized before any forwarding to container logs.
7. Sensitive child-process lines are dropped rather than echoed.
8. Logging remains stdout/stderr based only and does not add durable retention or external shipping.

## Test Plan

- Verify container/service startup configuration enables Gunicorn access logging to stdout/stderr by default.
- Verify a successful request produces a log entry with method, path, status, and duration.
- Verify handled invalid requests produce sanitized `client_error` summaries without request-body leakage.
- Verify timeout and unavailable failures produce sanitized coarse failure summaries.
- Verify unhandled exceptions produce sanitized `server_error` summaries.
- Verify managed runtime launch/ready/failure/restart/terminate events are logged.
- Verify child-process sanitization drops lines containing request bodies, prompt-like fields, `data:` URLs, media URLs, tokens, or authorization material.
- Verify safe child-process lifecycle lines can be forwarded with runtime context.

## Out of Scope

- prompt logging or redaction of logged prompt content
- log shipping to Loki, ELK, CloudWatch, or similar systems
- long-term retention or rotation policies outside container runtime defaults
- per-token tracing or span logging
- metrics implementation

## Traceability

Append only non-traceability commit hashes here. Traceability-only commits do not record themselves.

### Spec Commits

- 2026-05-17 | 46e4e3fbf081af3ff6e11954031464a04ad8c8e3 | add canonical operational logging spec

### Implementation Commits
