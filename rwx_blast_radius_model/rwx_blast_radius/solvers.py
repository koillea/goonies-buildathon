"""Approaches for both tasks, weakest to strongest.

Lifted verbatim (behaviour-preserving) from the original
``practice/rwx_blast_radius/solutions.py``. The ladder climbs by *modelling the
real dependency*, not pattern-matching the log text: latest-commit -> file named
in the log -> static import cone -> symbol from the error -> full graph with
package re-exports, dynamic imports and data files plus comment-only-diff
filtering. That climb (26% -> 100% on synthetic data) is the PLAYBOOK's rule 3,
"model the real dependency".
"""
from __future__ import annotations

import re


# ---------- shared: dependency graph from source text ----------
def static_deps(files: dict[str, str], *, packages=False, dynamic=False, data=False) -> dict[str, set[str]]:
    deps: dict[str, set[str]] = {f: set() for f in files}
    for path, src in files.items():
        if not path.endswith(".py"):
            continue
        for m in re.finditer(r"^\s*from\s+([\w.]+)\s+import\s+", src, re.M):
            mod = m.group(1).replace(".", "/")
            if f"{mod}.py" in files:
                deps[path].add(f"{mod}.py")
            elif packages and f"{mod}/__init__.py" in files:
                deps[path].add(f"{mod}/__init__.py")
        for m in re.finditer(r"^\s*import\s+([\w.]+)", src, re.M):
            mod = m.group(1).replace(".", "/")
            if f"{mod}.py" in files:
                deps[path].add(f"{mod}.py")
        if dynamic:
            for m in re.finditer(r"import_module\(\s*['\"]([\w.]+)['\"]", src):
                mod = m.group(1).replace(".", "/")
                if f"{mod}.py" in files:
                    deps[path].add(f"{mod}.py")
        if data:
            for m in re.finditer(r"['\"]([\w./-]+\.(?:json|ya?ml|csv|txt|toml|sql))['\"]", src):
                if m.group(1) in files:
                    deps[path].add(m.group(1))
    return deps


def closure(start: str, deps: dict[str, set[str]]) -> dict[str, int]:
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


def failing_test(log: str) -> str | None:
    m = re.search(r"FAILED\s+(\S+)", log)
    return m.group(1) if m else None


def strip_comments(src: str) -> str:
    return "\n".join(l for l in (re.sub(r"#.*", "", x).rstrip() for x in src.splitlines()) if l)


# ---------- task A: culprit ----------
def culprit_v0_latest(case):
    return case["commits"][-1]["id"]


def culprit_v1_log_file(case):
    """Commit touching a file path that appears in the log; else latest."""
    for c in reversed(case["commits"]):
        if any(f in case["log"] for f in c["changes"]):
            return c["id"]
    return culprit_v0_latest(case)


def culprit_v2_import_cone(case):
    """Nearest commit in the failing test's static import cone."""
    deps = static_deps(case["files"])
    cone = closure(failing_test(case["log"]) or "", deps)
    best = None
    for c in case["commits"]:
        d = min((cone[f] for f in c["changes"] if f in cone), default=None)
        if d is not None and (best is None or d <= best[0]):
            best = (d, c["id"])
    return best[1] if best else culprit_v0_latest(case)


def culprit_v3_symbol_only(case):
    m = re.search(r"name '(\w+)'|TypeError: (\w+)\(\)|bad (\w+)", case["log"])
    sym = next((g for g in (m.groups() if m else ()) if g), None)
    if not sym:
        return None
    for c in case["commits"]:
        for f, new in c["changes"].items():
            old = case["files"].get(f, "")
            old_def = re.search(rf"def {sym}\(.*?(?=\ndef |\Z)", old, re.S)
            new_def = re.search(rf"def {sym}\(.*?(?=\ndef |\Z)", new, re.S)
            if old_def and (not new_def or strip_comments(old_def.group()) != strip_comments(new_def.group())):
                return c["id"]
    return None


def culprit_v3_symbol(case):
    """Use the symbol named in the error: which commit changed its definition?"""
    hit = culprit_v3_symbol_only(case)
    return hit if hit else culprit_v2_import_cone(case)


def culprit_v4_semantic_cone(case):
    """Full graph (packages, dynamic imports, data files) + ignore comment-only diffs."""
    hit = culprit_v3_symbol_only(case)
    if hit:
        return hit
    deps = static_deps(case["files"], packages=True, dynamic=True, data=True)
    cone = closure(failing_test(case["log"]) or "", deps)
    semantic = []
    for c in case["commits"]:
        for f, new in c["changes"].items():
            if f in cone and strip_comments(new) != strip_comments(case["files"].get(f, "")):
                semantic.append((cone[f], c["id"]))
    if semantic:
        return min(semantic)[1]
    return culprit_v2_import_cone(case)


CULPRIT = [("v0 latest commit", culprit_v0_latest),
           ("v1 file named in log", culprit_v1_log_file),
           ("v2 static import cone", culprit_v2_import_cone),
           ("v3 symbol from error + cone", culprit_v3_symbol),
           ("v4 full graph + semantic diff", culprit_v4_semantic_cone)]


# ---------- task B: impact set ----------
def impact_v0_all(case):
    return case["tests"]


def impact_v1_name_match(case):
    out = []
    for t in case["tests"]:
        stem = t[len("tests/test_"):-3]
        if any(c[:-3].replace("/", "_") == stem or c == t for c in case["changed"]):
            out.append(t)
    return out


def _impact(case, **kw):
    deps = static_deps(case["files"], **kw)
    return [t for t in case["tests"] if any(c in closure(t, deps) for c in case["changed"])]


def impact_v2_static(case):
    return _impact(case)


def impact_v3_packages(case):
    return _impact(case, packages=True)


def impact_v4_full(case):
    return _impact(case, packages=True, dynamic=True, data=True)


IMPACT = [("v0 run every test", impact_v0_all),
          ("v1 test named after file", impact_v1_name_match),
          ("v2 static import closure", impact_v2_static),
          ("v3 + package re-exports", impact_v3_packages),
          ("v4 + dynamic imports + data files", impact_v4_full)]
