# Independent verification: Blast Radius and Mech Royale

Date: 2026-11-21. Method: only an external signal can confirm a claim (the official scorer, executed tests, or deterministic measurement). A working agent's own statement counts for nothing. Verdicts: **CONFIRMED**, **REFUTED / INACCURATE**, **UNVERIFIABLE**.

Rubric source: the official track pages and kits (`SCORING.md`, `score.py`, `blast-radius-sample.tar.gz`, `mechfight-kit.tar.gz`, `protocol.md`) at joinbuilders.org/buildathon.

---

## Blast Radius (RWX). Metric: busiest worker + 2 s per worker + 300 s per missed commit + CPU, lower is better

### Ground-truth harness (validated)
- The labelers' image (`python:3.13-slim@sha256:e48f59…`, Python 3.13.18, SQLite 3.46.1) plus the kit's `requirements.lock`, with sqlglot at `eb11aec`, `SKIP_INTEGRATION=0`, and the full suite run per patch.
- **Reproduces `answers.json` exactly** on sample commits 2vdj, 2jrq and 2haz: 3 of 3 match, and the clean tree has 0 failures.
- An import or collection error counts as failing every test in that file, per SCORING.md ("its file cannot be imported").

### A. `koillea/rwx-blast-radius-v1` @ `14a0960` (v5, latest commit)
| Claim / check | Evidence | Verdict |
|---|---|---|
| Sample score | Official `score.py`, 3 runs under the exact `make sample` flags: **179.454 s, 0 misses**, byte-identical output each run | CONFIRMED (measured) |
| CPU charged | 0.68 s CPU, 0.68 s wall, 106 MB RSS inside the container. Expected board figure on this sample: about 180.1 s | measured |
| README results table | Has a header row and **no data rows** (truncated in this commit and the previous one) | DEFECT: no number is claimed at all |
| No answer tables (rule) | No sample commit id appears in `selector.py`, `build/` or the maps. Map keys are coverage, usage, fixtures, spans and docstrings only | CONFIRMED compliant |
| `pinned_src.zip` is the pinned commit | 250 of 251 files byte-identical to sqlglot `eb11aec`. The 1 difference is `sqlglot/_version.py`, which is generated and git-ignored | CONFIRMED |
| "If a patched file no longer parses, every test runs" | p_syntax and p_indent → all 1620 selected, 0 missed | CONFIRMED |
| Unseen mutations, 12 kinds | **10 of 12 OK, 2 MISSES**, listed below | see below |
| Repo size, build | 4.8 MB, builds in seconds, standard library only | OK |

### B. `koillea/goonies-buildathon` top level @ `26b30c8` (v3)
| Claim | Evidence | Verdict |
|---|---|---|
| "This selector 248.1 s, 0 misses" | 248.146 s, 0 misses, 3 identical runs | CONFIRMED |
| "Starter 1210.5 s" | Official starter image scored 1210.470 s | CONFIRMED |
| No answer tables | No sample ids in code or maps | CONFIRMED compliant |
| Unseen mutations | **8 of 12 OK, 4 MISSES**: p_syntax, p_indent, p_default, p_lazy | generalization risk |
| Board 257.0 s | The board's practice set differs from the sample (board baseline 1614.1 vs sample 1210.5), so it is not comparable | UNVERIFIABLE locally |

v5 is strictly better than v3 on both the sample score and the mutation misses.

### Unseen-mutation results (`verification/mutations/*.patch`, never seen by either selector)
| Mutation | Real failing tests | v3 selected / missed | v5 selected / missed |
|---|---|---|---|
| c_cmt: comment in a function | 0 | 1 / 0 | 0 / 0 |
| c_code1, c_code2: value edits | 0 | 1 / 0 | 1 / 0 |
| c_fix: fixture edit | 1 | 2 / 0 | 2 / 0 |
| c_kw: tsql tokenizer KEYWORDS | 9 | 171 / 0 | 171 / 0 |
| c_none: README only | 0 | 0 / 0 | 0 / 0 |
| p_rename: method rename (dispatch) | 1 | 1 / 0 | 1 / 0 |
| p_typing: typing metadata | 0 | 24 / 0 | 24 / 0 |
| p_syntax: syntax error in a 1-test function | 171 | **1 / 170 MISS** | 1620 / 0 |
| p_indent: IndentationError in a never-run function | 813 | **0 / 813 MISS** | 1620 / 0 |
| p_default: `def f(..., _x=UNDEFINED_NAME)`, NameError at import | 171 | **1 / 170 MISS** | **1 / 170 MISS** |
| p_lazy: `import sqlglot.dialects.duckdb` added to `sqlglot/__init__.py` (import cycle) | 1600 | **1518 / 82 MISS** | **1518 / 82 MISS** |

