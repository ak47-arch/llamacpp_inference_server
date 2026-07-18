---
type: Architecture
title: LLM Inference Server Architecture
description: System architecture of the generic inference server, including provider routing, request lifecycle, managed runtimes, monitoring, and prompt capture.
tags: [architecture, providers, routing, monitoring, prompt-capture]
---

# Architecture Overview

## System Diagram

```
HTTP REQUEST ──> service_app.py ──> ProviderRouter ──> Provider (OpenAICompatible/LlamaCpp)
                                        │
                                        ├──> Monitoring (Prometheus metrics)
                                        │
                                        └──> PromptCapture (async NDJSON sink)
```

## Request Lifecycle

The request lifecycle is managed by central Flask lifecycle hooks (`@app.before_request`, `@app.after_request`, `@app.teardown_request`, `@app.errorhandler`) added in v0.3.0.

### 1. Input Validation (`service_app.py`)

The `LLMServiceRuntime.complete_chat()` method in [`/service_app.py`](/service_app.py) is the core request handler:

1. Extracts `model` and `messages` from the request payload
2. Calls `_validate_chat_messages()` which recursively validates each message and content part
3. Supports three content part types: `text`, `image_url`, `input_audio`
4. Resolves the provider via `ProviderRouter.get_provider(model)`
5. Checks modality support: `image` and `audio` are rejected with `400` if the selected provider doesn't support them

### 2. Provider Resolution (`router.py`)

[`/router.py`](/router.py) loads provider definitions from `service_models.yaml`:

- Each provider has an `id`, `provider_type` (`openai_compatible` or `llama_cpp`), `connection` details, `default_params`, and optional `capabilities`
- The config file supports `base_url_env` for resolving base URLs from environment variables
- `managed_server` blocks link an `openai_compatible` provider to a local `llama-server` process

### 3. Completion

The resolved `BaseProvider.complete()` method runs inference. See [Provider Architecture](#provider-architecture) below.

### 4. Response Assembly

The result is assembled into an OpenAI-compatible chat completion response with `id`, `object`, `created`, `model`, `choices`, and `usage`.

## Provider Architecture

### Provider Base (`provider_base.py`)

[`/provider_base.py`](/provider_base.py) defines:

- `BaseProvider` — abstract base class with `complete()` and `warmup()`
- `CompletionResult` — dataclass with `text`, `model_id`, `provider`, `latency_ms`, `tokens_used`
- `ProviderUnavailableError` — raised when backend is unreachable
- `ProviderTimeoutError` — raised when backend exceeds timeout

### OpenAICompatibleProvider (`openai_compatible_provider.py`)

[`/openai_compatible_provider.py`](/openai_compatible_provider.py) is the most-connected module in the system (41 graph edges per the architecture review). Responsibilities:

- Constructs OpenAI-compatible HTTP requests with headers, payload, and timeout
- Manages a linked `llama-server` process via `ensure_managed_server()` if `managed_server` config is set
- Handles `timeout`, `connection_error`, and non-200 responses
- Reports timing metrics to `monitoring.observe_current_chat_provider_duration()`
- Falls back to `reasoning_content` when `content` is empty (for audio-capable backends)

### LlamaCppProvider (`llama_cpp_provider.py`)

[`/llama_cpp_provider.py`](/llama_cpp_provider.py) runs `llama-cli` directly via subprocess:

- Builds command with model path, prompt, temperature, max tokens, threads
- Uses `subprocess.Popen` with `communicate(timeout=...)`
- Strips the echoed prompt prefix from output
- Cleans up timed-out processes with terminate-then-kill escalation

### Known Design Issues (from Architecture Review)

The July 2026 architecture review ([`/docs/technical/ARCHITECTURE_REVIEW_llm_2026-07.md`](/docs/technical/ARCHITECTURE_REVIEW_llm_2026-07.md)) identifies:

1. **No shared Provider interface** — `OpenAICompatibleProvider` and `LlamaCppProvider` evolved independently with no common seam
2. **OpenAICompatibleProvider is a god module** (41 edges) — combines payload construction, HTTP transport, and error mapping
3. **Empty exception types** (`ProviderTimeoutError`, `ProviderUnavailableError`) scattered across the codebase
4. **Prompt capture as explicit calls** rather than middleware wrapping a Provider seam

## Managed Runtime (`local_server_runtime.py`)

[`/local_server_runtime.py`](/local_server_runtime.py) manages the lifecycle of local `llama-server` processes:

- `ensure_managed_server()` checks readiness via `/health` or `/v1/models`, then starts a new process if needed
- Command construction includes: model path, host/port, threads, context size, batch size, optional mmproj path, and extra args
- `_build_subprocess_env()` ensures `LD_LIBRARY_PATH` includes the binary directory
- Child stdout/stderr are forwarded through the logging system (with sanitization to avoid leaking messages bodies, auth headers, or URLs)
- Readiness waits with configurable `startup_timeout_seconds` (default 30s, configured to 180s for the bundled Gemma provider)
- Automatic restart tracking via `monitoring.increment_managed_server_restart()`
- Startup success/failure and duration are reported via monitoring metrics

## Monitoring (`monitoring.py`)

[`/monitoring.py`](/monitoring.py) provides Prometheus metrics using `prometheus_client`:

**Metrics:**
- `llm_service_requests_total` — by route, model, provider, outcome
- `llm_service_in_flight_requests` — current gauge by route
- `llm_service_request_duration_seconds` — histogram by route, model, provider, outcome
- `llm_service_provider_duration_seconds` — provider execution time histogram
- `llm_service_readiness_checks_total` — by model, provider, outcome
- `llm_service_readiness_duration_seconds` — histogram
- `llm_service_managed_server_startups_total` — by model, base_url, outcome
- `llm_service_managed_server_startup_duration_seconds` — histogram
- `llm_service_managed_server_restarts_total` — Counter
- `llm_prompt_capture_records_total` — by mode, result

**Outcomes:** `success`, `client_error`, `timeout`, `unavailable`, `server_error`

**Request context:** per-request model and provider labels are tracked via `ContextVar` and updated through `set_resolved_model()` / `set_resolved_provider()`.

## Prompt Capture (`prompt_capture.py`)

[`/prompt_capture.py`](/prompt_capture.py) provides an async prompt and multimodal-asset capture pipeline:

- Configurable via env vars: `LLM_CAPTURE_ENABLED`, `LLM_CAPTURE_MODE` (`off`, `metadata`, `full`), `LLM_CAPTURE_SINK` (`ndjson`)
- Runs a background worker thread (`llm-prompt-capture`) with a bounded queue
- Supports redaction levels (`off`, `basic`, `strict`) and optional inline media storage
- `NDJSONCaptureSink` writes records as newline-delimited JSON
- Capture can include/exclude system prompts and error records

## Input Modality Support

The service validates and routes structured multimodal content:

| Modality | Supported Types | Provider Requirement |
|----------|----------------|---------------------|
| Text | `text` | All providers |
| Image | `image_url` with base64 data | OpenAI-compatible provider with `image` capability and resolved mmproj path |
| Audio | `input_audio` with base64 data + format | OpenAI-compatible provider with `audio` capability; requires recent `llama.cpp` build |

Modality validation in `_validate_content_parts()` rejects unknown types. Structured content is only supported for `openai_compatible` providers — `LlamaCppProvider` returns a 400 error for multimodal requests.