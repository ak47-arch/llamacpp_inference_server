# OpenAI-Compatible Provider

## Status

APPROVED

## Purpose

Define how this repository's OpenAI-compatible provider and bundled provider registry handle outbound chat-completions requests, optional request parameter merging, structured multimodal message pass-through, provider capability validation, and managed local `llama-server` multimodal projector wiring without introducing application-specific defaults or hidden model downloads.

## Scope

This spec covers:

- `openai_compatible_provider.py`
- `provider_base.py` provider-call contract used by the HTTP chat service
- `service_app.py` validation and pass-through of OpenAI-style chat messages
- `local_server_runtime.py` managed local `llama-server` command construction for multimodal projector wiring
- provider entries in `service_models.yaml` that target OpenAI-compatible backends
- the bundled example provider set shipped by this repository
- request parameter handling for `temperature`, `max_tokens`, and `timeout_seconds`
- structured multimodal content pass-through for OpenAI-compatible providers
- explicit provider capability checks for image/audio request parts
- externalized multimodal projector path configuration for managed local vision-capable providers

This spec does not cover:

- direct `llama_cpp_provider.py` subprocess multimodal behavior
- routing policy between providers
- model-specific sampling semantics implemented by upstream inference servers
- monitoring or observability features
- Docker runtime timeout tuning
- auto-downloading model or projector assets from the network
- repository-managed storage of multimodal projector artifacts

## Module Ownership

Owning modules and files:

- `provider_base.py` — provider completion interface used by the service/provider seam
- `openai_compatible_provider.py` — outbound OpenAI-compatible request construction, multimodal message pass-through, local timeout handling, and managed-runtime warmup entrypoints
- `service_app.py` — request validation, OpenAI-style message normalization, provider capability checks, and passing optional request parameters through to providers
- `local_server_runtime.py` — managed local `llama-server` startup command construction including optional multimodal projector arguments
- `service_models.yaml` — bundled provider registry examples, capability declarations, managed runtime wiring, and optional provider defaults
- `tests/test_openai_compatible_provider.py` — provider payload construction and capability regression tests
- `tests/test_generic_inference_server.py` — bundled provider config regression tests
- `tests/test_multimodal_chat.py` — service-level multimodal request validation and pass-through tests for this capability

`service_app.py` owns validation of inbound OpenAI-style message payloads and fail-fast capability checks. `openai_compatible_provider.py` owns upstream payload preservation. `local_server_runtime.py` owns `llama-server` command-line wiring. `service_models.yaml` owns bundled provider topology and declarative capability/config examples.

## Current Behavior

The repository ships bundled example OpenAI-compatible local providers in `service_models.yaml`.

The bundled provider set includes:

- `gemma_e2b_local`
- `gemma_e4b_local`
- `gemma_e4b_q4_local`

`gemma_e4b_q4_local` remains configured as a managed local provider backed by:

- model path `/models/google_gemma-4-E4B-it-Q4_K_M.gguf`
- local managed server port `18014`

The example bundled providers keep reasoning-related `llama-server` flags present as commented-out lines inside `managed_server.extra_args` rather than active runtime arguments. Because these lines are commented out, the bundled example providers do not actively force reasoning behavior on or off through `extra_args`.

The service accepts OpenAI-style `POST /v1/chat/completions` requests where each message `content` is either:

- a plain string, or
- a list of typed content parts

For OpenAI-compatible providers, the service preserves the inbound `messages` structure and forwards it upstream instead of flattening structured content into prompt text.

Supported structured content part types for pass-through are:

- `text`
- `image_url`
- `input_audio`

Existing text-only callers remain supported without changing their request shape.

If a request contains image or audio content parts and the selected provider does not have active support for those modalities, the service rejects the request with `400 invalid_request` before provider warmup or upstream inference is attempted.

`llama_cpp_provider.py` remains text-only in this feature area. Structured multimodal chat support is limited to the OpenAI-compatible provider path.

OpenAI-compatible providers send outbound `POST /v1/chat/completions` requests containing `model` and the validated `messages` array for every request.

