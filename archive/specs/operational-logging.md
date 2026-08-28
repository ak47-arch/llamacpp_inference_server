> **DEPRECATED** — This file is part of the retired spec-driven development process (2026-08-28).
> The factory workflow (PRDs at `docs/prd/` + vision docs at `docs/vision/`) replaces it.
> Retained for retrospective analysis only. Do not use as active guidance.

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

## Accepted Test Audit Report

# Test Audit Report

**Spec:** specs/operational-logging.md
**Tests Reviewed:** tests/test_operational_logging.py
**Red Output Reviewed:** yes
**Inputs provided:** spec ✓ | tests ✓ | red output ✓ | standards doc ✗
**Audited by:** test-verifier agent (independent session)
**Date:** 2026-05-17

---

## Requirement Coverage Matrix

| ID | Requirement | Coverage Status | Evidence (file:line) | Notes |
|---|---|---|---|---|
| AC-1 | Containerized service startup enables access logging to stdout/stderr by default. | COVERED_STRONG | tests/test_operational_logging.py:155-165 | Directly asserts Gunicorn `--access-logfile -` and `--error-logfile -` in `Dockerfile`. |
| AC-2 | Successful requests emit access logs including method, path, status, and duration. | COVERED_STRONG | tests/test_operational_logging.py:80-92 | Direct log assertions for `method=POST`, path, status, and duration. |
| AC-3 | Handled invalid requests emit a sanitized `client_error` failure summary. | COVERED_STRONG | tests/test_operational_logging.py:94-114 | Asserts `400`, path, `error_class=client_error`, and absence of sensitive request fields. |
| AC-4 | Provider timeout failures emit a sanitized `timeout` failure summary. | COVERED_STRONG | tests/test_operational_logging.py:116-127 | Directly asserts `504` and `error_class=timeout`. |
| AC-5 | Provider unavailable failures emit a sanitized `unavailable` failure summary. | COVERED_STRONG | tests/test_operational_logging.py:129-140 | Directly asserts `503` and `error_class=unavailable`. |
| AC-6 | Unhandled exceptions emit a sanitized `server_error` failure summary. | COVERED_STRONG | tests/test_operational_logging.py:142-153 | Directly asserts `500` and `error_class=server_error`. |
| AC-7 | Service logs must not contain prompt text, message content, raw request bodies, media URLs/payloads, authorization headers, bearer tokens, or API keys. | COVERED_WEAK | tests/test_operational_logging.py:80-92, 94-114 | Prompt/message/auth/api-key leakage is checked, but service-side cases for image URLs, audio URLs, inline `data:` URLs, and base64 media payloads are not exercised. |
| AC-8 | Managed runtime launch, ready, restart, failure, and terminate lifecycle events are logged. | COVERED_STRONG | tests/test_operational_logging.py:188-214, 241-266, 268-291, 293-303 | All required lifecycle events are directly asserted across tests. |
| AC-9 | Managed child-process stdout/stderr is captured and sanitized before forwarding. | COVERED_STRONG | tests/test_operational_logging.py:176-186, 188-214, 216-239 | Direct sanitizer unit tests plus forwarding tests cover safe and sensitive lines. |
| AC-10 | Sensitive child-process lines are dropped rather than echoed. | COVERED_STRONG | tests/test_operational_logging.py:176-182, 216-239 | Direct `None` assertions for sensitive lines and `assertNotIn` during forwarding. |
| AC-11 | Logging remains stdout/stderr based only and does not add durable retention or external shipping. | COVERED_WEAK | tests/test_operational_logging.py:155-165 | External shipping is partially guarded via compose text checks, but no direct guard covers durable retention or in-repo buffering. |
| API-1 | Failure summaries contain route, status, and coarse error class. | COVERED_STRONG | tests/test_operational_logging.py:94-114, 116-127, 129-140, 142-153 | All failure-summary tests assert path/status/error_class. |
| API-2 | Forwarded child lines include enough context to identify source runtime/model and stream. | COVERED_WEAK | tests/test_operational_logging.py:188-214 | The test checks `model`, `base_url`, `stream`, and forwarded text somewhere in combined logs, but not that the forwarded child line itself carries the required context/prefix. |
| DM-1 | Dropped child-process lines are not rewritten with request-content excerpts. | COVERED_STRONG | tests/test_operational_logging.py:176-182, 216-239 | Sensitive lines are expected to disappear entirely rather than be redacted/rewritten. |
| BC-1 | Logging changes must not alter inference request semantics beyond adding operational visibility. | COVERED_WEAK | tests/test_operational_logging.py:80-92, 94-153 | Tests validate status codes and log output, but do not verify response bodies/contracts remain unchanged. |

