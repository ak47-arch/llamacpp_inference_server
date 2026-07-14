import urllib.request, json, base64

with open("/tmp/dashboard.png", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

payload = json.dumps({
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": "What do you see in this screenshot? Describe the dashboard layout, all visible cards, numbers, metrics, headings and data shown."}
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
try:
    r = urllib.request.urlopen(req, timeout=300)
    resp = json.loads(r.read().decode())
    content = resp["choices"][0]["message"]["content"]
    print(content)
    usage = resp.get("usage", {})
    print("\n--- Usage:", json.dumps(usage, indent=2))
except Exception as e:
    print(f"Error: {e}")
    if hasattr(e, "read"):
        print(e.read().decode()[:500])