`temperature` is included in the outbound payload only when explicitly provided through provider configuration or the incoming request.

`max_tokens` is included in the outbound payload only when explicitly provided through provider configuration or the incoming request.

`timeout_seconds` is not forwarded as an upstream model parameter. It is used only as the local HTTP client timeout for the outbound request.

The example providers in `service_models.yaml` do not define application-specific `default_params` for `temperature` or `max_tokens`. A provider may define `timeout_seconds` only when an operational override is required for that provider.

Caller-supplied parameters override provider-configured parameters when both are present.

When no `temperature` or `max_tokens` is supplied, the upstream OpenAI-compatible backend receives no implicit defaults from this repository and may apply its own backend defaults.

Managed local OpenAI-compatible providers may declare a multimodal projector path using an environment-variable override and optional literal fallback. When a projector path resolves successfully, `local_server_runtime.py` adds `--mmproj <path>` to the launched `llama-server` command. The repository does not auto-download projector artifacts.

## Interfaces

### Provider configuration

OpenAI-compatible provider entries may define:

- `id`
- `provider_type: openai_compatible`
- `model_name`
- `capabilities.input_modalities` (optional)
- `connection.base_url`
- `connection.api_key` (optional)
- `connection.managed_server` (optional)
- `default_params.timeout_seconds` (optional)
- `default_params.temperature` (optional)
- `default_params.max_tokens` (optional)

If `capabilities.input_modalities` is omitted, the provider is treated as text-only and supports only `text` input.

Allowed `capabilities.input_modalities` values are:

- `text`
- `image`
- `audio`

### Bundled example provider set

The repository's bundled example provider ids are:

- `gemma_e2b_local`
- `gemma_e4b_local`
- `gemma_e4b_q4_local`

`gemma_e4b_q4_local` uses:

- `base_url: http://127.0.0.1:18014`
- `port: 18014`
- `model_path: /models/google_gemma-4-E4B-it-Q4_K_M.gguf`

Bundled providers may declare image support through `capabilities.input_modalities`, but image requests are only valid when the managed runtime also has a resolved projector path.

### Managed server fields used by bundled providers

Bundled managed providers may define:

- `binary_path`
- `model_path`
- `host`
- `port`
- `startup_timeout_seconds`
- `ctx_size`
- `threads`
- `extra_args`
- `mmproj_path_env` (optional)
- `mmproj_path` (optional fallback)

`mmproj_path_env` is resolved first. If it is unset or empty, `mmproj_path` may be used as a fallback. If neither resolves to a usable path, multimodal vision support is inactive for that provider.

### Commented reasoning example lines

The bundled example providers keep the following reasoning-related lines commented out inside `managed_server.extra_args`:

- `--reasoning`
- `off`
- `--reasoning-budget`
- `0`
- `--reasoning-format`
- `none`

### Inbound request schema

`service_app.py` accepts OpenAI-style chat payloads with:

- `model`
- `messages`
- optional `temperature`
- optional `max_tokens`
- optional `timeout_seconds`

Each `messages[]` item must be an object with:

- `role`
- `content`

`content` may be either:

- a string, or
- a list of typed content-part objects

Supported content-part object shapes are:

- `{ "type": "text", "text": <string> }`
- `{ "type": "image_url", "image_url": { "url": <string> } }`
- `{ "type": "input_audio", "input_audio": { ... } }`

### Outbound payload

Minimum outbound payload:

- `model`
- `messages`

Optional outbound payload fields:

- `temperature` only when explicitly configured or requested
- `max_tokens` only when explicitly configured or requested

`timeout_seconds` is never included in the outbound JSON payload.

For OpenAI-compatible providers, outbound `messages` preserve message ordering, role values, string content, and structured content-part arrays from the validated inbound request.

## Data Model

Merged runtime parameters are computed as:

- provider `default_params`
- overridden by caller-supplied request params

Relevant parameter semantics:

