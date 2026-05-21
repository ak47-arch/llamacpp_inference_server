# Generic Inference Server

A lightweight Python inference server for local and OpenAI-compatible LLM backends.

It provides:
- config-driven provider registration
- role-aware routing with fallback support
- managed local `llama-server` lifecycle
- an OpenAI-compatible `POST /v1/chat/completions` endpoint
- structured multimodal OpenAI-style message support for configured OpenAI-compatible providers
- Prometheus-compatible `GET /metrics`
- safe operational logging to stdout/stderr for service and managed runtime flows
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
├── tmp/
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
- `GET /openapi.json`
- `GET /v1/models`
- `GET /metrics`
- `POST /v1/chat/completions`

## Configuration

The server reads provider definitions from `service_models.yaml`.

Current defaults assume:
- model files mounted at `/models`
- `llama.cpp` binaries mounted at `/opt/llama-cpp`
- the managed local runtime listening on port `18014`

Bundled OpenAI-compatible local provider:
- `gemma_e4b_q4_local`

Commented-out E2B and non-Q4 E4B provider blocks remain in `service_models.yaml` as quick re-enable examples.

The bundled managed runtime uses the model's default context size by omitting an explicit `ctx_size` override.
The active bundled provider currently declares `text`, `image`, and `audio` input support.
For working Gemma 4 audio over the OpenAI-compatible HTTP path, use a recent `llama.cpp` build that reports audio modality support in `/props`; older builds such as the previously tested `b8763` exposed vision but not HTTP audio for Gemma 4.

For image input, the managed runtime also needs a matching multimodal projector (`mmproj`) file.
The checked-in `docker-compose.yml` expects:
- `/models/mmproj-google_gemma-4-E4B-it-f16.gguf`

via this environment variable:
- `GEMMA_E4B_Q4_LOCAL_MMPROJ_PATH`

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
docker-compose up --build
```

Compose expects:
- `./gemma` mounted to `/models`
- `LLAMA_CPP_DIR` pointing to a directory that contains `llama-server` and its shared libraries
- matching `mmproj` files present in `./gemma` for image/audio-capable Gemma 4 providers

The container serves traffic on port `8012`.
The container liveness healthcheck uses `GET /health`; `GET /ready` is still available for explicit warmup/readiness probing.
Service access logs, failure summaries, and managed runtime lifecycle logs are emitted to stdout/stderr.

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

### OpenAPI contract

```bash
curl http://127.0.0.1:8012/openapi.json
```

### Models

```bash
curl http://127.0.0.1:8012/v1/models
```

Example response:

```json
{
  "object": "list",
  "data": [
    {
      "id": "gemma_e4b_q4_local",
      "object": "model",
      "owned_by": "llm"
    }
  ]
}
```

### Metrics

```bash
curl http://127.0.0.1:8012/metrics
```

### Chat completions

```bash
curl -X POST http://127.0.0.1:8012/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gemma_e4b_q4_local",
    "messages": [
      {"role": "system", "content": "You are concise."},
      {"role": "user", "content": "Say hello."}
    ],
    "temperature": 0.0,
    "max_tokens": 32
  }'
```

Structured multimodal requests use standard OpenAI-style content arrays:

```bash
curl -X POST http://127.0.0.1:8012/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gemma_e4b_q4_local",
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "What is in this image? Reply briefly."},
          {
            "type": "image_url",
            "image_url": {
              "url": "data:image/png;base64,<BASE64_PNG>"
            }
          }
        ]
      }
    ]
  }'
```

Notes:
- image/audio structured content is supported only for configured OpenAI-compatible providers
- image requests fail fast with `400 invalid_request` when the selected provider has no active projector support
- some recent `llama.cpp` Gemma 4 audio responses can populate `reasoning_content` while leaving `content` empty; this repository now falls back to `reasoning_content` when needed so audio answers are surfaced instead of dropped
- very small images can fail inside `llama.cpp`; use images of at least a few pixels in each dimension for manual smoke tests

## Development workflow

Spec-driven work in this repository now uses living canonical specs rather than chronological per-change specs.
all feature work must use the `feature-development` skill / prompt.

See:

- `.pi/prompts/feature-development.md`
- `.agents/skills/feature-development/SKILL.md`
- `docs/FEATURE_DEVELOPMENT_WORKFLOW.md`
- `specs/feature-development-workflow.md`
- `specs/TEMPLATE.md`
- `CHANGELOG.md`

## Notes

- This repository intentionally contains only generic inference-server code.
- Legacy application-specific extraction, queue, benchmark, and wiki-generation code has been removed.
