---
type: Service
title: LLM Generic Inference Server
description: A lightweight, config-driven Python inference server providing an OpenAI-compatible HTTP API for local and remote LLM backends, with a shared pip-installable workflow client.
tags: [llm, inference, openai-compatible, monitoring, prompt-capture]
---

# LLM Generic Inference Server

## Overview

This repository contains two products:

1. **Generic Inference Server** — a Flask-based HTTP service that exposes an OpenAI-compatible `POST /v1/chat/completions` endpoint, plus health, readiness, model discovery, OpenAPI schema, and Prometheus metrics. It routes requests to configurable backends: local `llama.cpp` subprocess, managed `llama-server` processes, or any OpenAI-compatible remote provider.

2. **`llm_client`** — a pip-installable Python package (`llm-client`) that provides a uniform workflow-driven client for any OpenAI-compatible server. It uses per-project YAML config files to define model endpoints and named workflows, with built-in JSON output parsing, fallback resolution, and env-var substitution.

Key capabilities:
- Config-driven provider registration via `service_models.yaml`
- Role-aware routing with provider resolution
- Managed local `llama-server` lifecycle (start, wait, health-check, restart)
- Structured multimodal input (text, image, audio) for OpenAI-compatible providers
- Prometheus-compatible `GET /metrics`
- Safe operational logging to stdout/stderr
- Optional durable prompt/asset capture with NDJSON sink
- Container packaging for standalone deployment

## Repository Layout

```
.
├── service_app.py              # Flask app, routes, request validation
├── router.py                   # ProviderRouter — loads providers from YAML
├── provider_base.py            # Abstract base provider + result/error types
├── openai_compatible_provider.py  # HTTP provider for OpenAI-compatible backends
├── llama_cpp_provider.py       # Local subprocess provider (llama-cli)
├── local_server_runtime.py     # Managed llama-server lifecycle
├── monitoring.py               # Prometheus metrics
├── prompt_capture.py           # Async prompt/asset capture pipeline
├── service_models.yaml         # Provider definitions
├── llm_client/                 # Shared pip-installable workflow client
│   ├── __init__.py
│   ├── config.py               # Pydantic config models (WorkflowConfig)
│   ├── workflow_client.py      # WorkflowClient class
│   ├── schemas.py              # WorkflowResult dataclass
│   └── errors.py               # Typed exceptions
├── Dockerfile                  # Container image
├── docker-compose.yml          # Compose stack
├── scripts/compose_env_preflight.sh  # Preflight validation
├── specs/                      # Living canonical specifications
├── tests/                      # Test suite
└── docs/                       # Technical documentation
```

## Quick Start

### Local run

```bash
python -m llm.service_app
```

Configure via environment variables:

```bash
export LLM_SERVER_HOST=0.0.0.0
export LLM_SERVER_PORT=8012
export LLM_SERVER_CONFIG_FILE=/absolute/path/to/llm/service_models.yaml
python -m llm.service_app
```

### Container run

Podman (default runtime):

```bash
podman network create workspace-shared-llm-network
bash scripts/compose_env_preflight.sh
LLAMA_CPP_DIR=/home/user/llama-cpp/llama-b8763 podman compose up --build
```

Docker fallback:

```bash
docker network create workspace-shared-llm-network
bash scripts/compose_env_preflight.sh
LLAMA_CPP_DIR=/home/user/llama-cpp/llama-b8763 docker compose up --build
```

### Make a request

```bash
curl -X POST http://127.0.0.1:8012/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gemma_e2b_q4_local",
    "messages": [
      {"role": "system", "content": "You are concise."},
      {"role": "user", "content": "Say hello."}
    ],
    "temperature": 0.0,
    "max_tokens": 32
  }'
```

### Using llm_client

```python
from llm_client import WorkflowClient

client = WorkflowClient("config/workflows.yaml")
result = client.complete_text("classify_tweet", prompt="A tweet about AI...")
print(result.data)   # parsed JSON if output=json
print(result.text)   # raw response
```

## Documentation Sections

| Section | Description |
|---------|-------------|
| [Architecture](/openwiki/architecture/overview.md) | System design, request lifecycle, provider architecture, monitoring, prompt capture |
| [llm_client](/openwiki/llm_client/index.md) | Shared workflow-driven Python client library |
| [Operations](/openwiki/operations/index.md) | Deployment, configuration, runtime tuning, logging |
| [Specifications](/openwiki/specs/index.md) | Spec-driven development workflow, canonical specs |

## Backlog

- **Streaming**: The `/v1/chat/completions` endpoint currently does not support streaming responses. The `openai-compatible-api.md` spec explicitly excludes streaming from scope.
- **Provider interface seam**: The architecture review (July 2026) recommends extracting a formal `Provider` abstract interface shared by both `OpenAICompatibleProvider` and `LlamaCppProvider`, enabling middleware for cross-cutting concerns like prompt capture and monitoring.
- **Centralized retry/fallback**: Error handling logic (retry, fallback, circuit-breaker) is currently scattered across providers. The architecture review recommends centralizing it behind the Provider interface.
- **Prompt capture as middleware**: Prompt capture is currently called explicitly by providers. The architecture review recommends making it a middleware wrapper at the Provider seam.
- **Authentication/CORS**: No authentication or CORS policy is implemented.