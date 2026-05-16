# llama.cpp Inference Server

A lightweight Python LLM service and routing layer for local inference.

This repository contains a small inference stack built around:
- local `llama.cpp` runtimes
- OpenAI-compatible HTTP backends
- a provider router with role-based dispatch and fallback support
- a Flask service exposing `/v1/chat/completions`
- helper pipeline functions for event extraction and markdown synthesis
- benchmark/eval assets for structured extraction workloads

## Repository status

This codebase appears to be the `llm/` package extracted from a larger project.
Some files are complete and usable, while a few surrounding pieces still assume the original parent-repo layout.

### What is implemented

- provider abstraction layer
- OpenAI-compatible provider
- direct `llama.cpp` CLI provider
- managed local `llama-server` lifecycle
- provider router with fallback support
- Flask inference service
- extraction / synthesis pipeline helpers
- deterministic validation helpers
- file-based async job queue and worker loop
- benchmark and evaluation assets

### Important caveats

A few things still reflect the original parent project:

1. **Package layout assumption**
   - The code imports `llm.*` in some places.
   - This works best when this repository is checked out as a directory named `llm`, or when the package is placed inside a parent project as `llm/`.

2. **Standalone Docker mismatch**
   - `Dockerfile` still expects files like `requirements.txt`, `llm/`, and `config/` from the original layout.
   - As committed here, the Docker assets are useful as reference but may need adjustment before a standalone build works.

3. **Async queue dependency**
   - `job_queue.py` depends on an external `parse_service` module that is not included in this repository snapshot.
   - The queue/worker code is present, but not fully runnable end-to-end by itself.

4. **Eval default config path**
   - `eval.py` defaults to `models.yaml`, but this repository currently ships `service_models.yaml`.
   - Use `--config` explicitly when running evals.

## Repository layout

```text
.
├── benchmarks/
│   ├── complex_events.jsonl
│   └── rubric.json
├── gemma/
│   ├── *.gguf
│   └── GEMMA4_NOTES.md
├── __init__.py
├── provider_base.py
├── router.py
├── openai_compatible_provider.py
├── llama_cpp_provider.py
├── local_server_runtime.py
├── service_app.py
├── pipeline.py
├── validator.py
├── job_queue.py
├── worker.py
├── eval.py
├── service_models.yaml
├── docker-compose.yml
├── Dockerfile
└── LLM_SERVICE_TUNING.md
```

## Core components

### `provider_base.py`
Defines the provider interface and shared result/error types:
- `BaseProvider`
- `CompletionResult`
- `ProviderUnavailableError`
- `ProviderTimeoutError`

### `router.py`
Loads provider definitions from YAML and routes requests by logical role.

Supports:
- provider registry construction
- role-based routing
- primary/fallback provider resolution
- provider warmup

### `openai_compatible_provider.py`
Calls any OpenAI-compatible backend over HTTP.

Typical targets:
- local `llama-server`
- other local inference servers
- OpenAI-compatible gateways

### `llama_cpp_provider.py`
Runs `llama-cli` directly via subprocess.

Useful when you want:
- no HTTP server
- local CLI invocation
- direct control over threads, max tokens, timeout, etc.

### `local_server_runtime.py`
Starts and manages a local `llama-server` process on demand.

Supports:
- health checks
- start-on-first-use
- readiness waiting
- process reuse
- managed shutdown/reset

### `service_app.py`
Flask application exposing a shared inference service.

Endpoints:
- `GET /health`
- `GET /ready`
- `POST /v1/chat/completions`

### `pipeline.py`
Prompt-driven helper functions for:
- structured event extraction
- person wiki synthesis
- topic wiki synthesis
- extraction judging / actor correction

### `validator.py`
Deterministic validation for extraction outputs.

### `job_queue.py` and `worker.py`
Durable file-based async processing layer with:
- queued/processing/success/failure states
- retries with backoff
- dead-letter handling
- startup recovery
- background worker loop

## Configuration

### `service_models.yaml`
This repository ships a service config with two local Gemma-backed providers:
- `gemma_e2b_local`
- `gemma_e4b_local`

Both are configured as `openai_compatible` providers backed by managed local `llama-server` processes.

Current config highlights:
- model files are expected under `/models`
- `llama-server` is expected under `/opt/llama-cpp`
- HTTP ports used by managed runtimes:
  - `18012`
  - `18013`

