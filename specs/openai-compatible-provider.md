# OpenAI-Compatible Provider

## Status

VERIFIED

## Purpose

Define how this repository's OpenAI-compatible provider and bundled provider registry are configured, how outbound chat-completions requests are constructed, how optional provider configuration is merged with caller-supplied parameters, and how the generic inference service avoids inheriting application-specific defaults.

## Scope

This spec covers:

- `openai_compatible_provider.py`
- provider entries in `service_models.yaml` that target OpenAI-compatible backends
- the bundled example provider set shipped by this repository
- request parameter handling for `temperature`, `max_tokens`, and `timeout_seconds`
- reasoning-related `extra_args` treatment in bundled example providers

This spec does not cover:

- direct `llama_cpp_provider.py` subprocess invocation behavior
- routing policy between providers
- model-specific sampling semantics implemented by upstream inference servers
- monitoring or observability features
- Docker runtime timeout tuning

## Module Ownership

Owning modules and files:

- `openai_compatible_provider.py` — outbound OpenAI-compatible request construction and timeout handling
- `service_models.yaml` — bundled provider registry examples, managed runtime wiring, and optional provider defaults
- `service_app.py` — passes optional request parameters through to providers
- `tests/test_generic_inference_server.py` — regression tests for durable bundled-provider expectations in this repository

`openai_compatible_provider.py` owns payload construction. `service_models.yaml` owns the bundled provider topology and example provider configuration. Provider-level overrides may be defined there, but the bundled configuration must not force old application defaults into the generic service.

## Current Behavior

The repository ships bundled example OpenAI-compatible local providers in `service_models.yaml`.

The bundled provider set includes:

- `gemma_e2b_local`
- `gemma_e4b_local`
- `gemma_e4b_q4_local`

`gemma_e4b_q4_local` is configured as a managed local provider backed by:

- model path `/models/google_gemma-4-E4B-it-Q4_K_M.gguf`
- local managed server port `18014`

The example bundled providers keep reasoning-related llama-server flags present as commented-out lines inside `managed_server.extra_args` rather than active runtime arguments. Because these lines are commented out, the bundled example providers do not actively force reasoning behavior on or off through `extra_args`.

OpenAI-compatible providers send outbound `POST /v1/chat/completions` requests containing `model` and `messages` for every request.

`temperature` is included in the outbound payload only when explicitly provided through provider configuration or the incoming request.

`max_tokens` is included in the outbound payload only when explicitly provided through provider configuration or the incoming request.

`timeout_seconds` is not forwarded as an upstream model parameter. It is used only as the local HTTP client timeout for the outbound request.

The example providers in `service_models.yaml` do not define application-specific `default_params` for `temperature` or `max_tokens`. A provider may define `timeout_seconds` only when an operational override is required for that provider.

Caller-supplied parameters override provider-configured parameters when both are present.

When no `temperature` or `max_tokens` is supplied, the upstream OpenAI-compatible backend receives no implicit defaults from this repository and may apply its own backend defaults.

## Interfaces

### Provider configuration

OpenAI-compatible provider entries may define:

- `id`
- `provider_type: openai_compatible`
- `model_name`
- `connection.base_url`
- `connection.api_key` (optional)
- `connection.managed_server` (optional)
- `default_params.timeout_seconds` (optional)
- `default_params.temperature` (optional)
- `default_params.max_tokens` (optional)

If `default_params.temperature` or `default_params.max_tokens` are omitted, they must not appear in the outbound payload unless the caller supplies them.

### Bundled example provider set

The repository's bundled example provider ids are:

- `gemma_e2b_local`
- `gemma_e4b_local`
- `gemma_e4b_q4_local`

`gemma_e4b_q4_local` uses:

- `base_url: http://127.0.0.1:18014`
- `port: 18014`
- `model_path: /models/google_gemma-4-E4B-it-Q4_K_M.gguf`

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

### Commented reasoning example lines

The bundled example providers keep the following reasoning-related lines commented out inside `managed_server.extra_args`:

- `--reasoning`
- `off`
- `--reasoning-budget`
- `0`
- `--reasoning-format`
- `none`

