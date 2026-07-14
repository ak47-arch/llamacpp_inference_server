import yaml

with open("/app/llm/service_models.yaml") as f:
    config = yaml.safe_load(f)

for p in config.get("providers", []):
    if p.get("id") == "gemma_e2b_q4_local":
        conn = p.get("connection", {})
        ms = conn.get("managed_server", {})
        if "threads" in ms:
            print(f"Old threads: {ms["threads"]}")
            ms["threads"] = 0
            print(f"New threads: {ms["threads"]}")

with open("/app/llm/service_models.yaml", "w") as f:
    yaml.dump(config, f, default_flow_style=False)

print("Config updated")
