# OpenAI-Compatible API

## Status

VERIFIED

## Purpose

Define the repository's external HTTP API contract for health, readiness, model discovery, machine-readable schema publication, and OpenAI-compatible chat completions so other applications can integrate against a stable interface.

## Scope

This spec covers:

- `service_app.py` HTTP routes and JSON response shapes
- `README.md` API examples for external callers
- `tests/test_generic_inference_server.py` coverage for published contract endpoints
- the machine-readable OpenAPI document exposed by the service

This spec does not cover:

- provider-specific outbound request construction
- routing policy between providers
- authentication or CORS policy
- streaming chat completion responses
- prompt retention, analytics, or training-data storage

## Module Ownership

Owning modules and files:

- `service_app.py` — Flask routes, response payloads, and OpenAPI schema publication
- `router.py` — configured provider registry used for model discovery
- `README.md` — public usage examples for external callers
- `tests/test_generic_inference_server.py` — regression coverage for contract publication and model listing

`service_app.py` owns the HTTP boundary. `router.py` owns the configured model ids surfaced through model discovery. `README.md` documents public usage without defining behavior independently of this spec.

## Current Behavior

The service exposes the following HTTP endpoints:

- `GET /health`
- `GET /ready`
- `GET /openapi.json`
- `GET /v1/models`
- `GET /metrics`
- `POST /v1/chat/completions`

`GET /openapi.json` returns an OpenAPI 3.1 document describing the repository's external HTTP contract.

`GET /v1/models` returns the configured logical model ids as an OpenAI-style list response. Each item includes:

- `id`
- `object: "model"`
- `owned_by: "llm"`

The top-level response includes:

- `object: "list"`
- `data`: array of model objects

`POST /v1/chat/completions` remains the canonical inference endpoint. It returns an OpenAI-style chat completion response containing:

- `id`
- `object: "chat.completion"`
- `created`
- `model`
- `choices`
- `usage`

The published OpenAPI schema documents the request and response shapes for health, readiness, model listing, chat completions, and error responses.

## Interfaces

### `GET /health`

Response body:

```json
{"status":"ok","service":"inference-server"}
```

### `GET /ready`

Success response body:

```json
{"ready":true,"models":["<configured-model-id>"]}
```

Failure responses use the standard error body shape described below.

### `GET /v1/models`

Response body:

```json
{
  "object": "list",
  "data": [
    {
      "id": "gemma_e4b_q4_local",
      "object": "model",
      "owned_by": "llm"
    }
  ]
}
```

### `GET /openapi.json`

Response body is JSON with:

- `openapi: "3.1.0"`
- `info`
- `paths`
- `components.schemas`

The schema must include path entries for:

- `/health`
- `/ready`
- `/v1/models`
- `/v1/chat/completions`
- `/metrics`

### `POST /v1/chat/completions`

Request body fields:

- `model`
- `messages`
- optional `temperature`
- optional `max_tokens`
- optional `timeout_seconds`

Response body fields:

- `id`
- `object`
- `created`
- `model`
- `choices`
- `usage`

### Standard error shape

Error responses use:

```json
{
  "error": {
    "type": "<error-type>",
    "message": "<human-readable-message>"
  }
}
```

## Data Model

Model discovery response semantics:

- `object` is always `list`
- each `data[]` item represents one configured logical model id
- `owned_by` is always `llm`

OpenAPI publication semantics:

- `openapi` version is `3.1.0`
- `ChatCompletionRequest` and `ChatCompletionResponse` are present under `components.schemas`
- the chat completions path references the request schema via `$ref`

## Rules and Invariants

1. `POST /v1/chat/completions` remains the canonical inference endpoint.
2. `GET /v1/models` reflects configured provider ids from the active runtime.
3. `GET /v1/models` does not require provider warmup or inference.
4. `GET /openapi.json` publishes a machine-readable schema without requiring external files.
5. The OpenAPI document must describe the same externally supported endpoints the service exposes.
6. Model discovery uses OpenAI-style response framing with `object: "list"` and per-item `object: "model"`.

## Edge Cases

- If no providers are configured, `GET /v1/models` returns `{"object":"list","data":[]}`.
- Readiness failures return the standard error body with HTTP 503.
- Invalid chat-completions requests return the standard error body with HTTP 400.
- Provider timeouts return the standard error body with HTTP 504.
- Provider/runtime availability failures return the standard error body with HTTP 503.

## Acceptance Criteria

1. The Flask app exposes `GET /v1/models` and returns configured model ids in an OpenAI-style list response.
2. The Flask app exposes `GET /openapi.json` and returns an OpenAPI 3.1 document.
3. The OpenAPI document includes `/v1/chat/completions` and `/v1/models` path definitions.
4. The OpenAPI document includes `ChatCompletionRequest` and `ChatCompletionResponse` schemas.
5. `README.md` documents the published OpenAPI contract endpoint and model discovery endpoint.

## Test Plan

- create an app with a stub runtime and verify `GET /v1/models` returns `200` with the configured model id
- create an app with a stub runtime and verify `GET /openapi.json` returns `200` with OpenAPI 3.1 metadata and the expected path/schema references
- run the relevant Python test suite to confirm no regressions in existing API behavior

## Out of Scope

- bearer-token authentication
- CORS headers and browser policy
- SSE or chunked streaming responses
- SDK-specific helper libraries
- storage, retention, or analysis of prompt/context payloads

## Traceability

Append only non-traceability commit hashes here. Traceability-only commits do not record themselves.

### Spec Commits

- 2026-05-21 | 6f75815189931e290c0df5b9a0403dd594e4858c | add canonical external API contract

### Implementation Commits

- 2026-05-21 | 83fad9bd6efb0a1c29826480a24376ee31e01c97 | publish OpenAPI contract and model discovery
