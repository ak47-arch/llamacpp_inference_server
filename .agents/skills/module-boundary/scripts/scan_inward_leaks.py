#!/usr/bin/env python3
"""
scan_inward_leaks.py — Find callers outside a package that bypass its public surface.

For a given package path, scans all files OUTSIDE the package for imports that
reach into internal submodules rather than the package's inferred public surface.

Produces a JSON list of findings, each with:
  - file: the importing file (relative to repo root)
  - line: line number
  - import_statement: what was imported
  - imported_module: the dotted module path imported
  - symbols: specific symbols imported (if any)
  - verdict: "BREACH" | "CLEAN" | "REVIEW"
  - reason: explanation

Read-only. Writes nothing. Outputs JSON to stdout.

Usage:
    python3 scan_inward_leaks.py <repo_root> <package_rel_path>
    python3 scan_inward_leaks.py <repo_root> <package_rel_path> --public SymA,SymB

    package_rel_path: relative path to the package, e.g. "myapp/pipeline/wiki"
    --public: comma-separated list of known public symbols (overrides inference)
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

ENTRYPOINT_NAMES = {"module.py", "facade.py", "api.py", "interface.py", "public.py"}


def infer_public_symbols(package_dir: Path) -> list[str]:
    """Infer public symbols from __init__.py or entrypoint file."""
    symbols: list[str] = []

    # Check __init__.py
    init_path = package_dir / "__init__.py"
    if init_path.exists():
        symbols.extend(_extract_symbols(init_path))

    # Check entrypoint files
    candidates = list(ENTRYPOINT_NAMES) + [f"{package_dir.name}.py"]
    for cname in candidates:
        ep = package_dir / cname
        if ep.exists():
            for s in _extract_symbols(ep):
                if s not in symbols:
                    symbols.append(s)
            break  # only the first match

    return symbols


def _extract_symbols(filepath: Path) -> list[str]:
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8", errors="ignore"))
    except (SyntaxError, OSError):
        return []

    # Prefer __all__
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        return [
                            e.s for e in node.value.elts
                            if isinstance(e, ast.Constant) and isinstance(e.s, str)
                        ]

    # Fall back to top-level public class/function names
    return [
        n.name for n in ast.iter_child_nodes(tree)
        if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and not n.name.startswith("_")
    ]


def package_python_path(repo_root: Path, package_dir: Path) -> str:
    return str(package_dir.relative_to(repo_root)).replace(os.sep, ".")


def scan_file_for_inward_leaks(
    filepath: Path,
    repo_root: Path,
    pkg_dir: Path,
    pkg_python_path: str,
    public_symbols: list[str],
) -> list[dict]:
    findings = []
    try:
        source = filepath.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, OSError):
        return []

    rel_file = str(filepath.relative_to(repo_root))

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module is None or node.level > 0:
            continue

        mod = node.module
        # Check if this import touches our package
        if not (mod == pkg_python_path or mod.startswith(pkg_python_path + ".")):
            continue

        symbols = [a.name for a in node.names]
        import_stmt = "from {} import {}".format(mod, ", ".join(symbols))

        if mod == pkg_python_path:
            # Importing from the package root — check if these are public symbols
            non_public = [s for s in symbols if s not in public_symbols and s != "*"]
            if not non_public:
                findings.append({
                    "file": rel_file,
                    "line": node.lineno,
                    "import_statement": import_stmt,
                    "imported_module": mod,
                    "symbols": symbols,
                    "verdict": "CLEAN",
                    "reason": "imports from package root; all symbols in inferred public surface",
                })
            else:
                findings.append({
                    "file": rel_file,
                    "line": node.lineno,
                    "import_statement": import_stmt,
                    "imported_module": mod,
                    "symbols": symbols,
                    "verdict": "REVIEW",
                    "reason": f"symbols not in inferred public surface: {non_public} — verify manually",
                })
        else:
            # Importing a submodule directly — this is always an inward leak
            # unless the submodule name matches the package name (module.py pattern)
            submodule = mod[len(pkg_python_path) + 1:].split(".")[0]
            is_entrypoint = (submodule + ".py") in {e for e in ENTRYPOINT_NAMES} or submodule == pkg_dir.name
            if is_entrypoint and all(s in public_symbols for s in symbols):
                findings.append({
                    "file": rel_file,
                    "line": node.lineno,
                    "import_statement": import_stmt,
                    "imported_module": mod,
                    "symbols": symbols,
                    "verdict": "CLEAN",
                    "reason": "imports from entrypoint submodule, symbols are public",
                })
            else:
                findings.append({
                    "file": rel_file,
                    "line": node.lineno,
                    "import_statement": import_stmt,
                    "imported_module": mod,
                    "symbols": symbols,
                    "verdict": "BREACH",
                    "reason": f"imports internal submodule '{submodule}' directly, bypassing package seam",
                })

    return findings


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: scan_inward_leaks.py <repo_root> <package_rel_path> [--public Sym1,Sym2]",
              file=sys.stderr)
        sys.exit(1)

    repo_root = Path(sys.argv[1]).resolve()
    pkg_rel = sys.argv[2].rstrip("/").rstrip(os.sep)
    pkg_dir = (repo_root / pkg_rel).resolve()

    if not pkg_dir.is_dir():
        print(f"Error: package directory does not exist: {pkg_dir}", file=sys.stderr)
        sys.exit(1)

    # Parse --public override
    public_override: list[str] | None = None
    i = 3
    while i < len(sys.argv):
        if sys.argv[i] == "--public" and i + 1 < len(sys.argv):
            public_override = sys.argv[i + 1].split(",")
            i += 2
        else:
            i += 1

    pkg_python_path = package_python_path(repo_root, pkg_dir)
    public_symbols = public_override if public_override is not None else infer_public_symbols(pkg_dir)

    exclude = set(DEFAULT_EXCLUDE)
    all_findings: list[dict] = []

    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in exclude and not d.startswith(".")
        )
        dp = Path(dirpath)
        # Skip the package itself
        try:
            dp.relative_to(pkg_dir)
            continue
        except ValueError:
            pass

        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            fpath = dp / fname
            findings = scan_file_for_inward_leaks(
                fpath, repo_root, pkg_dir, pkg_python_path, public_symbols
            )
            all_findings.extend(findings)

    result = {
        "package": pkg_rel,
        "python_path": pkg_python_path,
        "inferred_public_symbols": public_symbols,
        "findings": all_findings,
        "breach_count": sum(1 for f in all_findings if f["verdict"] == "BREACH"),
        "review_count": sum(1 for f in all_findings if f["verdict"] == "REVIEW"),
        "clean_count": sum(1 for f in all_findings if f["verdict"] == "CLEAN"),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
