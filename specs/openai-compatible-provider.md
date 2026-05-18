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

## Accepted Test Audit Report

# Test Audit Report

**Spec:** specs/openai-compatible-provider.md  
**Tests Reviewed:** tests/test_openai_compatible_provider.py, tests/test_generic_inference_server.py, tests/test_multimodal_chat.py  
**Red Output Reviewed:** yes  
**Inputs provided:** spec ✓ | tests ✓ | red output ✓ | standards doc ✗  
**Audited by:** test-verifier agent (independent session)  
**Date:** 2026-05-18

---

## Requirement Coverage Matrix

| ID | Requirement | Coverage Status | Evidence (file:line) | Notes |
|---|---|---|---|---|
| AC-1 | `service_models.yaml` includes `gemma_e4b_q4_local`. | COVERED_STRONG | `tests/test_generic_inference_server.py:51` | Direct config assertion. |
| API-1 | `gemma_e4b_q4_local` uses `base_url: http://127.0.0.1:18014`. | COVERED_STRONG | `tests/test_generic_inference_server.py:51` | Direct config assertion. |
| API-2 | `gemma_e4b_q4_local` managed runtime uses port `18014`. | COVERED_STRONG | `tests/test_generic_inference_server.py:51` | Direct config assertion. |
| AC-2 | `gemma_e4b_q4_local` uses model path `/models/google_gemma-4-E4B-it-Q4_K_M.gguf`. | COVERED_STRONG | `tests/test_generic_inference_server.py:51` | Direct config assertion. |
| AC-3 | Bundled providers keep reasoning-related `extra_args` lines commented out in `service_models.yaml`. | COVERED_STRONG | `tests/test_generic_inference_server.py:63` | Checks all listed commented lines for all bundled providers. |
| AC-4 | Commented reasoning lines are not interpreted as active runtime arguments. | COVERED_STRONG | `tests/test_generic_inference_server.py:75` | Asserts built command omits reasoning flags/values. |
| AC-5 | Repository tests assert bundled provider presence and commented reasoning lines. | COVERED_STRONG | `tests/test_generic_inference_server.py:51, tests/test_generic_inference_server.py:63` | The reviewed suite contains both assertions. |
| AC-6 | Bundled example providers do not define `default_params.temperature`. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:19` | Checks bundled providers' `default_params`. |
| AC-7 | Bundled example providers do not define `default_params.max_tokens`. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:19` | Checks bundled providers' `default_params`. |
| RI-1 | Example config does not encode old application-specific defaults for generic use. | COVERED_WEAK | `tests/test_openai_compatible_provider.py:19` | Test enforces absence of `temperature`/`max_tokens`, but not the broader rule wording. |
| API-3 | OpenAI-compatible provider posts to `/v1/chat/completions`. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:31` | Asserts exact request URL. |
| API-4 | Outbound payload always includes `model`. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:31` | Direct payload assertion. |
| API-5 | Outbound payload always includes `messages`. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:31, tests/test_openai_compatible_provider.py:182` | Covered for plain-string and structured-message paths. |
| AC-8 | Outbound payload omits `temperature` when not explicitly configured or requested. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:31` | Direct omission assertion. |
| AC-9 | Outbound payload omits `max_tokens` when not explicitly configured or requested. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:31` | Direct omission assertion. |
| EC-1 | If provider config sets `temperature` and caller omits it, configured value is sent. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:55` | Direct payload assertion. |
| EC-2 | If provider config sets `max_tokens` and caller omits it, configured value is sent. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:55` | Direct payload assertion. |
| AC-10 | Caller-supplied `temperature` overrides provider-configured value. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:77` | Direct payload assertion. |
| AC-11 | Caller-supplied `max_tokens` overrides provider-configured value. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:77` | Direct payload assertion. |
| AC-12 | Provider uses a local HTTP timeout fallback when no timeout is specified. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:99` | Asserts `timeout` kwarg exists and is positive. |
| RI-2 | `timeout_seconds` is used only as local HTTP timeout and never forwarded in outbound JSON. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:120, tests/test_openai_compatible_provider.py:140, tests/test_openai_compatible_provider.py:161` | Multiple assertions cover request, configured, and override cases. |
| EC-3 | If provider config sets `timeout_seconds` and caller omits it, configured timeout is used. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:140` | Direct timeout assertion. |
| EC-4 | Caller-supplied `timeout_seconds` overrides provider-configured timeout. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:161` | Direct timeout assertion. |
| AC-13 | Service accepts string `content` in OpenAI-style messages. | COVERED_STRONG | `tests/test_multimodal_chat.py:94` | Positive path with unchanged request shape. |
| AC-14 | Service accepts ordered structured content-part arrays using supported part types. | COVERED_STRONG | `tests/test_multimodal_chat.py:68, tests/test_multimodal_chat.py:107` | Positive image/text and audio/text structured-message paths. |
| AC-15 | For OpenAI-compatible providers, structured `messages` are forwarded upstream unchanged rather than flattened. | COVERED_STRONG | `tests/test_multimodal_chat.py:68, tests/test_openai_compatible_provider.py:182` | Equality checks on forwarded `messages`; provider test also checks no `prompt` field in payload. |
| API-6 | Service passes caller `temperature` and `max_tokens` through the provider seam. | COVERED_STRONG | `tests/test_multimodal_chat.py:68` | Asserts exact `params` dict at provider call site. |
| AC-16 | Image requests to providers without active image support fail fast with `400 invalid_request` before warmup/provider invocation. | COVERED_STRONG | `tests/test_multimodal_chat.py:128` | Asserts 400, error type/message, zero warmup calls, and zero provider calls. |
| AC-17 | Audio requests to providers without active audio support fail fast with `400 invalid_request` before warmup/provider invocation. | COVERED_STRONG | `tests/test_multimodal_chat.py:155` | Asserts 400, error type/message, zero warmup calls, and zero provider calls. |
| API-7 | Missing `model` returns `400 invalid_request`. | COVERED_STRONG | `tests/test_multimodal_chat.py:259` | Direct service-boundary validation. |
| API-8 | Missing `messages` returns `400 invalid_request`. | COVERED_STRONG | `tests/test_multimodal_chat.py:274` | Direct service-boundary validation. |
| API-9 | Empty `messages` returns `400 invalid_request`. | COVERED_STRONG | `tests/test_multimodal_chat.py:286` | Direct service-boundary validation. |
| API-10 | Non-object message items return `400 invalid_request`. | COVERED_STRONG | `tests/test_multimodal_chat.py:301` | Direct service-boundary validation. |
| API-11 | Messages missing `role` return `400 invalid_request`. | COVERED_STRONG | `tests/test_multimodal_chat.py:316` | Direct service-boundary validation. |
| API-12 | Messages missing `content` return `400 invalid_request`. | COVERED_STRONG | `tests/test_multimodal_chat.py:330` | Direct service-boundary validation. |
| API-13 | Message `content` must be a string or list of content parts. | COVERED_STRONG | `tests/test_multimodal_chat.py:223` | Rejects numeric content. |
| API-14 | Content parts must be objects. | COVERED_STRONG | `tests/test_multimodal_chat.py:241` | Rejects string list member. |
| API-15 | `text` content parts require a `text` field. | COVERED_STRONG | `tests/test_multimodal_chat.py:344` | Direct validation assertion. |
| API-16 | `image_url` content parts require `image_url.url`. | COVERED_STRONG | `tests/test_multimodal_chat.py:182` | Direct validation assertion. |
| API-17 | `input_audio` content parts require `input_audio.data` and `input_audio.format`. | COVERED_STRONG | `tests/test_multimodal_chat.py:361` | Direct validation assertion. |
| API-18 | Unknown content-part types return `400 invalid_request`. | COVERED_STRONG | `tests/test_multimodal_chat.py:200` | Rejects `video_url`. |
| BC-1 | If `capabilities.input_modalities` is omitted, provider is treated as text-only. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:242` | Direct modality assertion. |
| BC-2 | Invalid `input_modalities` values are rejected. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:250` | Rejects unsupported `video` modality. |
| BC-3 | Managed local image support requires declared image capability plus a resolved projector path. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:259, tests/test_multimodal_chat.py:394` | Provider-level and service-level coverage. |
| AC-18 | `mmproj_path_env` is preferred and `mmproj_path` is used as fallback when env is unset/empty. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:274` | Covers env-set, env-unset, and empty-string cases. |
| AC-19 | `llama-server` command includes `--mmproj` only when a projector path resolves. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:296` | Covers env path, fallback path, and no-path cases. |
| AC-20 | Repository does not auto-download multimodal projector assets or enable implicit network fetches. | COVERED_WEAK | `tests/test_openai_compatible_provider.py:296, tests/test_openai_compatible_provider.py:368` | Behavioral intent is targeted, but repository-wide enforcement is proxy-based and partial. |
| OS-1 | Direct `llama_cpp_provider.py` remains text-only. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:413` | Direct modality assertion on real provider class. |
| OS-2 | Structured multimodal requests are rejected for non-OpenAI providers at the service boundary. | COVERED_STRONG | `tests/test_multimodal_chat.py:451, tests/test_multimodal_chat.py:477` | Covered with recording non-OpenAI provider and real `LlamaCppProvider`. |
| EC-5 | If a provider declares image capability but no projector path resolves, image requests are rejected as invalid for that provider. | COVERED_STRONG | `tests/test_multimodal_chat.py:394` | Direct service-boundary assertion. |
| EC-6 | If request contains only string content or `text` parts, no multimodal projector is required and text-only callers still work unchanged. | COVERED_STRONG | `tests/test_multimodal_chat.py:94, tests/test_multimodal_chat.py:425` | Covers plain-string and text-part-array paths. |
| EC-7 | `timeout_seconds` is accepted by the service and passed through to the provider params. | COVERED_STRONG | `tests/test_multimodal_chat.py:380` | Direct provider-call assertion. |
| EC-8 | If upstream backend rejects the request, provider surfaces `ProviderUnavailableError`. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:334` | Direct exception assertion. |
| EC-9 | If upstream backend is unreachable, provider resets managed-runtime readiness and surfaces `ProviderUnavailableError`. | COVERED_STRONG | `tests/test_openai_compatible_provider.py:349` | Direct exception and state-reset assertions. |

