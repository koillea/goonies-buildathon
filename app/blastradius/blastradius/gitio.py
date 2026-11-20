"""Thin wrappers over `git` for reading repo state. Standard library only."""
from __future__ import annotations

import subprocess


def _git(args: list[str], cwd: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def repo_root(cwd: str) -> str:
    return _git(["rev-parse", "--show-toplevel"], cwd).strip()


def tracked_py_and_data(root: str) -> dict[str, str]:
    """Every tracked .py and common data file, as repo-relative path -> current text."""
    names = _git(["ls-files", "*.py", "*.json", "*.yaml", "*.yml", "*.csv", "*.txt", "*.toml", "*.ini", "*.cfg", "*.sql"], root).splitlines()
    out: dict[str, str] = {}
    for n in names:
        try:
            with open(f"{root}/{n}", encoding="utf-8", errors="ignore") as fh:
                out[n] = fh.read()
        except OSError:
            pass
    return out


def changed_files(root: str, base: str | None) -> list[str]:
    """Changed .py/data files. base=None -> uncommitted (working tree + staged) vs HEAD."""
    if base:
        diff = _git(["diff", "--name-only", f"{base}...HEAD"], root)
    else:
        diff = _git(["status", "--porcelain"], root)
        diff = "\n".join(l[3:] for l in diff.splitlines())
    return [l.strip() for l in diff.splitlines() if l.strip()]


def commits_since(root: str, since: str) -> list[str]:
    """Commit hashes from `since`..HEAD, oldest first."""
    out = _git(["rev-list", "--reverse", f"{since}..HEAD"], root).splitlines()
    return [c.strip() for c in out if c.strip()]


def commit_changed_files(root: str, sha: str) -> list[str]:
    return [l.strip() for l in _git(["show", "--name-only", "--pretty=format:", sha], root).splitlines() if l.strip()]


def file_at(root: str, sha: str, path: str) -> str | None:
    try:
        return _git(["show", f"{sha}:{path}"], root)
    except subprocess.CalledProcessError:
        return None
