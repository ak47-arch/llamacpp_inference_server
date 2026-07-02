# Changelog

This file is both:

1. a concise human-readable change summary, and
2. an append-only traceability ledger for agents.

## Rules

- Record every non-traceability commit that changes a canonical spec.
- Record every implementation commit tied to a canonical spec.
- Record those hashes in the immediately following traceability commit.
- Do not self-record traceability-only commits.

## v0.3.0 - 2026-07-02

### Summary

- Switched active provider from `gemma_e4b_q4_local` (E4B Q4, 5.1 GB, port 18014) to `gemma_e2b_q4_local` (E2B Q4, 3.3 GB, port 18012) for faster model loading and lower memory usage.
- Removed dead code: `router.route()` with fallback routing, `router.ensure_runtime_ready()`, `monitoring.clear_request_context()`, `local_server_runtime.reset_managed_servers()`, the `pipeline_routing` config section.
- Removed `inspect.signature` hack in `service_app.py` — now always passes `messages` to providers uniformly.
- Centralized Flask request lifecycle: replaced per-route try/except/log/metrics boilerplate with `@app.before_request`, `@app.after_request`, `@app.teardown_request` and `@app.errorhandler` for each exception type.
- Simplified readiness probe: dropped the redundant `provider.complete()` inference call; readiness now only calls `provider.warmup()`.
- Merged `capture_sinks.py` into `prompt_capture.py` and deleted the standalone file.
- Added `monitoring.start_request_context()` and `monitoring.end_request_context()` public API for Flask lifecycle hooks.
- All 92 relevant tests pass (1 pre-existing failure unrelated to these changes).

## v0.4.0 - 2026-07-02

### Summary

- Added `docs/technical/ARCHITECTURE_REVIEW_2026-07.md` — deep-module analysis based on graphify AST graph.
- Added explicit `reasoning=off` argument in active provider to disable LLM reasoning preamble for structured outputs.

## v0.5.0 - 2026-07-02

### Summary

- Added `llm_client/` package — a pip-installable shared LLM workflow client (`llm-client`).
  - `WorkflowClient` class with `complete()` and `complete_text()` driven by per-project `config/workflows.yaml`.
  - Pydantic-based config models with env-var substitution, JSON output parsing, fallback resolution.
  - Typed exceptions: `LLMClientError`, `LLMTimeoutError`, `LLMUnavailableError`, `LLMBadResponseError`.
  - 34 tests (31 unit + 3 integration) all passing.
- Added `pyproject.toml` for pip-installable packaging.

## v0.5.1 - 2026-07-02

### Summary

- Fixed `_fallback_or_error` to pass `user_prompt` text (not the messages array) to fallback functions.
  - This fixes YAML-configured fallback functions (e.g., `heuristic_classify`) that expect a plain string argument.

## v0.2.0 - 2026-06-29

### Summary

- Simplified the bundled local provider config so only `gemma_e4b_q4_local` is active, while E2B and non-Q4 E4B remain as commented reference blocks.
- Dropped the active provider's explicit `ctx_size` override so managed `llama-server` uses the model default context size.
- Enabled bundled Gemma E4B Q4 audio input support, documented the requirement for a newer `llama.cpp` build, and taught the provider to surface `reasoning_content` when audio-capable backends leave `message.content` empty.
- Updated container/runtime documentation so liveness healthchecks use `/health` instead of `/ready`, avoiding readiness-triggered warmup loops during development.
- Added a canonical external API contract spec for the service HTTP surface, including model discovery and published OpenAPI schema endpoints.
- Published `GET /openapi.json` and `GET /v1/models` so external applications can discover the HTTP contract and available logical model ids.
- Added an approved canonical spec for prompt and multimodal-asset capture, explicitly separating capture from downstream dataset/training workflows.
- Clarified the monitoring spec so additional feature-owned metrics may share `monitoring.py` as long as they preserve bounded low-privacy labels.
- Added opt-in async prompt capture with an NDJSON sink, metadata/full modes, low-cardinality capture metrics, and default omission of inline media bytes unless explicitly enabled.
- Raised the container Gunicorn timeout default to 600 seconds and documented `GUNICORN_TIMEOUT` so long local inferences are less likely to fail with request timeouts.

### Traceability Ledger

- 2026-05-19 | spec: specs/openai-compatible-provider.md | kind: implementation | commit: 4865b2a81eb5d26c71574ca33af69c25b91f3545 | summary: simplify bundled config to the active e4b q4 provider and use model-default context sizing
- 2026-05-20 | spec: specs/openai-compatible-provider.md | kind: implementation | commit: 6167becd1cd4673035d368e9cf351c81778c4a00 | summary: enable bundled gemma audio path, add reasoning_content fallback, and update runtime/docs
- 2026-05-21 | spec: specs/openai-compatible-api.md | kind: spec | commit: 6f75815189931e290c0df5b9a0403dd594e4858c | summary: add canonical external API contract
- 2026-05-21 | spec: specs/openai-compatible-api.md | kind: implementation | commit: 83fad9bd6efb0a1c29826480a24376ee31e01c97 | summary: publish OpenAPI contract and model discovery
- 2026-05-21 | spec: specs/prompt-capture.md | kind: spec | commit: 721172b62703d786c17ab624f98e8f89deb2c952 | summary: add canonical capture spec
- 2026-05-23 | spec: specs/monitoring.md | kind: spec | commit: 392b6802de46371885bc9256d805eb17c6ec9240 | summary: allow bounded feature-owned metrics in shared monitoring module
- 2026-05-23 | spec: specs/prompt-capture.md | kind: implementation | commit: 241931c51d84ed2c508c233c3830b4ec7ad14c21 | summary: capture prompts and multimodal assets
- 2026-05-23 | spec: specs/monitoring.md | kind: implementation | commit: 241931c51d84ed2c508c233c3830b4ec7ad14c21 | summary: add bounded prompt-capture record metrics to the shared monitoring module