---

## Test Quality Issues

TQ-1  
Category: weak-assertion  
Severity: medium  
Location: `tests/test_openai_compatible_provider.py:368`  
Reasoning: The no-auto-download requirement is asserted partly by scanning only top-level `*.py` files plus `service_models.yaml`, `Dockerfile`, and `README.md`. That does not fully exercise the repository-wide spec claim that multimodal projector assets are never auto-downloaded, so coverage for that rule is only partial.

TQ-2  
Category: flaky-risk  
Severity: low  
Location: `tests/test_openai_compatible_provider.py:368`  
Reasoning: The same test fails on literal token presence in non-runtime files such as `README.md` and `Dockerfile`. Documentation or example text could trigger failure without any behavioral regression in code, reducing signal quality.

TQ-3  
Category: coverage-gap  
Severity: low  
Location: `tests/test_openai_compatible_provider.py:19`  
Reasoning: The broader rule forbidding application-specific generic defaults is tested only through absence of `temperature` and `max_tokens` in bundled provider `default_params`. That directly covers the main named defaults in the spec, but only weakly covers the broader wording of the rule.

---

## Red-Phase Validity

Status: VALID_RED  
Evidence: The failures are feature-aligned red failures, not infrastructure failures. Examples from the provided output include: `TypeError: OpenAICompatibleProvider.complete() got an unexpected keyword argument 'messages'`, `TypeError: OpenAICompatibleProvider.__init__() got an unexpected keyword argument 'input_modalities'`, `AttributeError: 'OpenAICompatibleProvider' object has no attribute 'supported_input_modalities'`, `AssertionError: '--mmproj' not found in [...]`, and multiple service-boundary expectation failures such as `AssertionError: 200 != 400` for unsupported multimodal and invalid payload cases. The single Flask `500` trace terminates in the test's own sentinel `AssertionError("complete should not be called")`, which indicates missing fail-fast validation rather than an unrelated harness or environment problem.

