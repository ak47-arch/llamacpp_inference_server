# Feature Matrix

## Implemented

| Feature | Status | Notes |
|---|---|---|
| Flask HTTP server | Implemented | `service_app.py` |
| `GET /health` | Implemented | Simple liveness endpoint |
| `GET /ready` | Implemented | Warms providers and checks readiness |
| `POST /v1/chat/completions` | Implemented | OpenAI-style chat completions endpoint |
| OpenAI-style request parsing | Implemented | Supports `model`, `messages`, `temperature`, `max_tokens`, `timeout_seconds` |
| OpenAI-style response shape | Implemented | Returns `id`, `object`, `created`, `choices`, `usage` |
| Config-driven provider registry | Implemented | `service_models.yaml` + `ProviderRouter` |
| Provider abstraction layer | Implemented | `BaseProvider`, `CompletionResult`, provider errors |
| OpenAI-compatible backend provider | Implemented | `openai_compatible_provider.py` |
| Direct `llama-cli` backend provider | Implemented | `llama_cpp_provider.py` |
| Managed local `llama-server` startup | Implemented | Auto-start on first use |
| Managed local runtime readiness checks | Implemented | `/health` and `/v1/models` probing |
| Managed local runtime reuse | Implemented | Reuses already-started process per `base_url` |
| Managed runtime shutdown/reset helper | Implemented | `reset_managed_servers()` |
| Role-based routing | Implemented | `ProviderRouter.route(role, ...)` supports it |
| Fallback providers per role | Implemented | Supported in router config |
| Role routing used by HTTP endpoint | Configurable but currently unused | HTTP endpoint selects provider by explicit `model`, not routing role |
| Relative model path resolution | Implemented | In `router.py` for `llama_cpp` providers |
| Env-var override for config path | Implemented | `LLM_SERVER_CONFIG_FILE` |
| Env-var override for bind host/port | Implemented | `LLM_SERVER_HOST`, `LLM_SERVER_PORT` |
| Dockerfile for standalone container | Implemented | Uses `gunicorn` |
| Docker Compose deployment | Implemented | Port 8012, mounted models + llama.cpp dir |
| Container healthcheck | Implemented | Calls `/ready` |
| Bundled example provider config | Implemented | Two Gemma-based local providers in `service_models.yaml` |
| Requests-based outbound HTTP inference | Implemented | For OpenAI-compatible providers |
| Timeout handling | Implemented | Maps to provider timeout errors / HTTP 504 |
| Unavailable-backend handling | Implemented | Maps to provider unavailable errors / HTTP 503 |
| Basic tests for generic-server cleanup | Implemented | `tests/test_generic_inference_server.py` |
| Pi `/module-boundary` isolated audit command | Implemented | Project-local extension in `.pi/extensions/subagents/` |
| Pi subagent helper tests | Implemented | `tests/subagents.test.mjs` |

## Configurable but not really surfaced as product features

| Feature | Status | Notes |
|---|---|---|
| Multi-role model topology | Available | You can define routing roles in `service_models.yaml`, but current HTTP API does not expose role selection |
| Alternate OpenAI-compatible backends | Available | Can target other servers/gateways by changing config |
| API-key backed remote providers | Available | Supported by `OpenAICompatibleProvider` |
| Extra llama.cpp runtime flags | Available | Via `managed_server.extra_args` |
| Batch size tuning | Available | Supported in managed runtime config |
| Thread/context tuning | Available | Supported in config and docs |

## Not currently provided

| Feature | Status | Notes |
|---|---|---|
| Embeddings endpoint | Not implemented | No `/v1/embeddings` |
| Responses API | Not implemented | No `/v1/responses` |
| Streaming chat completions | Not implemented | No SSE/chunked streaming |
| Auth on server endpoints | Not implemented | No API key or token check on incoming requests |
| Metrics endpoint | Not implemented | No Prometheus or usage metrics endpoint |
| Request logging/audit trail | Not implemented | No structured request log layer |
| Rate limiting | Not implemented | No concurrency or quota controls at HTTP layer |
| Multi-tenant isolation | Not implemented | No tenant-aware config or auth |
| Admin API for model lifecycle | Not implemented | Runtime mgmt is internal only |
| Dynamic config reload | Not implemented | Config is loaded at startup/runtime creation |
| Test suite for live provider behavior | Minimal | Only basic cleanup/config tests are present |
| Kubernetes manifests | Not implemented | Docker/Compose only |
| Event extraction / wiki generation / queue workflows | Removed | Intentionally deleted as legacy app logic |

## Practical summary

### What the project is now
A **generic Docker-deployable inference server** with:
- OpenAI-compatible chat completions
- config-driven providers
- managed local `llama-server` runtimes
- optional role-routing support in the internals

### What it is not yet
A full production platform with:
- auth
- streaming
- metrics
- embeddings
- admin controls
- advanced observability