- `temperature`: optional numeric sampling control
- `max_tokens`: optional numeric output cap
- `timeout_seconds`: optional numeric local HTTP timeout

Chat message semantics:

- `messages`: ordered list of chat messages
- `role`: chat role string passed through to the upstream OpenAI-compatible backend
- `content`: either plain string content or ordered structured content parts
- structured content parts are preserved as provided after validation

Provider capability semantics:

- omitted `capabilities.input_modalities` means `text` only
- string-only message content requires only `text`
- any `image_url` content part requires active `image` support
- any `input_audio` content part requires active `audio` support
- for managed local providers, active image support requires both configured `image` capability and a resolved multimodal projector path

Bundled provider ids currently expected:

- `gemma_e2b_local`
- `gemma_e4b_local`
- `gemma_e4b_q4_local`

`gemma_e4b_q4_local` managed runtime values:

- `base_url: http://127.0.0.1:18014`
- `port: 18014`
- `model_path: /models/google_gemma-4-E4B-it-Q4_K_M.gguf`

Commented reasoning example lines are textual config artifacts, not active runtime arguments.

Invariants:

- `model` and `messages` are always present in outbound requests
- existing string-content callers remain supported unchanged
- supported structured message content is forwarded only for OpenAI-compatible providers
- omitted optional parameters remain omitted in the outbound payload
- caller-supplied values override provider defaults
- timeout configuration affects only the HTTP client call, not upstream model semantics
- commented reasoning lines are not active runtime flags
- the repository never auto-downloads multimodal projector assets

## Rules and Invariants

1. The bundled example provider registry must include `gemma_e4b_q4_local`.
2. `gemma_e4b_q4_local` must point to `/models/google_gemma-4-E4B-it-Q4_K_M.gguf`.
3. The reasoning-related `llama-server` lines remain commented out in the bundled example providers.
4. Commented reasoning-related lines are documentation/config examples only and must not be interpreted as active runtime arguments.
5. The provider must not inject implicit `temperature` defaults into outbound requests.
6. The provider must not inject implicit `max_tokens` defaults into outbound requests.
7. `timeout_seconds` must be used only as a local request timeout.
8. Provider example configuration in `service_models.yaml` must not encode old application-specific defaults for generic use.
9. Caller-supplied parameters must override provider-configured defaults.
10. The absence of `temperature` or `max_tokens` in the inbound request must not be converted into repository-defined fallback values in the outbound payload.
11. The HTTP service must preserve validated OpenAI-style structured `messages` content for OpenAI-compatible providers instead of flattening it into prompt text.
12. Existing text-only OpenAI chat requests must keep working without changing their request shape.
13. Requests containing image or audio content must fail fast with `400 invalid_request` when the selected provider lacks active support for those modalities.
14. Direct `llama_cpp_provider.py` invocation remains text-only and is out of scope for multimodal chat support in this feature.
15. Managed local vision support must use only explicitly configured projector paths from provider configuration and environment overrides.
16. The repository must not auto-download multimodal projector artifacts or enable network fetches implicitly.

## Edge Cases

- If provider configuration sets `temperature` and the caller omits it, the configured value is sent.
- If provider configuration sets `max_tokens` and the caller omits it, the configured value is sent.
- If both provider configuration and caller request set the same parameter, the caller value wins.
- If no `timeout_seconds` is configured or requested, the provider uses its built-in local HTTP timeout fallback.
- If the upstream backend rejects the request, the provider surfaces a provider-unavailable error.
- If the upstream backend is unreachable, the provider resets managed-runtime readiness and surfaces a provider-unavailable error.
- If `messages` is missing, empty, or contains non-object items, the service returns `400 invalid_request`.
- If a structured content part is missing its required field for the declared `type`, the service returns `400 invalid_request`.
- If a content part uses an unknown `type`, the service returns `400 invalid_request`.
- If a provider declares `image` capability but no projector path resolves at runtime, image requests are rejected as invalid for that provider.
- If a provider receives only string content or `text` parts, no multimodal projector is required.
- If a future change adds multimodal support for direct `llama_cpp_provider.py`, this spec must be updated before implementation.
- If the E4B Q4 model path changes, both the config and this spec must be updated in place.
- If bundled example providers are renamed, tests and this spec must be updated together.

