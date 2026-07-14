import urllib.request, json, base64, time, sys, os

with open("/tmp/dash.png", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

payload = json.dumps({
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": "What do you see in this screenshot? List all headings, cards, numbers, metrics, tables, buttons, and layout sections visible."}
            ]
        }
    ],
    "max_tokens": 800,
    "temperature": 0.0
}).encode()

req = urllib.request.Request(
    "http://127.0.0.1:18012/v1/chat/completions",
    data=payload,
    headers={"Content-Type": "application/json"}
)

t0 = time.time()
r = urllib.request.urlopen(req, timeout=280)
t1 = time.time()

resp = json.loads(r.read().decode())
content = resp["choices"][0]["message"]["content"]
usage = resp.get("usage", {})
timings = resp.get("timings", {})

print("TOTAL_TIME: %.2f" % (t1-t0))
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
print("===RESPONSE===")
print(content)
print("===END===")
