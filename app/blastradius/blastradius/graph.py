"""Build a dependency graph from Python source and compute transitive closures.

Standard library only. Paths are repo-relative POSIX strings.
"""
from __future__ import annotations

import re

_FROM = re.compile(r"^\s*from\s+([\w.]+)\s+import\s+", re.M)
_IMPORT = re.compile(r"^\s*import\s+([\w.]+(?:\s*,\s*[\w.]+)*)", re.M)
_DYN = re.compile(r"import_module\(\s*['\"]([\w.]+)['\"]")
_DATA = re.compile(r"""['"]([\w./-]+\.(?:json|ya?ml|csv|txt|toml|sql|ini|cfg))['"]""")
_COMMENT = re.compile(r"#.*")


def _mod_to_path(mod: str, files: set[str]) -> str | None:
    base = mod.replace(".", "/")
    if f"{base}.py" in files:
        return f"{base}.py"
    if f"{base}/__init__.py" in files:
        return f"{base}/__init__.py"
    return None


def build_graph(sources: dict[str, str]) -> dict[str, set[str]]:
    """sources: repo-relative path -> file text. Returns path -> set of paths it depends on."""
    files = set(sources)
    deps: dict[str, set[str]] = {f: set() for f in files}
    for path, src in sources.items():
        if not path.endswith(".py"):
            continue
        d = deps[path]
        for m in _FROM.finditer(src):
            p = _mod_to_path(m.group(1), files)
            if p and p != path:
                d.add(p)
        for m in _IMPORT.finditer(src):
            for mod in re.split(r"\s*,\s*", m.group(1)):
                p = _mod_to_path(mod.strip(), files)
                if p and p != path:
                    d.add(p)
        for m in _DYN.finditer(src):
            p = _mod_to_path(m.group(1), files)
            if p and p != path:
                d.add(p)
        for m in _DATA.finditer(src):
            if m.group(1) in files and m.group(1) != path:
                d.add(m.group(1))
    return deps


def closure(start: str, deps: dict[str, set[str]]) -> dict[str, int]:
    """Transitive dependencies of `start`, mapped to hop distance (start = 0)."""
    dist = {start: 0}
    frontier = [start]
    while frontier:
        nxt = []
        for f in frontier:
            for d in sorted(deps.get(f, ())):
                if d not in dist:
                    dist[d] = dist[f] + 1
                    nxt.append(d)
        frontier = nxt
    return dist


def strip_comments(src: str) -> str:
    return "\n".join(l for l in (_COMMENT.sub("", x).rstrip() for x in src.splitlines()) if l)
