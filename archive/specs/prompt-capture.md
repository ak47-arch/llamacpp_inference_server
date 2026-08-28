> **DEPRECATED** — This file is part of the retired spec-driven development process (2026-08-28).
> The factory workflow (PRDs at `docs/prd/` + vision docs at `docs/vision/`) replaces it.
> Retained for retrospective analysis only. Do not use as active guidance.

# Prompt Capture

## Status

VERIFIED

## Purpose

Define a separate, explicitly configurable prompt/context capture capability focused on durably capturing the prompts and multimodal assets sent for inference, without weakening the repository's existing low-privacy operational logging and metrics boundaries. Downstream dataset-building, curation, export, and training workflows are acknowledged as future plans but are not implemented in this stage.

## Scope

This spec covers:

- capture of inbound chat-completions request content and associated multimodal assets
- capture of completion results and handled error outcomes needed to analyze inference traffic later
- separation between operational logs and durable prompt-capture records
- request-id correlation between inference requests and capture records
- configurable capture modes, sinks, redaction, retention, and failure behavior
- asynchronous capture delivery so inference availability does not depend on storage success
- multimodal handling rules for text, image, and audio request content

This spec does not cover:

- authentication or CORS
- public client-facing APIs for querying captured records
- dataset-building, dataset-review, curation, labeling, export, model training, or fine-tuning workflows
- automatic consent, legal-policy, or tenant-contract enforcement outside configured repository behavior
- operational stdout/stderr logging rules already owned by `specs/operational-logging.md`
- metrics semantics already owned by `specs/monitoring.md`

Future plan note: captured records are intended to support downstream dataset and training work later, but those downstream capabilities are explicitly out of scope for this stage.

## Module Ownership

Owning modules and files after implementation:

- `service_app.py` — request-id creation, capture hooks, and post-request capture invocation
- `prompt_capture.py` — capture configuration, record assembly, redaction, queueing, and dispatch
- `capture_sinks.py` — sink implementations and sink factory logic
- `monitoring.py` — low-cardinality metrics for capture success/failure/drop/queue behavior
- `tests/test_prompt_capture.py` — prompt-capture regression and acceptance tests
- `specs/prompt-capture.md` — canonical specification for this capability

`service_app.py` must remain thin at the HTTP boundary. Prompt/content persistence, redaction, and sink logic belong outside the request handler implementation.

## Current Behavior

Prompt capture is disabled by default.

When disabled, the service behavior remains unchanged:

- inference requests succeed or fail independently of any capture subsystem
- operational logs remain metadata-only and do not include prompt content
- metrics remain low-privacy and do not expose prompt-derived labels

When enabled, the service generates a stable `request_id` for each `POST /v1/chat/completions` request and uses it for:

- operational correlation
- capture-record identity
- future downstream analysis workflows

Capture runs after request validation and provider execution has produced either a completion result or a handled error outcome.

Capture records are written through an asynchronous in-process queue. Request handling must not block on durable sink latency beyond bounded queue insertion work.

If the capture queue is full, capture is dropped for that request, a low-cardinality metric is incremented, and inference continues normally.

Capture behavior is controlled by configuration modes:

- `off` — no capture records are produced
- `metadata` — capture request/response metadata only, without raw prompt or completion text
- `full` — capture full normalized messages, params, completion output, and selected metadata after configured redaction

The first implemented durable sink is an NDJSON append-only file sink. When prompt capture is enabled through environment variables, the repository currently supports:

- `LLM_CAPTURE_SINK=ndjson`
- `LLM_CAPTURE_FILE_PATH=/absolute/path/to/capture.ndjson`

Additional sinks may be added later behind the same sink interface.

Multimodal capture stores structured request content in normalized form. Raw inline image/audio payload bytes are not stored by default. Instead, metadata mode stores modality, approximate size, and checksum/fingerprint fields only. Full mode may store raw inline payloads only when explicitly enabled by configuration.

## Interfaces

### Configuration

Prompt capture configuration may be supplied through environment variables and/or structured config. The capability must support at least the following conceptual fields:

- `capture.enabled`
- `capture.mode` — `off`, `metadata`, or `full`
- `capture.sink` — sink identifier
- `capture.redaction_level` — `off`, `basic`, or `strict`
- `capture.queue_max_records`
- `capture.retention_days` or sink-specific retention configuration
- `capture.store_inline_media` — boolean, default `false`
- `capture.include_system_prompts` — boolean, default `false`
- `capture.include_error_records` — boolean

Equivalent environment variables may include:

- `LLM_CAPTURE_ENABLED`
- `LLM_CAPTURE_MODE`
- `LLM_CAPTURE_SINK`
- `LLM_CAPTURE_REDACTION_LEVEL`
- `LLM_CAPTURE_QUEUE_MAX_RECORDS`
- `LLM_CAPTURE_RETENTION_DAYS`
- `LLM_CAPTURE_STORE_INLINE_MEDIA`
- `LLM_CAPTURE_INCLUDE_SYSTEM_PROMPTS`
- `LLM_CAPTURE_INCLUDE_ERROR_RECORDS`
- `LLM_CAPTURE_FILE_PATH` for the NDJSON sink

### Capture record shape

Each persisted capture record contains at least:

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

### Request section

Normalized request data may include:

- `messages`
- `params`
- `message_count`
- `input_modalities`
- `system_prompt_included` flag
- content hashes, byte counts, or checksums for inline media

### Response section

Normalized response data may include:

