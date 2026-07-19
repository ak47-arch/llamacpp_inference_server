# Plan: Uniform LLM Workflow Client

**Goal**: Extract a single shared `llm_client` package that any project can install and use to call LLM workflows the same way. The llm/ server stays a dumb OpenAI-compatible pipe; all intelligence (model selection, parameter setting, fallback logic, response parsing) moves into the client, driven by a per-project YAML config.

---

## Problem

Today, three LLM-consuming codebases call the same server with different plumbing:

| Project | Pattern | Config location | Params location |
|---------|---------|----------------|-----------------|
| survival-infrastructure | Gateway → Router → Client (3 classes) | `config/models.yaml` + `config/inference_profiles.yaml` | YAML |
| feed_analyser | `requests.post()` | Hardcoded in Python | Code |
| *(future project)* | ??? | ??? | ??? |

Adding a new model or changing a workflow's temperature requires touching different places in each project. There is no reusable client SDK.

---

## Target Architecture

```
┌─────────────────────────────────────────────┐
│  llm/ repo (pip install llm-client)         │
│                                              │
│  llm_client/                                 │
│    __init__.py                               │
│    workflow_client.py    ← WorkflowClient    │
│    config.py             ← config models     │
│    schemas.py            ← response types    │
│    errors.py             ← typed exceptions  │
│                                              │
│  pyproject.toml          ← pip-installable   │
│  service_models.yaml     ← server-side only  │
└─────────────────────────────────────────────┘
         ▲                         ▲
         │ pip install             │ pip install
         │                         │
┌────────┴──────────────┐  ┌──────┴──────────────┐
│  survival-infra/      │  │  feed_analyser/      │
│  config/              │  │  config/             │
│    workflows.yaml     │  │    workflows.yaml    │
│                       │  │                      │
│  from llm_client      │  │  from llm_client     │
│  import WorkflowClient│  │  import WorkflowClient│
└───────────────────────┘  └──────────────────────┘
```

Each project owns a single `config/workflows.yaml` that defines:
- Which models it knows about (name + URL)
- Which workflows exist (model reference + temperature + max_tokens + output type + fallback)

The client code is identical across projects.

---

## Design

### `config/workflows.yaml` (per project)

```yaml
models:
  fast:
    url: "http://host.containers.internal:8012"
    model: "gemma_e2b_q4_local"
    timeout: 180

  quality:
    url: "http://llm-inference-server:8012"
    model: "gemma_e2b_q4_local"
    timeout: 300

workflows:
  extraction:
    model_ref: fast
    temperature: 0.0
    max_tokens: 160
    output: json          # auto-parse choices[0].message.content as JSON
    system_prompt: "Extract structured event fields as JSON..."
    fallback: none

  extraction_judge:
    model_ref: fast
    temperature: 0.0
    max_tokens: 96
    output: json
    fallback: none

  wiki_synthesis:
    model_ref: quality
    temperature: 0.3
    max_tokens: 2048
    output: text
    fallback: none

  classify_tweet:
    model_ref: fast
    temperature: 0.0
    max_tokens: 256
    output: json
    fallback: module.heuristic_classify

  scout_project_card:
    model_ref: fast
    temperature: 0.0
    max_tokens: 512
    output: json
    fallback: module.fallback_card
```

### `WorkflowClient` (shared, in llm/)

```python
class WorkflowClient:
    def __init__(self, config_path: str | Path):
        self.config = WorkflowConfig.from_yaml(config_path)

    def complete(
        self,
        workflow_name: str,
        messages: list[dict] | None = None,
        user_prompt: str | None = None,
        system: str | None = None,
        **override_params,
    ) -> WorkflowResult:
        """Execute an LLM workflow.

        Args:
            workflow_name: Key in workflows.yaml.
            messages: Full messages array (overrides prompt+system).
            user_prompt: Shortcut for {"role": "user", "content": prompt}.
            system: Shortcut for system message (prepended if messages absent).
            **override_params: Override any workflow config field.

        Returns:
            WorkflowResult with .text, .data (parsed JSON if output=json),
            .model_id, .latency_ms, .success, .error.
        """
        ...

    def complete_text(self, workflow_name, prompt, system=None, **kw) -> WorkflowResult:
        """Convenience: complete() with user_prompt."""
        return self.complete(workflow_name, user_prompt=prompt, system=system, **kw)
```

### `WorkflowResult` (return type)

```python
@dataclass
class WorkflowResult:
    text: str                           # raw response text
    data: dict | list | None            # parsed JSON (if output=json and parse succeeded)
    model_id: str
    latency_ms: float
    success: bool
    error: str | None
    fallback_used: bool
```