---

## Test Quality Issues

TQ-1
Category: coverage-gap
Severity: high
Location: tests/test_operational_logging.py:80-153
Reasoning: Service-log sanitization coverage is incomplete. The suite checks prompt/message/auth/api-key leakage, but does not exercise service requests containing image URLs, audio URLs, inline `data:` URLs, or base64 media payloads even though the spec explicitly forbids those from appearing in emitted service logs.

TQ-2
Category: weak-assertion
Severity: medium
Location: tests/test_operational_logging.py:188-214
Reasoning: The runtime-context requirement for forwarded child lines is asserted against the combined log output, not against the forwarded line itself. A log stream could satisfy `model=...`, `base_url=...`, `stream=stdout`, and the child text via separate entries, while still failing to prefix the forwarded child line with sufficient operational context.

TQ-3
Category: weak-assertion
Severity: medium
Location: tests/test_operational_logging.py:80-153
Reasoning: The suite does not directly validate that logging instrumentation preserves inference response semantics. Success and failure tests assert HTTP statuses and selected log fields, but not the returned payload/body contracts that must remain unchanged apart from added observability.

TQ-4
Category: coverage-gap
Severity: medium
Location: tests/test_operational_logging.py:155-165
Reasoning: The stdout/stderr-only guard is partial. It checks Dockerfile flags and absence of several compose logging-driver strings, but it does not directly cover the spec's no-durable-retention/no in-repo-buffering constraint.

---

## Red-Phase Validity

Status: VALID_RED
Evidence: The provided failures are implementation-facing and match the intended red phase: `AttributeError: module 'llm.local_server_runtime' has no attribute '_sanitize_child_log_line'`, repeated `AssertionError: no logs of level INFO or higher triggered on llm.service`, repeated `AssertionError: no logs of level INFO or higher triggered on llm.runtime`, and the Dockerfile assertion failure for missing `--access-logfile -`. The Flask traceback for `Exception: boom` occurs during the unhandled-exception scenario and reflects missing/incorrect application behavior rather than an unrelated test-harness or environment failure.

---

## Summary Verdict

**TEST GAPS** - one or more requirements are MISSING/COVERED_WEAK/MISALIGNED.

Unverifiable items:
- No project testing standards document was provided.
- No baseline overlapping tests were provided.

---

*This report is read-only. No code changes have been made.*

## Latest Spec Audit Report

# Spec Audit Report

**Spec:** `specs/operational-logging.md`  
**Diff reviewed:** `/tmp/spec_feature_b.diff`  
**Inputs provided:** spec ✓ | diff ✓ | process doc ✗ | additional context ✓  
**Audited by:** spec-verifier agent (independent session)  
**Date:** 2026-05-18

---

## Spec Compliance

*Mapping note: repeated Acceptance Criteria / Interface / Data Model / Edge Case statements were mapped to composite criteria where they describe the same contract surface. The embedded “Accepted Test Audit Report” was treated as additional context, not as a normative requirement source.*

| ID | Section | Criterion | Status | Evidence (file:line) | Notes |
|---|---|---|---|---|---|
| FR-1 | Scope | `service_app.py` provides request/access logging and failure-summary logging | MET | `service_app.py:55-67`, `service_app.py:224-343` | Logging hooks exist on `/health`, `/ready`, and `/v1/chat/completions` |
| FR-2 | Scope | `local_server_runtime.py` provides managed-runtime lifecycle logging and child-process log forwarding | PARTIAL | `local_server_runtime.py:121-139`, `local_server_runtime.py:170`, `local_server_runtime.py:183`, `local_server_runtime.py:197`, `local_server_runtime.py:219`, `local_server_runtime.py:236` | Lifecycle events and forwarding exist, but child-log sanitization is incomplete |
| FR-3 | Scope | `Dockerfile` enables default Gunicorn logging to stdout/stderr | MET | `Dockerfile:22` | `--access-logfile -` and `--error-logfile -` are enabled |
| FR-4 | Scope | `docker-compose.yml` keeps default runtime behavior container-output based | MET | `grep: no matches for 'logging:|fluentd|gelf|awslogs|loki|cloudwatch|elk' in docker-compose.yml` | No alternate shipping driver configured |
| FR-5 | Scope | Service and managed-runtime sanitization rules are implemented | PARTIAL | `service_app.py:55-67`; `local_server_runtime.py:101-118` | Service logs are metadata-only; runtime sanitizer misses prompt/body-like lines and plain base64 |
| FR-6 | Scope | Regression tests for safe logging behavior exist | MET | `tests/test_operational_logging.py:80-332` | Dedicated operational logging test file present |