At the moment, `pipeline_routing` is empty in `service_models.yaml`, so role-based pipeline calls are not yet wired there.

## Running the service

## Option 1: use the Flask app directly

Because this code expects package-style imports, the safest way is to place the repository in a directory named `llm` and run it from that directory's parent.

Example:

```bash
git clone https://github.com/ak47-arch/llamacpp_inference_server.git llm
cd ..
python -m llm.service_app
```

Environment variables:

```bash
export SURVIVAL_LLM_HOST=0.0.0.0
export SURVIVAL_LLM_PORT=8012
export SURVIVAL_LLM_CONFIG_FILE=/absolute/path/to/llm/service_models.yaml
python -m llm.service_app
```

Default values in `service_app.py`:
- host: `0.0.0.0`
- port: `8012`

## Option 2: use Docker Compose

A compose file is included:

```bash
docker compose up -d
```

It exposes:
- service: `llm`
- host port: `8012`

Mounted volumes:
- `./gemma:/models:ro`
- `${SURVIVAL_LLAMA_CPP_DIR}:/opt/llama-cpp:ro`

### Docker caveat

The current `Dockerfile` still assumes the original parent-repo layout (`llm/`, `config/`, `requirements.txt`).
You may need to adapt it for this standalone repository before it builds successfully.

## API

### Health

```bash
curl http://127.0.0.1:8012/health
```

Example response:

```json
{"status":"ok","service":"llm"}
```

### Readiness

```bash
curl http://127.0.0.1:8012/ready
```

Example response:

```json
{"ready":true,"models":["gemma_e2b_local","gemma_e4b_local"]}
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

The response shape is OpenAI-style chat completions JSON.

## Using the pipeline helpers

`pipeline.py` exposes higher-level helpers.

### Event extraction

```python
from llm.router import ProviderRouter
from llm.pipeline import extract_event

router = ProviderRouter("/path/to/service_models.yaml")
result = extract_event(
    router,
    narrative="Met Rahul at the office to hand off the quarterly report.",
    date="2026-04-14",
    time_str="10:00",
)
print(result)
```

### Person page synthesis

```python
from llm.pipeline import synthesize_person_page

page = synthesize_person_page(
    router,
    person_profile="Rahul is a teammate involved in planning and handoff work.",
    events=[
        "Met Rahul at the office to hand off the quarterly report."
    ],
)
```

### Topic page synthesis

```python
from llm.pipeline import synthesize_topic_page

page = synthesize_topic_page(
    router,
    label="Quarterly reporting",
    people_pages={
        "rahul": "# Rahul\n..."
    },
)
```

## Evaluation

`eval.py` compares providers for a role across a set of cases.

Example with explicit config path:

```bash
python -m llm.eval \
  --role extraction \
  --config /absolute/path/to/llm/service_models.yaml
```

Or specify providers directly:

```bash
python -m llm.eval \
  --models gemma_e2b_local,gemma_e4b_local \
  --config /absolute/path/to/llm/service_models.yaml
```

### Benchmarks

Included assets:
- `benchmarks/complex_events.jsonl`
- `benchmarks/rubric.json`

These are geared toward structured narrative extraction evaluation.

## Model assets

The `gemma/` directory contains:
- local GGUF model files
- benchmark / deployment notes in `GEMMA4_NOTES.md`

The `.gguf` files are intentionally ignored by Git in `.gitignore`.

## Tuning notes

See:
- `LLM_SERVICE_TUNING.md`
- `gemma/GEMMA4_NOTES.md`

These documents capture current baseline settings, tuning ideas, and model observations.

## Pi / agent resources

This repository also includes local Pi resources:
- `.agents/skills/`
- `.pi/prompts/`

These are developer-assistance assets and are not required to run the inference service.

## Known gaps / cleanup opportunities

If you want to make this repository fully standalone, likely next steps are:

1. add a `requirements.txt`
2. align `Dockerfile` with the current repo layout
3. either rename/restructure the package for standalone use or remove hardcoded `llm.*` assumptions
4. ship a standalone `models.yaml` or align `eval.py` to `service_models.yaml`
5. include or remove the external `parse_service` dependency used by `job_queue.py`
6. add tests for service, router, providers, and pipeline helpers

## License

No license file is currently included in this repository snapshot.
Add one if you intend to distribute the project publicly.