## Acceptance Criteria

1. `service_models.yaml` includes `gemma_e4b_q4_local`.
2. `gemma_e4b_q4_local` uses model path `/models/google_gemma-4-E4B-it-Q4_K_M.gguf`.
3. `service_models.yaml` keeps the reasoning-related `extra_args` example lines commented out for the bundled providers.
4. Repository tests assert the presence of `gemma_e4b_q4_local` and the commented reasoning-related lines.
5. `service_models.yaml` example providers do not define `default_params.temperature`.
6. `service_models.yaml` example providers do not define `default_params.max_tokens`.
7. `openai_compatible_provider.py` omits `temperature` from the outbound payload when it is not explicitly configured or requested.
8. `openai_compatible_provider.py` omits `max_tokens` from the outbound payload when it is not explicitly configured or requested.
9. `openai_compatible_provider.py` still applies a local HTTP timeout fallback when no timeout is specified.
10. Caller-supplied `temperature` and `max_tokens` still override provider configuration when supplied.
11. `service_app.py` accepts OpenAI-style `messages` whose `content` is either a string or an ordered list of supported structured content parts.
12. For OpenAI-compatible providers, structured `messages` content is forwarded upstream without being flattened into plain prompt text.
13. A multimodal request to a provider without active support for the required modality returns `400 invalid_request` before provider warmup or upstream inference.
14. Managed local OpenAI-compatible providers can resolve multimodal projector paths from `mmproj_path_env` with optional `mmproj_path` fallback and pass them to `llama-server` as `--mmproj`.
15. The repository does not auto-download multimodal projector assets.
16. Direct `llama_cpp_provider.py` remains text-only and existing text-only callers continue to work unchanged.

## Test Plan

- Load `service_models.yaml` and assert that `gemma_e4b_q4_local` is present.
- Assert that `gemma_e4b_q4_local` points to `/models/google_gemma-4-E4B-it-Q4_K_M.gguf`.
- Read `service_models.yaml` text and assert that the reasoning-related lines remain commented out.
- Verify example providers in `service_models.yaml` do not define `temperature` or `max_tokens` under `default_params`.
- Verify outbound payload omits `temperature` and `max_tokens` when neither config nor request supplies them.
- Verify outbound payload includes `temperature` and `max_tokens` when provided by provider config.
- Verify caller-supplied `temperature` and `max_tokens` override configured values.
- Verify the HTTP client still uses a timeout fallback when no timeout is specified.
- Verify `service_app.py` accepts string `content` and structured content-part arrays for OpenAI-compatible requests.
- Verify structured `messages` are forwarded upstream unchanged for OpenAI-compatible providers.
- Verify unsupported multimodal requests fail with `400 invalid_request` before provider invocation.
- Verify managed local projector path resolution prefers `mmproj_path_env` and falls back to `mmproj_path`.
- Verify `llama-server` command construction includes `--mmproj` only when a projector path resolves.
- Run the repository test suite covering generic inference server repository expectations and multimodal request behavior.

## Out of Scope

- Adding multimodal support to direct `llama_cpp_provider.py`
- Changing request routing or model selection behavior
- Standardizing backend-specific default sampling behavior across all upstream servers
- Monitoring or observability implementation
- Docker runtime timeout tuning
- Downloading or vendoring multimodal projector assets into the repository

## Traceability

Append only non-traceability commit hashes here. Traceability-only commits do not record themselves.

### Spec Commits

- 2026-05-17 | 0affeba38d2f6c8f7cfe1652875649d54e8d8e40 | consolidate bundled provider config and defaulting rules into canonical spec

### Implementation Commits

- 2026-05-17 | 4fbdb89841c35c5b522c187508dd04c3208bc476 | add e4b q4 provider and remove implicit temperature and max_tokens defaults
