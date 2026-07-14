import urllib.request, json, base64, time

with open("/tmp/dash.png", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

payload = json.dumps({
    "model": "gemma_e2b_q4_local",
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": "Look at this screenshot carefully and answer these specific questions:\n\n1. Is this dark mode (black/dark background) or light mode (white/light background)?\n2. Is the text and content clearly readable, or is it too dark and hard to see?\n3. What is the background color of the main content area?\n4. Briefly describe the top-level layout - header, tabs, cards."}
            ]
        }
    ],
    "max_tokens": 500,
    "temperature": 0.0,
    "timeout_seconds": 300
}).encode()

req = urllib.request.Request(
    "http://localhost:8012/v1/chat/completions",
    data=payload,
    headers={"Content-Type": "application/json"}
)

t0 = time.time()
r = urllib.request.urlopen(req, timeout=300)
t1 = time.time()
resp = json.loads(r.read().decode())
content = resp["choices"][0]["message"]["content"]
usage = resp.get("usage", {})

print("TIME: %.1fs" % (t1-t0))
print("TOKENS: %s" % usage.get("total_tokens", "?"))
print()
print(content)
