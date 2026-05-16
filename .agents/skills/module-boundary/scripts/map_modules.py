#!/usr/bin/env python3
"""
map_modules.py — Discover Python packages and infer their public surfaces.

For each package (directory with __init__.py), extracts:
  - package_path: filesystem path relative to repo root
  - python_path: dotted import path
  - public_symbols: names exported via __all__, or top-level public names in __init__.py
  - entrypoint: a module.py or facade.py that likely defines the main class
  - entrypoint_classes: top-level class names in the entrypoint file
  - all_py_files: all .py files in the package

Read-only. Writes nothing. Outputs JSON to stdout.

Usage:
    python3 map_modules.py <repo_root> [--exclude dir1,dir2]
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


def extract_all_export(tree: ast.Module) -> list[str] | None:
    """Return __all__ list if present, else None."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        names = []
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.s, str):
                                names.append(elt.s)
                        return names
    return None


def extract_top_level_public_names(tree: ast.Module) -> list[str]:
    """Return top-level class/function definitions that don't start with _."""
    names = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                names.append(node.name)
    return names


def parse_file_safe(filepath: Path) -> ast.Module | None:
    try:
        source = filepath.read_text(encoding="utf-8", errors="ignore")
        return ast.parse(source, filename=str(filepath))
    except (SyntaxError, OSError):
        return None


def infer_public_symbols(init_path: Path) -> list[str]:
    tree = parse_file_safe(init_path)
    if tree is None:
        return []
    all_export = extract_all_export(tree)
    if all_export is not None:
        return all_export
    return extract_top_level_public_names(tree)


def find_entrypoint(package_dir: Path, pkg_basename: str) -> tuple[str | None, list[str]]:
    """Find the most likely public-surface entrypoint file and its classes."""
    candidates = list(ENTRYPOINT_NAMES) + [f"{pkg_basename}.py"]
    for candidate in candidates:
        path = package_dir / candidate
        if path.exists():
            tree = parse_file_safe(path)
            if tree is None:
                return str(path.name), []
            classes = [
                node.name for node in ast.iter_child_nodes(tree)
                if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
            ]
            return str(path.name), classes
    return None, []


def scan_packages(repo_root: Path, exclude: set[str]) -> list[dict]:
    packages = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in exclude and not d.startswith(".")
        )
        dp = Path(dirpath)
        if "__init__.py" not in filenames:
            continue

        rel = dp.relative_to(repo_root)
        python_path = str(rel).replace(os.sep, ".")

        init_file = dp / "__init__.py"
        public_symbols = infer_public_symbols(init_file)

        entrypoint_name, entrypoint_classes = find_entrypoint(dp, dp.name)
        # Merge entrypoint classes into public symbols (deduped)
        for cls in entrypoint_classes:
            if cls not in public_symbols:
                public_symbols.append(cls)

        all_py = sorted(
            str((dp / f).relative_to(repo_root))
            for f in filenames if f.endswith(".py")
        )

        packages.append({
            "package_path": str(rel),
            "python_path": python_path,
            "entrypoint": entrypoint_name,
            "entrypoint_classes": entrypoint_classes,
            "public_symbols": public_symbols,
            "all_py_files": all_py,
            "file_count": len(all_py),
        })

    return packages


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: map_modules.py <repo_root> [--exclude dir1,dir2]", file=sys.stderr)
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

    packages = scan_packages(repo_root, exclude)
    print(json.dumps(packages, indent=2))


if __name__ == "__main__":
    main()
