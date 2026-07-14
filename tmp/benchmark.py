import urllib.request, json, base64, time, sys

def do_inference(image_path, prompt_text, max_tokens=600, timeout_sec=600):
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    payload = json.dumps({
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": prompt_text}
                ]
            }
        ],
        "max_tokens": max_tokens,
        "temperature": 0.0
    }).encode()

    req = urllib.request.Request(
        "http://127.0.0.1:18012/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    t0 = time.time()
    r = urllib.request.urlopen(req, timeout=timeout_sec)
    t1 = time.time()
    resp = json.loads(r.read().decode())
    return t1 - t0, resp

# Run benchmark with screenshot
print("=== BENCHMARK: -t 0 (auto-detect threads) ===")
total_time, resp = do_inference(
    "/tmp/dash.png",
    "What do you see in this screenshot? List all headings, cards, numbers, metrics, tables, buttons visible.",
    max_tokens=600,
    timeout_sec=600
)

content = resp["choices"][0]["message"]["content"]
usage = resp.get("usage", {})
timings = resp.get("timings", {})

print("TOTAL_TIME: %.2f" % total_time)
print("PROMPT_TOKENS: %s" % usage.get("prompt_tokens", "?"))
print("COMPLETION_TOKENS: %s" % usage.get("completion_tokens", "?"))
print("TOTAL_TOKENS: %s" % usage.get("total_tokens", "?"))
print("PROMPT_MS: %s" % timings.get("prompt_ms", "?"))
print("PREDICTED_MS: %s" % timings.get("predicted_ms", "?"))
print("PROMPT_PER_TOKEN_MS: %s" % timings.get("prompt_per_token_ms", "?"))
print("PREDICTED_PER_TOKEN_MS: %s" % timings.get("predicted_per_token_ms", "?"))
print("PROMPT_PER_SECOND: %s" % timings.get("prompt_per_second", "?"))
print("PREDICTED_PER_SECOND: %s" % timings.get("predicted_per_second", "?"))
print("PROMPT_N: %s" % timings.get("prompt_n", "?"))
print("PREDICTED_N: %s" % timings.get("predicted_n", "?"))
print()
print("=== RESPONSE ===")
print(content)
print("=== END ===")