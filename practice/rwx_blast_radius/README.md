# RWX — Blast Radius

**Idea:** know what a code change breaks *before* CI does — which commit broke a build, and which tests a change actually needs.

**Sponsor & why it's real:** RWX builds CI/automation tooling. In any large monorepo, "which of these commits turned main red?" and "which tests must this PR re-run?" cost real engineering hours and CI dollars every day.

**Anticipated problem / metric** (real brief opens at kickoff): find the commit that caused a failed build — accuracy over 100 hidden test cases, higher wins. We also built the sibling task: given a change, predict the exact set of tests to re-run (F1).

## Run it
```bash
python3 practice/rwx_blast_radius/run.py   # prints both tables, writes RESULTS.md
```

## Current practice results (synthetic data, held-out "hidden" split)
- **Culprit (accuracy):** latest-commit guess 26% → use the symbol in the error 76% → full dependency graph + semantic diff **100%**.
- **Impact (F1):** run-everything 0.37 → static imports 0.87 → +package re-exports & dynamic imports & data files **1.00**.

The lesson: model the *real* dependency graph and parse *what actually broke* (the symbol in the error), don't pattern-match the log text. Full reasoning in `NOTES.md`.

## Files
`bench.py` (data + scorer) · `solutions.py` (approaches weak→strong) · `run.py` (scores dev + hidden) · `NOTES.md` (reasoning) · `RESULTS.md` (latest scores).

This track also ships as a usable tool at `app/blastradius/` — the same logic wired to a real git repo.

## When the real brief drops
Replace `bench.py`'s generator/scorer with the real repo format and metric; keep `static_deps` + `closure` + the symbol-from-error trick. The 100% is a synthetic ceiling — real code has edges the generator doesn't model, so keep the graph conservative.
