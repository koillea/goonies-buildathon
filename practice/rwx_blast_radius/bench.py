"""Practice benchmark for the anticipated RWX "Blast Radius" track.

Two tasks on synthetic Python monorepos (we do not know the real format yet):

  A. culprit  - a CI build fails after a batch of commits; name the commit that broke it.
                Metric: accuracy over N cases (the site's example: "find the cause of a
                failed build: accuracy on the same 100 test cases, higher wins").
  B. impact   - given the files a change touches, list the tests that must re-run.
                Metric: mean F1 over N cases (exact-match rate also reported).

Hidden edges that make it hard: transitive imports, re-exports through __init__,
data files opened by path, dynamic imports by string, benign edits to files in the
dependency cone, and logs that only name the failing test.
"""
from __future__ import annotations

import random
import re

SYMS = ["load", "parse", "render", "merge", "price", "route", "sync", "score", "pack", "trim",
        "apply", "build", "check", "emit", "fold", "group", "hash", "index", "join", "keep"]
PKGS = ["core", "billing", "search", "ingest", "auth", "notify", "report", "catalog", "orders", "geo"]


def make_repo(rng: random.Random):
    """Return (files, deps, tests). deps[path] = set of paths it truly depends on."""
    pkgs = rng.sample(PKGS, rng.randint(4, 7))
    files: dict[str, str] = {}
    deps: dict[str, set[str]] = {}
    mods: list[str] = []
    defs: dict[str, list[str]] = {}
    for p in pkgs:
        for i in range(rng.randint(3, 5)):
            mods.append(f"{p}/m{i}.py")
    data_files = [f"data/{n}.json" for n in ("rates", "regions", "flags", "schema")]
    for d in data_files:
        files[d] = '{"v": %d}\n' % rng.randint(1, 99)
        deps[d] = set()
    order = mods[:]
    rng.shuffle(order)
    for idx, m in enumerate(order):
        mine = rng.sample(SYMS, rng.randint(2, 3))
        defs[m] = mine
        earlier = order[:idx]
        d: set[str] = set()
        lines: list[str] = []
        for up in rng.sample(earlier, min(len(earlier), rng.choice([0, 1, 1, 2, 2, 3]))):
            sym = rng.choice(defs[up])
            modname = up[:-3].replace("/", ".")
            style = rng.random()
            if style < 0.55:
                lines.append(f"from {modname} import {sym}")
            elif style < 0.75:
                lines.append(f"import {modname}")
            elif style < 0.9:  # dynamic import: invisible to a naive import parser
                lines.append("import importlib")
                lines.append(f"_dyn = importlib.import_module('{modname}')")
            else:  # re-export through the package __init__
                pkg = up.split("/")[0]
                init = f"{pkg}/__init__.py"
                stem = up.split("/")[1][:-3]
                files[init] = files.get(init, "") + f"from {pkg}.{stem} import {sym}\n"
                deps.setdefault(init, set()).add(up)
                lines.append(f"from {pkg} import {sym}")
                d.add(init)
            d.add(up)
        if rng.random() < 0.3:
            df = rng.choice(data_files)
            lines.append(f"_cfg = open('{df}').read()")
            d.add(df)
        for s in mine:
            lines.append(f"def {s}(x, y=0):\n    return x")
        files[m] = "\n".join(lines) + "\n"
        deps[m] = d
    for p in pkgs:
        files.setdefault(f"{p}/__init__.py", "")
        deps.setdefault(f"{p}/__init__.py", set())
    tests: list[str] = []
    for m in mods:
        if rng.random() < 0.85:
            t = f"tests/test_{m[:-3].replace('/', '_')}.py"
            sym = rng.choice(defs[m])
            files[t] = f"from {m[:-3].replace('/', '.')} import {sym}\n\ndef test_{sym}():\n    assert {sym}(1) == 1\n"
            deps[t] = {m}
            tests.append(t)
    return files, deps, tests, defs


def closure(start: str, deps: dict[str, set[str]]) -> dict[str, int]:
    """Transitive dependencies of `start` with hop distance."""
    dist = {start: 0}
    frontier = [start]
    while frontier:
        nxt = []
        for f in frontier:
            for d in deps.get(f, ()):
                if d not in dist:
                    dist[d] = dist[f] + 1
                    nxt.append(d)
        frontier = nxt
    return dist


