# Known Issues

Last updated: 2026-08-28

This document tracks open and resolved issues discovered during the July 2026
architecture audit (`docs/technical/ARCHITECTURE_REVIEW_llm_2026-07.md`, now archived
as company data) and subsequent operational experience. Issues are organised by source.

---

## Status Key

| Badge | Meaning |
|-------|---------|
| ❌ **OPEN** | Issue confirmed present in current codebase |
| ⚠️ **PARTIAL** | Issue partially addressed; residual problem remains |
| ✅ **RESOLVED** | Issue has been fixed (kept for historical reference) |

---

## 🔴 Architecture Issues (from July 2026 Audit)

These issues were identified by graphify AST analysis (354 nodes, 785 edges, 14 communities)
of the `service_app` server code. They affect the server path which is currently **dormant**
(applications route directly to cloud via `llm_client`, bypassing `:8012`). The issues
will need resolution before the pluggable local-backend feature is picked up.

### A-1: `OpenAICompatibleProvider` is a god module — ❌ OPEN

**Source**: `ARCHITECTURE_REVIEW_llm_2026-07.md` Issue 1
**Graph evidence**: 41 edges — the most-connected node in the system. Next-closest is
`ProviderTimeoutError` at 34 edges.

**The problem**: The provider handles chat completion requests, streaming vs non-streaming,
error response interpretation, request payload construction, and usage metric reporting,
all in one module. 22 other nodes depend on it directly. A deeper module would separate
payload construction, HTTP transport, and error mapping behind a `Provider` interface.

**Current context**: This code is in the `service_app` server which is not actively serving
(cloud workflows bypass the server). Still OPEN because it hasn't been refactored.

**Suggested fix**: Split into `PayloadBuilder`, `TransportClient`, `ErrorMapper` behind
an `LLMProvider` interface. Tests then mock the transport, not the entire provider.

---

### A-2: No shared `Provider` interface — ❌ OPEN

**Source**: `ARCHITECTURE_REVIEW_llm_2026-07.md` Issue 3
**Graph evidence**: `OpenAICompatibleProvider` (41 edges, Community 7) and
`LlamaCppProvider` (22 edges, Community 0) share no community cluster and have no
edges between them in the AST graph.

**The problem**: Both providers implement similar operations (complete chat, handle errors,
report usage) but there is **no shared `Provider` abstract interface**. They evolved
independently. Adding a new backend (vLLM, TGI, Ollama) means duplicating common error
handling, timeout logic, and metric reporting.

**Current context**: The pluggable backend feature is deferred. This issue must be
resolved when local inference resumes, because a `Provider` interface is the prerequisite
for the pluggable registry.

**Suggested fix**: Extract a `Provider` abstract interface. This creates a seam for all
future backends, eliminates the `RecordingOpenAIProvider` test double, and enables
middleware for cross-cutting concerns like prompt capture.

---

### A-3: Error types are empty exception classes scattered everywhere — ❌ OPEN

**Source**: `ARCHITECTURE_REVIEW_llm_2026-07.md` Issue 4
**Graph evidence**: `ProviderTimeoutError` (34 edges) and `ProviderUnavailableError`
(27 edges) are more connected than most production modules despite carrying **no
behaviour** — they are empty exception classes.

**The problem**: Every call site must import, raise, and catch these. The high edge count
reflects the cost of a shallow exception hierarchy scattered across the server codebase.
If retry/fallback logic were centralised behind the `Provider` interface, these
exceptions would be internal to one module.

**Current context**: The `llm_client` package has its own typed exception hierarchy
(`LLMClientError`, `LLMTimeoutError`, `LLMUnavailableError`, `LLMBadResponseError`)
that is independent of the server's exceptions. The server-side issue remains open.

**Suggested fix**: Centralise retry/fallback logic behind the `Provider` interface.
Callers make a single call; retries, timeouts, and fallback happen inside the interface
implementation. Exception classes become internal to the provider module.

---