---

## Summary Verdict

**TEST GAPS** - one or more requirements are MISSING/COVERED_WEAK/MISALIGNED.

Unverifiable items:
- None

---

*This report is read-only. No code changes have been made.*

## Latest Spec Audit Report

# Spec Audit Report

**Spec:** `specs/openai-compatible-provider.md`  
**Diff reviewed:** `/tmp/spec_feature_a.diff`  
**Inputs provided:** spec ✓ | diff ✓ | process doc ✗ | additional context ✗  
**Audited by:** spec-verifier agent (independent session)  
**Date:** 2026-05-18

---

Mapping note: duplicated requirements across Current Behavior, Interfaces, Data Model, Rules/Invariants, Edge Cases, Acceptance Criteria, Test Plan, and Out of Scope were consolidated into unique criteria IDs below.

## Spec Compliance

| ID | Section | Criterion | Status | Evidence (file:line) | Notes |
|---|---|---|---|---|---|
| CFG-1 | Bundled example provider set | Bundled provider registry includes `gemma_e2b_local`, `gemma_e4b_local`, and `gemma_e4b_q4_local` | MET | `service_models.yaml:4,32,60`; `tests/test_generic_inference_server.py:51` | All three ids present |
| CFG-2 | Bundled example provider set / Data Model | `gemma_e4b_q4_local` uses `base_url http://127.0.0.1:18014`, `port 18014`, and model path `/models/google_gemma-4-E4B-it-Q4_K_M.gguf` | MET | `service_models.yaml:68,71,73`; `tests/test_generic_inference_server.py:59-61` | Matches spec |
| CFG-3 | Commented reasoning example lines | Bundled providers keep reasoning-related `extra_args` lines commented out | MET | `service_models.yaml:23-28,51-56,79-84`; `tests/test_generic_inference_server.py:63` | Comment markers preserved |
| CFG-4 | Commented reasoning example lines | Commented reasoning lines are not treated as active runtime arguments | MET | `local_server_runtime.py:94-96`; `tests/test_generic_inference_server.py:75` | Runtime only appends actual `extra_args` list items |
| CFG-5 | Rules / Acceptance Criteria | Bundled example providers do not encode generic `temperature`/`max_tokens` defaults; bundled `default_params` are limited to `timeout_seconds` | MET | `service_models.yaml:29-30,57-58,86-87`; `tests/test_openai_compatible_provider.py:19-29` | No bundled sampling defaults present |
| INT-1 | Provider configuration | If `capabilities.input_modalities` is omitted, provider is text-only; allowed values are only `text`, `image`, `audio` | MET | `openai_compatible_provider.py:39-43,70-74`; `router.py:63`; `tests/test_openai_compatible_provider.py:242,250` | Default and validation both implemented |
| PAY-1 | Outbound payload | OpenAI-compatible provider sends `POST /v1/chat/completions` and always includes `model` and `messages` | MET | `openai_compatible_provider.py:98-114`; `tests/test_openai_compatible_provider.py:31-53` | Exact path and payload asserted |
| PAY-2 | Rules / Edge Cases | `temperature` is omitted when unspecified and included when explicitly configured/requested | MET | `openai_compatible_provider.py:86,102-103`; `tests/test_openai_compatible_provider.py:31-53,55-75` | Conditional payload population present |
| PAY-3 | Rules / Edge Cases | `max_tokens` is omitted when unspecified and included when explicitly configured/requested | MET | `openai_compatible_provider.py:86,104-105`; `tests/test_openai_compatible_provider.py:31-53,55-75` | Conditional payload population present |
| PAY-4 | Rules / Edge Cases | Caller-supplied `temperature` and `max_tokens` override provider defaults | MET | `openai_compatible_provider.py:86,102-105`; `tests/test_openai_compatible_provider.py:77-97` | Merge order gives request precedence |
| PAY-5 | Rules / Edge Cases | `timeout_seconds` is used only as local HTTP timeout, never forwarded upstream, and a built-in/configured timeout applies when omitted by caller | MET | `openai_compatible_provider.py:86,107-114`; `tests/test_openai_compatible_provider.py:99-159` | Outbound JSON never includes `timeout_seconds` |
| PAY-6 | Rules / Edge Cases | Caller-supplied `timeout_seconds` overrides provider-configured timeout | MET | `openai_compatible_provider.py:86,107-114`; `tests/test_openai_compatible_provider.py:161-180` | Same merge order applies to timeout |
| API-1 | Inbound request schema | Service requires `model` and a non-empty `messages` list | MET | `service_app.py:152-158,317`; `tests/test_multimodal_chat.py:259,274,286` | Missing/empty cases return 400 |
| API-2 | Inbound request schema | Each message must be an object containing `role` and `content` | MET | `service_app.py:79-87,317`; `tests/test_multimodal_chat.py:301,316,330` | Validation is explicit |
| API-3 | Inbound request schema | Message `content` may be a string or a list of content-part objects | MET | `service_app.py:89-99,24,317`; `tests/test_multimodal_chat.py:94,223,241` | Positive and negative paths covered |
| API-4 | Inbound request schema | Supported structured content-part types are `text`, `image_url`, and `input_audio`; unknown types are rejected | MET | `service_app.py:15,27-28,317`; `tests/test_multimodal_chat.py:68,107,200` | Allowed set matches spec |
| API-5 | Inbound request schema | `text` content parts require a `text` field | MET | `service_app.py:30-33,317`; `tests/test_multimodal_chat.py:344-359` | Direct validation |
| API-6 | Inbound request schema | `image_url` content parts require `image_url.url` | MET | `service_app.py:34-38,317`; `tests/test_multimodal_chat.py:182-197` | Direct validation |
| API-7 | Inbound request schema | `input_audio` content parts require `input_audio.data` and `input_audio.format` | MET | `service_app.py:39-49,317`; `tests/test_multimodal_chat.py:361-378` | Direct validation |
| MOD-1 | Current Behavior / Acceptance Criteria | For OpenAI-compatible providers, structured `messages` are forwarded upstream unchanged instead of being flattened | MET | `service_app.py:188-190`; `openai_compatible_provider.py:88-105`; `tests/test_multimodal_chat.py:68-92`; `tests/test_openai_compatible_provider.py:182-211` | Service and provider preserve structure |
| MOD-2 | Current Behavior / Invariants | Existing string-content callers continue to work unchanged | MET | `service_app.py:90-93,188-190`; `tests/test_multimodal_chat.py:94-105` | String path still accepted and forwarded |
| MOD-3 | Current Behavior | Valid structured audio messages pass through when audio support is active | MET | `service_app.py:160-176,188-190`; `openai_compatible_provider.py:98-105`; `tests/test_multimodal_chat.py:107-126`; `tests/test_openai_compatible_provider.py:213-240` | Positive audio path present |
| MOD-4 | Acceptance Criteria / Edge Cases | Image requests to a provider without active image support fail fast with `400 invalid_request` before warmup/provider invocation | MET | `service_app.py:170-176,317`; `tests/test_multimodal_chat.py:128-153` | Test asserts 400 and zero warmup/provider calls |
| MOD-5 | Acceptance Criteria / Edge Cases | Audio requests to a provider without active audio support fail fast with `400 invalid_request` before warmup/provider invocation | MET | `service_app.py:170-176,317`; `tests/test_multimodal_chat.py:155-180` | Test asserts 400 and zero warmup/provider calls |
| MOD-6 | Current Behavior / Out of Scope | Structured multimodal support is limited to the OpenAI-compatible path; non-OpenAI providers and direct `llama_cpp_provider.py` remain text-only at the service boundary | MET | `service_app.py:167-168,190-192`; `provider_base.py:29-31`; `tests/test_multimodal_chat.py:452-476,478-500`; `tests/test_openai_compatible_provider.py:413-419` | Non-OpenAI structured requests rejected |
| MM-1 | Data Model / Edge Cases | Managed local image support requires declared `image` capability plus a resolved projector path | MET | `openai_compatible_provider.py:70-74`; `router.py:63`; `tests/test_openai_compatible_provider.py:259-272`; `tests/test_multimodal_chat.py:394-423` | Active image modality is gated |
| MM-2 | Managed server fields | `mmproj_path_env` is preferred; `mmproj_path` is used as fallback when env is unset/empty | MET | `openai_compatible_provider.py:60-68`; `local_server_runtime.py:35-44`; `tests/test_openai_compatible_provider.py:274-294` | Preference order matches spec |
| MM-3 | Acceptance Criteria | `llama-server` command includes `--mmproj <path>` only when a projector path resolves | MET | `local_server_runtime.py:90-92`; `tests/test_openai_compatible_provider.py:296-332` | Conditional flag insertion present |
| ERR-1 | Edge Cases | If the upstream backend rejects the request, provider surfaces `ProviderUnavailableError` | MET | `openai_compatible_provider.py:136-140`; `tests/test_openai_compatible_provider.py:334-347` | Non-200 path raises unavailable |
| ERR-2 | Edge Cases | If the upstream backend is unreachable, provider resets managed-runtime readiness and surfaces `ProviderUnavailableError` | MET | `openai_compatible_provider.py:124-128`; `tests/test_openai_compatible_provider.py:349-366` | Readiness reset is explicit |
| OS-1 | Out of Scope | No routing-policy changes, backend-sampling standardization, or Docker-timeout tuning scope creep is introduced by this feature | MET | `router.py:63`; `openai_compatible_provider.py:102-107` | Diff adds capability wiring and conditional forwarding only |
| OS-2 | Out of Scope | Monitoring/observability features are out of scope and should not be introduced by this feature | MISSING | `service_app.py:16,56,66`; `local_server_runtime.py:14,134,170,183,196,218,236`; `openai_compatible_provider.py:117,126,137,149`; `llama_cpp_provider.py:73,84,97` | New logging and monitoring instrumentation were added |
| OS-3 | Out of Scope | Repository must not auto-download or vendor/store multimodal projector artifacts | MET | `local_server_runtime.py:35-44,90-92`; `service_models.yaml:21,49,77`; `tests/test_openai_compatible_provider.py:296-332,368-411` | Diff uses only explicit paths/env overrides; no fetch behavior added |