## v0.1.0 - 2026-05-19

### Summary

- Workflow documentation migrated to living canonical specs with append-only commit-hash traceability.
- Added the canonical spec, template, workflow guide, README pointers, and Pi workflow updates for feature development.
- Feature work now hard-requires the `feature-development` skill, with multi-requirement decomposition and dependency planning rules.
- Added a canonical spec for bundled OpenAI-compatible provider config and request-defaulting behavior.
- Bundled provider config now includes E4B Q4, keeps reasoning flags commented out, and no longer injects implicit temperature/max_tokens defaults.
- Added structured multimodal chat pass-through for OpenAI-compatible providers, including image/audio content-part validation and fail-fast modality checks.
- Added explicit managed `llama-server` `mmproj` wiring for bundled Gemma Q4 image-capable providers.
- Validated image inference end-to-end for `gemma_e2b_local` and `gemma_e4b_q4_local` with configured projector files.
- Added a canonical monitoring and observability spec for Prometheus metrics, readiness telemetry, and managed runtime startup instrumentation.
- Implemented Prometheus `/metrics`, request/readiness metrics, and managed llama-server startup/restart telemetry.
- Added safe operational logging for service access/failure summaries and managed runtime lifecycle events.
- Fixed managed runtime child-log forwarding so startup no longer blocks waiting for child log EOF.
- Added a canonical spec for isolated subagent verification commands and artifact-limited verifier handoffs.
- Implemented local isolated verifier commands for `module-boundary`, `spec-verifier`, and `test-verifier`.
- Recorded latest spec-verifier audit reports for the multimodal OpenAI-compatible provider and operational logging specs.

### Traceability Ledger

- 2026-05-17 | spec: specs/feature-development-workflow.md | kind: spec | commit: bc417fa8b7e2ba2c919635f1f2c812eda4b2fefe | summary: add canonical feature development workflow spec
- 2026-05-17 | spec: specs/feature-development-workflow.md | kind: implementation | commit: ec4d80472f3d2093cb4d983edf1d4fa4f3e22451 | summary: align repository docs and skills with canonical specs
- 2026-05-17 | spec: specs/feature-development-workflow.md | kind: spec | commit: e296e5ac8d69b3d44a398388ed95492fc5ec8c2b | summary: require feature-development skill and multi-feature dependency planning
- 2026-05-17 | spec: specs/feature-development-workflow.md | kind: implementation | commit: 00d06ba5f804a325197e9d1d1aaa54434786171f | summary: require workflow skill and multi-feature planning in docs and prompts
- 2026-05-17 | spec: specs/openai-compatible-provider.md | kind: spec | commit: 0affeba38d2f6c8f7cfe1652875649d54e8d8e40 | summary: consolidate bundled provider config and defaulting rules into canonical spec
- 2026-05-17 | spec: specs/openai-compatible-provider.md | kind: implementation | commit: 4fbdb89841c35c5b522c187508dd04c3208bc476 | summary: add e4b q4 provider and remove implicit temperature and max_tokens defaults
- 2026-05-17 | spec: specs/monitoring.md | kind: spec | commit: 297a8299eb0eca77c33cd9118227f818e2b57cf2 | summary: add canonical monitoring and observability spec
- 2026-05-17 | spec: specs/monitoring.md | kind: implementation | commit: 99b4ff5d9b49d5220a7860ef52b693be064326b4 | summary: add Prometheus metrics endpoint and runtime telemetry
- 2026-05-17 | spec: specs/subagents.md | kind: spec | commit: ec7e0e02196dddeb848d84e8a88baaf474fe5868 | summary: add canonical isolated subagent verification commands spec
- 2026-05-17 | spec: specs/openai-compatible-provider.md | kind: spec | commit: bc6b4c9b70a7bd418991d808765f54210e60fc93 | summary: add multimodal pass-through and managed projector configuration to canonical spec
- 2026-05-17 | spec: specs/operational-logging.md | kind: spec | commit: 46e4e3fbf081af3ff6e11954031464a04ad8c8e3 | summary: add canonical operational logging spec
- 2026-05-18 | spec: specs/openai-compatible-provider.md | kind: spec | commit: 6f2f3e924021d83048462b5e4353ac924a7207d0 | summary: record multimodal provider verifier audit reports and status note
- 2026-05-18 | spec: specs/operational-logging.md | kind: spec | commit: 6f2f3e924021d83048462b5e4353ac924a7207d0 | summary: record operational logging verifier audit reports and status note
- 2026-05-18 | spec: specs/openai-compatible-provider.md | kind: implementation | commit: b831568f0716154a36070ea8495c1fe95394489c | summary: add multimodal message pass-through and managed mmproj support
- 2026-05-18 | spec: specs/operational-logging.md | kind: implementation | commit: b831568f0716154a36070ea8495c1fe95394489c | summary: add operational service/runtime logging and sanitized child log forwarding
- 2026-05-18 | spec: specs/monitoring.md | kind: implementation | commit: b831568f0716154a36070ea8495c1fe95394489c | summary: update monitoring integration and regression coverage alongside service changes
- 2026-05-18 | spec: specs/subagents.md | kind: implementation | commit: b831568f0716154a36070ea8495c1fe95394489c | summary: add isolated spec and test verifier commands to the local extension
