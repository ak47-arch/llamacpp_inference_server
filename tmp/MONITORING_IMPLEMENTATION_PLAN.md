# Monitoring Implementation Plan

Date: 2026-05-17

## Goal

Add observability to the inference server in a staged, low-risk way so runtime, latency, warmup, and failure behavior can be measured before optimization work begins.

## Guiding Principle

Do not start with raw prompt logging as the first observability feature.

Begin with low-privacy, high-value telemetry that helps explain:

- request latency
- readiness delays
- managed `llama-server` warmup behavior
- provider failures and timeouts
- per-model throughput and error rates

## Observability Areas

### 1. Request metrics

Capture service-level metrics such as:

- total requests
- requests by route
- requests by model/provider
- in-flight requests
- success / client error / server error counts
- timeout counts
- provider unavailable counts
- end-to-end latency histograms
- upstream request latency histograms

### 2. Managed runtime telemetry

Capture per-managed-server lifecycle data such as:

- process started / not started
- pid
- model id
- port
- startup attempts
- startup duration
- warm / cold state
- restart count
- last successful health probe
- readiness failures and reasons

### 3. Stage timing / request tracing

Track major stages in request handling:

- request received
- provider selected
- warmup started
- warmup completed
- upstream request sent
- upstream response received
- response returned

Even if full distributed tracing is not added initially, structured stage timing should be recorded.

### 4. Structured request logging

Start with metadata-only logging:

- request id
- timestamp
- route
- model/provider
- request params (`temperature`, `max_tokens`, `timeout_seconds` when present)
- prompt/message count
- prompt size
- prompt fingerprint/hash
- response size
- total latency
- outcome class

Do not make raw prompt logging the first implementation step.

### 5. Prompt logging policy and privacy controls

If raw prompt logging is later added, it must be governed by explicit policy:

- disabled by default or metadata-only by default
- optional redaction mode
- retention policy
- environment-based enablement
- clear documentation of privacy implications

### 6. Debug/diagnostic surfaces

Potential future surfaces:

- `/metrics`
- `/debug/providers`
- `/debug/runtime`
- `/debug/recent-requests`
- `/debug/errors`

These should be optional and protected if exposed outside local development.

## Recommended Implementation Order

### Phase 1

Metrics and stage timing only:

- request counters
- latency histograms
- provider/model breakdown
- readiness/warmup durations
- timeout/error counts

### Phase 2

Managed runtime telemetry:

- per-provider runtime state
- startup/restart visibility
- readiness-failure diagnostics

### Phase 3

Structured request logging, metadata only:

- request id
- params
- prompt size/fingerprint
- outcome + latency

### Phase 4

Prompt logging policy:

- raw prompt capture controls
- redaction and retention decisions

### Phase 5

Debug/admin observability endpoints.

## Why This Order

This order gives immediate operational value with minimal privacy risk.

It also directly supports the currently observed runtime issues:

- long readiness time
- local model warmup delays
- high end-to-end latency
- timeout sensitivity under Gunicorn

## Open Questions For Later Specs

- Should metrics be Prometheus-compatible?
- Should request logging go to stdout, file, or both?
- Should prompt fingerprints use hashing, truncation, or both?
- Should debug endpoints be local-only or auth-protected?
- What retention policy should apply to logs and metrics exports?
- Should per-model resource usage be collected inside the service or delegated to container/host monitoring?

## Recommended Next Feature After Loose Ends Are Resolved

Start with a metrics-focused feature covering:

- request counters
- latency histograms
- readiness/warmup timing
- provider/model breakdown
- timeout/error counts

Do not start with raw prompt capture.