| API-1 | Interfaces | Access logging is enabled by default and intended to be container-visible | MET | `Dockerfile:22`; `service_app.py:55-62` | Gunicorn stdio logging is enabled; service also emits access logs |
| API-2 | Interfaces / Data Model | Access logs include method, path, status, and duration | MET | `service_app.py:57`, `service_app.py:248`, `service_app.py:293`, `service_app.py:343` | Access log template includes all required fields |
| API-3 | Interfaces / Data Model | Failure summaries contain route, status, and coarse `error_class` | PARTIAL | `service_app.py:67`, `service_app.py:292`, `service_app.py:342` | Summary includes status and `error_class`, but logs `path=` instead of required `route=` |
| API-4 | Interfaces / Rules | Failure summaries use only allowed coarse classes (`client_error`, `timeout`, `unavailable`, `server_error`) | MET | `service_app.py:269-274`, `service_app.py:315-325`; `monitoring.py:176-195` | Exception classification is restricted to allowed values |
| API-5 | Interfaces / Rules | Managed runtime lifecycle logs include `launch`, `ready`, `restart`, `failure`, and `terminate` events | MET | `local_server_runtime.py:170`, `local_server_runtime.py:183`, `local_server_runtime.py:197`, `local_server_runtime.py:219`, `local_server_runtime.py:236` | All required event types are logged |
| API-6 | Interfaces / Data Model | Lifecycle logs carry model/base_url and duration/error_class where applicable | PARTIAL | `local_server_runtime.py:170`, `local_server_runtime.py:183`, `local_server_runtime.py:197`, `local_server_runtime.py:219`, `local_server_runtime.py:236` | `ready`/`failure` include duration, `failure` includes `error_class`, but termination logs `model=unknown` |
| API-7 | Interfaces | Child stdout/stderr is captured, sanitized, and forwarded with model/base_url/stream context | MET | `local_server_runtime.py:121-139`, `local_server_runtime.py:186-188` | Forwarded child lines include `model`, `base_url`, `stream`, and sanitized message |
| API-8 | Sanitization Rules | Emitted logs must not contain prompt text, chat text, raw request bodies, or payload dumps | PARTIAL | `service_app.py:55-67`; `local_server_runtime.py:101-118` | Service logs are safe, but runtime sanitizer does not detect generic prompt/body-like text |
| API-9 | Sanitization Rules | Emitted logs must not contain image/audio URLs, inline `data:` URLs, or base64 media payloads | PARTIAL | `local_server_runtime.py:112-114`; `service_app.py:55-67` | URLs and `data:` are blocked; plain base64 payloads without `data:` are not detected |
| API-10 | Sanitization Rules | Emitted logs must not contain authorization headers, bearer tokens, or API keys | MET | `local_server_runtime.py:108-110`; `service_app.py:55-67` | Explicit markers are blocked; service logs never interpolate request content |
| API-11 | Sanitization / Invariants | Sensitive child lines are dropped rather than rewritten with excerpts | PARTIAL | `local_server_runtime.py:101-118` | Blocked lines return `None`, but incomplete detection means some sensitive lines could still pass |

| DM-1 | Data Model / Invariants | Logging remains stdout/stderr based and adds no in-repo buffering or durable retention | MET | `Dockerfile:22`; `grep: no matches for 'FileHandler|RotatingFileHandler|TimedRotatingFileHandler|basicConfig(filename=' in service_app.py, local_server_runtime.py` | No file handlers or retention logic added |
| BC-1 | Rules and Invariants | Logging changes do not alter inference/runtime semantics beyond operational visibility | MISSING | `service_app.py:15-52`, `service_app.py:74-95`, `service_app.py:168-190`; `local_server_runtime.py:35-42`, `local_server_runtime.py:90-92` | Diff adds multimodal request validation/messages-path handling and `--mmproj` runtime behavior unrelated to logging |

