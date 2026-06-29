# Local Inference Traces

## Status

DRAFT

## Purpose

Define the repository's local inference tracing capability so requests served by locally hosted models can be durably captured, queried, and inspected without changing the existing inference contract or conflating local-model tracing with future remote-provider proxying work.

This capability exists to let developers and operators answer questions such as:

- what request payload was sent to the local model
- what multimodal inputs were present
- what completion or handled error came back
- what redaction and capture settings were applied
- which trace record corresponds to a given local inference request

## Scope

This spec covers:

- durable per-request trace capture for `POST /v1/chat/completions` requests resolved to locally hosted providers
- request-id correlation between the inference response path and stored trace records
- query/read APIs for recent local inference traces
- a visualization-ready trace record shape for local inspection tools and a minimal built-in visual UI for local trace browsing
- trace storage, indexing, retention, and filtering for local inference records
- reuse and extension of the existing prompt-capture normalization pipeline where appropriate
- safety rules for exposing trace-read surfaces on a developer workstation
- regression coverage for trace capture, query behavior, redaction, and local-only enforcement

This spec does not cover:

- proxying or forwarding requests to third-party provider APIs
- machine-wide egress interception, TLS interception, or firewall policy
- routing policy across local and remote providers
- public multi-tenant trace browsing or user-facing admin consoles
- dataset-building, labeling, export, or training workflows
- changing the external public inference contract documented by `specs/openai-compatible-api.md`

Future plan note: remote-provider proxying and machine-level inference firewall behavior are a separate future capability and must land under their own canonical spec.

## Module Ownership

Owning modules and files after implementation:

- `service_app.py` — request-id creation, local-trace capture hooks, and local trace-read route registration
- `prompt_capture.py` — request/response normalization, capture-mode handling, redaction, and asynchronous dispatch used by the local trace pipeline
- `capture_sinks.py` — sink abstractions and append-only export sinks where still used
- `trace_store.py` — durable local trace storage, indexed queries, retention, and record loading
- `trace_views.py` — trace summary/detail serialization for inspection clients and future visualization tools
- `trace_ui.py` — minimal built-in HTML trace list/detail pages for local developer inspection
- `monitoring.py` — bounded low-privacy metrics for trace write/query success, failure, and retention outcomes when added
- `tests/test_prompt_capture.py` — existing write-path regression coverage retained for prompt-capture behavior
- `tests/test_local_inference_traces.py` — acceptance and regression tests for trace storage, JSON read APIs, and minimal built-in UI routes
- `specs/local-inference-traces.md` — canonical specification for this capability

`service_app.py` must remain thin at the HTTP boundary. Durable storage, query filtering, record shaping, and retention belong outside the request handlers.

## Current Behavior

When local inference tracing is disabled, the service behavior remains unchanged:

- `POST /v1/chat/completions` continues serving locally hosted models without storing trace records
- operational stdout/stderr logs remain metadata-only
- `GET /metrics` remains aggregate-only and does not expose request bodies or trace content
- no trace query endpoints or trace UI routes are available

When local inference tracing is enabled, each handled local inference request receives a stable opaque `request_id` and may produce one durable trace record.

A request is considered a local inference request for this capability when the resolved provider is backed by repository-managed local runtime infrastructure or another explicitly configured local provider implementation. Requests that target future remote-provider adapters are out of scope for this spec.

Trace capture continues to run asynchronously so inference completion does not wait on durable storage latency beyond bounded queue insertion work.

The durable trace record is a queryable superset of the repository's existing prompt-capture record shape. It preserves the normalized request, response, usage, and redaction metadata already produced by the capture pipeline and adds the indexing and summary fields needed for query/read APIs.

The first implemented queryable store is SQLite. NDJSON may remain available as an append-only export sink, but it is not the primary query path for trace inspection.

- listing recent local inference traces in reverse chronological order
- filtering by bounded indexed fields such as `model`, `provider`, `outcome`, and time window
- fetching one full stored trace by `request_id`
- serving a minimal built-in HTML UI for recent-trace browsing and per-trace inspection

The trace-read surface is for local inspection only. It is excluded from the public OpenAPI contract exposed at `GET /openapi.json`.

Unless explicitly overridden by configuration, the trace-read surface only serves loopback clients. Requests from non-loopback addresses are rejected even when the main inference API is bound on `0.0.0.0`.

## Interfaces

### Configuration

The capability must support at least the following conceptual configuration fields:

