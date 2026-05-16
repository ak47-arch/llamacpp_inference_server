#!/usr/bin/env python3
"""
pack_evidence.py — Orchestrate all analysis scripts into a single evidence pack.

Runs: map_modules, deletion_test, scan_inward_leaks, scan_outward_leaks,
and enumerate_callers for each candidate module, then writes a combined
JSON evidence file to a temp path.

The temp file path is printed to stdout so the calling agent can read it.

IMPORTANT: The agent MUST delete this temp file before publishing the report.
This script enforces that the file location is always under /tmp or the system
temp directory and never inside the repository.

Read-only with respect to the codebase. Creates one temporary file only.
Never writes inside the repo.

Usage:
    python3 pack_evidence.py <repo_root> [--focus pkg/path1,pkg/path2] [--exclude dir1,dir2]

    --focus: comma-separated relative package paths to deep-scan
             (if omitted, all packages with deletion_score >= 4 and fan_in >= 1 are included)
"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

DEFAULT_EXCLUDE = {"__pycache__", ".venv", "venv", "env", ".env",
                   "node_modules", ".git", "build", "dist", ".tox",
                   ".mypy_cache", ".pytest_cache", "htmlcov"}


def run_script(script_name: str, args: list[str]) -> dict | list | None:
    script_path = SCRIPT_DIR / script_name
    cmd = [sys.executable, str(script_path)] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip(), "script": script_name}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "script": script_name}
    except json.JSONDecodeError as e:
        return {"error": f"json_decode: {e}", "script": script_name}
    except Exception as e:
        return {"error": str(e), "script": script_name}


def pick_candidate_packages(
    modules: list[dict],
    deletion_scores: list[dict],
    focus_paths: list[str] | None,
) -> list[dict]:
    """Select packages to deep-scan."""
    if focus_paths:
        focus_set = set(focus_paths)
        return [m for m in modules if m["package_path"] in focus_set]

    # Auto-select: packages with real seams (fan_in >= 2) or moderate deletion scores
    score_map = {d["package_path"]: d for d in (deletion_scores or [])}
    candidates = []
    for m in modules:
        pkg_path = m["package_path"]
        score_info = score_map.get(pkg_path, {})
        fan_in = score_info.get("fan_in", 0)
        deletion_score = score_info.get("deletion_score", 0)
        # Include if: has callers AND (has an entrypoint OR non-trivial file count)
        if fan_in >= 1 and (m.get("entrypoint") or m.get("file_count", 0) >= 2):
            candidates.append({**m, **score_info})

    return candidates


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: pack_evidence.py <repo_root> [--focus pkg1,pkg2] [--exclude dir1,dir2]",
              file=sys.stderr)
        sys.exit(1)

    repo_root = Path(sys.argv[1]).resolve()
    if not repo_root.is_dir():
        print(f"Error: {repo_root} is not a directory", file=sys.stderr)
        sys.exit(1)

    focus_paths: list[str] | None = None
    extra_excludes: list[str] = []
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--focus" and i + 1 < len(sys.argv):
            focus_paths = [p.strip() for p in sys.argv[i + 1].split(",") if p.strip()]
            i += 2
        elif sys.argv[i] == "--exclude" and i + 1 < len(sys.argv):
            extra_excludes = sys.argv[i + 1].split(",")
            i += 2
        else:
            i += 1

    exclude_arg = ",".join(DEFAULT_EXCLUDE | set(extra_excludes))
    repo_str = str(repo_root)

    evidence: dict = {
        "meta": {
            "repo_root": repo_str,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "focus": focus_paths or "auto",
            "note": "AGENT: delete this temp file before publishing the report",
        },
    }

    print("[pack_evidence] Discovering modules...", file=sys.stderr)
    modules = run_script("map_modules.py", [repo_str, "--exclude", exclude_arg])
    evidence["modules"] = modules

    print("[pack_evidence] Running deletion test...", file=sys.stderr)
    deletion_scores = run_script("deletion_test.py", [repo_str, "--exclude", exclude_arg])
    evidence["deletion_scores"] = deletion_scores

    if not isinstance(modules, list) or not isinstance(deletion_scores, list):
        evidence["error"] = "module discovery or deletion test failed — check stderr"
        _write_and_exit(evidence)
        return

    candidates = pick_candidate_packages(modules, deletion_scores, focus_paths)
    evidence["candidate_packages"] = [c["package_path"] for c in candidates]

    print(f"[pack_evidence] Deep-scanning {len(candidates)} candidate packages...", file=sys.stderr)

    per_package: dict[str, dict] = {}
    for pkg in candidates:
        pkg_path = pkg["package_path"]
        print(f"  → {pkg_path}", file=sys.stderr)
        pkg_evidence: dict = {}

        pkg_evidence["inward_leaks"] = run_script(
            "scan_inward_leaks.py", [repo_str, pkg_path]
        )
        pkg_evidence["outward_leaks"] = run_script(
            "scan_outward_leaks.py", [repo_str, pkg_path]
        )
        pkg_evidence["callers"] = run_script(
            "enumerate_callers.py", [repo_str, pkg_path]
        )

        per_package[pkg_path] = pkg_evidence

    evidence["per_package"] = per_package

    _write_and_exit(evidence)


def _write_and_exit(evidence: dict) -> None:
    # Write to system temp — never inside the repo
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    tmp_fd, tmp_path = tempfile.mkstemp(
        prefix=f"mb_evidence_{timestamp}_",
        suffix=".json",
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(evidence, f, indent=2)
    except Exception as e:
        print(f"Error writing evidence file: {e}", file=sys.stderr)
        sys.exit(1)

    # The path (not the contents) goes to stdout so the agent can read it
    print(tmp_path)


if __name__ == "__main__":
    main()
