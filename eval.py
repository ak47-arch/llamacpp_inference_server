"""Run simple model eval comparisons across provider IDs.

Usage:
    python -m llm.eval --role extraction --cases llm/eval_cases.jsonl

Case format (JSONL):
    {"input": "narrative text", "system": "optional system prompt"}

If --cases is omitted, a built-in default case set is used so eval runs
non-interactively.
"""

import argparse
import json
import os
import statistics
import time

from llm.router import ProviderRouter
from llm.provider_base import ProviderTimeoutError, ProviderUnavailableError


DEFAULT_CASES = [
    {
        "input": "Date: 2026-04-19 18:30\nNarrative: Met Rahul at the station and discussed next week follow-up plan.\nJSON:",
        "system": "Extract one event as JSON only.",
    },
    {
        "input": "Date: 2026-04-19 11:15\nNarrative: Spoke with Aman over phone about timeline risks and agreed to reconvene Friday.\nJSON:",
        "system": "Extract one event as JSON only.",
    },
    {
        "input": "Date: 2026-04-19 09:50\nNarrative: Observed Nikhil finalize the vendor handoff while I documented open blockers.\nJSON:",
        "system": "Extract one event as JSON only.",
    },
]


def _load_cases(path: str) -> list:
    cases = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "input" not in row:
                raise ValueError("Each eval case must contain 'input'")
            cases.append(row)
    return cases


def load_cases_or_default(path: str | None) -> list:
    if not path:
        return list(DEFAULT_CASES)
    return _load_cases(path)


def _run_one(provider, case: dict):
    prompt = case["input"]
    system = case.get("system", "")
    start = time.monotonic()
    result = provider.complete(prompt=prompt, system=system)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return {
        "latency_ms": elapsed_ms,
        "tokens_used": result.tokens_used,
        "output_len": len(result.text),
    }


def main():
    parser = argparse.ArgumentParser(description="Compare providers for a pipeline role.")
    parser.add_argument("--role", default="extraction", help="Pipeline role (e.g., extraction)")
    parser.add_argument("--cases", default="", help="Path to JSONL eval cases")
    parser.add_argument(
        "--models",
        default="",
        help="Comma-separated provider IDs. If omitted, uses role's routed provider only.",
    )
    parser.add_argument(
        "--config",
        default=os.path.join(os.path.dirname(os.path.dirname(__file__)), "models.yaml"),
        help="Path to models.yaml",
    )
    args = parser.parse_args()

    router = ProviderRouter(args.config)
    cases = load_cases_or_default(args.cases)

    if args.models.strip():
        provider_ids = [m.strip() for m in args.models.split(",") if m.strip()]
    else:
        routed = router.routing().get(args.role)
        if not routed:
            raise KeyError(f"No provider mapped for role '{args.role}'")
        provider_ids = [routed]

    print(f"role={args.role} cases={len(cases)}")
    print("provider_id | success | fail | p50_ms | p95_ms | avg_len")
    print("-" * 70)

    for provider_id in provider_ids:
        provider = router._providers.get(provider_id)
        if not provider:
            print(f"{provider_id} | 0 | {len(cases)} | - | - | -")
            continue

        latencies = []
        out_lens = []
        fail = 0

        for case in cases:
            try:
                row = _run_one(provider, case)
                latencies.append(row["latency_ms"])
                out_lens.append(row["output_len"])
            except (ProviderTimeoutError, ProviderUnavailableError, Exception):
                fail += 1

        success = len(latencies)
        if success:
            p50 = int(statistics.median(latencies))
            p95 = int(sorted(latencies)[max(0, int(success * 0.95) - 1)])
            avg_len = int(statistics.mean(out_lens))
            print(f"{provider_id} | {success} | {fail} | {p50} | {p95} | {avg_len}")
        else:
            print(f"{provider_id} | 0 | {fail} | - | - | -")


if __name__ == "__main__":
    main()