### Inbound request parameters

`service_app.py` may pass through these optional request parameters to the provider:

- `temperature`
- `max_tokens`
- `timeout_seconds`

### Outbound payload

Minimum payload:

- `model`
- `messages`

Optional payload fields:

- `temperature` only when explicitly configured or requested
- `max_tokens` only when explicitly configured or requested

`timeout_seconds` is never included in the outbound JSON payload.

## Data Model

Merged runtime parameters are computed as:

- provider `default_params`
- overridden by caller-supplied request params

Relevant parameter semantics:

- `temperature`: optional numeric sampling control
- `max_tokens`: optional numeric output cap
- `timeout_seconds`: optional numeric local HTTP timeout

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
- omitted optional parameters remain omitted in the outbound payload
- caller-supplied values override provider defaults
- timeout configuration affects only the HTTP client call, not upstream model semantics
- commented reasoning lines are not active runtime flags

## Rules and Invariants

1. The bundled example provider registry must include `gemma_e4b_q4_local`.
2. `gemma_e4b_q4_local` must point to `/models/google_gemma-4-E4B-it-Q4_K_M.gguf`.
3. The reasoning-related llama-server lines remain commented out in the bundled example providers.
4. Commented reasoning-related lines are documentation/config examples only and must not be interpreted as active runtime arguments.
5. The provider must not inject implicit `temperature` defaults into outbound requests.
6. The provider must not inject implicit `max_tokens` defaults into outbound requests.
7. `timeout_seconds` must be used only as a local request timeout.
8. Provider example configuration in `service_models.yaml` must not encode old application-specific defaults for generic use.
9. Caller-supplied parameters must override provider-configured defaults.
10. The absence of `temperature` or `max_tokens` in the inbound request must not be converted into repository-defined fallback values in the outbound payload.

## Edge Cases

- If provider configuration sets `temperature` and the caller omits it, the configured value is sent.
- If provider configuration sets `max_tokens` and the caller omits it, the configured value is sent.
- If both provider configuration and caller request set the same parameter, the caller value wins.
- If no `timeout_seconds` is configured or requested, the provider uses its built-in local HTTP timeout fallback.
- If the upstream backend rejects the request, the provider surfaces a provider-unavailable error.
- If the upstream backend is unreachable, the provider resets managed-runtime readiness and surfaces a provider-unavailable error.
- If a future change activates reasoning-related runtime flags, this spec must be updated before implementation.
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
9. `openai_compatible_provider.py` still applies a local HTTP timeout fallback when `timeout_seconds` is not configured or requested.
10. Caller-supplied `temperature` and `max_tokens` still override provider configuration when supplied.

## Test Plan

- Load `service_models.yaml` and assert that `gemma_e4b_q4_local` is present.
- Assert that `gemma_e4b_q4_local` points to `/models/google_gemma-4-E4B-it-Q4_K_M.gguf`.
- Read `service_models.yaml` text and assert that the reasoning-related lines remain commented out.
- Verify example providers in `service_models.yaml` do not define `temperature` or `max_tokens` under `default_params`.
- Verify outbound payload omits `temperature` and `max_tokens` when neither config nor request supplies them.
- Verify outbound payload includes `temperature` and `max_tokens` when provided by provider config.
- Verify caller-supplied `temperature` and `max_tokens` override configured values.
- Verify the HTTP client still uses a timeout fallback when no timeout is specified.
- Run the repository test suite covering generic inference server repository expectations.

## Out of Scope

- Changing managed llama-server runtime flags unrelated to request defaults
- Changing request routing or model selection behavior
- Standardizing backend-specific default sampling behavior across all upstream servers
- Monitoring or observability implementation
- Docker runtime timeout tuning

## Traceability

Append only non-traceability commit hashes here. Traceability-only commits do not record themselves.

### Spec Commits

- 2026-05-17 | 0affeba38d2f6c8f7cfe1652875649d54e8d8e40 | consolidate bundled provider config and defaulting rules into canonical spec

### Implementation Commits

- YYYY-MM-DD | <commit-hash> | <summary>