| EC-1 | Edge Cases | Successful text-only inference still produces an access log line | MET | `service_app.py:304-343` | Success path logs access |
| EC-2 | Edge Cases | Handled `400 invalid_request` emits an access log and sanitized `client_error` summary without body content | MET | `service_app.py:314-318`, `service_app.py:341-343` | 400 maps to `client_error` summary plus access log |
| EC-3 | Edge Cases | Provider timeout emits an access log and sanitized `timeout` summary | MET | `service_app.py:318-321`, `service_app.py:341-343` | 504 maps to `timeout` summary plus access log |
| EC-4 | Edge Cases | Provider unavailable error emits an access log and sanitized `unavailable` summary | MET | `service_app.py:322-325`, `service_app.py:341-343` | 503 maps to `unavailable` summary plus access log |
| EC-5 | Edge Cases | Unhandled exception emits an access log and sanitized `server_error` summary | MET | `service_app.py:326-339` | 500 path logs `server_error` summary and access log before re-raise |
| EC-6 | Edge Cases | Relaunch after an exited managed runtime logs `restart` and subsequent `launch`/`ready` or `launch`/`failure` | MET | `local_server_runtime.py:167-170`, `local_server_runtime.py:183`, `local_server_runtime.py:197`, `local_server_runtime.py:219` | Restart is logged before replacement launch; ready/failure is logged after launch |
| EC-7 | Edge Cases | Child lines containing a `data:` URL, prompt dump, or body-like JSON are dropped | PARTIAL | `local_server_runtime.py:111-114` | `data:` and exact `"messages"` dumps are dropped; prompt dumps / generic body-like JSON are not detected |
| EC-8 | Edge Cases | Safe child lifecycle text may be forwarded with operational context | MET | `local_server_runtime.py:135-139` | Forwarded lines include operational context |
| EC-9 | Edge Cases | Outside Docker, logging still goes to stdout/stderr without requiring an external sink | UNVERIFIABLE | `service_app.py:16`; `local_server_runtime.py:14` | Code emits `INFO` logs, but the diff adds no explicit standalone logger configuration |

| AC-1 | Acceptance Criteria | Containerized startup enables access logging to stdout/stderr by default | MET | `Dockerfile:22` | Direct Gunicorn stdio flags present |
| AC-2 | Acceptance Criteria | Successful requests emit access logs with method, path, status, and duration | MET | `service_app.py:57`, `service_app.py:343` | Success path logs required fields |
| AC-3 | Acceptance Criteria | Handled request failures emit sanitized failure summaries using only coarse error classes | MET | `service_app.py:65-69`, `service_app.py:268-274`, `service_app.py:314-325`, `service_app.py:341-342` | Failure branches emit coarse summaries |
| AC-4 | Acceptance Criteria | Service logs do not include request bodies, prompts, messages, media, or credentials | MET | `service_app.py:55-67`, `service_app.py:304-343` | Service logger emits metadata only |
| AC-5 | Acceptance Criteria | Managed runtime launch/ready/restart/failure/termination events are logged to stdout/stderr | MET | `local_server_runtime.py:170`, `local_server_runtime.py:183`, `local_server_runtime.py:197`, `local_server_runtime.py:219`, `local_server_runtime.py:236` | All required lifecycle events present |
| AC-6 | Acceptance Criteria | Managed child stdout/stderr is captured and sanitized before forwarding | MET | `local_server_runtime.py:121-139`, `local_server_runtime.py:186-188` | Sanitizer is applied before `logger.info` |
| AC-7 | Acceptance Criteria | Sensitive child-process lines are dropped rather than echoed | PARTIAL | `local_server_runtime.py:106-116` | Some sensitive markers are dropped, but prompt/body-like lines can still pass |
| AC-8 | Acceptance Criteria | Logging stays stdout/stderr only and does not add durable retention or external shipping | MET | `Dockerfile:22`; `docker-compose.yml:1-29`; `grep: no file-handler matches in service_app.py/local_server_runtime.py` | No shipping or retention mechanism added |

