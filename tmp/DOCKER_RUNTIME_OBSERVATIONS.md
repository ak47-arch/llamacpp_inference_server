# Docker Runtime Observations

Date: 2026-05-17

Historical note: this document records observations from the earlier three-provider bundled configuration. The current repository defaults keep only `gemma_e4b_q4_local` active, retain the other provider blocks as commented reference examples, and omit an explicit `ctx_size` override so the active model uses its default context length.
A newer `llama.cpp` build than the originally tested `b8763` is now required for working Gemma 4 audio over the HTTP server path; the old build exposed vision support but not HTTP audio modality for Gemma 4.

## Goal

Build the repository Docker image, run the container, and verify live inference against the bundled local Gemma models.

## Build Result

Image build succeeded.

- Image name: `llm-llm`
- Image id: `sha256:3a16a0008ab4b9b5f79b8954b15571af50314188dea2f79a9cc6d257d9d57f6d`

Build command used:

```bash
LLAMA_CPP_DIR=/home/anupam/llama-cpp/llama-b8763 docker-compose build
```

## Runtime Environment Used

Docker host already had another container bound to port `8012`:

- `survival-llm` -> `0.0.0.0:8012->8012`

To avoid disrupting it, this repo image was run separately on host port `8013`.

Mounted paths used:

- `./gemma -> /models`
- `/home/anupam/llama-cpp/llama-b8763 -> /opt/llama-cpp`

Test container launch command:

```bash
docker run -d \
  --name llm-inference-server-test \
  -p 8013:8012 \
  -e LLM_SERVER_HOST=0.0.0.0 \
  -e LLM_SERVER_PORT=8012 \
  -e LLM_SERVER_CONFIG_FILE=/app/llm/service_models.yaml \
  -v "$PWD/gemma:/models:ro" \
  -v /home/anupam/llama-cpp/llama-b8763:/opt/llama-cpp:ro \
  llm-llm \
  sh -c 'gunicorn --timeout 600 --bind ${LLM_SERVER_HOST:-0.0.0.0}:${LLM_SERVER_PORT:-8012} llm.service_app:app'
```

## Key Finding

The image and server work, but the default container runtime settings are not robust for local model warmup.

### Initial failure mode

With the default image command, `/ready` triggered a Gunicorn worker timeout during managed model startup/warmup.

Observed symptom:

- Gunicorn worker timed out at the default worker timeout
- request to `/ready` was aborted while waiting for local `llama-server` managed runtimes to become ready

### Workaround that succeeded

Restarting the container with:

```bash
gunicorn --timeout 600 ...
```

allowed readiness and inference to complete successfully.

## Readiness Result

After increasing the Gunicorn timeout, readiness succeeded:

```json
{"models":["gemma_e2b_local","gemma_e4b_local","gemma_e4b_q4_local"],"ready":true}
```

## Inference Verification

Successful responses were received from the running container.

### `gemma_e2b_local`

Prompt:

- `Reply with exactly: E2B_OK`

Response:

- `E2B_OK`

### `gemma_e4b_q4_local`

Prompt:

- `Reply with exactly: E4B_Q4_OK`

Response:

- `E4B_Q4_OK`

## Measured Sequential Request Times

These timings were measured after warmup, one request at a time.

- `gemma_e2b_local`: ~133.6s
- `gemma_e4b_q4_local`: ~62.0s

These are successful requests, but the latency is high enough that short worker/request timeouts will cause operational failures.

## Current Assessment

### Working

- Docker image build
- Container startup
- `/health`
- `/ready` after increasing Gunicorn timeout
- Inference through `/v1/chat/completions`

### Not yet operationally acceptable

- Default Gunicorn timeout for local managed model warmup
- First-request/readiness robustness under current container defaults
- End-to-end latency on this hardware

## Deferred Follow-Up

Do not optimize blindly yet.

Recommended next step is to build monitoring/observability infrastructure first, then use measured data to address:

1. Gunicorn timeout defaults
2. Readiness duration
3. First-token latency
4. Per-model latency and throughput
5. Warm vs cold request behavior
6. Resource usage during managed `llama-server` startup and inference

## Useful Endpoints During Later Investigation

- `http://127.0.0.1:8013/health`
- `http://127.0.0.1:8013/ready`
- `http://127.0.0.1:8013/v1/chat/completions`

## Cleanup

To stop the test container:

```bash
docker rm -f llm-inference-server-test
```
