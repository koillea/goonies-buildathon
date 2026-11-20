# RWX Blast Radius — reasoning

**Anticipated problem.** Slug `blast-radius`; the site's worked example is *"find the cause of a failed build: accuracy on the same 100 test cases."* RWX builds CI/automation tooling, so the real task is likely one of: (a) given a failing CI run + the recent commits, name the culprit commit; (b) given a diff, name the minimal set of tests to run ("blast radius" of a change). We built both.

**Why it's a real company problem.** In a large monorepo, "which of these 30 commits broke main?" and "which tests must I re-run for this PR?" cost real engineering hours and CI dollars. Getting the blast radius right lets you skip 90% of the test suite safely.

**What moved the score (dev→hidden, culprit task):**
- Guessing the latest commit: 26%.
- Matching a file named in the log: 32%.
- Following the failing test's static import cone: 15% (worse! — a symmetric/naive parse misses the real edges and adds noise).
- Using the **symbol named in the error** and checking which commit changed *that definition*: 76%.
- Full dependency graph (package re-exports, dynamic `import_module`, data-file reads) + ignoring comment-only diffs: 100% on synthetic.

**Lesson:** model the real dependency graph; don't pattern-match the log. The jump came from parsing *what actually broke* (the symbol) and *what actually depends on it* (the full graph), not from heuristics on text.

**When the real brief drops:** replace `make_repo`/`make_*_case` with the real repo format and the real "failing build" signal; keep `static_deps` + `closure` + the symbol-from-error trick. If they give real language tooling (e.g. an actual import graph or build system), use it instead of the regex parser. The 100% is a synthetic ceiling — real code has edges our generator doesn't model (reflection, config, generated code), so expect <100% and keep the graph conservative (prefer false "affected" over missed ones for the impact task).