| OS-1 | Out of Scope | External log shipping to Loki/ELK/CloudWatch-like systems is not added | MET | `grep: no matches for 'logging:|fluentd|gelf|awslogs|loki|cloudwatch|elk' in docker-compose.yml` | No external shipper config introduced |
| OS-2 | Out of Scope | Long-term retention/rotation is not added | MET | `grep: no matches for 'FileHandler|RotatingFileHandler|TimedRotatingFileHandler|basicConfig(filename=' in service_app.py, local_server_runtime.py` | No durable retention plumbing added |
| OS-3 | Out of Scope | Per-token tracing/span logging is not added | MET | `grep: no matches for 'span|trace|per-token|tracing' in service_app.py, local_server_runtime.py, Dockerfile, docker-compose.yml` | Scope respected |
| OS-4 | Out of Scope | Provider routing policy is not changed | MET | `service_app.py:116-117`, `service_app.py:163` | Provider selection still flows through existing router lookups |

---

## Test-Spec Alignment

| ID | Spec Criterion | Test Location | Alignment | Gap |
|---|---|---|---|---|
| TSA-1 | FR-1: `service_app.py` provides request/access and failure-summary logging | `tests/test_operational_logging.py:80-163,184-191` | ALIGNED | — |
| TSA-2 | FR-2: `local_server_runtime.py` provides lifecycle logging and child forwarding | `tests/test_operational_logging.py:193-332` | SHALLOW | Uses mocks and `StringIO`; does not validate real long-running subprocess behavior or sanitizer breadth |
| TSA-3 | FR-3: Dockerfile enables default Gunicorn stdout/stderr logging | `tests/test_operational_logging.py:165-182` | ALIGNED | — |
| TSA-4 | FR-4: docker-compose remains container-output based | `tests/test_operational_logging.py:165-175` | SHALLOW | Checks absence of common shipping strings, not actual runtime container output behavior |
| TSA-5 | FR-5: service/runtime sanitization rules implemented | `tests/test_operational_logging.py:95-122,193-199,238-268` | SHALLOW | Covers selected markers only; does not exercise generic prompt/body-like child lines or plain base64 payloads |
| TSA-6 | FR-6: regression tests for safe logging behavior exist | `tests/test_operational_logging.py:80-332` | ALIGNED | — |

| TSA-7 | API-1: default, container-visible access logging | `tests/test_operational_logging.py:80-92,165-182` | SHALLOW | Confirms access-log fields and Dockerfile flags, but not actual container-visible emission of application logs |
| TSA-8 | API-2: access logs include method/path/status/duration | `tests/test_operational_logging.py:80-92` | ALIGNED | — |
| TSA-9 | API-3: failure summaries contain route/status/error_class | `tests/test_operational_logging.py:95-163` | MISALIGNED | Tests assert `path=/v1/chat/completions`; the spec requires the failure-summary field `route` |
| TSA-10 | API-4: failure summaries use only allowed coarse classes | `tests/test_operational_logging.py:95-163` | ALIGNED | — |
| TSA-11 | API-5: lifecycle logs include launch/ready/restart/failure/terminate | `tests/test_operational_logging.py:205-332` | ALIGNED | — |
| TSA-12 | API-6: lifecycle logs carry model/base_url and duration/error_class where applicable | `tests/test_operational_logging.py:205-332` | SHALLOW | Checks some `model`/`base_url` substrings, but not `duration_seconds`, failure `error_class`, or terminate model identity |
| TSA-13 | API-7: child stdout/stderr captured, sanitized, and forwarded with context | `tests/test_operational_logging.py:205-268` | ALIGNED | — |
| TSA-14 | API-8: no prompt/chat/body/payload dumps in emitted logs | `tests/test_operational_logging.py:95-122,193-199` | SHALLOW | Covers prompt absence in service logs and exact `"messages"` child JSON, but not generic prompt/body-like child lines |
| TSA-15 | API-9: no media URLs / `data:` URLs / base64 payloads in emitted logs | `tests/test_operational_logging.py:95-122,193-199,238-268` | SHALLOW | Covers URLs and `data:` URLs only; plain base64 payloads without `data:` are untested |
| TSA-16 | API-10: no authorization headers / bearer tokens / API keys in emitted logs | `tests/test_operational_logging.py:95-122,193-199` | ALIGNED | — |
| TSA-17 | API-11: sensitive child lines are dropped rather than rewritten | `tests/test_operational_logging.py:193-199,238-268` | SHALLOW | Verifies selected lines disappear, but not that all sensitive-child patterns are dropped |
| TSA-18 | DM-1: stdout/stderr only, no durable retention/buffering | `tests/test_operational_logging.py:165-182` | SHALLOW | Guards file handlers and common compose drivers, but not other buffering/retention patterns |
| TSA-19 | BC-1: logging changes do not alter request/runtime semantics | `tests/test_operational_logging.py:80-163` | SHALLOW | Verifies statuses and selected payload fields only; would not fail on unrelated multimodal/mmproj semantic changes |