- `local_traces.enabled`
- `local_traces.capture_mode` — `off`, `metadata`, or `full`
- `local_traces.redaction_level` — `off`, `basic`, or `strict`
- `local_traces.include_system_prompts` — boolean, default `false`
- `local_traces.include_error_records` — boolean, default `false`
- `local_traces.store_inline_media` — boolean, default `false`
- `local_traces.queue_max_records`
- `local_traces.store.backend` — `sqlite`
- `local_traces.store.path`
- `local_traces.retention.max_records` and/or `local_traces.retention.max_age_days`
- `local_traces.api.enabled` — boolean, default `false`
- `local_traces.api.allow_remote` — boolean, default `false`
- `local_traces.api.default_page_size`
- `local_traces.api.max_page_size`

Equivalent environment variables may include:

- `LLM_LOCAL_TRACES_ENABLED`
- `LLM_LOCAL_TRACES_MODE`
- `LLM_LOCAL_TRACES_REDACTION_LEVEL`
- `LLM_LOCAL_TRACES_INCLUDE_SYSTEM_PROMPTS`
- `LLM_LOCAL_TRACES_INCLUDE_ERROR_RECORDS`
- `LLM_LOCAL_TRACES_STORE_INLINE_MEDIA`
- `LLM_LOCAL_TRACES_QUEUE_MAX_RECORDS`
- `LLM_LOCAL_TRACES_STORE_BACKEND`
- `LLM_LOCAL_TRACES_SQLITE_PATH`
- `LLM_LOCAL_TRACES_RETENTION_MAX_RECORDS`
- `LLM_LOCAL_TRACES_RETENTION_MAX_AGE_DAYS`
- `LLM_LOCAL_TRACES_API_ENABLED`
- `LLM_LOCAL_TRACES_API_ALLOW_REMOTE`
- `LLM_LOCAL_TRACES_API_DEFAULT_PAGE_SIZE`
- `LLM_LOCAL_TRACES_API_MAX_PAGE_SIZE`

The existing `LLM_CAPTURE_*` environment variables may remain as a compatibility layer for the write path during migration, but the local trace capability must expose a clear dedicated configuration surface.

### Visual UI configuration

The capability must also support a minimal built-in visual UI configuration surface:

- `local_traces.ui.enabled` — boolean, default `false`
- `local_traces.ui.show_full_payloads_by_default` — boolean, default `false`

Equivalent environment variables may include:

- `LLM_LOCAL_TRACES_UI_ENABLED`
- `LLM_LOCAL_TRACES_UI_SHOW_FULL_PAYLOADS_BY_DEFAULT`

The built-in UI is a local developer convenience layered on the same trace store and read policy as the JSON endpoints. It must not require a separate frontend build pipeline.


### Read endpoints

#### `GET /debug/traces`

Lists recent local inference traces.

Supported query parameters:

- `limit`
- `before`
- `after`
- `model`
- `provider`
- `outcome`
- `capture_mode`

Response body:

```json
{
  "object": "list",
  "data": [
    {
      "request_id": "req_123",
      "timestamp": "2026-05-31T12:34:56Z",
      "model": "gemma_e2b_q4_local",
      "provider": "openai_compatible",
      "status_code": 200,
      "outcome": "success",
      "capture_mode": "full",
      "message_count": 2,
      "input_modalities": ["text"],
      "assistant_text_present": true
    }
  ],
  "paging": {
    "has_more": false,
    "next_before": null
  }
}
```

#### `GET /debug/traces/<request_id>`

Returns one full local inference trace record.

Response body contains at least:

- `request_id`
- `timestamp`
- `route`
- `model`
- `provider`
- `status_code`
- `outcome`
- `capture_mode`
- `request`
- `response`
- `usage`
- `redaction`
- `metadata`

When the record does not exist, the route returns `404` with the repository's standard error body shape.

#### `GET /debug/traces/ui`

Returns a minimal server-rendered HTML page for browsing recent local inference traces.

The page must, at minimum:

- show the current filter state
- show a reverse-chronological table or list of recent traces
- include descriptive columns/labels for timestamp, model, provider, outcome, status code, capture mode, message count, and input modalities
- provide a clear link from each summary row to the corresponding detail page
- render safely without requiring client-side JavaScript to see the main trace information

The default presentation should be plain, readable, and descriptive rather than highly styled. Clear field labels and visible empty states are preferred over compactness.

#### `GET /debug/traces/ui/<request_id>`

Returns a minimal server-rendered HTML detail page for one local inference trace.

The page must, at minimum:

- show top-level request metadata near the top
- show request, response, usage, and redaction sections with explicit headings
- show whether the record was captured in `metadata` or `full` mode
- preserve the stored redaction results without attempting to reconstruct omitted content
- link back to the recent-traces page