**Remaining v5 gaps (each costs 300 s per commit if it appears in the hidden set):**
1. **Def-line edits are evaluated at import time** (default arguments, decorators, annotations without `from __future__`). The edit is mapped to the function's body tests, but a bad default breaks the module import for every importer. Fix: an edit on a `def` or decorator line whose new expression is not a literal should select the file-level set.
2. **Tests the maps never see.** These 5 tests appear in no unit or file set: `test_dialect::test_lazy_load` (runs a subprocess), three `test_sqlglotc` tests, and `test_typing::test_no_redundant_expression_metadata` (static). Any non-narrowed edit to `sqlglot/__init__.py`, `sqlglot/dialects/__init__.py` or the import graph should add them. The 82 misses in p_lazy are mostly tests in files that failed to import, which the file-level map of `__init__.py` doesn't include. Safest fix: any edit that adds or changes an `import` at module level → run all (about 37 s, against 300 s for a miss).

Note: the official rules say the final includes "kinds of change not in practice", and they define a failure to include "its file cannot be imported". Both point at import-breaking commits.

---

## Mech Royale (Builders). Metric: mean (16 − place) over 48 practice matches, higher is better. Baseline 1.15

Candidate: `origin/claude/awesome-archimedes-ozpquo` @ `096f2b7`, folder `mech-royale/`.

| Claim / check | Evidence | Verdict |
|---|---|---|
| Kit files "unchanged" (`mechfight.py`, protocol, check.py, stream, arena) | Byte-compared against the freshly downloaded official kit: identical | CONFIRMED |
| Quality gate passes (pytest 13/13, static checks, conformance) | Rerun locally and with `--docker` in the exact match sandbox (1 CPU, 512 MB, read-only, uid 65534, no network): **PASS**, 300/300 answered in time | CONFIRMED |
| Latency "p99 ~12 ms in sandbox" | Measured p99 7.6 ms, max 8.8 ms in the sandbox. Init 0.15 s (budget 20 s), RSS 24 MB (limit 512 MB) | CONFIRMED (better than claimed) |
| "468 of 469 recorded positions walkable" | Recomputed: 468 / 469 | CONFIRMED |
| "Terrain within 5 mm" | Max error 5.5 mm. The dossier's "< 6 mm" is the accurate statement | minor rounding |
| Upgrade ids (`plating`, `nanites`, `gyros`…) | Absent from `protocol.md`'s prose but present in `hello.config.upgrades` of the recorded match | CONFIRMED real |
| Recorded match: kit bot placed 13th | `end` message: `place: 13` | CONFIRMED |
| "Lost ~950 HP to **three** 315-damage laser shots from **150 m**" (dossier marks this "verified") | **4** laser hits = 1260 HP, at 151, 149, 100 and 56 m (only 2 at about 150 m), plus 405 HP of gun damage | **INACCURATE** (design conclusion still sound) |
| Play strength or placement score | No local simulator. `check.py` replays a non-reactive recording. `submissions: []`, and Goonies is not on the Mech board | **UNVERIFIABLE**: only the board can score it. The agent did not claim a score (honest) |
| Submittable as-is | The Dockerfile is in `mech-royale/`, not at the repo top level. The commit says it mirrors `koillea/mech-royale-goonies`, which this session cannot read | NOT submittable from this branch: copy the folder to the top of a public repo |
| Pinned versions ("finalists are rebuilt") | `FROM python:3.13-slim` has no digest | minor risk: pin the digest |
| Dossier leaderboard snapshot | Differs from the live board (e.g. "3141592654 4.23" vs board "314159265 4.69") | stale or garbled: do not rely on it |

## Reproduce
```
# Blast Radius sample score: unpack the kit, then in it
make sample IMAGE=<image>          # or: docker run <scorer flags> <image> > out.jsonl; python3 score.py sample sample/answers.json out.jsonl
# Mutation ground truth (needs the pinned sqlglot checkout at /tmp/claude-0/gt/sqlglot and image br-gt from scripts/gt.Dockerfile)
python3 -I verification/scripts/gt.py verification/mutations/<id>.patch <outprefix>
DATA_DIR=<dir with commits/ and tests.json> python3 -I selector.py > sel.jsonl
python3 -I verification/scripts/score_mut.py sel.jsonl
```