| TSA-20 | EC-1: successful text-only inference still produces an access log | `tests/test_operational_logging.py:80-93` | ALIGNED | — |
| TSA-21 | EC-2: handled `400 invalid_request` logs access + sanitized `client_error` summary | `tests/test_operational_logging.py:95-122` | ALIGNED | — |
| TSA-22 | EC-3: timeout logs access + sanitized `timeout` summary | `tests/test_operational_logging.py:124-136` | ALIGNED | — |
| TSA-23 | EC-4: unavailable error logs access + sanitized `unavailable` summary | `tests/test_operational_logging.py:138-150` | ALIGNED | — |
| TSA-24 | EC-5: unhandled exception logs access + sanitized `server_error` summary | `tests/test_operational_logging.py:152-163` | ALIGNED | — |
| TSA-25 | EC-6: relaunch logs restart plus launch/ready or launch/failure | `tests/test_operational_logging.py:270-320` | SHALLOW | Asserts `restart` and `launch`; does not assert the post-restart `ready`/`failure` completion event |
| TSA-26 | EC-7: child `data:` URL / prompt dump / body-like JSON is dropped | `tests/test_operational_logging.py:193-199,238-268` | SHALLOW | Covers `data:` and exact `"messages"` JSON only; prompt dumps / generic body-like JSON are not exercised |
| TSA-27 | EC-8: safe lifecycle text may be forwarded with operational context | `tests/test_operational_logging.py:201-236` | ALIGNED | — |
| TSA-28 | EC-9: outside Docker, logging still goes to stdout/stderr without external sink | `tests/test_operational_logging.py:165-191` | SHALLOW | Uses `assertLogs` and static file checks, not real stdout/stderr emission in standalone mode |

| TSA-29 | AC-1: container startup enables access logging to stdout/stderr by default | `tests/test_operational_logging.py:165-182` | ALIGNED | — |
| TSA-30 | AC-2: successful requests emit access logs with method/path/status/duration | `tests/test_operational_logging.py:80-92` | ALIGNED | — |
| TSA-31 | AC-3: handled failures emit sanitized failure summaries using coarse classes | `tests/test_operational_logging.py:95-163` | ALIGNED | — |
| TSA-32 | AC-4: service logs exclude bodies/prompts/messages/media/credentials | `tests/test_operational_logging.py:80-122` | ALIGNED | — |
| TSA-33 | AC-5: managed runtime lifecycle events are logged | `tests/test_operational_logging.py:205-332` | ALIGNED | — |
| TSA-34 | AC-6: managed child stdout/stderr is captured and sanitized before forwarding | `tests/test_operational_logging.py:193-199,205-268` | ALIGNED | — |
| TSA-35 | AC-7: sensitive child lines are dropped rather than echoed | `tests/test_operational_logging.py:193-199,238-268` | SHALLOW | Covers selected sensitive markers only; prompt/body-like lines are not tested |
| TSA-36 | AC-8: logging stays stdout/stderr only, no durable retention/external shipping | `tests/test_operational_logging.py:165-182` | SHALLOW | Partial guard only; durable buffering/retention is not directly tested |

| TSA-37 | OS-1: external shipping is not added | `tests/test_operational_logging.py:165-175` | SHALLOW | Checks a few compose strings, not broader shipping integrations |
| TSA-38 | OS-2: long-term retention/rotation is not added | `tests/test_operational_logging.py:176-182` | SHALLOW | Guards file-handler patterns only |
| TSA-39 | OS-3: per-token tracing/span logging is not added | — | ABSENT | No direct test guards against tracing/span logging additions |
| TSA-40 | OS-4: provider routing policy is not changed | — | ABSENT | No direct test guards against routing-policy drift |

---

## Code Quality Issues

