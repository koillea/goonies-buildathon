"""Blast Radius selector for sqlglot.

For each patch: find the lines it touches (as line numbers in the pinned commit),
map each line to the function that contains it, and run only the tests that executed
that function when the maps were built. Lines outside any function (class or module
level, e.g. a dialect's class attribute) select every test that executed the file or
used a class defined in it. Anything the maps cannot vouch for runs every test.
Then the chosen tests are split over the worker count that minimises
busiest-worker time + 2 s per worker.

Inputs:  $DATA_DIR/commits/<id>.patch, $DATA_DIR/tests.json   (default /data)
Maps:    maps/maps.json, built from the pinned commit by build/ (see README.md)
Output:  one JSON line per commit on stdout; logs on stderr.
"""
from __future__ import annotations

import json
import os
import re
import sys
from bisect import bisect_right
from pathlib import Path

DATA = Path(os.environ.get("DATA_DIR", "/data"))
MAPS = Path(__file__).resolve().parent / "maps" / "maps.json"
MAX_WORKERS = 8
WORKER_MS = 2000
VERBOSE = os.environ.get("BR_VERBOSE") == "1"


def log(*a):
    if VERBOSE:
        print(*a, file=sys.stderr)


# ------------------------------------------------------------------ patches
_DIFF = re.compile(r"^diff --git a/(.+?) b/(.+)$")
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class FileChange:
    __slots__ = ("old", "new", "lines", "added", "deleted")

    def __init__(self, old, new):
        self.old, self.new = old, new
        self.lines: set[int] = set()  # line numbers in the pinned (old) file
        self.added = False
        self.deleted = False


def parse_patch(text: str) -> list[FileChange]:
    """Collect, per file, the pinned-commit line numbers a patch touches.

    Hunk bodies are consumed by their declared line counts, so a removed line whose
    content starts with "-- " (shown as "--- ...") is never mistaken for a header.
    """
    changes: list[FileChange] = []
    cur: FileChange | None = None
    old = rem_old = rem_new = 0
    lines = text.split("\n")
    for line in lines:
        if rem_old > 0 or rem_new > 0:
            c = line[:1]
            if c == " " or line == "":
                old += 1
                rem_old -= 1
                rem_new -= 1
            elif c == "-":
                cur.lines.add(old)
                old += 1
                rem_old -= 1
            elif c == "+":
                cur.lines.add(old - 1)
                cur.lines.add(old)
                rem_new -= 1
            # "\ No newline at end of file" consumes nothing
            continue
        m = _DIFF.match(line)
        if m:
            cur = FileChange(m.group(1), m.group(2))
            changes.append(cur)
            continue
        if cur is None:
            continue
        if line.startswith("new file mode") or line == "--- /dev/null":
            cur.added = True
        elif line.startswith("deleted file mode") or line == "+++ /dev/null":
            cur.deleted = True
        elif line.startswith("rename from") or line.startswith("rename to"):
            cur.deleted = True  # treat a rename as "cannot vouch"
        else:
            h = _HUNK.match(line)
            if h:
                old = int(h.group(1))
                rem_old = int(h.group(2)) if h.group(2) is not None else 1
                rem_new = int(h.group(4)) if h.group(4) is not None else 1
    return changes


# ------------------------------------------------------------------ split
def split(nums, dur):
    if not nums:
        return []
    order = sorted(nums, key=lambda n: dur[n], reverse=True)
    best = None
    for k in range(1, MAX_WORKERS + 1):
        loads = [0] * k
        ws = [[] for _ in range(k)]
        for n in order:
            i = loads.index(min(loads))
            ws[i].append(n)
            loads[i] += dur[n]
        used = sum(1 for w in ws if w)
        cost = max(loads) + WORKER_MS * used
        if best is None or cost < best[0]:
            best = (cost, [w for w in ws if w])
    return best[1]


# ------------------------------------------------------------------ selection
DOC_EXT = (".md", ".rst", ".txt", ".png", ".svg", ".html")


