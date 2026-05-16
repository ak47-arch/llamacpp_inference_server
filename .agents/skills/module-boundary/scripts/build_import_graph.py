#!/usr/bin/env python3
"""
build_import_graph.py — Build forward and reverse import adjacency for all Python files.

Forward graph:  file -> list of {module, symbols, line, is_relative, is_stdlib}
Reverse graph:  top-level module name -> list of files that import it

Read-only. Writes nothing. Outputs JSON to stdout.

Usage:
    python3 build_import_graph.py <repo_root> [--exclude dir1,dir2]
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

# Conservative stdlib top-level names (Python 3.9+)
STDLIB_TOP = frozenset({
    "abc", "ast", "asyncio", "atexit", "base64", "binascii", "builtins",
    "calendar", "cgi", "cmath", "cmd", "code", "codecs", "collections",
    "colorsys", "compileall", "concurrent", "configparser", "contextlib",
    "contextvars", "copy", "copyreg", "csv", "ctypes", "curses", "dataclasses",
    "datetime", "dbm", "decimal", "difflib", "dis", "distutils", "email",
    "encodings", "enum", "errno", "faulthandler", "fcntl", "filecmp",
    "fileinput", "fnmatch", "fractions", "ftplib", "functools", "gc",
    "getopt", "getpass", "gettext", "glob", "grp", "gzip", "hashlib",
    "heapq", "hmac", "html", "http", "idlelib", "imaplib", "importlib",
    "inspect", "io", "ipaddress", "itertools", "json", "keyword", "lib2to3",
    "linecache", "locale", "logging", "lzma", "mailbox", "marshal", "math",
    "mimetypes", "mmap", "modulefinder", "multiprocessing", "netrc",
    "numbers", "operator", "os", "ossaudiodev", "pathlib", "pdb", "pickle",
    "pickletools", "pipes", "pkgutil", "platform", "plistlib", "poplib",
    "posix", "posixpath", "pprint", "profile", "pstats", "pty", "pwd",
    "py_compile", "pyclbr", "pydoc", "queue", "quopri", "random", "re",
    "readline", "reprlib", "resource", "rlcompleter", "runpy", "sched",
    "secrets", "select", "selectors", "shelve", "shlex", "shutil", "signal",
    "site", "smtpd", "smtplib", "sndhdr", "socket", "socketserver",
    "spwd", "sqlite3", "sre_compile", "sre_constants", "sre_parse", "ssl",
    "stat", "statistics", "string", "stringprep", "struct", "subprocess",
    "sunau", "symtable", "sys", "sysconfig", "syslog", "tabnanny",
    "tarfile", "telnetlib", "tempfile", "termios", "test", "textwrap",
    "threading", "time", "timeit", "tkinter", "token", "tokenize", "tomllib",
    "trace", "traceback", "tracemalloc", "tty", "turtle", "turtledemo",
    "types", "typing", "unicodedata", "unittest", "urllib", "uu", "uuid",
    "venv", "warnings", "wave", "weakref", "webbrowser", "wsgiref",
    "xdrlib", "xml", "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib",
    "zoneinfo", "_thread", "_collections_abc",
})


def is_stdlib(module_name: str) -> bool:
    return module_name.split(".")[0] in STDLIB_TOP


def extract_imports(filepath: Path) -> list[dict]:
    try:
        source = filepath.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, OSError):
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({
                    "type": "import",
                    "module": alias.name,
                    "symbols": [],
                    "line": node.lineno,
                    "is_relative": False,
                    "is_stdlib": is_stdlib(alias.name),
                })
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            relative = node.level > 0
            full_module = ("." * node.level + module) if relative else module
            imports.append({
                "type": "from",
                "module": full_module,
                "symbols": [a.name for a in node.names],
                "line": node.lineno,
                "is_relative": relative,
                "is_stdlib": (not relative) and is_stdlib(module),
            })
    return imports


def build_graph(repo_root: Path, exclude: set[str]) -> dict:
    forward: dict[str, list[dict]] = {}
    reverse: dict[str, list[str]] = {}

    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in exclude and not d.startswith(".")
        )
        dp = Path(dirpath)
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            fpath = dp / fname
            rel = str(fpath.relative_to(repo_root))
            imports = extract_imports(fpath)
            forward[rel] = imports

            for imp in imports:
                if imp["is_stdlib"] or imp["is_relative"]:
                    continue
                top = imp["module"].split(".")[0]
                if top:
                    reverse.setdefault(imp["module"], [])
                    if rel not in reverse[imp["module"]]:
                        reverse[imp["module"]].append(rel)

    return {"forward": forward, "reverse": reverse}


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: build_import_graph.py <repo_root> [--exclude dir1,dir2]", file=sys.stderr)
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

    graph = build_graph(repo_root, exclude)
    print(json.dumps(graph, indent=2))


if __name__ == "__main__":
    main()
