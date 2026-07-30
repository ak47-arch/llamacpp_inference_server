# LLM Inference Server & Client Vision

## Why This Exists

Every project in the workspace needs LLM inference — classification, extraction, synthesis, summarization, and structured reasoning. Without a shared inference layer, each project would either bundle its own model runner (duplicating infrastructure and model downloads) or hardcode provider-specific API calls (coupling to a single backend).

A centralized inference server decouples model management from application logic. Downstream projects interact through a uniform API and client package, while the server handles provider routing, model lifecycle, and operational concerns.

## Core Intent

A pluggable, OpenAI-compatible inference server that serves as the single LLM access point for all workspace projects, paired with a pip-installable client that provides config-driven workflow execution, model fallback, and structured output parsing.

The server is the **provider abstraction layer** — applications never call models directly. They call workflows, and the server resolves which model, with what parameters, and with what fallback strategy.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│  Downstream Projects                                      │
│  survival-infrastructure, feed_analyser, (future)         │
│  Each owns config/workflows.yaml                          │
└──────────────────────┬───────────────────────────────────┘
                       │ pip install llm-client
                       ▼
┌──────────────────────────────────────────────────────────┐
│  llm_client (WorkflowClient)                              │
│  Config-driven: model selection, temperature, fallback    │
│  Methods: complete_text(), complete_json()                │
│  Structured output parsing (auto JSON)                    │
└──────────────────────┬───────────────────────────────────┘
                       │ HTTP :8012 (OpenAI-compatible)
                       ▼
┌──────────────────────────────────────────────────────────┐
│  Inference Server (Flask on :8012)                        │
│  ProviderRouter → Provider implementations                │
│    ├── openai_compatible_provider (HTTP to any backend)   │
│    └── llama_cpp_provider (direct subprocess)             │
│  Managed server lifecycle (local_runtime)                 │
│  Optional prompt capture + Prometheus metrics             │
└──────────────────────┬───────────────────────────────────┘
                       │ model-specific protocols
                       ▼
┌──────────────────────────────────────────────────────────┐
│  Model Backends                                           │
│  llama-server (local), OpenAI API, Anthropic API, etc.    │
│  Each registered as a provider in service_models.yaml     │
└──────────────────────────────────────────────────────────┘
```

## Scope Boundaries

### This project is:
- An OpenAI-compatible inference endpoint
- A pluggable provider system for different model backends
- A managed server lifecycle for local models
- A pip-installable client with config-driven workflows
- Prompt capture for observability
- Prometheus metrics for monitoring

### This project is not:
- A model training or fine-tuning platform
- A vector database or embedding service
- A prompt management system (prompts live in downstream projects)
- A multi-modal processing pipeline (though image input is supported)

## Guiding Principles

1. **Provider abstraction** — Applications never import provider-specific code. The server routes, the client abstracts.
2. **Config-driven behavior** — Model selection, workflow parameters, and fallback chains are declared in YAML, not hardcoded.
3. **Graceful degradation** — When a provider is unavailable, the system falls back through configured chains rather than failing hard.
4. **Observability by default** — Every request is measurable (latency, tokens, model) and optionally capturable for debugging.
5. **OpenAI-compatible API** — The server exposes a standard API that any OpenAI-compatible tool can call, not just the workspace client.

## Active Tasks

- (none yet — project is stable and running)

## Future Direction

1. Multi-modal support (image input is partially implemented, audio planned)
2. Provider-level rate limiting and quota management
3. Streaming responses through the server
4. Structured output schemas (JSON Schema-driven response validation)
5. Provider health monitoring and auto-recovery

## A Living Vision

This document defines intent and direction, not frozen implementation details. It should evolve as inference needs change and new provider capabilities emerge.