# Graph Report - llm  (2026-06-22)

## Corpus Check
- 41 files · ~41,281 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 753 nodes · 1151 edges · 31 communities (29 shown, 2 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 125 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5d053721`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]

## God Nodes (most connected - your core abstractions)
1. `OpenAICompatibleProvider` - 40 edges
2. `ProviderTimeoutError` - 36 edges
3. `CompletionResult` - 30 edges
4. `ProviderUnavailableError` - 29 edges
5. `RecordingOpenAIProvider` - 27 edges
6. `MultimodalChatTests` - 27 edges
7. `MonitoringSpecTests` - 26 edges
8. `OpenAICompatibleProviderSpecTests` - 24 edges
9. `LlamaCppProvider` - 21 edges
10. `ProviderRouter` - 21 edges

## Surprising Connections (you probably didn't know these)
- `Any` --uses--> `NDJSONCaptureSink`  [INFERRED]
  prompt_capture.py → capture_sinks.py
- `MultimodalChatTests` --uses--> `LlamaCppProvider`  [INFERRED]
  tests/test_multimodal_chat.py → llama_cpp_provider.py
- `RecordingNonOpenAIProvider` --uses--> `LlamaCppProvider`  [INFERRED]
  tests/test_multimodal_chat.py → llama_cpp_provider.py
- `RecordingOpenAIProvider` --uses--> `LlamaCppProvider`  [INFERRED]
  tests/test_multimodal_chat.py → llama_cpp_provider.py
- `StubRouter` --uses--> `LlamaCppProvider`  [INFERRED]
  tests/test_multimodal_chat.py → llama_cpp_provider.py

## Import Cycles
- 1-file cycle: `service_app.py -> service_app.py`

## Communities (31 total, 2 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (34): ABC, Flask, Generic inference server package., LlamaCppProvider, CompletionResult, Popen, Provider that calls a local llama-cli binary via subprocess., Terminate a timed-out process and escalate to kill if needed. (+26 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (7): BlockingStream, InvalidRuntime, OperationalLoggingTests, SuccessRuntime, TimeoutRuntime, UnavailableRuntime, UnhandledRuntime

### Community 2 - "Community 2"
Cohesion: 0.15
Nodes (5): DummyRuntime, ExplodingRuntime, MonitoringSpecTests, StubProvider, StubRouter

### Community 3 - "Community 3"
Cohesion: 0.11
Nodes (23): Any, CaptureSink, NDJSONCaptureSink, Path, Durable sinks for prompt-capture records., build_capture_manager_from_env(), _build_capture_record(), _decode_base64_payload() (+15 more)

### Community 4 - "Community 4"
Cohesion: 0.06
Nodes (35): Acceptance Criteria, Current Behavior, Data Model, Dependency interface, Edge Cases, `GET /metrics`, HTTP endpoints, Implementation Commits (+27 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (34): Acceptance Criteria, Accepted Test Audit Report, Bundled example provider set, Code Quality Issues, Commented reasoning example lines, Current Behavior, Data Model, Edge Cases (+26 more)

### Community 6 - "Community 6"
Cohesion: 0.13
Nodes (4): MultimodalChatTests, RecordingNonOpenAIProvider, RecordingOpenAIProvider, StubRouter

### Community 7 - "Community 7"
Cohesion: 0.06
Nodes (33): Acceptance Criteria, Accepted Test Audit Report, Child-process log forwarding, Code Quality Issues, Current Behavior, Data Model, Edge Cases, Implementation Commits (+25 more)

### Community 8 - "Community 8"
Cohesion: 0.06
Nodes (31): Acceptance Criteria, Capture modes, Configuration, Current Behavior, Data Model, Edge Cases, `GET /debug/traces`, `GET /debug/traces/<request_id>` (+23 more)

### Community 9 - "Community 9"
Cohesion: 0.07
Nodes (28): Acceptance Criteria, Allowlisted isolated skills, Child session constraints, Current Behavior, Data Model, Edge Cases, Generic isolated run summary, Implementation Commits (+20 more)

### Community 10 - "Community 10"
Cohesion: 0.07
Nodes (27): Bootstrap Rule for This Repository, Canonical spec traceability format, Changelog Rules, Changelog traceability format, Choosing the Owning Spec, Core Rules, Feature Development Workflow, Migration Guidance (+19 more)

### Community 11 - "Community 11"
Cohesion: 0.13
Nodes (3): BaseProvider, OpenAICompatibleProvider, OpenAICompatibleProviderSpecTests

### Community 12 - "Community 12"
Cohesion: 0.08
Nodes (25): 1. Gemma 4 Model Family, 2. Downloaded Models, 3. Benchmark Results (CPU-Only, 8 Threads, `llama-cli`), 4. llama.cpp Setup & Run Commands, 5. Smoke Test Results, 6. On-Device / Edge Deployment Assessment, 7. Quantization Reference, 8. HuggingFace Download Commands (+17 more)

### Community 13 - "Community 13"
Cohesion: 0.08
Nodes (25): Acceptance Criteria, Capture modes, Capture record shape, Configuration, Current Behavior, Data Model, Downstream planning note, Edge Cases (+17 more)

### Community 14 - "Community 14"
Cohesion: 0.14
Nodes (17): classify_exception(), classify_readiness_exception(), current_request_metric_labels(), increment_managed_server_restart(), _normalize_label(), _normalize_outcome(), observe_current_chat_provider_duration(), observe_managed_server_startup() (+9 more)

### Community 15 - "Community 15"
Cohesion: 0.08
Nodes (24): API, `capture_sinks.py`, Chat completions, Configuration, Containers, Core modules, Development workflow, Generic Inference Server (+16 more)

### Community 16 - "Community 16"
Cohesion: 0.16
Nodes (5): FailingSink, PromptCaptureTests, Path, StubProvider, StubRouter

### Community 17 - "Community 17"
Cohesion: 0.09
Nodes (22): Acceptance Criteria, Current Behavior, Data Model, Edge Cases, `GET /health`, `GET /openapi.json`, `GET /ready`, `GET /v1/models` (+14 more)

### Community 18 - "Community 18"
Cohesion: 0.22
Nodes (16): ALLOWED_ISOLATED_SKILLS, buildSkillPrompt(), buildSpecVerifierPrompt(), buildTestVerifierPrompt(), filterSkillsByName(), parseIsolatedSkillArgs(), parseSpecVerifyArgs(), parseTestVerifyArgs() (+8 more)

### Community 19 - "Community 19"
Cohesion: 0.10
Nodes (19): 1. Request metrics, 2. Managed runtime telemetry, 3. Stage timing / request tracing, 4. Structured request logging, 5. Prompt logging policy and privacy controls, 6. Debug/diagnostic surfaces, Goal, Guiding Principle (+11 more)

### Community 20 - "Community 20"
Cohesion: 0.13
Nodes (3): GenericInferenceServerTests, StubProvider, StubRouter

### Community 21 - "Community 21"
Cohesion: 0.11
Nodes (18): Build Result, Cleanup, Current Assessment, Deferred Follow-Up, Docker Runtime Observations, `gemma_e2b_local`, `gemma_e4b_q4_local`, Goal (+10 more)

### Community 22 - "Community 22"
Cohesion: 0.12
Nodes (16): Acceptance Criteria, Current Behavior, Data Model, Edge Cases, Feature Development Workflow, Implementation Commits, Interfaces, Module Ownership (+8 more)

### Community 23 - "Community 23"
Cohesion: 0.12
Nodes (16): Acceptance Criteria, <Capability Name>, Current Behavior, Data Model, Edge Cases, Implementation Commits, Interfaces, Module Ownership (+8 more)

### Community 24 - "Community 24"
Cohesion: 0.23
Nodes (12): _build_server_command(), _build_subprocess_env(), ensure_managed_server(), _forward_child_stream(), _healthcheck_urls(), Popen, Managed local llama.cpp server lifecycle for low-latency HTTP inference., _resolve_mmproj_path() (+4 more)

### Community 25 - "Community 25"
Cohesion: 0.18
Nodes (10): Better reliability, Configuration surfaces, Container deployment notes, Higher throughput, Inference Server Tuning Notes, Lower latency, Managed runtime settings, Request defaults (+2 more)

### Community 26 - "Community 26"
Cohesion: 0.22
Nodes (8): Changelog, Rules, Summary, Summary, Traceability Ledger, Traceability Ledger, Unreleased, v0.1.0 - 2026-05-19

### Community 27 - "Community 27"
Cohesion: 0.25
Nodes (7): Configurable but not really surfaced as product features, Feature Matrix, Implemented, Not currently provided, Practical summary, What it is not yet, What the project is now

### Community 28 - "Community 28"
Cohesion: 0.48
Nodes (3): DANGEROUS_PATTERNS, getConfirmationMessage(), shouldConfirmBashCommand()

## Knowledge Gaps
- **317 isolated node(s):** `DANGEROUS_PATTERNS`, `RunSkillOptions`, `Path`, `compose_env_preflight.sh script`, `Rules` (+312 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CompletionResult` connect `Community 0` to `Community 2`, `Community 6`, `Community 11`, `Community 16`, `Community 20`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Why does `ProviderTimeoutError` connect `Community 0` to `Community 1`, `Community 2`, `Community 11`, `Community 14`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Why does `OpenAICompatibleProvider` connect `Community 11` to `Community 0`, `Community 24`, `Community 6`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Are the 31 inferred relationships involving `OpenAICompatibleProvider` (e.g. with `BaseProvider` and `CompletionResult`) actually correct?**
  _`OpenAICompatibleProvider` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 26 inferred relationships involving `ProviderTimeoutError` (e.g. with `Flask` and `LlamaCppProvider`) actually correct?**
  _`ProviderTimeoutError` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `CompletionResult` (e.g. with `LlamaCppProvider` and `CompletionResult`) actually correct?**
  _`CompletionResult` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `ProviderUnavailableError` (e.g. with `Flask` and `LlamaCppProvider`) actually correct?**
  _`ProviderUnavailableError` has 19 INFERRED edges - model-reasoned connections that need verification._