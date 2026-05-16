#!/usr/bin/env python3
"""
deletion_test.py — Rank modules by their shallow/pass-through score.

For each package, computes:
  - fan_in:  number of distinct files that import from this package
  - fan_out: number of distinct external packages this package imports
  - file_count: number of .py files in the package
  - public_symbol_count: number of inferred public symbols
  - pass_through_ratio: fan_out / max(file_count, 1)
    High pass-through with low file count = likely shallow (re-exporting shell)
  - deletion_score: 0–10, higher = more likely to be shallow
    Formula: min(10, round((fan_in * pass_through_ratio) / max(public_symbol_count, 1) * 5))

Packages with deletion_score >= 6 are flagged as shallow candidates.

Read-only. Writes nothing. Outputs JSON to stdout (sorted by score descending).

Usage:
    python3 deletion_test.py <repo_root> [--exclude dir1,dir2]
"""

import ast
import json
import os
import sys
from pathlib import Path

DEFAULT_EXCLUDE = {
    "__pycache__", ".venv", "venv", "env", ".env",
    "node_modules", ".git", "build", "dist", ".tox",
    ".mypy_cache", ".pytest_cache", "htmlcov",
}

STDLIB_TOP = frozenset({
    "abc", "ast", "asyncio", "base64", "builtins", "calendar", "codecs",
    "collections", "concurrent", "contextlib", "copy", "csv", "dataclasses",
    "datetime", "decimal", "difflib", "email", "enum", "errno", "functools",
    "gc", "glob", "gzip", "hashlib", "html", "http", "importlib", "inspect",
    "io", "ipaddress", "itertools", "json", "logging", "math", "mimetypes",
    "multiprocessing", "operator", "os", "pathlib", "pickle", "platform",
    "pprint", "queue", "random", "re", "secrets", "shutil", "signal",
    "socket", "sqlite3", "ssl", "stat", "string", "struct", "subprocess",
    "sys", "tempfile", "threading", "time", "traceback", "types", "typing",
    "unicodedata", "unittest", "urllib", "uuid", "warnings", "weakref",
    "xml", "zipfile", "zlib", "_thread",
})

ENTRYPOINT_NAMES = {"module.py", "facade.py", "api.py", "interface.py", "public.py"}


def is_stdlib(name: str) -> bool:
    return name.split(".")[0] in STDLIB_TOP


def extract_top_public(filepath: Path) -> list[str]:
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8", errors="ignore"))
    except (SyntaxError, OSError):
        return []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        return [
                            e.s for e in node.value.elts
                            if isinstance(e, ast.Constant) and isinstance(e.s, str)
                        ]
    return [
        n.name for n in ast.iter_child_nodes(tree)
        if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and not n.name.startswith("_")
    ]


def get_external_imports(filepath: Path, package_python_path: str) -> set[str]:
    """Get all top-level external package names imported by this file."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8", errors="ignore"))
    except (SyntaxError, OSError):
        return set()

    externals: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if not is_stdlib(top):
                    externals.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0 or not node.module:
                continue
            if node.module.startswith(package_python_path):
                continue
            top = node.module.split(".")[0]
            if not is_stdlib(top):
                externals.add(top)
    return externals


def build_module_metrics(repo_root: Path, exclude: set[str]) -> list[dict]:
    # Step 1: gather all packages
    packages: dict[str, dict] = {}  # python_path -> info
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = sorted(
            d for d in dirnames if d not in exclude and not d.startswith(".")
        )
        dp = Path(dirpath)
        if "__init__.py" not in filenames:
            continue
        rel = dp.relative_to(repo_root)
        python_path = str(rel).replace(os.sep, ".")
        py_files = [dp / f for f in filenames if f.endswith(".py")]

        # Infer public symbols
        public: list[str] = []
        init_syms = extract_top_public(dp / "__init__.py")
        public.extend(init_syms)
        for ep_name in list(ENTRYPOINT_NAMES) + [f"{dp.name}.py"]:
            ep_path = dp / ep_name
            if ep_path.exists():
                for s in extract_top_public(ep_path):
                    if s not in public:
                        public.append(s)
                break

        # fan_out: external packages imported by any file in this package
        fan_out_pkgs: set[str] = set()
        for py_file in py_files:
            fan_out_pkgs |= get_external_imports(py_file, python_path)
        # Remove own package
        fan_out_pkgs.discard(python_path.split(".")[0])

        packages[python_path] = {
            "package_path": str(rel),
            "python_path": python_path,
            "file_count": len(py_files),
            "public_symbol_count": len(public),
            "public_symbols": public,
            "fan_out": len(fan_out_pkgs),
            "fan_out_packages": sorted(fan_out_pkgs),
            "fan_in": 0,  # computed below
        }

    # Step 2: compute fan_in by scanning all imports in the full repo
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = sorted(
            d for d in dirnames if d not in exclude and not d.startswith(".")
        )
        dp = Path(dirpath)
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            fpath = dp / fname
            try:
                tree = ast.parse(fpath.read_text(encoding="utf-8", errors="ignore"))
            except (SyntaxError, OSError):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.level > 0 or not node.module:
                        continue
                    mod = node.module
                    # Match any package or its submodule
                    for pkg_path in packages:
                        if mod == pkg_path or mod.startswith(pkg_path + "."):
                            # Only count imports from outside the package
                            rel_file = str(fpath.relative_to(repo_root)).replace(os.sep, ".")
                            in_pkg = rel_file.startswith(pkg_path)
                            if not in_pkg:
                                packages[pkg_path]["fan_in"] += 1
                            break

    # Step 3: compute scores
    results = []
    for info in packages.values():
        fan_in = info["fan_in"]
        fan_out = info["fan_out"]
        file_count = info["file_count"]
        public_count = max(info["public_symbol_count"], 1)

        pass_through_ratio = fan_out / max(file_count, 1)
        raw_score = (fan_in * pass_through_ratio) / public_count * 5
        deletion_score = min(10, round(raw_score))

        results.append({
            **info,
            "pass_through_ratio": round(pass_through_ratio, 3),
            "deletion_score": deletion_score,
            "shallow_candidate": deletion_score >= 6,
            "seam_type": "real" if fan_in >= 2 else "hypothetical",
        })

    results.sort(key=lambda x: x["deletion_score"], reverse=True)
    return results


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: deletion_test.py <repo_root> [--exclude dir1,dir2]", file=sys.stderr)
        sys.exit(1)

    repo_root = Path(sys.argv[1]).resolve()
    if not repo_root.is_dir():
        print(f"Error: {repo_root} is not a directory", file=sys.stderr)
        sys.exit(1)

    exclude = set(DEFAULT_EXCLUDE)
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--exclude" and i + 1 < len(sys.argv):
            exclude |= set(sys.argv[i + 1].split(","))
            i += 2
        else:
            i += 1

    metrics = build_module_metrics(repo_root, exclude)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