CQ-1  
Category: logic error  
Severity: high  
Location: `local_server_runtime.py:121-139`, `local_server_runtime.py:183-219`  
Reasoning: Child stdout/stderr are redirected to `PIPE`, but they are not consumed until after `_wait_for_server()` returns. A verbose child can block on full pipe buffers before readiness, and after readiness `_forward_child_logs()` iterates live pipes to EOF, which ordinarily blocks until the process exits. This can hang `ensure_managed_server()` or prevent startup from completing under reachable conditions.

CQ-2  
Category: security  
Severity: high  
Location: `local_server_runtime.py:101-118`  
Reasoning: `_sanitize_child_log_line()` blocks only a short marker list (`authorization`, `bearer`, `api_key`, exact `"messages"`, `data:`, `http://`, `https://`). Prompt-like text, generic body-like JSON such as `{"prompt":"..."}`, plain message dumps without the exact `"messages"` token, and base64 payloads without a `data:` prefix are forwarded unchanged. Sensitive request-derived content can therefore leak into container logs.

CQ-3  
Category: edge case  
Severity: medium  
Location: `service_app.py:16`; `local_server_runtime.py:14`  
Reasoning: The new `llm.service` and `llm.runtime` loggers are created, but the diff adds no explicit handler/level configuration for standalone execution. Outside Gunicorn or test harnesses that install handlers, `INFO` logs may be suppressed entirely, so the spec’s non-Docker stdout/stderr visibility is not guaranteed by the changed code alone.

CQ-4  
Category: design pattern  
Severity: medium  
Location: `service_app.py:15-52`, `service_app.py:74-95`, `service_app.py:168-190`; `local_server_runtime.py:35-42`, `local_server_runtime.py:90-92`  
Reasoning: The operational-logging diff also introduces multimodal request validation/messages-path dispatch and `--mmproj` runtime configuration. These are unrelated behavior changes that expand the change surface and alter request/runtime semantics inside a logging feature, increasing regression risk and violating the spec’s “observability-only” boundary.

---

## Summary Verdict

**SPEC GAPS + QUALITY ISSUES + TEST DRIFT**

**SPEC GAPS** — the following items are MISSING or PARTIAL:
- FR-2 / FR-5: managed-runtime logging exists, but child-log sanitization is incomplete
- API-3: failure summaries log `path=` instead of required `route=`
- API-6: lifecycle termination logs lose logical model identity (`model=unknown`)
- API-8 / API-9 / API-11 / EC-7 / AC-7: child-log sanitization does not cover generic prompt/body-like content or plain base64 payloads
- BC-1: the diff changes request/runtime semantics beyond logging (`messages` multimodal path and `--mmproj` support)

**QUALITY ISSUES** — the following High issues are present:
- CQ-1 (high): child log capture/forwarding can deadlock or hang managed-server startup
- CQ-2 (high): child-log sanitizer can leak sensitive request-derived content

**TEST DRIFT** — the following spec requirements have SHALLOW or MISALIGNED coverage:
- TSA-9: tests validate `path=` rather than required `route=` in failure summaries
- TSA-12: lifecycle metadata tests do not verify `duration_seconds`, failure `error_class`, or terminate model identity
- TSA-14 / TSA-15 / TSA-17 / TSA-26 / TSA-35: sanitizer tests miss prompt-dump/body-like and plain-base64 cases
- TSA-19: tests do not guard the “no semantics change” invariant
- TSA-28 / TSA-36 / TSA-37 / TSA-38: stdout/stderr-only and no-shipping/no-retention guards are partial

UNVERIFIABLE items requiring manual check:
- EC-9: outside-Docker stdout/stderr emission of `llm.service` / `llm.runtime` `INFO` logs

*This report is read-only. No code changes have been made.*

## Traceability

Append only non-traceability commit hashes here. Traceability-only commits do not record themselves.

### Spec Commits

- 2026-05-17 | 46e4e3fbf081af3ff6e11954031464a04ad8c8e3 | add canonical operational logging spec
- 2026-05-18 | 6f2f3e924021d83048462b5e4353ac924a7207d0 | record accepted test audit and failed spec audit reports for operational logging

### Implementation Commits

- 2026-05-18 | b831568f0716154a36070ea8495c1fe95394489c | add operational service/runtime logging and sanitized child log forwarding