---

## Test-Spec Alignment

| ID | Spec Criterion | Test Location | Alignment | Gap |
|---|---|---|---|---|
| TSA-1 | CFG-1 bundled provider ids present | `tests/test_generic_inference_server.py:51` | ALIGNED | — |
| TSA-2 | CFG-2 `gemma_e4b_q4_local` base_url/port/model_path | `tests/test_generic_inference_server.py:51` | ALIGNED | — |
| TSA-3 | CFG-3 reasoning lines remain commented | `tests/test_generic_inference_server.py:63` | ALIGNED | — |
| TSA-4 | CFG-4 commented reasoning lines not active at runtime | `tests/test_generic_inference_server.py:75` | ALIGNED | — |
| TSA-5 | CFG-5 bundled defaults omit generic sampling defaults | `tests/test_openai_compatible_provider.py:19` | ALIGNED | — |
| TSA-6 | INT-1 text-only default + invalid modality rejection | `tests/test_openai_compatible_provider.py:242,250` | ALIGNED | — |
| TSA-7 | PAY-1 outbound POST includes path/model/messages | `tests/test_openai_compatible_provider.py:31` | ALIGNED | — |
| TSA-8 | PAY-2 conditional `temperature` omission/inclusion | `tests/test_openai_compatible_provider.py:31,55` | ALIGNED | — |
| TSA-9 | PAY-3 conditional `max_tokens` omission/inclusion | `tests/test_openai_compatible_provider.py:31,55` | ALIGNED | — |
| TSA-10 | PAY-4 caller overrides configured sampling params | `tests/test_openai_compatible_provider.py:77` | ALIGNED | — |
| TSA-11 | PAY-5 timeout local-only and fallback/configured application | `tests/test_openai_compatible_provider.py:99,120,140` | ALIGNED | — |
| TSA-12 | PAY-6 caller timeout overrides configured timeout | `tests/test_openai_compatible_provider.py:161` | ALIGNED | — |
| TSA-13 | API-1 `model` and non-empty `messages` required | `tests/test_multimodal_chat.py:259,274,286` | ALIGNED | — |
| TSA-14 | API-2 each message must be object with `role` and `content` | `tests/test_multimodal_chat.py:301,316,330` | ALIGNED | — |
| TSA-15 | API-3 content must be string or list of part objects | `tests/test_multimodal_chat.py:94,223,241` | ALIGNED | — |
| TSA-16 | API-4 supported part types only; unknown rejected | `tests/test_multimodal_chat.py:68,107,200` | ALIGNED | — |
| TSA-17 | API-5 text parts require `text` | `tests/test_multimodal_chat.py:344` | ALIGNED | — |
| TSA-18 | API-6 image parts require `image_url.url` | `tests/test_multimodal_chat.py:182` | ALIGNED | — |
| TSA-19 | API-7 audio parts require `data` and `format` | `tests/test_multimodal_chat.py:361` | ALIGNED | — |
| TSA-20 | MOD-1 structured messages preserved unchanged upstream | `tests/test_multimodal_chat.py:68`; `tests/test_openai_compatible_provider.py:182` | ALIGNED | — |
| TSA-21 | MOD-2 string-content callers remain supported | `tests/test_multimodal_chat.py:94` | ALIGNED | — |
| TSA-22 | MOD-3 valid structured audio pass-through | `tests/test_multimodal_chat.py:107`; `tests/test_openai_compatible_provider.py:213` | ALIGNED | — |
| TSA-23 | MOD-4 unsupported image input fails fast before warmup/provider call | `tests/test_multimodal_chat.py:128` | ALIGNED | — |
| TSA-24 | MOD-5 unsupported audio input fails fast before warmup/provider call | `tests/test_multimodal_chat.py:155` | ALIGNED | — |
| TSA-25 | MOD-6 multimodal limited to OpenAI-compatible path; direct llama_cpp remains text-only | `tests/test_multimodal_chat.py:452,478`; `tests/test_openai_compatible_provider.py:413` | ALIGNED | — |
| TSA-26 | MM-1 image capability requires resolved projector path | `tests/test_openai_compatible_provider.py:259`; `tests/test_multimodal_chat.py:394` | ALIGNED | — |
| TSA-27 | MM-2 `mmproj_path_env` preferred, fallback to `mmproj_path` | `tests/test_openai_compatible_provider.py:274` | ALIGNED | — |
| TSA-28 | MM-3 `--mmproj` only when path resolves | `tests/test_openai_compatible_provider.py:296` | ALIGNED | — |
| TSA-29 | ERR-1 upstream non-200 -> `ProviderUnavailableError` | `tests/test_openai_compatible_provider.py:334` | ALIGNED | — |
| TSA-30 | ERR-2 unreachable upstream resets readiness and raises unavailable | `tests/test_openai_compatible_provider.py:349` | ALIGNED | — |
| TSA-31 | OS-1 no routing/sampling/Docker timeout scope creep | — | ABSENT | No test asserts routing policy, backend-sampling semantics, or Docker timeout behavior stayed untouched |
| TSA-32 | OS-2 monitoring/observability remains out of scope | — | ABSENT | No test guards against observability code being added |
| TSA-33 | OS-3 no projector auto-download or vendored/storage behavior | `tests/test_openai_compatible_provider.py:368` | SHALLOW | The test uses token scanning over a limited file subset plus mocked network calls. It does not fully validate repository-wide absence of download/storage behavior, so the exclusion could be violated outside the scanned paths while the test still passes. |

