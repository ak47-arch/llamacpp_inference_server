# Architecture Review — July 2026 — LLM Service

Based on graphify AST graph (354 nodes, 785 edges, 14 communities) and code inspection.

---

## Overview

A generic OpenAI-compatible LLM inference server. Provides a local API endpoint that routes requests to configurable backends: local subprocess (llama.cpp), OpenAI-compatible remote providers, or managed model servers.

```
HTTP REQUEST ──> service_app.py ──> Router ──> Provider (OpenAI/LlamaCpp)
                                        └──> Monitoring ──> PromptCapture
```

---

## Issues Found

### Issue 1: `OpenAICompatibleProvider` is a god module (41 edges)

It is the **most-connected node** by far. Next-closest is `ProviderTimeoutError` at 34 edges. The provider:
- Handles chat completion requests
- Manages streaming vs non-streaming
- Interprets error responses
- Constructs request payloads
- Reports usage metrics

**Problem:** A deep provider would separate concerns: one module for payload construction, one for HTTP transport, one for error mapping. Currently,
`OpenAICompatibleProvider` does all of these, and 22 other nodes depend on it directly.

**Depth fix:** Split into `PayloadBuilder`, `TransportClient`, `ErrorMapper` behind an `LLMProvider` interface. Tests then mock the transport, not the entire provider.

---

### Issue 2: Test classes dominate god node list (5 of top 10)

```
5.  RecordingOpenAIProvider    (27 edges)  ← test double
6.  MultimodalChatTests        (27 edges)  ← test class
7.  MonitoringSpecTests        (26 edges)  ← test class
8.  OpenAICompatibleProviderSpecTests (24) ← test class
10. OperationalLoggingTests     (20 edges)  ← test class
```

**Problem:** Five of the ten most-connected nodes are test doubles or test classes. This means the implementation modules are **shallow** — the real behaviour is spread across so many small modules that test infrastructure has as many connections as production code. The test surface is as large as the implementation surface, which is a classic sign of shallow modules (callers — in this case tests — need to learn as much as the module itself contains).

**Depth fix:** Consolidate related tests into fewer, deeper test modules that exercise real production modules through their public interfaces rather than reaching into internals. The `RecordingOpenAIProvider` test double should be replaced with a seam — a `Provider` interface that a real provider and a test fake both satisfy, so tests don't need recording infrastructure at all.

---

### Issue 3: Two providers, one seam not realized

```
OpenAICompatibleProvider  (41 edges)  ← remote HTTP
LlamaCppProvider          (22 edges)  ← local subprocess
```

Both implement similar operations (complete chat, handle errors, report usage) but there is **no shared `Provider` interface**. They evolved independently. The graph shows they share no community (they're in different clusters), yet they serve the same role.

**Evidence from graph:** Community 7 (`OpenAI Compatible Provider`) and Community 0 (`Local LLM Subprocess Provider`) are the two largest communities, and the graph shows no edges between their core provider nodes — they share no common base class or interface in the AST.

**Depth fix:** Extract a `Provider` abstract interface that both satisfy. This creates a real seam at which future backends (ollama, vLLM, TGI) can be added as adapters without duplicating common error handling, timeout logic, and metric reporting.

---

### Issue 4: `ProviderTimeoutError` and `ProviderUnavailableError` are the second-most-connected nodes

```
ProviderTimeoutError    (34 edges)
ProviderUnavailableError (27 edges)
```

These error types are more connected than most production modules. They appear in every provider and every test, but they carry **no behaviour** — they're empty exception classes.

**Problem:** Every call site must import, raise, and catch these. The high edge count reflects the cost of a shallow exception hierarchy scattered across the codebase. If the error handling logic (retry, fallback, circuit-breaker) were centralized, these exceptions would be internal to one module instead of imported everywhere.

**Depth fix:** Centralize retry/fallback logic behind the `Provider` interface. Callers get a single call; retries, timeouts, and fallback to alternate providers happen inside the interface implementation. The exception classes become implementation details.

---

### Issue 5: Prompt Capture is a separate module with 36 nodes

Community 4 (`Prompt Capture Manager`) has 36 nodes — larger than some providers. It captures prompts, manages sinks, handles encoding, and manages state.

**Problem:** Prompt capture is cross-cutting concern that every provider call passes through, yet it's implemented as a standalone module that providers must explicitly call. This creates coupling: every provider must know about capture. If a new provider forgets to add capture calls, monitoring silently misses data.

**Depth fix:** Make prompt capture a **middleware** that wraps the `Provider` interface, not something each provider calls explicitly. A decorator or wrapper adapter that satisfies the `Provider` seam and adds capture transparently.

---

## Summary

| Module | Current State | Problem | Depth Fix |
|--------|--------------|---------|-----------|
| `OpenAICompatibleProvider` | 41-edge hub | Does payload + transport + error mapping | Split into `PayloadBuilder` / `Transport` / `ErrorMapper` |
| Test classes | 5 of top 10 nodes | Implementation too shallow, test infras equal to production | Consolidate tests; use Provider seam instead of RecordingOpenAIProvider |
| Providers | No shared interface | Two providers evolved independently | Extract `Provider` abstract interface for real seam |
| Error types | 34+27 edges | Empty exceptions scattered everywhere | Centralize retry/fallback behind Provider interface |
| Prompt Capture | 36-node standalone | Providers must explicitly call it | Make it middleware at the Provider seam |

## Recommendations (priority order)

1. **Extract a `Provider` interface** — creates the seam for all future backends (olla, vLLM, TGI), eliminates RecordingOpenAIProvider test double, and enables middleware for cross-cutting concerns like prompt capture and monitoring.

2. **Centralize retry/fallback** — move error handling inside the Provider interface so callers make one call instead of importing and catching 3+ exception types.

3. **Make prompt capture middleware** — wrap the Provider seam with a capture adapter instead of having each provider call capture explicitly.