When the record does not exist, the route returns `404` with the repository's standard error body shape or a minimal HTML not-found page produced from the same route family.


### Write-path trace record shape

Each stored local inference trace contains at least:

- `request_id`
- `timestamp`
- `route`
- `model`
- `provider`
- `status_code`
- `outcome`
- `capture_mode`
- `request`
- `response`
- `usage`
- `redaction`
- `metadata`

The record may additionally include indexed summary fields derived from stored content, such as:

- `message_count`
- `input_modalities`
- `assistant_text_present`
- `assistant_text_length`
- `error_type`

### Public API contract separation

`GET /debug/traces`, `GET /debug/traces/<request_id>`, `GET /debug/traces/ui`, and `GET /debug/traces/ui/<request_id>` are local developer/debug surfaces. They are not part of the public external inference API and must not be published in `GET /openapi.json` during this stage.

## Data Model

### Capture modes

`off`
- no durable trace record
- no trace query data

`metadata`
- store queryable request/response metadata only
- do not store raw prompt text or completion text
- do not store raw inline media bytes
- may store lengths, counts, modality sets, checksums, and safe summary fields

`full`
- store normalized request messages and completion output after configured redaction
- default to excluding system prompts unless explicitly enabled
- default to excluding raw inline media bytes unless explicitly enabled
- preserve multimodal part ordering in normalized form

### Primary store

The first queryable store is SQLite.

The SQLite store must provide:

- uniqueness by `request_id`
- reverse-chronological listing by indexed timestamp
- filtering by bounded fields used by the list API
- bounded retention enforcement without requiring raw file scans

NDJSON append-only output may still be supported for export or audit workflows, but query/read endpoints must not depend on scanning NDJSON files.

### Request section

Normalized request data may include:

- `messages`
- `params`
- `message_count`
- `input_modalities`
- `system_prompt_included`
- checksums and byte counts for inline media when computable

### Response section

Normalized response data may include:

- `assistant_text`
- `assistant_text_present`
- `assistant_text_length`
- `finish_reason`
- `error_type`
- `error_message`

### Metadata section

The metadata section may include repository-owned operationally safe fields such as:

- storage backend identity
- retention status markers
- write failure/drop markers when represented after the fact
- future visualization hints derived from bounded safe fields

It must not contain unbounded raw log lines, auth material, or reconstructed dropped content.

### UI view model

The built-in UI view model may derive bounded presentation fields from stored trace data, such as:

- display-safe timestamps
- human-readable modality summaries
- explicit empty-state messages
- truncated previews for long text fields on list pages

The UI must read from stored trace data and safe derived fields only. It must not depend on operational logs or reconstruct content that was omitted during capture.


## Rules and Invariants

1. Local inference tracing is opt-in and disabled by default.
2. This capability applies only to locally hosted inference providers. Remote-provider proxying is a separate feature.
3. Inference request success or failure must not depend on trace storage success.
4. Queue backpressure must degrade by dropping trace records rather than blocking inference indefinitely.
5. Operational stdout/stderr logging must remain metadata-only and must not become the storage or query path for prompt content.
6. The public external API documented by `specs/openai-compatible-api.md` must remain unchanged during this feature; local trace-read routes are separate debug surfaces.
7. The trace-read surface must be disabled by default.
8. The built-in trace UI must also be disabled by default unless explicitly enabled.
9. When trace-read surfaces are enabled, non-loopback clients must be rejected unless `allow_remote` is explicitly enabled.
10. Redaction is applied before durable persistence; the read path and UI must not reconstruct content intentionally removed or replaced during capture.
11. Query filters and metric labels for this capability must remain bounded and must not accept prompt-derived values as labels or indexed dimensions.
12. Requests captured in `metadata` mode must remain inspectable through summaries and UI detail views without exposing raw prompt or completion text.
13. Multimodal request normalization must preserve part ordering and type information while respecting capture mode and inline-media storage settings.
14. Trace retention must be enforced by the durable store and must not require scanning raw append-only export files.
15. The capability must preserve existing request semantics for `POST /v1/chat/completions` whether tracing is enabled or disabled.
16. The built-in UI must remain minimal, server-rendered, and readable by default; it must not require a separate frontend asset pipeline.

## Edge Cases