---

## Code Quality Issues

CQ-1  
Category: logic error  
Severity: high  
Location: `local_server_runtime.py:121-140`, `local_server_runtime.py:184-189`, `local_server_runtime.py:195`, `local_server_runtime.py:217`  
Reasoning: `_forward_child_logs()` iterates over `stdout` and `stderr` until EOF. `ensure_managed_server()` calls it immediately after readiness succeeds and also on failure before terminating the child. A managed `llama-server` is a long-lived process whose pipes normally remain open, so these iterations can block indefinitely. The launch path can therefore hang after the server becomes ready, and the failure path can hang before cleanup. Because the subprocess is also created with `stdout/stderr=PIPE`, the child can additionally stall later if it keeps writing logs and nothing drains the pipes asynchronously.

CQ-2  
Category: logic error  
Severity: high  
Location: `service_app.py:109-111`, `service_app.py:113-148`  
Reasoning: `LLMServiceRuntime` still stores `_last_probe_ok`, `_last_probe_at`, and `_probe_ttl_seconds`, and it still updates those values at the end of `readiness()`, but the fast-path cache check is gone. Every `/ready` request now warms up every provider and performs an actual completion probe. Under normal health-check traffic this makes readiness far more expensive and can cause avoidable probe failures or latency spikes, especially for managed local providers.

