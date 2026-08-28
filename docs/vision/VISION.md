# LLM Inference Server & Client — Vision

## Why This Exists

Every project in the workspace needs LLM inference — classification, extraction, synthesis, summarization, and structured reasoning. Without a shared inference layer, each project would either bundle its own model runner (duplicating infrastructure and model downloads) or hardcode provider-specific API calls (coupling to a single backend).

The `llm/` repository ships **two complementary artifacts** in one repo:

- **`llm_client`** — a pip-installable library that apps import directly. It reads a per-project `config/workflows.yaml` and makes LLM calls wherever the config points.
- **`service_app`** — an OpenAI-compatible inference server (`POST /v1/chat/completions` on `:8012`) for local model backends, with managed lifecycle, Prometheus metrics, and optional prompt capture.

They are independent — apps can use the client without the server, and the server can be called by any OpenAI-compatible tool.

## Core Intent

A config-driven LLM access layer where:

1. Each application owns its workflow definitions (temperature, model, prompt, output format) in `config/workflows.yaml` — centralising these parameters is a losing battle because different workloads need different settings.
2. Routing is just a URL — the workflow config declares where the request goes (`url: https://openrouter.ai/api` for cloud, `url: http://localhost:8012` for a local inference server). The client does not need a central router.
3. The server provides a pluggable local backend interface so different inference engines (llama.cpp, vLLM, TGI, Ollama) can be swapped in without changing application code.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Application (survival-infrastructure, feed_analyser, etc.)  │
│  └─ pip install llm-client                                  │
│       └─ WorkflowClient                                      │
│            └─ reads config/workflows.yaml                    │
│                 ├─ model_ref: fast     → url: cloud API      │
│                 ├─ model_ref: quality  → url: cloud API      │
│                 └─ model_ref: local    → url: localhost:8012 │
└──────────────────┬───────────────────────────────────────────┘
                   │
          ┌────────┴──────────────┐
          ▼                       ▼
┌──────────────────┐   ┌────────────────────────┐
│  Cloud API       │   │  service_app (:8012)   │
│  (OpenRouter,    │   │  └─ BackendRegistry    │
│   OpenAI, etc.)  │   │       ├─ llama_cpp     │
│                  │   │       ├─ openai_http   │
│  Direct HTTP     │   │       └─ (pluggable)   │
│  from client     │   │  └─ managed lifecycle  │
└──────────────────┘   └────────────────────────┘
```

**Key point**: the client **does not** have to route through the server. When a workflow targets a cloud provider, the client calls it directly via HTTP. The server is the abstraction for *local* backends and for cases where you want observability (metrics, capture) at the request level.

## Per-Workflow Configuration (Deliberate)

Different workloads need fundamentally different inference parameters:

- **Extraction**: low temperature (0.0), few tokens (160), JSON output
- **Judge/quality check**: low temperature (0.0), very few tokens (96), JSON
- **Wiki synthesis**: moderate temperature (0.3), many tokens (2048), Markdown text
- **Classification**: medium temperature (0.1–0.3), few tokens, JSON

Centralising these in a single shared config is counterproductive — every project has its own workloads. The solution is:

- Each project owns its own `config/workflows.yaml`
- The `llm_client` reads it at runtime and resolves the workflow inline
- Model entries are in the same file, scoped to the project's needs

This is not an accidental gap — it's the design.

## Routing-by-URL Convention

A model entry in `workflows.yaml` declares its target via `url`:

```yaml
models:
  fast:
    url: "https://openrouter.ai/api"        # cloud
    model: "openai/gpt-4o-mini"
    api_key: "${OPENROUTER_API_KEY}"

  local:
    url: "http://localhost:8012"             # local server
    model: "gemma2:latest"
```

The `WorkflowClient` formats the endpoint as `url/v1/chat/completions` and sends a standard OpenAI-compatible request. No routing logic, no central dispatcher — the URL is the route.

## Server Pluggability (Future Feature — Not In Scope Now)

The `service_app` currently supports two providers:
- `llama_cpp_provider` — direct subprocess to llama.cpp CLI
- `openai_compatible_provider` — HTTP calls to any OpenAI-compatible backend

A pluggable `BackendProvider` interface is **not yet extracted** — this is deferred because local models are not in active use. When local inference resumes, the plan is:

1. Define a `BackendProvider` abstract class with `complete()`, `health()`, `supports_modality()` methods
2. Each backend (llama.cpp, vLLM, TGI, Ollama) implements it
3. `service_models.yaml` registers providers by name
4. `router.py` selects at request time

## Scope Boundaries

### This project is:
- An **inference server** with pluggable local backends (llama.cpp today, more later)
- A **client library** for config-driven workflow execution
- A managed model lifecycle for local inference
- Prompt capture for observability
- Prometheus metrics for monitoring

### This project is not:
- A model training or fine-tuning platform
- A vector database or embedding service
- A prompt management system (prompts live in downstream projects)
- A multi-modal processing pipeline (though image input is supported)

## Guiding Principles

1. **One repo, two artifacts** — the server and client ship from the same source but are independently usable.
2. **Per-project config** — workflow parameters belong to the application, not the infrastructure layer.
3. **Routing by URL** — no central router; the workflow config declares the target in plain YAML.
4. **Provider abstraction** — applications never import provider-specific code. The server routes (when used), the client abstracts.
5. **Observability by default** — every request is measurable (latency, tokens, model) and optionally capturable.
6. **OpenAI-compatible API** — the server exposes a standard API that any OpenAI-compatible tool can call.

## Active Tasks

- (none — project is stable, currently routing all workflows to cloud via OpenRouter)

## Future Direction

1. Pluggable `BackendProvider` interface for local inference engines (llama.cpp, vLLM, TGI, Ollama) — deferred until local models are active
2. Multi-modal support (image input is partially implemented, audio planned)
3. Provider-level rate limiting and quota management
4. Streaming responses through the server
5. Structured output schemas (JSON Schema-driven response validation)
6. Provider health monitoring and auto-recovery

## A Living Vision

This document defines intent and direction, not frozen implementation details. It should evolve as inference needs change and new provider capabilities emerge.