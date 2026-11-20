"""The two analyses, decoupled from git so they are unit-testable with plain dicts."""
from __future__ import annotations

import re

from .graph import build_graph, closure, strip_comments

_SYM_FROM_LOG = re.compile(r"name '(\w+)'|(\w+)\(\) (?:missing|takes)|(?:ValueError|TypeError|RuntimeError): .*?\b(\w+)\b")


def is_test(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return path.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py") or "/tests/" in f"/{path}")


def impacted_tests(sources: dict[str, str], changed: list[str]) -> list[str]:
    """Tests whose dependency closure includes any changed file. Conservative."""
    deps = build_graph(sources)
    changed_set = set(changed)
    tests = [p for p in sources if is_test(p)]
    hit = []
    for t in tests:
        cl = closure(t, deps)
        if t in changed_set or (cl.keys() & changed_set):
            hit.append(t)
    # a changed test always runs, even if nothing depends on it
    for c in changed:
        if is_test(c) and c in sources and c not in hit:
            hit.append(c)
    return sorted(set(hit))


def _symbol_from_log(log: str) -> str | None:
    m = _SYM_FROM_LOG.search(log or "")
    if not m:
        return None
    return next((g for g in m.groups() if g), None)


def _def_changed(old: str, new: str, sym: str) -> bool:
    pat = rf"def {sym}\(.*?(?=\ndef |\Z)"
    o = re.search(pat, old, re.S)
    n = re.search(pat, new, re.S)
    if o is None:
        return False
    if n is None:
        return True  # the definition was removed or renamed
    return strip_comments(o.group()) != strip_comments(n.group())


def rank_culprits(
    sources: dict[str, str],
    failing_test: str,
    commits: list[dict],
    log: str = "",
) -> list[dict]:
    """commits: oldest-first list of {"id", "changes": {path: new_text}, "before": {path: old_text}}.
    Returns commits ranked most-suspect first, each with a reason.
    """
    deps = build_graph(sources)
    cone = closure(failing_test, deps)
    sym = _symbol_from_log(log)
    ranked: list[tuple[tuple, dict]] = []
    for order, c in enumerate(commits):
        in_cone = [f for f in c["changes"] if f in cone]
        if not in_cone:
            continue
        hit_sym = None
        if sym:
            for f in in_cone:
                old = c.get("before", {}).get(f, sources.get(f, ""))
                if _def_changed(old, c["changes"][f], sym):
                    hit_sym = f
                    break
        nearest = min(cone[f] for f in in_cone)
        # sort key: symbol match first, then nearest to the failure, then most recent commit
        key = (0 if hit_sym else 1, nearest, -order)
        reason = (f"changed definition of `{sym}` in {hit_sym}" if hit_sym
                  else f"changed {', '.join(in_cone)} ({nearest} hop(s) from the failing test)")
        ranked.append((key, {"id": c["id"], "reason": reason, "files": in_cone, "symbol_match": bool(hit_sym)}))
    ranked.sort(key=lambda x: x[0])
    return [r for _, r in ranked]
