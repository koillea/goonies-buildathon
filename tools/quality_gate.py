"""Repository quality gate.

Runs, from the repository root and fully offline (there are no credentials to
need -- every track is pure stdlib on seeded synthetic data):

1. the complete pytest suite;
2. every track package's CLI with a small case count;
3. every example script in each track folder and the top-level harness;
4. static checks that enforce the repo invariants from docs/ARCHITECTURE.md:
   no third-party imports in track packages (stdlib-only scorer-fleet rule),
   and no `print(` left inside a package module (CLIs print, packages return).

Exit status is non-zero if anything fails. Use it in CI and before a submission::

    python tools/quality_gate.py            # everything
    python tools/quality_gate.py --fast     # tests + static checks only

Modelled on tools/quality_gate.py in the reference repo
(prebuilt-ai-technique-models).
"""
from __future__ import annotations

import argparse
import ast
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# folder -> package
MODEL_FOLDERS = {
    "rwx_blast_radius_model": "rwx_blast_radius",
    "databricks_shopping_model": "databricks_shopping",
    "machina_deid_model": "machina_deid",
    "mech_royale_model": "mech_royale",
}

# A small, representative CLI invocation per track (few cases so the gate is fast).
CLI_ARGS = {
    "rwx_blast_radius": ["--n", "10"],
    "databricks_shopping": ["--n", "10"],
    "machina_deid": ["--n", "10"],
    "mech_royale": ["--n", "10"],
}

# Standard-library top-level modules a track package may import. Anything else is
# a third-party dependency and breaks the scorer-fleet invariant.
STDLIB_OK = set(sys.stdlib_module_names) | {"buildathon_core"}


def pythonpath() -> str:
    parts = ["common", *MODEL_FOLDERS.keys()]
    return os.pathsep.join(str(ROOT / p) for p in parts)


def run(cmd: list[str], *, cwd: Path = ROOT, timeout: int = 900) -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = pythonpath() + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True,
                              text=True, timeout=timeout, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                roots.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return roots


def check_static() -> list[str]:
    problems: list[str] = []
    for folder, pkg in MODEL_FOLDERS.items():
        pkg_dir = ROOT / folder / pkg
        if not pkg_dir.exists():
            problems.append(f"{folder}: package directory {pkg} missing")
            continue
        for py in sorted(pkg_dir.rglob("*.py")):
            text = py.read_text(encoding="utf-8", errors="replace")
            try:
                tree = ast.parse(text)
            except SyntaxError as e:
                problems.append(f"{py.relative_to(ROOT)}: syntax error: {e}")
                continue
            for root in _imported_roots(tree) - STDLIB_OK - set(MODEL_FOLDERS.values()):
                problems.append(f"{py.relative_to(ROOT)}: third-party import {root!r} breaks stdlib-only invariant")
            # CLIs and __main__ print to the user; package logic returns values.
            if py.name not in {"cli.py", "__main__.py"}:
                for node in ast.walk(tree):
                    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                            and node.func.id == "print"):
                        problems.append(f"{py.relative_to(ROOT)}:{node.lineno}: print() inside package module (CLIs print, packages return)")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="skip CLI and example runs")
    args = ap.parse_args()
    failures: list[str] = []

    print("== pytest")
    code, out = run([sys.executable, "-m", "pytest", "-q"])
    print(out.strip().splitlines()[-1] if out.strip() else "(no output)")
    if code != 0:
        failures.append("pytest failed")
        print(out[-4000:])

    print("== static checks")
    problems = check_static()
    for p in problems:
        print("  ", p)
    if problems:
        failures.append(f"{len(problems)} static check problem(s)")
    else:
        print("   ok")

    if not args.fast:
        print("== CLIs")
        for folder, pkg in MODEL_FOLDERS.items():
            if not (ROOT / folder / pkg).exists():
                print(f"   {pkg}: missing")
                failures.append(f"{pkg} package missing")
                continue
            code, out = run([sys.executable, "-m", pkg, *CLI_ARGS[pkg]])
            print(f"   {pkg}: {'ok' if code == 0 else f'exit {code}'}")
            if code != 0:
                failures.append(f"CLI {pkg} failed")
                print(out[-2000:])

        print("== examples")
        flat = sorted(p for f in MODEL_FOLDERS for p in (ROOT / f / "examples").glob("*.py"))
        ep = ROOT / "examples" / "buildathon_harness.py"
        if ep.exists():
            flat.append(ep)
        for ex in flat:
            code, out = run([sys.executable, str(ex), "--n", "10"])
            print(f"   {ex.relative_to(ROOT)}: {'ok' if code == 0 else f'exit {code}'}")
            if code != 0:
                failures.append(f"example {ex.relative_to(ROOT)} failed")
                print(out[-2000:])

    print("== result")
    if failures:
        for f in failures:
            print("   FAIL:", f)
        return 1
    print("   all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