def make_culprit_case(rng: random.Random):
    while True:
        files, deps, tests, defs = make_repo(rng)
        failing = rng.choice(tests)
        cone = closure(failing, deps)
        cands = [f for f in cone if f.endswith(".py") and f in defs]
        if cands:
            break
    broken_file = rng.choice(cands)
    # break a symbol that something on the path to the failing test really uses
    users = [f for f in cone if broken_file in deps.get(f, ())]
    used = [s for s in defs[broken_file] if any(re.search(rf"\b{s}\b", files[u]) for u in users)]
    sym = rng.choice(used or defs[broken_file])
    kind = rng.choice(["removed", "signature", "raises"])
    n = rng.randint(4, 8)
    culprit_idx = rng.randrange(n)
    commits = []
    others = [f for f in files if f != broken_file]
    in_cone = [f for f in cone if f != broken_file and f.endswith(".py")]
    for i in range(n):
        if i == culprit_idx:
            src = files[broken_file]
            if kind == "removed":
                new = src.replace(f"def {sym}(x, y=0):", f"def {sym}_v2(x, y=0):")
            elif kind == "signature":
                new = src.replace(f"def {sym}(x, y=0):", f"def {sym}(x, y, z):")
            else:
                new = src.replace(f"def {sym}(x, y=0):\n    return x", f"def {sym}(x, y=0):\n    raise ValueError('bad {sym}')")
            commits.append({"id": f"c{i}", "changes": {broken_file: new}})
        else:
            # distractors: often inside the dependency cone, sometimes the same file earlier
            pool = in_cone if (in_cone and rng.random() < 0.55) else others
            f = rng.choice(pool)
            ch = {f: files[f] + f"# tweak {i}\n"}
            if rng.random() < 0.25:
                g = rng.choice(others)
                ch[g] = files[g] + f"# tweak {i}b\n"
            if rng.random() < 0.15 and i < culprit_idx:
                ch[broken_file] = files[broken_file] + f"# refactor note {i}\n"
            commits.append({"id": f"c{i}", "changes": ch})
    style = rng.random()
    test_name = failing
    if style < 0.35:  # full traceback naming the broken module and symbol
        msg = {"removed": f"ImportError: cannot import name '{sym}' from '{broken_file[:-3].replace('/', '.')}'",
               "signature": f"TypeError: {sym}() missing 1 required positional argument: 'z'",
               "raises": f"ValueError: bad {sym}"}[kind]
        log = f"FAILED {test_name}\n  File \"{broken_file}\", line 7\n{msg}\n"
    elif style < 0.7:  # error message only, no file path
        msg = {"removed": f"ImportError: cannot import name '{sym}'",
               "signature": f"TypeError: {sym}() missing 1 required positional argument: 'z'",
               "raises": f"ValueError: bad {sym}"}[kind]
        log = f"FAILED {test_name}\n{msg}\n"
    else:  # only the failing test is known
        log = f"FAILED {test_name}\nexit code 1\n"
    return {"files": files, "commits": commits, "log": log}, f"c{culprit_idx}"


def make_impact_case(rng: random.Random):
    files, deps, tests, _ = make_repo(rng)
    changed = rng.sample(sorted(files), rng.randint(1, 3))
    affected = sorted(t for t in tests if any(c in closure(t, deps) for c in changed))
    return {"files": files, "tests": tests, "changed": changed}, affected


def dataset(kind: str, n: int, seed: int):
    rng = random.Random(seed)
    make = make_culprit_case if kind == "culprit" else make_impact_case
    return [make(rng) for _ in range(n)]


def score_culprit(solve, cases) -> float:
    return sum(solve(c) == truth for c, truth in cases) / len(cases)


def score_impact(solve, cases) -> tuple[float, float]:
    f1s, exact = [], 0
    for c, truth in cases:
        pred, t = set(solve(c)), set(truth)
        if pred == t:
            exact += 1
        if not pred and not t:
            f1s.append(1.0)
            continue
        tp = len(pred & t)
        p = tp / len(pred) if pred else 0.0
        r = tp / len(t) if t else 0.0
        f1s.append(2 * p * r / (p + r) if p + r else 0.0)
    return sum(f1s) / len(f1s), exact / len(cases)
