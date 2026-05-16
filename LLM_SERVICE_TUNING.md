# LLM Service Tuning Roadmap

**Status:** Planning (not yet implemented)
**Date:** 2026-05-03
**Context:** Post-reasoning-disable investigation; extraction now completes in ~16s vs 180s+ timeouts

---

## Current Baseline

### Service Configuration (service_models.yaml)

**Both e2b/e4b models:**
```yaml
managed_server:
  binary_path: /opt/llama-cpp/llama-server
  ctx_size: 8192
  threads: 8
  extra_args:
    - --reasoning: "off"
    - --reasoning-budget: "0"
    - --reasoning-format: none

default_params:
  temperature: 0.0 (e2b) / 0.1 (e4b)
  max_tokens: 1024 (e2b) / 512 (e4b)
  timeout_seconds: 120 (e2b) / 180 (e4b)
```

**Current Performance:**
- Extraction latency: ~16-17s (direct inference)
- End-to-end job completion: ~62s (including queue polling overhead)
- Timeout success rate: 100% (no more hung jobs)

---

## Tunable Parameters Reference

### Server Runtime Settings (managed_server)

| Parameter | Flag | Range | Current | Impact |
|-----------|------|-------|---------|--------|
| `threads` | `-t` | 1-N | 8 | CPU parallelism; higher = more throughput, higher load |
| `ctx_size` | `-c` | 512-8192 | 8192 | Context window; larger = slower inference, more nuance |
| `batch_size` | `-b` | 8-256 | *(not set)* | Tokens/batch; affects latency vs throughput tradeoff |
| `--reasoning` | flag | `on`/`off` | `off` | Enable/disable model thinking mode |
| `--reasoning-budget` | tokens | 0-4096 | 0 | Max reasoning tokens (only if reasoning=on) |
| `--reasoning-format` | format | `standard`/`none` | `none` | Reasoning output style |
| `--mlock` | flag | N/A | *(not set)* | Lock model in RAM; prevents paging |
| `--flash-attn` | flag | N/A | *(not set)* | Flash attention optimization (if supported) |

### Inference Request Settings (default_params)

| Parameter | Range | Current (e2b/e4b) | Impact |
|-----------|-------|---|--------|
| `temperature` | 0.0-2.0 | 0.0/0.1 | 0.0=deterministic, 1.0+=creative |
| `max_tokens` | 1-ctx_size | 1024/512 | Response length cap |
| `timeout_seconds` | 1+ | 120/180 | HTTP read timeout |

---

## Optimization Scenarios

### Scenario 1: Faster Extraction (Latency Optimization)

**Goal:** Reduce extraction latency from ~16s to ~12-14s

**Changes:**
```yaml
# service_models.yaml - extraction task variant
gemma_e2b_extraction:
  managed_server:
    threads: 4                    # Reduce CPU contention if bottlenecked
    ctx_size: 4096                # Halve context; extraction narratives are short
    extra_args: [--reasoning, off, --reasoning-budget, 0, --reasoning-format, none]
  default_params:
    temperature: 0.0              # Ensure deterministic (no random sampling)
    max_tokens: 256               # Lower cap; JSON extraction rarely needs 1K
    timeout_seconds: 60           # Can be tighter; extraction should complete in <30s
```