### A-4: Prompt capture is a standalone module called explicitly — ❌ OPEN

**Source**: `ARCHITECTURE_REVIEW_llm_2026-07.md` Issue 5
**Graph evidence**: Community 4 (`Prompt Capture Manager`) has 36 nodes — larger than
some providers.

**The problem**: Prompt capture is a cross-cutting concern that every provider call
passes through, yet it is implemented as a standalone module that providers must
explicitly call. This creates coupling: every provider must know about capture. If a
new provider forgets to add capture calls, monitoring silently misses data.

**Suggested fix**: Make prompt capture a **middleware** that wraps the `Provider`
interface (decorator or wrapper adapter), not something each provider calls explicitly.

---

### A-5: Test classes dominate the god-node list — ⚠️ PARTIAL (structural observation)

**Source**: `ARCHITECTURE_REVIEW_llm_2026-07.md` Issue 2
**Graph evidence**: 5 of the top 10 most-connected nodes are test doubles or test classes
(`RecordingOpenAIProvider`, `MultimodalChatTests`, etc.).

**The problem**: Implementation modules are **shallow** — the real behaviour is spread
across so many small modules that test infrastructure has as many connections as
production code. The `RecordingOpenAIProvider` test double would be eliminated by the
`Provider` interface fix (A-2), but the general observation about test-surface-to-
implementation ratio remains.

**Suggested fix**: Consolidate related tests into fewer, deeper test modules that
exercise real production modules through their public interfaces. Replace
`RecordingOpenAIProvider` with a seam — a `Provider` interface that a real provider
and a test fake both satisfy.

---

## 🟡 Model Constraints

### M-1: DeepSeek V4 Flash internal reasoning consumes output budget — ❌ OPEN

**Source**: Operational finding (Decision 08, knowledge index)

**The problem**: DeepSeek V4 Flash uses internal chain-of-thought reasoning tokens that
count toward the `max_tokens` budget. For small JSON extraction tasks (<80 expected
output tokens), the reasoning overhead consumes the entire budget and the model returns
`content: null` with `finish_reason: "length"`. This applies to all variants tested:
`deepseek/deepseek-v4-flash`, `deepseek/deepseek-v4-flash-0731`,
`~deepseek/deepseek-v4-flash-latest`. The `deepseek/deepseek-chat` (V3, non-Flash) does
not have this behaviour.

**Impact**: Any model with internal reasoning tokens (DeepSeek V4 Flash, Gemini thinking
models, Claude extended thinking) is unsuitable for small JSON extraction tasks unless
the provider exposes a way to disable reasoning at the request level.

**Workaround**: Use `openai/gpt-4o-mini` for extraction workflows (no reasoning bleed,
~1.6s latency, $0.000066/extraction). Keep DeepSeek V4 Flash for wiki synthesis where
reasoning is beneficial.

**Revision trigger**: If OpenRouter or DeepSeek adds a `reasoning: false` request flag,
re-evaluate DeepSeek Flash for the fast tier.

---

## ✅ Resolved Issues (Historical)

| ID | Description | Fix |
|----|-------------|------|
| — | llm_client `_try_parse_json` crashes on `None` content | Added null-guard in `workflow_client.py` (2026-08-28) |

---

## Deleted Documents (2026-08-28)

The following documents were removed/archived as part of the spec-driven development
process retirement:

| Document | Fate |
|----------|-------|
| `CHANGELOG.md` | Deleted — dual-purpose changelog + traceability ledger for retired spec-driven process |
| `PLAN_shared_llm_client.md` | Deleted — design intent captured in `docs/vision/VISION.md` |
| `docs/FEATURE_DEVELOPMENT_WORKFLOW.md` | Archived to `archive/` — part of retired spec-driven process |
| `docs/technical/ARCHITECTURE_REVIEW_llm_2026-07.md` | Deleted — observations folded into this `KNOW_ISSUES.md` |
| `specs/` (entire directory) | Archived to `archive/specs/` — retained for retrospective analysis