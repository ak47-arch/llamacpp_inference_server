# Gemma 4 Models — Research & Benchmark Notes

**Date:** April 17, 2026  
**Hardware:** x86_64 Linux, 8-core CPU, ~13GB RAM, no GPU (CPU-only inference)  
**Runtime:** llama.cpp b8763 (ff5ef8278), extracted to `~/llama-cpp/llama-b8763/`

---

## 1. Gemma 4 Model Family

Google's Gemma 4 family (smallest → largest):

| Model | Effective Params | Total Params | Notes |
|-------|-----------------|--------------|-------|
| **E2B** | 2.3B | 5.1B | Smallest, on-device target |
| **E4B** | 4.5B | 8B | Edge, better quality |
| 26B-A4B | 3.8B active | 26B total | MoE architecture |
| 31B | 31B | 31B | Largest, cloud/server |

The E-series models ("Edge") are designed for on-device use. E2B is the absolute smallest in the Gemma 4 family.

---

## 2. Downloaded Models

### E2B — IQ2_M
- **File:** `google_gemma-4-E2B-it-IQ2_M.gguf`
- **Size:** 2.5GB
- **Source:** `bartowski/google_gemma-4-E2B-it-GGUF` (HuggingFace)
- **Quantization:** IQ2_M — irregular 2-bit with multipliers (very aggressive compression)

### E2B — Q4_K_M
- **File:** `google_gemma-4-E2B-it-Q4_K_M.gguf`
- **Size:** 3.3GB
- **Source:** `bartowski/google_gemma-4-E2B-it-GGUF` (HuggingFace)
- **Quantization:** Q4_K_M — 4-bit groups with K-means clustering (standard quality)

### E4B — UD-IQ2_M
- **File:** `gemma-4-E4B-it-UD-IQ2_M.gguf`
- **Size:** 3.3GB
- **Source:** `unsloth/gemma-4-E4B-it-GGUF` (HuggingFace)
- **Quantization:** UD-IQ2_M — unsloth dynamic IQ2_M (slightly better than standard IQ2_M)

### E4B — Q4_K_M
- **File:** `google_gemma-4-E4B-it-Q4_K_M.gguf`
- **Size:** 5.1GB
- **Source:** `bartowski/google_gemma-4-E4B-it-GGUF` (HuggingFace)
- **Quantization:** Q4_K_M — 4-bit groups with K-means clustering (standard quality)

---

## 3. Benchmark Results (CPU-Only, 8 Threads, `llama-cli`)

### Generation Speed (tokens/second)

| Model | Quant | Size | Prompt t/s | Generation t/s |
|-------|-------|------|-----------|----------------|
| E2B | IQ2_M | 2.5GB | 13.6 | 7.3 |
| **E2B** | **Q4_K_M** | **3.3GB** | **26.4** | **8.8** |
| E4B | UD-IQ2_M | 3.3GB | 6.2 | 3.0 |
| E4B | Q4_K_M | 5.1GB | 18.26 | 3.28 |

### Key Observations

- **Q4_K_M is faster than IQ2_M despite being larger.** IQ2_M uses irregular quantization blocks that thrash CPU caches; Q4_K_M uses 4-bit blocks that align with SIMD/AVX instructions on x86 CPUs. This is a known property of llama.cpp on CPU-only hardware.
- **E2B > E4B in speed** because it has ~half the effective parameters (2.3B vs 4.5B). E4B takes 3x+ longer on CPU.
- **E2B Q4_K_M is the best model for this hardware** — fastest generation AND highest quality quant of the three.
- **E4B Q4_K_M is the best E4B variant currently tested** — nearly 3x faster prompt processing than E4B UD-IQ2_M and modestly faster generation.
- **E4B Q4_K_M is a viable quality-first extractor** when better schema fidelity matters more than raw throughput, but E2B Q4_K_M remains the speed leader.

### Real-World Latency Estimate (E2B Q4_K_M)

| Response Length | Estimated Wall-Clock Time |
|----------------|--------------------------|
| 50 tokens | ~6 seconds |
| 100 tokens | ~11 seconds |
| 200 tokens | ~23 seconds |
| 500 tokens | ~57 seconds |

---

## 4. llama.cpp Setup & Run Commands

### Installation
```
Binary: ~/llama-cpp/llama-b8763/
Version: b8763 (ff5ef8278), GNU 11.4.0, Linux x86_64
All .so libs co-located in same directory — must set LD_LIBRARY_PATH
```

### Standard Run Command
```bash
cd ~/llama-cpp/llama-b8763
echo "Your prompt here" > /tmp/prompt.txt
timeout 120 bash -c "LD_LIBRARY_PATH=. ./llama-cli \
  -m /home/anupam/Desktop/forthechemicals/gemma/<model>.gguf \
  -ngl 0 \        # no GPU offload (CPU-only)
  -t 8 \          # 8 threads (matches CPU cores)
  -n 128 \        # max tokens to generate
  -f /tmp/prompt.txt"  # prompt from file (avoids stdin interception)
```

**Critical:** Always use `-f <file>` not pipe/stdin when calling non-interactively. Using `printf ... |` in llama-cli conversation mode (`-cnv`) causes stdin interception issues where subsequent shell input gets consumed as chat.

### Smoke Test Command
```bash
cd ~/llama-cpp/llama-b8763
LD_LIBRARY_PATH=. ./llama-bench \
  -m <model>.gguf \
  -ngl 0 -t 8 -p 64 -n 32 -r 1
```

