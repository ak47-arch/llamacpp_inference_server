#!/usr/bin/env python3
"""
enumerate_callers.py — List all direct callers of a package and which symbols they use.

For a given package path, finds every file outside the package that imports from it,
and records which symbols are used at each call site.

Read-only. Writes nothing. Outputs JSON to stdout.

Usage:
    python3 enumerate_callers.py <repo_root> <package_rel_path> [--symbol SymName]

    --symbol: focus on a specific exported symbol only
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


def package_python_path(repo_root: Path, pkg_dir: Path) -> str:
    return str(pkg_dir.relative_to(repo_root)).replace(os.sep, ".")


def find_callers(
    repo_root: Path,
    pkg_dir: Path,
    pkg_python_path: str,
    focus_symbol: str | None,
    exclude: set[str],
) -> list[dict]:
    callers: list[dict] = []

    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = sorted(
            d for d in dirnames if d not in exclude and not d.startswith(".")
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
            rel_file = str(fpath.relative_to(repo_root))

            try:
                source = fpath.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source, filename=str(fpath))
            except (SyntaxError, OSError):
                continue

            # Collect import lines for this package
            import_lines: list[dict] = []
            imported_names: set[str] = set()

            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                if node.module is None or node.level > 0:
                    continue
                mod = node.module
                if not (mod == pkg_python_path or mod.startswith(pkg_python_path + ".")):
                    continue

                syms = [a.name for a in node.names]
                if focus_symbol and focus_symbol not in syms:
                    continue

                import_stmt = "from {} import {}".format(mod, ", ".join(syms))
                import_lines.append({
                    "line": node.lineno,
                    "import_statement": import_stmt,
                    "sourced_from": mod,
                    "symbols": syms,
                })
                imported_names.update(syms)

            if not import_lines:
                continue

            # Find usages of imported symbols in the file
            usages: dict[str, list[int]] = {name: [] for name in imported_names}
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute):
                    # e.g. WikiModule.method()
                    if isinstance(node.value, ast.Name) and node.value.id in imported_names:
                        sym = node.value.id
                        ln = getattr(node, "lineno", None)
                        if ln and ln not in usages[sym]:
                            usages[sym].append(ln)
                elif isinstance(node, ast.Name):
                    if node.id in imported_names:
                        ln = getattr(node, "lineno", None)
                        if ln:
                            usages[node.id] = sorted(set(usages.get(node.id, []) + [ln]))

            callers.append({
                "file": rel_file,
                "imports": import_lines,
                "symbols_used": {k: sorted(set(v)) for k, v in usages.items() if v},
                "all_imported_symbols": sorted(imported_names),
            })

    return callers


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: enumerate_callers.py <repo_root> <package_rel_path> [--symbol SymName]",
              file=sys.stderr)
        sys.exit(1)

    repo_root = Path(sys.argv[1]).resolve()
    pkg_rel = sys.argv[2].rstrip("/").rstrip(os.sep)
    pkg_dir = (repo_root / pkg_rel).resolve()

    if not pkg_dir.is_dir():
        print(f"Error: package directory does not exist: {pkg_dir}", file=sys.stderr)
        sys.exit(1)

    focus_symbol: str | None = None
    i = 3
    while i < len(sys.argv):
        if sys.argv[i] == "--symbol" and i + 1 < len(sys.argv):
            focus_symbol = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    pkg_python_path_str = package_python_path(repo_root, pkg_dir)
    exclude = set(DEFAULT_EXCLUDE)

    callers = find_callers(repo_root, pkg_dir, pkg_python_path_str, focus_symbol, exclude)

    result = {
        "package": pkg_rel,
        "python_path": pkg_python_path_str,
        "focus_symbol": focus_symbol,
        "caller_count": len(callers),
        "callers": callers,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
