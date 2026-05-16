#!/usr/bin/env python3
"""
scan_outward_leaks.py — Find domain logic that has escaped a package's own seam.

Scans all Python files INSIDE a given package for absolute (non-relative, non-stdlib)
imports, then classifies each imported symbol as either:
  - infrastructure: generic, domain-agnostic abstraction (CLEAN)
  - domain logic: symbol likely belongs inside this module (BREACH or REVIEW)

Classification is heuristic — uses symbol naming patterns. The agent must make
the final judgment for borderline cases marked REVIEW.

Read-only. Writes nothing. Outputs JSON to stdout.

Usage:
    python3 scan_outward_leaks.py <repo_root> <package_rel_path>
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

# Stdlib top-level names
STDLIB_TOP = frozenset({
    "abc", "ast", "asyncio", "atexit", "base64", "binascii", "builtins",
    "calendar", "codecs", "collections", "concurrent", "contextlib",
    "contextvars", "copy", "csv", "dataclasses", "datetime", "decimal",
    "difflib", "dis", "email", "enum", "errno", "functools", "gc",
    "getopt", "getpass", "glob", "gzip", "hashlib", "heapq", "hmac",
    "html", "http", "importlib", "inspect", "io", "ipaddress", "itertools",
    "json", "logging", "lzma", "math", "mimetypes", "mmap", "multiprocessing",
    "operator", "os", "pathlib", "pickle", "platform", "pprint", "queue",
    "random", "re", "secrets", "shlex", "shutil", "signal", "socket",
    "sqlite3", "ssl", "stat", "statistics", "string", "struct", "subprocess",
    "sys", "tempfile", "threading", "time", "timeit", "traceback", "types",
    "typing", "unicodedata", "unittest", "urllib", "uuid", "warnings",
    "weakref", "xml", "zipfile", "zlib", "zoneinfo", "_thread",
    "collections_abc", "_collections_abc",
})

# Infrastructure symbol name patterns — these are almost always CLEAN
INFRA_PATTERNS = [
    "client", "Client", "connection", "Connection", "session", "Session",
    "router", "Router", "provider", "Provider", "adapter", "Adapter",
    "config", "Config", "settings", "Settings", "logger", "Logger",
    "middleware", "Middleware", "handler", "Handler", "registry", "Registry",
    "queue", "Queue", "worker", "Worker", "executor", "Executor",
    "cache", "Cache", "pool", "Pool", "lock", "Lock",
    "base", "Base", "abstract", "Abstract", "mixin", "Mixin",
    "exception", "Exception", "error", "Error",
    "schema", "Schema", "validator", "Validator",
    "serializer", "Serializer", "deserializer", "Deserializer",
    "encoder", "Encoder", "decoder", "Decoder",
    "request", "Request", "response", "Response",
]

# Well-known infrastructure package name prefixes
INFRA_PKG_PREFIXES = (
    "flask", "django", "fastapi", "starlette", "aiohttp",
    "sqlalchemy", "alembic", "psycopg", "pymongo", "redis",
    "celery", "kombu", "pydantic", "marshmallow",
    "boto3", "botocore", "google", "azure",
    "requests", "httpx", "aiohttp", "urllib3",
    "yaml", "toml", "dotenv",
    "pytest", "unittest", "mock",
    "openai", "anthropic", "cohere", "tiktoken",
    "numpy", "pandas", "scipy",
    "click", "typer", "argparse",
    "logging", "structlog", "loguru",
)


def is_stdlib(module_name: str) -> bool:
    return module_name.split(".")[0] in STDLIB_TOP


def is_likely_infrastructure(module: str, symbols: list[str]) -> tuple[bool, str]:
    """
    Return (is_infra, reason).
    If confidently infra: (True, reason)
    If confidently domain: (False, reason)
    """
    pkg_top = module.split(".")[0]

    # Known third-party infra packages
    if any(module.startswith(p) for p in INFRA_PKG_PREFIXES):
        return True, f"well-known infrastructure package '{pkg_top}'"

    # Module path contains infra indicators
    module_lower = module.lower()
    for pat in ("client", "provider", "adapter", "router", "config", "util", "helper",
                "common", "shared", "base", "abstract", "exception", "error",
                "schema", "validator", "serializer", "middleware"):
        if pat in module_lower:
            return True, f"module path contains infrastructure indicator '{pat}'"

    # Check each symbol name
    infra_syms = []
    domain_syms = []
    for sym in symbols:
        sym_lower = sym.lower()
        is_infra_sym = any(
            sym_lower == p.lower() or sym_lower.endswith(p.lower()) or sym_lower.startswith(p.lower())
            for p in INFRA_PATTERNS
        )
        if is_infra_sym:
            infra_syms.append(sym)
        else:
            domain_syms.append(sym)

    if domain_syms and not infra_syms:
        return False, f"symbols have no infrastructure naming pattern: {domain_syms}"
    if infra_syms and not domain_syms:
        return True, f"all symbols match infrastructure naming pattern: {infra_syms}"

    # Mixed or uncertain
    return False, f"mixed signals — domain symbols: {domain_syms}, infra symbols: {infra_syms} — REVIEW required"


def scan_package_for_outward_leaks(
    repo_root: Path,
    pkg_dir: Path,
    pkg_python_path: str,
    exclude: set[str],
) -> list[dict]:
    findings: list[dict] = []

    for dirpath, dirnames, filenames in os.walk(pkg_dir):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in exclude and not d.startswith(".")
        )
        dp = Path(dirpath)
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            fpath = dp / fname
            rel_file = str(fpath.relative_to(repo_root))

            try:
                source = fpath.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source, filename=str(fpath))
            except (SyntaxError, OSError):
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                if node.module is None or node.level > 0:
                    continue  # skip relative imports

                mod = node.module

                # Skip stdlib
                if is_stdlib(mod):
                    continue

                # Skip imports from within the same package
                if mod == pkg_python_path or mod.startswith(pkg_python_path + "."):
                    continue

                symbols = [a.name for a in node.names]
                import_stmt = "from {} import {}".format(mod, ", ".join(symbols))

                is_infra, reason = is_likely_infrastructure(mod, symbols)

                if is_infra:
                    verdict = "CLEAN"
                else:
                    # Check if any symbol looks domain-specific
                    # (we can't execute the code, so this is heuristic)
                    verdict = "REVIEW"  # Agent must make final call

                findings.append({
                    "file": rel_file,
                    "line": node.lineno,
                    "import_statement": import_stmt,
                    "external_module": mod,
                    "symbols": symbols,
                    "verdict": verdict,
                    "infrastructure": is_infra,
                    "reason": reason,
                })

    return findings


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: scan_outward_leaks.py <repo_root> <package_rel_path>", file=sys.stderr)
        sys.exit(1)

    repo_root = Path(sys.argv[1]).resolve()
    pkg_rel = sys.argv[2].rstrip("/").rstrip(os.sep)
    pkg_dir = (repo_root / pkg_rel).resolve()

    if not pkg_dir.is_dir():
        print(f"Error: package directory does not exist: {pkg_dir}", file=sys.stderr)
        sys.exit(1)

    pkg_python_path = str(pkg_dir.relative_to(repo_root)).replace(os.sep, ".")
    exclude = set(DEFAULT_EXCLUDE)

    findings = scan_package_for_outward_leaks(repo_root, pkg_dir, pkg_python_path, exclude)

    result = {
        "package": pkg_rel,
        "python_path": pkg_python_path,
        "findings": findings,
        "clean_count": sum(1 for f in findings if f["verdict"] == "CLEAN"),
        "review_count": sum(1 for f in findings if f["verdict"] == "REVIEW"),
        "note": "REVIEW items require agent judgment — check symbol definition location with grep",
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