### Piped Non-Interactive (for scripting)
```bash
printf "Your prompt\n/exit\n" | bash -c "LD_LIBRARY_PATH=. ./llama-cli -m <model>.gguf -ngl 0 -t 8 -c 1024 -n 64 -cnv"
```

---

## 5. Smoke Test Results

Both models responded correctly to `Reply with exactly: E2B_OK` / `Reply with exactly: E4B_OK`.

- **E2B:** Replied `E2B_OK` ✅
- **E4B:** Replied `E4B_OK` ✅

---

## 6. On-Device / Edge Deployment Assessment

### CPU (desktop, 8 cores)
- E2B Q4_K_M: 8.8 t/s — viable for batch/async ops
- E4B UD-IQ2_M: 3.0 t/s — slow, marginal for async
- E4B Q4_K_M: 3.28 t/s — still slow for interactive use, but the strongest E4B option tested so far

### Browser (WebGPU) — estimate
- WebGPU acceleration is browser/driver-dependent
- Old phones likely don't support WebGPU
- Even with WebGPU: expect 2–5x the desktop latency on phone hardware
- E2B at 8.8 t/s desktop → ~1–4 t/s browser on WebGPU-capable phone

### Old Android/iOS Phones (native app via llama.cpp)
- CPU-only: ~1–2 t/s (E2B), slower than desktop
- Memory constraint: E2B Q4_K_M needs ~3.5GB RAM — won't fit on <4GB RAM phones
- IQ2_M at 2.5GB is tighter but more viable for 4GB RAM devices
- Real-time per-frame analysis: **not feasible** even on desktop
- Async/batch (every 2–5 seconds): feasible but slow

### Conclusion
- Real-time inference: Use MediaPipe, MobileNet, or CNN models (not LLMs)
- Batch/async operations (labeling assist, dataset QA, coaching): **E2B Q4_K_M is the speed-first choice**
- Quality-first local extraction/parsing: **E4B Q4_K_M is the better E4B option**
- All current ForTheChemicals ML pipeline operations are batch/async → no real-time constraint

---

## 7. Quantization Reference

| Format | Bits | Size Est. (E2B) | Speed (CPU) | Quality |
|--------|------|-----------------|-------------|---------|
| IQ2_M | ~2.2 | 2.5GB | Medium (cache-unfriendly) | Lowest |
| Q4_K_M | 4 | 3.3GB | Fast (SIMD-friendly) | Good |
| Q5_K_M | 5 | ~4GB | Slightly slower | Better |
| Q8_0 | 8 | ~6GB | Slow | Near-lossless |
| F16 | 16 | ~10GB | Very slow | Lossless |

**Recommended for this hardware:** Q4_K_M (best speed/quality balance on x86 CPU)

---

## 8. HuggingFace Download Commands

```bash
# Activate project venv first
source /home/anupam/Desktop/forthechemicals/.venv/bin/activate

# E2B IQ2_M (downloaded)
python3 -c "from huggingface_hub import snapshot_download; snapshot_download('bartowski/google_gemma-4-E2B-it-GGUF', allow_patterns='*IQ2_M.gguf', local_dir='/home/anupam/Desktop/forthechemicals/gemma/')"

# E2B Q4_K_M (downloaded)
python3 -c "from huggingface_hub import snapshot_download; snapshot_download('bartowski/google_gemma-4-E2B-it-GGUF', allow_patterns='*Q4_K_M.gguf', local_dir='/home/anupam/Desktop/forthechemicals/gemma/')"

# E4B UD-IQ2_M (downloaded)
python3 -c "from huggingface_hub import snapshot_download; snapshot_download('unsloth/gemma-4-E4B-it-GGUF', allow_patterns='*UD-IQ2_M.gguf', local_dir='/home/anupam/Desktop/forthechemicals/gemma/')"

# E4B Q4_K_M (downloaded)
python3 -c "from huggingface_hub import snapshot_download; snapshot_download('bartowski/google_gemma-4-E4B-it-GGUF', allow_patterns='*Q4_K_M.gguf', local_dir='/home/anupam/Desktop/forthechemicals/gemma/')"
```

Note: `hf` CLI alias not available in this environment — use `huggingface_hub` Python API directly.

---

## 9. Lessons Learned / Gotchas

1. **Interactive mode stdin trap:** `llama-cli` in default mode reads stdin interactively. If you run it via subprocess without `capture_output=True` or without `-f <file>`, subsequent shell commands get swallowed as chat input.
2. **IQ2_M is slower than Q4_K_M on x86 CPU** — cache-unfriendly irregular quant blocks hurt CPU SIMD performance. Always test both before assuming smaller = faster.
3. **E4B is notably slower than E2B on CPU** — the effective parameter increase hits proportionally harder on CPU than GPU.
4. **llama-bench vs llama-cli:** For pure speed numbers, `llama-bench` is cleaner. `llama-cli` with `grep` on the status bar (Prompt/Generation t/s) works fine for quick comparisons.
5. **120s timeout is too short for heavy configs.** For `-n 128` on E2B Q4_K_M it's fine. For IQ2_M with thinking mode on complex prompts, it can exceed 120s.
6. **`-ngl 0` required** on this machine (no GPU). Omitting it won't break anything but is explicit.
7. **This llama.cpp build has Gemma chat-template quirks.** `llama-bench` is stable for throughput measurement, but `llama-cli` may need `-no-cnv` or other non-chat invocations to avoid template/runtime crashes.
