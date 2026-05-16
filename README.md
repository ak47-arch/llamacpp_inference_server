# Generic Inference Server

A lightweight Python inference server for local and OpenAI-compatible LLM backends.

It provides:
- config-driven provider registration
- role-aware routing with fallback support
- managed local `llama-server` lifecycle
- an OpenAI-compatible `POST /v1/chat/completions` endpoint
- Docker packaging for standalone deployment

## Repository layout

```text
.
├── __init__.py
├── provider_base.py
├── router.py
├── openai_compatible_provider.py
├── llama_cpp_provider.py
├── local_server_runtime.py
├── service_app.py
├── service_models.yaml
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── LLM_SERVICE_TUNING.md
└── gemma/
```

## Core modules

### `provider_base.py`
Shared provider interface and result/error types.

### `router.py`
Loads provider definitions from YAML and resolves providers for logical roles.

### `openai_compatible_provider.py`
Calls any OpenAI-compatible HTTP backend.

### `llama_cpp_provider.py`
Runs `llama-cli` directly through a subprocess.

### `local_server_runtime.py`
Starts and manages local `llama-server` processes on demand.

### `service_app.py`
Flask application exposing:
- `GET /health`
- `GET /ready`
- `POST /v1/chat/completions`

## Configuration

The server reads provider definitions from `service_models.yaml`.

Current defaults assume:
- model files mounted at `/models`
- `llama.cpp` binaries mounted at `/opt/llama-cpp`
- managed local runtimes listening on ports `18012` and `18013`

## Local run

From the parent directory of this repository:

```bash
python -m llm.service_app
```

Environment variables:

```bash
export LLM_SERVER_HOST=0.0.0.0
export LLM_SERVER_PORT=8012
export LLM_SERVER_CONFIG_FILE=/absolute/path/to/llm/service_models.yaml
python -m llm.service_app
```

## Docker

Build and run with Docker Compose:

```bash
docker compose up --build
```

Compose expects:
- `./gemma` mounted to `/models`
- `LLAMA_CPP_DIR` pointing to a directory that contains `llama-server`

The container serves traffic on port `8012`.

## API

### Health

```bash
curl http://127.0.0.1:8012/health
```

Example response:

```json
{"status":"ok","service":"inference-server"}
```

### Readiness

```bash
curl http://127.0.0.1:8012/ready
```

### Chat completions

```bash
curl -X POST http://127.0.0.1:8012/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gemma_e2b_local",
    "messages": [
      {"role": "system", "content": "You are concise."},
      {"role": "user", "content": "Say hello."}
    ],
    "temperature": 0.0,
    "max_tokens": 32
  }'
```

## Notes

- This repository intentionally contains only generic inference-server code.
- Legacy application-specific extraction, queue, benchmark, and wiki-generation code has been removed.
