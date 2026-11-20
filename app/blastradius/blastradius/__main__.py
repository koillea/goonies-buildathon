"""blastradius CLI: `impact` (which tests to run) and `culprit` (which commit broke it)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from . import core, gitio


def _to_repo_rel(paths, root):
    """Map user-supplied paths (relative to cwd, or absolute) to repo-root-relative POSIX."""
    out = []
    for p in paths:
        ap = os.path.abspath(p)
        rel = os.path.relpath(ap, root)
        out.append(rel.replace(os.sep, "/"))
    return out


def _impact(args) -> int:
    root = gitio.repo_root(".")
    sources = gitio.tracked_py_and_data(root)
    changed = _to_repo_rel(args.files, root) if args.files else gitio.changed_files(root, args.base)
    changed = [c for c in changed if c in sources or core.is_test(c)]
    if not changed:
        print("No changed Python/data files detected.", file=sys.stderr)
        return 0
    tests = core.impacted_tests(sources, changed)
    all_tests = [p for p in sources if core.is_test(p)]
    if args.format == "json":
        print(json.dumps({"changed": changed, "impacted_tests": tests,
                          "skipped": len(all_tests) - len(tests), "total_tests": len(all_tests)}, indent=2))
    else:
        print(f"Changed files: {len(changed)}")
        print(f"Tests to run: {len(tests)} of {len(all_tests)} "
              f"(skip {len(all_tests) - len(tests)}, {(len(all_tests) - len(tests)) / max(1, len(all_tests)):.0%})")
        for t in tests:
            print(f"  {t}")
        if tests and args.pytest:
            print("\n# run just these:")
            print("pytest " + " ".join(tests))
    return 0


def _culprit(args) -> int:
    root = gitio.repo_root(".")
    sources = gitio.tracked_py_and_data(root)
    test = _to_repo_rel([args.test], root)[0]
    if test not in sources:
        print(f"Test file not found in repo: {args.test}", file=sys.stderr)
        return 2
    args.test = test
    shas = gitio.commits_since(root, args.since)
    if not shas:
        print(f"No commits in {args.since}..HEAD", file=sys.stderr)
        return 0
    commits = []
    for sha in shas:
        changes, before = {}, {}
        for f in gitio.commit_changed_files(root, sha):
            if f in sources:
                new = gitio.file_at(root, sha, f)
                old = gitio.file_at(root, f"{sha}~1", f)
                if new is not None:
                    changes[f] = new
                    before[f] = old or ""
        if changes:
            commits.append({"id": sha, "changes": changes, "before": before})
    log = sys.stdin.read() if args.log_stdin else args.log or ""
    ranked = core.rank_culprits(sources, args.test, commits, log)
    if args.format == "json":
        print(json.dumps({"failing_test": args.test, "suspects": ranked[: args.top]}, indent=2))
    else:
        if not ranked:
            print("No commit in range touched the failing test's dependency graph.")
            return 0
        print(f"Most likely culprits for {args.test}:")
        for i, r in enumerate(ranked[: args.top], 1):
            mark = "★" if r["symbol_match"] else " "
            print(f"  {i}. {mark} {r['id'][:10]}  {r['reason']}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="blastradius", description="Know what a change breaks before CI does.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("impact", help="which tests must run for a set of changes")
    pi.add_argument("--files", nargs="*", help="changed files (default: your uncommitted changes)")
    pi.add_argument("--base", help="diff against this ref instead of the working tree (e.g. origin/main)")
    pi.add_argument("--format", choices=["text", "json"], default="text")
    pi.add_argument("--pytest", action="store_true", help="also print a ready pytest command")
    pi.set_defaults(fn=_impact)

    pc = sub.add_parser("culprit", help="which commit most likely broke a failing test")
    pc.add_argument("test", help="path to the failing test file")
    pc.add_argument("--since", default="HEAD~20", help="search commits in <since>..HEAD (default HEAD~20)")
    pc.add_argument("--log", help="the failure message/traceback (helps pinpoint the symbol)")
    pc.add_argument("--log-stdin", action="store_true", help="read the failure log from stdin")
    pc.add_argument("--top", type=int, default=5)
    pc.add_argument("--format", choices=["text", "json"], default="text")
    pc.set_defaults(fn=_culprit)

    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except FileNotFoundError:
        print("git not found or not a git repository.", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as e:
        print(f"git error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