### Error types

```python
class LLMClientError(RuntimeError): ...
class LLMTimeoutError(LLMClientError): ...
class LLMUnavailableError(LLMClientError): ...
class LLMBadResponseError(LLMClientError): ...   # unparseable JSON, empty response
```

---

## Migration steps

### Phase 1 — Build the shared client (in llm/ repo)

1. Create `llm_client/` directory in llm/ repo with:
   - `config.py` — pydantic models for WorkflowConfig, ModelEntry, WorkflowDef
   - `workflow_client.py` — WorkflowClient class with `complete()` + `complete_text()`
   - `schemas.py` — WorkflowResult dataclass
   - `errors.py` — typed exceptions
2. Add `pyproject.toml` to make it pip-installable
3. Write tests (unit test the config loading + request building; integration test against the running server)

### Phase 2 — Migrate feed_analyser (easier, fewer workflows)

1. Create `config/workflows.yaml` with 2 workflows (classify_tweet, scout_project_card)
2. Pip-install the shared client: `pip install -e /path/to/llm`
3. Replace the two `requests.post()` blocks in `classifier.py` and `github_scout.py` with:
   ```python
   client = WorkflowClient("config/workflows.yaml")
   result = client.complete_text("classify_tweet", prompt=text)
   ```
4. Remove hardcoded `LLM_CHAT_URL`, `LLM_MODEL`, `temperature`, `max_tokens`, `timeout` constants
5. Route fallback through the config (the `module.path.function` reference in workflows.yaml)
6. Test: run classification + scouting, verify output matches existing behavior
7. Commit and push

### Phase 3 — Migrate survival-infrastructure (more complex)

1. Create `config/workflows.yaml` consolidating current `models.yaml` + `inference_profiles.yaml`
2. Pip-install the shared client
3. Replace the 3-class inference stack:
   - Remove `GenericLLMClient` (llm_generic_client.py)
   - Remove `GenericRoleRouter` (llm_role_router.py)
   - Remove `WorkflowInferenceGateway` (workflow_inference.py)
   - Remove `InferenceProfileRegistry` (inference_profiles.py)
4. Update all callers in extraction pipeline + wiki synthesis to use `WorkflowClient.complete_text()`
5. The lint gate (`wiki/lint.py`) stays — it's deterministic, not an LLM call
6. Test: run extraction pipeline + wiki synthesis, verify output matches existing behavior
7. Remove dead config: `config/models.yaml`, `config/inference_profiles.yaml`
8. Commit and push

---

## What changes per project

| | Before | After |
|---|---|---|
| **survival-infra** | 4 inference classes + 2 config files | `WorkflowClient` + 1 config file |
| **feed_analyser** | `requests.post()` with hardcoded constants | `WorkflowClient` + 1 config file |
| **future project** | ??? | `WorkflowClient` + 1 config file from day one |

## What stays unchanged

- **llm/ server** — no changes. It remains a generic OpenAI-compatible pipe.
- **`service_models.yaml`** — still the server's model registry.
- **Wiki lint gate** — deterministic, not an LLM call.
- **Per-project ownership** — each project's `config/workflows.yaml` is its own.

## What adding a new model looks like after migration

1. Add GGUF + `service_models.yaml` entry in llm/ repo
2. Add model entry + (optionally) update workflow `model_ref` in each project's `config/workflows.yaml`
3. **Zero Python code changes** in any project

---

## Open questions to resolve during Phase 1

1. **Dynamic system prompts** — workflows like extraction and wiki synthesis pass a task-specific system prompt at call time, not from config. Should `system_prompt` in YAML be a default (overridable in `complete()`), or should it always come from the caller? **Proposal**: config holds a default, caller overrides via `system=` kwarg.
2. **Fallback resolution** — the YAML `fallback: module.heuristic_classify` needs to resolve `module` to a Python import. Should the client handle this (eval/import at runtime), or should the caller pass the fallback as a Python callable? **Proposal**: YAML holds a string path, client imports it lazily. This keeps the config self-documenting.
3. **Package name** — `llm_client` vs `llm.client` vs `llmclient`. **Proposal**: `llm_client` (installed as `pip install llm-client`), importing as `from llm_client import WorkflowClient`.
4. **Package location** — inside the llm/ repo alongside the server, or as a standalone repo? **Proposal**: inside llm/ under `client/` directory, with its own `pyproject.toml`. This keeps server + client versioned together. Install via local path reference.