class Selector:
    def __init__(self, tests):
        m = json.loads(MAPS.read_text())
        self.all = {t["number"] for t in tests}
        self.ids = {t["id"]: t["number"] for t in tests}
        self.by_file: dict[str, set[int]] = {}
        self.by_class: dict[str, set[int]] = {}
        for t in tests:
            self.by_file.setdefault(t["file"], set()).add(t["number"])
            self.by_class.setdefault(t["id"].rsplit("::", 1)[0], set()).add(t["number"])
        self.file_cov = m["file_cov"]
        self.file_use = m["file_use"]
        self.fixtures = m["fixtures"]
        self.spans = {f: sorted(v) for f, v in m["spans"].items()}
        self.units = {(f, s, e): (set(ts), bool(imp)) for f, s, e, ts, imp in m["units"]}
        self.test_spans = m["test_spans"]
        fdirs: dict[str, set[int]] = {}
        for fx, ts in self.fixtures.items():
            fdirs.setdefault(os.path.dirname(fx), set()).update(ts)
        self.fixture_dirs = fdirs

    def file_level(self, f):
        cov, use = self.file_cov.get(f), self.file_use.get(f)
        if cov is None and use is None:
            return None
        return set(cov or ()) | set(use or ())

    def source(self, ch: FileChange):
        f = ch.old
        sel: set[int] = set()
        spans = self.spans.get(f)
        if spans is None:
            log(f"  {f}: unknown source file -> all")
            return None
        for line in sorted(ch.lines):
            inner = None
            for s, e, b in spans:
                if s <= line <= e and (inner is None or e - s < inner[1] - inner[0]):
                    inner = (s, e, b)
            if inner is None:
                fl = self.file_level(f)
                if fl is None:
                    return None
                log(f"  {f}:{line} module/class level -> {len(fl)}")
                sel |= fl
                continue
            ts, imp = self.units.get((f, inner[0], inner[1]), (set(), False))
            sel |= ts
            if imp:
                fl = self.file_level(f)
                if fl is None:
                    return None
                sel |= fl
            log(f"  {f}:{line} in fn {inner[:2]} -> {len(ts)}{' +file' if imp else ''}")
        return sel

    def test_file(self, ch: FileChange):
        f = ch.old
        spans = self.test_spans.get(f)
        if spans is None:
            return None
        sel: set[int] = set()
        for line in ch.lines:
            inner = None
            for s, e, q in spans:
                if s <= line <= e and (inner is None or e - s < inner[1] - inner[0]):
                    inner = (s, e, q)
            tid = f + "::" + inner[2].replace(".", "::") if inner else None
            if tid in self.ids:
                sel.add(self.ids[tid])
            else:
                return None  # helper or module level in a test file: may be shared
        return sel

    def fixture(self, ch: FileChange):
        f = ch.old if not ch.added else ch.new
        if f in self.fixtures:
            return set(self.fixtures[f])
        d = os.path.dirname(f)
        if d in self.fixture_dirs:
            log(f"  {f}: unread fixture -> its directory's readers")
            return set(self.fixture_dirs[d])
        return None

    def select(self, changes: list[FileChange]) -> set[int]:
        sel: set[int] = set()
        for ch in changes:
            path = ch.new if ch.added else ch.old
            log(f" {path} lines={sorted(ch.lines)[:12]} added={ch.added} deleted={ch.deleted}")
            if path.endswith(DOC_EXT) or path.startswith(("docs/", "posts/", "pdoc/", ".github/")):
                continue
            if path.startswith("tests/fixtures/"):
                r = self.fixture(ch) if not ch.deleted else None
            elif ch.added or ch.deleted:
                r = None
            elif path.startswith("sqlglot/") and path.endswith(".py"):
                r = self.source(ch)
            elif path.startswith("tests/") and path.endswith(".py"):
                r = self.test_file(ch)
            else:
                r = None
            if r is None:
                log(f"  {path}: cannot vouch -> all tests")
                return set(self.all)
            sel |= r
        return sel


def main():
    tests = json.loads((DATA / "tests.json").read_text())["tests"]
    dur = {t["number"]: round(t["seconds"] * 1000) for t in tests}
    sel = Selector(tests)
    out = []
    for p in sorted((DATA / "commits").glob("*.patch")):
        log(p.stem)
        chosen = sel.select(parse_patch(p.read_text(encoding="utf-8", errors="replace")))
        out.append(json.dumps({"commit": p.stem, "workers": split(sorted(chosen), dur)}))
    sys.stdout.write("\n".join(out) + ("\n" if out else ""))


if __name__ == "__main__":
    main()