- `assistant_text`
- `finish_reason`
- `error_type`
- `error_message`
- provider/model response metadata safe for persistence

### Downstream planning note

Captured records may later feed separate dataset-building, review, labeling, export, or training workflows.

That future use is planning context only. This stage does not implement:

- review queues
- quality labels
- safety labels
- dataset exports
- fine-tuning jobs
- training orchestration

## Data Model

### Capture modes

`off`
- no durable record
- no prompt/content serialization

`metadata`
- store request/response metadata only
- do not store raw text content from prompts or completions
- do not store raw inline media bytes
- may store lengths, counts, modality sets, fingerprints, and checksums

`full`
- store normalized message content and completion output after redaction
- store params and usage
- default to excluding system prompts unless explicitly enabled
- default to excluding raw inline media bytes unless explicitly enabled

### Request id semantics

- one `request_id` per inbound chat-completions request
- request id is opaque and non-sequential
- request id may appear in logs and capture records but not as a metric label

### Redaction levels

`off`
- no repository-applied content redaction before persistence

`basic`
- remove obvious secrets/tokens/credentials
- hash or drop explicit user identifiers when configured
- mask email addresses, phone numbers, and bearer-token-like strings

`strict`
- apply `basic`
- drop or hash system prompts by default
- replace inline media payloads with metadata-only placeholders
- allow sink-specific allowlists for fields permitted to remain in cleartext

### Multimodal normalization

For structured content-part arrays:

- preserve ordering and part types
- preserve plain text parts subject to capture mode and redaction
- represent image/audio parts in normalized objects
- include `sha256` or equivalent checksum fields when payload bytes are present
- include payload byte counts when computable

## Rules and Invariants

1. Prompt capture is opt-in and disabled by default.
2. Operational stdout/stderr logging must remain metadata-only and must not become the storage mechanism for prompts or completions.
3. Capture failures must not fail inference requests.
4. Queue backpressure must degrade by dropping capture records rather than blocking inference indefinitely.
5. Capture metrics must remain low-cardinality and must not use request ids, prompt text, or user-derived content as labels.
6. `request_id` must be stable across the operational path for one request and must link logs, metrics context, and capture records.
7. Metadata mode must never store raw prompt text, completion text, or raw inline media bytes.
8. Full mode must exclude system prompts by default unless explicitly enabled.
9. Raw inline image/audio payload storage must remain disabled by default even in full mode.
10. Capture records must distinguish successful completions from handled client, timeout, unavailable, and server-error outcomes.
11. The capture subsystem must be modular so new sinks can be added without changing HTTP request semantics.
12. Prompt capture must be specified and tested independently from operational logging.
13. This stage captures inference inputs and outputs only; downstream dataset curation and training workflows remain separate future work.

## Edge Cases

- If capture is disabled, no background worker or sink writes are started.
- If the sink cannot be initialized, startup either fails fast when capture is required or disables capture with an explicit operational warning, depending on configuration.
- If queue insertion fails because the queue is full, the record is dropped and inference still returns normally.
- If a request fails validation before provider execution, capture may still persist a metadata/error record when `include_error_records` is enabled.
- If a provider returns multimodal content with empty text and auxiliary reasoning fields, capture stores the surfaced assistant text that the service returned, not hidden discarded fields.
- If inline media storage is disabled, raw base64 payloads are replaced with modality metadata and checksums before persistence.
- If redaction transforms fields, the record indicates which redaction level and substitutions were applied.
- If no token counts are available, usage fields may be `null`.

## Acceptance Criteria

1. Prompt capture is disabled by default and existing inference behavior remains unchanged when it is off.
2. Enabling metadata mode persists request/response metadata without storing raw prompts, completion text, or raw inline media bytes.
3. Enabling full mode persists normalized prompt/response content while still applying configured redaction and default exclusions.
4. The service generates a per-request `request_id` and includes it in capture records.
5. Capture write failures or full queues do not change inference response status codes or bodies.
6. Capture metrics record low-cardinality success/failure/drop behavior without request-id or prompt-derived labels.
7. Multimodal requests are normalized so image/audio parts can be represented without storing raw payload bytes by default.
8. At least one durable local sink is implemented behind a sink abstraction.

## Test Plan

- verify capture disabled by default and no capture samples are emitted during normal chat completions
- verify metadata mode persists a record with request_id, model, status, counts, modality metadata, and no raw prompt/completion text
- verify full mode persists normalized messages and assistant response while excluding system prompts by default
- verify explicit config can include system prompts when desired
- verify inline image/audio base64 payloads are replaced with metadata-only placeholders unless explicitly enabled
- verify sink write failure does not fail the HTTP response
- verify full queue causes dropped-capture accounting without blocking inference
- verify capture metrics expose low-cardinality totals for written, failed, and dropped records
- verify handled invalid requests can optionally emit metadata/error capture records

## Out of Scope

- auth and access control for capture administration
- CORS behavior
- data subject request workflows or legal review processes
- review queues, labeling tools, or dataset curation workflows
- fine-tuning job launchers
- automatic dataset quality scoring
- dataset export pipelines
- public APIs for browsing or downloading capture records
- distributed queue infrastructure beyond an in-process first phase

## Traceability

Append only non-traceability commit hashes here. Traceability-only commits do not record themselves.

### Spec Commits

- 2026-05-21 | 721172b62703d786c17ab624f98e8f89deb2c952 | add canonical capture spec

### Implementation Commits

- 2026-05-23 | 241931c51d84ed2c508c233c3830b4ec7ad14c21 | capture prompts and multimodal assets
