# Inference Server Tuning Notes

This document captures practical tuning knobs for the generic inference server.

## Configuration surfaces

### Managed runtime settings
Configured under `connection.managed_server` in `service_models.yaml`.

Common knobs:
- `threads`
- `ctx_size`
- `batch_size`
- `startup_timeout_seconds`
- `extra_args`

Typical `llama-server` flags controlled here:
- `-t` threads
- `-c` context size
- `-b` batch size
- `--reasoning`
- `--reasoning-budget`
- `--reasoning-format`
- `--mlock`
- `--flash-attn`

### Request defaults
Configured under `default_params` in `service_models.yaml`.

Common knobs:
- `temperature`
- `max_tokens`
- `timeout_seconds`

## Tuning goals

### Lower latency
Try:
- smaller `ctx_size`
- smaller `max_tokens`
- fewer concurrent managed runtimes per host

### Higher throughput
Try:
- increasing `threads`
- setting `batch_size`
- using separate providers for separate models or workloads

### Better reliability
Try:
- longer `startup_timeout_seconds` for large models
- larger request `timeout_seconds` for slow hardware
- readiness probes before putting the container behind a load balancer

## Container deployment notes

Recommended mounts:
- `/models` for GGUF files
- `/opt/llama-cpp` for `llama-server`

Recommended environment variables:
- `LLM_SERVER_HOST`
- `LLM_SERVER_PORT`
- `LLM_SERVER_CONFIG_FILE`
- `LLAMA_CPP_DIR` (compose usage)

## Validation checklist

After changing model or runtime settings, verify:
- `GET /health` returns 200
- `GET /ready` returns 200 after warmup
- `POST /v1/chat/completions` succeeds for each configured provider
- managed `llama-server` processes start on expected ports
- timeout settings are appropriate for your hardware