---

## Summary Verdict

**SPEC GAPS + QUALITY ISSUES + TEST DRIFT**

**Spec gaps**
- `OS-2`: out-of-scope monitoring/observability code was added in `service_app.py`, `local_server_runtime.py`, `openai_compatible_provider.py`, and `llama_cpp_provider.py`

**Quality issues**
- `CQ-1` (high): managed server startup can block indefinitely while draining live child pipes
- `CQ-2` (high): `/ready` now re-probes every provider on every request because the TTL cache is no longer used

**Test drift**
- `TSA-33`: the no-auto-download/no-vendoring guard is shallow and only partially validates the exclusion

UNVERIFIABLE items requiring manual check:
- None

*"This report is read-only. No code changes have been made."*

## Traceability

Append only non-traceability commit hashes here. Traceability-only commits do not record themselves.

### Spec Commits

- 2026-05-17 | 0affeba38d2f6c8f7cfe1652875649d54e8d8e40 | consolidate bundled provider config and defaulting rules into canonical spec
- 2026-05-17 | bc6b4c9b70a7bd418991d808765f54210e60fc93 | add multimodal pass-through and managed projector configuration to canonical spec
- 2026-05-18 | 6f2f3e924021d83048462b5e4353ac924a7207d0 | record accepted test audit and failed spec audit reports for multimodal provider work

### Implementation Commits

- 2026-05-17 | 4fbdb89841c35c5b522c187508dd04c3208bc476 | add e4b q4 provider and remove implicit temperature and max_tokens defaults