**Expected Gains:**
- ~15-20% latency reduction (4096 ctx + lower max_tokens)
- Deterministic behavior (extraction doesn't need creativity)
- Tighter timeout budget catches slow cases earlier

**Risk Level:** Low — extraction quality should be identical on short narratives

**Regression Tests Needed:**
- `test_033_llm_service.py`: Verify extraction still passes on C1-C5 benchmark dataset
- `test_007_job_queue.py`: Confirm job completion rate unchanged

---

### Scenario 2: Quality-First Wiki Synthesis (Reasoning Enabled)

**Goal:** Enable reasoning for wiki synthesis (future stages) with bounded budget

**Changes:**
```yaml
# service_models.yaml - wiki synthesis task variant
gemma_e2b_wiki:
  managed_server:
    threads: 8                    # Full parallelism for thorough synthesis
    ctx_size: 8192                # Full context needed for nuance
    extra_args: 
      - --reasoning: "on"         # ENABLE reasoning (off by default)
      - --reasoning-budget: 1000  # BOUND to prevent 180s+ hangs
      - --reasoning-format: standard
  default_params:
    temperature: 0.3              # Some creativity, not deterministic
    max_tokens: 2048              # Longer responses for synthesis
    timeout_seconds: 300          # Generous timeout for reasoning time
```

**Expected Gains:**
- Better character relationship inference
- More nuanced topic synthesis
- Reasoning visible in output (debugging + transparency)

**Risk Level:** Medium — reasoning can still timeout if budget is too high

**Testing for Bounded Reasoning:**
- Benchmark wiki synthesis latency on 10-20 event batches
- Measure `reasoning_content` token usage vs budget
- Confirm no 180s timeouts even with budget=1000
- Run `test_018_llm_wiki_synthesis.py` (if exists)

---

### Scenario 3: Multi-Concurrent Extraction (Throughput Optimization)

**Goal:** Handle 5+ concurrent extraction jobs without queue backup

**Changes:**
```yaml
gemma_e2b_extraction:
  managed_server:
    batch_size: 64                # Process larger batches
    threads: 12                   # Higher parallelism
    ctx_size: 4096                # Same as Scenario 1
    extra_args: [--reasoning, off, --reasoning-budget, 0, --reasoning-format, none, --mlock]
  default_params:
    temperature: 0.0
    max_tokens: 256
    timeout_seconds: 120          # Slightly higher for batch contention
```

**Expected Gains:**
- ~30-40% throughput improvement if CPU-bound (tokens/second across parallel jobs)
- Individual job latency might increase slightly (batching overhead)
- `--mlock` prevents model from being paged to disk under memory pressure

**Risk Level:** Medium — requires CPU availability; can increase latency under load

**Testing:**
- Run 5+ extraction jobs simultaneously via job queue
- Monitor throughput (jobs/second) and individual latencies
- Check CPU utilization (target: 70-85% for sustainable workload)

---

### Scenario 4: Memory-Constrained Deployment (Size Optimization)

**Goal:** Reduce memory footprint and startup time (e.g., for CI/CD or smaller instances)

**Changes:**
```yaml
gemma_e2b_extraction:
  managed_server:
    ctx_size: 2048                # 1/4 default context
    threads: 2                    # Low CPU footprint
    n_gpu_layers: 0               # CPU-only (already true, explicit)
  default_params:
    max_tokens: 128               # Shorter responses
    timeout_seconds: 120
```

**Expected Gains:**
- ~50-60% memory reduction
- 2-3x faster startup (smaller model to load)
- Lower CPU baseline

**Tradeoff:**
- ~5-10% accuracy loss on complex narratives (C4-C5)
- Narrative length capped at ~500 tokens
- max_tokens=128 might truncate responses on edge cases

**Risk Level:** High — accuracy visible degradation

---

## Implementation Priority

### Phase 1: Safe Wins (No risk)
1. **Scenario 1 (Faster Extraction)**
   - Implement: `ctx_size: 4096`,  `max_tokens: 256` for extraction
   - Test: Full regression suite
   - Expected: 15-20% latency gain, zero accuracy loss

### Phase 2: Quality Enhancement (Medium risk)
2. **Scenario 2 (Wiki Synthesis with Reasoning)**
   - Implement: Separate model config for wiki tasks; enable reasoning with `budget=1000`
   - Test: Wiki synthesis benchmarks; monitor timeout rate
   - Expected: Better synthesis quality, ~5-10% latency increase (acceptable for async tasks)

### Phase 3: Throughput (If needed)
3. **Scenario 3 (Concurrent Extraction)**
   - Implement: `batch_size=64`, `threads=12`, `--mlock`
   - Test: Multi-job queue stress tests
   - Condition: Only if extraction queue backup observed

### Phase 4: Edge Cases (Defer)
4. **Scenario 4 (Memory Constraints)**
   - Implement: Only for specific CI/CD or resource-constrained environments
   - Test: Full regression suite + accuracy benchmarks
   - Condition: Only if memory or startup time becomes a problem

---

## Testing Strategy

### Regression Suite
```bash
# Existing tests that must pass
pytest tests/test_033_llm_service.py         # Provider contracts
pytest tests/test_007_job_queue.py           # Job queue state machine
pytest tests/test_008_robust_capture_ux.py   # UI contracts
pytest tests/test_015_actor_curation.py      # Curation flow
```

### Benchmark Suite
```bash
# To measure tuning impact
python scripts/extraction_complexity_benchmark.py  # Latency + accuracy (C1-C5)
# (wiki synthesis benchmarks if they exist)
```

### Load Tests
```bash
# For concurrent extraction scenarios
# Launch 5+ extraction jobs simultaneously via job queue
# Monitor: throughput (jobs/sec), latency distribution, CPU/mem usage
```

---

## Decision Checkpoints

**Before Scenario 1 → Implementation:**
- [ ] Confirm extraction narratives are typically <2K tokens (small context is safe)
- [ ] Run extraction benchmark on C1-C3 (majority cases) with `ctx_size=4096`
- [ ] Verify no accuracy regression on test dataset

**Before Scenario 2 → Implementation:**
- [ ] Measure wiki synthesis latency with `reasoning_budget=1000` (target: <60s)
- [ ] Confirm no 180s timeout on realistic 50-event batches
- [ ] Decide: Is wiki synthesis currently enabled? (If not, defer)

**Before Scenario 3 → Implementation:**
- [ ] Identify: Are there real use cases with 5+ concurrent extractions? (If not, nice-to-have)
- [ ] Measure CPU utilization under current load
- [ ] Decide: Is throughput a real bottleneck?

**Before Scenario 4 → Implementation:**
- [ ] Measure current memory usage in production
- [ ] Identify: Is memory a constraint in target deployment?
- [ ] Defer unless explicitly required

---

## Related Documentation

- **Spec 033**: LLM Service provider architecture (managed vs subprocess)
- **GEMMA4_NOTES.md**: Reasoning-mode findings (why we disabled it)
- **service_models.yaml**: Current live configuration
- **llm/local_server_runtime.py**: Managed server lifecycle + extra_args support
- **scripts/extraction_complexity_benchmark.py**: Baseline metrics

---

## Notes

1. **Multiple Model Configs in One File:**  
   Current design uses single provider per model (e2b, e4b).  
   To support task-specific tuning (e.g., extraction vs wiki), either:
   - Option A: Create separate model entries (`gemma_e2b_extraction`, `gemma_e2b_wiki`)
   - Option B: Add `variants` dict per provider with task-specific overrides
   - Decision: Defer until Scenario 2 implementation

2. **Backward Compatibility:**  
   All tuning changes should be backward-compatible (no API changes).  
   Existing extraction/curation flows continue unchanged.

3. **Observability:**  
   Add metrics to `_latency_ms` tracking:
   - Reasoning token count (if reasoning enabled)
   - Actual tokens used vs `max_tokens` cap
   - Batch size (if batching enabled)

4. **Gemma4 Model Notes:**  
   - E2B (2.3B params, Q4_K_M): Faster, lower quality
   - E4B (4.5B params, UD-IQ2_M): Slower, higher quality
   - Choose per task based on latency vs quality needs