- tracing enabled but storage backend initialization fails
- queue full while inference succeeds
- durable write fails after inference succeeds
- handled provider timeout or unavailable outcomes when error-record capture is disabled
- handled provider timeout or unavailable outcomes when error-record capture is enabled
- multimodal requests with inline image/audio payloads in `metadata` mode
- multimodal requests with inline image/audio payloads in `full` mode and media storage disabled
- requests with system prompts when system-prompt capture is disabled
- requests with system prompts when system-prompt capture is enabled
- read request for an unknown `request_id`
- read request from a non-loopback client while remote access is disabled
- retention removing older records while newer records remain queryable
- requests resolved to non-local providers after future provider adapters are added; those requests must not be captured under this capability unless explicitly classified as local
- UI route requested while the JSON trace API is enabled but the visual UI is disabled
- metadata-mode trace viewed through the HTML detail page
- very long assistant text requiring readable truncation on list pages without truncating stored detail records

## Acceptance Criteria

1. The repository provides a canonical local inference trace capability separate from remote-provider proxying.
2. When local tracing is disabled, existing local inference behavior remains unchanged and no trace query routes or trace UI routes are served.
3. When local tracing is enabled in `metadata` mode, successful local inference requests persist queryable records without storing raw prompt or completion text.
4. When local tracing is enabled in `full` mode, successful local inference requests persist normalized request and response content subject to configured redaction.
5. Trace capture continues to run asynchronously and trace storage failures do not fail inference requests.
6. The first queryable store is SQLite and supports indexed listing by recency plus bounded filtering by `model`, `provider`, `outcome`, and time range.
7. `GET /debug/traces` lists recent trace summaries in reverse chronological order with bounded pagination.
8. `GET /debug/traces/<request_id>` returns one full stored trace record or `404` when absent.
9. When enabled, `GET /debug/traces/ui` renders a minimal readable HTML summary view for recent traces without requiring client-side JavaScript for core content.
10. When enabled, `GET /debug/traces/ui/<request_id>` renders a minimal readable HTML detail view with explicit request, response, usage, and redaction sections.
11. Trace-read routes and trace UI routes are disabled by default and are rejected for non-loopback clients unless remote access is explicitly enabled.
12. The public `GET /openapi.json` document does not publish the local trace JSON routes or trace UI routes during this stage.
13. Multimodal text/image/audio requests remain inspectable in stored trace records and the built-in UI without storing raw inline media bytes unless explicitly enabled.
14. Existing prompt-capture normalization and redaction behavior remains consistent for the local trace write path.
15. Retention limits can remove older trace records without affecting newer-query correctness or inference availability.
16. Regression tests cover disabled behavior, metadata/full modes, non-loopback rejection, query filtering, missing-record behavior, retention, multimodal normalization, and the minimal built-in UI routes.

## Test Plan

- create an app with local tracing disabled and verify `POST /v1/chat/completions` still succeeds while `GET /debug/traces` and `GET /debug/traces/ui` return `404`
- enable metadata-mode tracing with a SQLite store, issue a successful local inference request, and verify the stored/listed record excludes raw prompt and assistant text
- enable full-mode tracing with redaction controls, issue a successful local inference request, and verify the stored/detail record includes normalized request/response data with expected redaction behavior
- issue image/audio multimodal local requests and verify stored records preserve type/order and metadata while omitting inline media bytes by default
- force store write failure or queue saturation and verify inference still succeeds while failure/drop outcomes are recorded through bounded metrics
- query `GET /debug/traces` with bounded filters and verify reverse-chronological ordering and pagination behavior
- query `GET /debug/traces/<request_id>` for an existing and a missing record and verify `200`/`404` behavior
- render `GET /debug/traces/ui` and verify the page shows descriptive summary labels, recent trace rows, filter state, and links to detail pages
- render `GET /debug/traces/ui/<request_id>` for traces captured in `metadata` and `full` modes and verify explicit request/response/usage/redaction headings plus preserved redaction behavior
- call trace-read routes from a simulated non-loopback client and verify rejection unless remote access is explicitly enabled
- enforce retention limits and verify older records are pruned without breaking newer lookups
- run the relevant Python test suite to confirm no regression in the existing local inference API

## Out of Scope

- provider-API proxying for OpenAI, Anthropic, Gemini, or other remote services
- machine-wide interception of inference traffic from arbitrary applications
- TLS MITM, certificate installation, or transparent proxying
- destination allow/block policy for third-party inference endpoints
- billing, quota, or remote-provider budget enforcement
- rich frontend application frameworks, SPA state management, or a separate frontend asset pipeline for trace browsing
- multi-user auth or tenant-aware access control
- publishing trace-read routes as part of the public external API contract
- dataset review queues, labeling workflows, export pipelines, or training jobs

## Traceability

Append only non-traceability commit hashes here. Traceability-only commits do not record themselves.

### Spec Commits

### Implementation Commits
