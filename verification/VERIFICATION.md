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

---

## Addendum: `koillea/mech-royale-goonies` @ `1bc77f0` ("Mech Royale bot v1", the only commit)
| Check | Evidence | Verdict |
|---|---|---|
| Same as the verified mirror branch `096f2b7` | `diff -r`: identical, file for file | CONFIRMED |
| Kit files untouched | `protocol.md`, `check.py`, stream, arena and `mechfight.py` byte-identical to the official kit | CONFIRMED |
| Submittable layout | `Dockerfile` at top level, 2.1 MB (cap 20 MB), public | CONFIRMED |
| Official kit check in the scorer sandbox (fresh build from this clone) | `ready in 548 ms`, 300/300 in time, 0 late, 0 wrong tick, 0 bad lines, debug drawings within caps: **PASS** | CONFIRMED |
| Repo gate (`tools/quality_gate.py`) | all checks passed | CONFIRMED |
| Laser-damage claim (README line 99, dossier) | Still says "three 315 hits from 150 m". The recording shows 4 hits at 151/149/100/56 m | **INACCURATE** (unchanged) |
| Base image pinned | `FROM python:3.13-slim`, no digest | minor risk |
| Play strength or board score | No simulator. The only "Goonies" row on the builders page has score 257, which matches Goonies' Blast Radius score, not a Mech score | **UNVERIFIABLE**: no Mech score for this commit yet |

---

## Addendum: `koillea/rwx-blast-radius-v1` @ `96c71b8` (v7, latest push; includes v6 `6532704`)
| Claim / check | Evidence | Verdict |
|---|---|---|
| README: "v7 126.699 s, 0 misses" on the sample | Official `score.py`, 3 runs under scorer flags: **126.699 s, 0 misses**, byte-identical output | CONFIRMED |
| README: v4 179.454 s | Matches my earlier measurement of v5 (179.454 s; v5 changed nothing on the sample) | CONFIRMED |
| README: CPU "about 0.4 s" | Measured **1.06 s** CPU in the container (109 MB RSS). Expected board figure on this sample: about 127.8 s | **understated** (minor, about 0.7 s) |
| v6: "no collected test reads a docstring" | `tests/test_docs.py` uses unittest's `load_tests`, which pytest ignores, so tests.json has no doctest entries | CONFIRMED |
| v7 comparison-swap rule is sound | 18 **new** single-operator swaps (`is`↔`==`, `is not`↔`!=`, `<`↔`<=`, `>=`↔`>`) at randomly chosen sites that ≥ 20 tests run (seeded; patches in `verification/swap_mutations/`). Ground truth from full suite runs: **0 misses**. In 12 cases the selector ran nothing and nothing failed; in 4 cases with real failures (1, 1, 5, 3 tests) it selected exactly the failing tests | CONFIRMED on this sample of swaps |
| Swap rule only fires on a pure swap | Code check: exactly one `Compare` op may change, to its partner, and the rest of the AST must be identical, else it falls through to the normal rules. Chained comparisons are excluded, and import-time sites fall back | CONFIRMED by reading |
| Old 12 mutations | Same as v5: **p_default (170 missed) and p_lazy (82 missed) still miss**. The other 10 are fine | UNCHANGED gap |
| The sample gain comes from 3 of the 30 commits | The verbose log shows the swap rule firing on 3 sample commits (179.5 → 126.7 s) | measured |

**Rules risk (human judgment needed):** `maps/cmp.json` is computed only from the pinned commit (a runtime probe evaluates both operators at every comparison while the pinned suite runs), not from any patch or answer. But it is keyed by *site + kind of edit* (an operator swap) and lists the tests where that edit could change behaviour. The rule bans "a table from a patch, **or from a kind of edit**, to the tests it breaks", while explicitly allowing "maps built from the pinned commit (coverage, imports, fixtures)". I read cmp.json as a value-sensitivity map, closer to coverage than to an answer table. It records where an edit *could* matter, not which tests *do* break. Still, it is the part of the entry a reviewer is most likely to question ("Top entries are read"). Consider confirming with the organizers before relying on it in the final.

---

## Addendum: `koillea/rwx-blast-radius-v1` @ `832535b` (v9, latest push; includes v8 `25c06f7`), stress-tested for expensive, slow tests
| Claim / check | Evidence | Verdict |
|---|---|---|
| README: v9 119.652 s, 0 misses | Official `score.py`, 3 runs under scorer flags: **119.652 s, 0 misses**, byte-identical output | CONFIRMED |
| README: v8 "same picks as v7, less CPU" | v9 makes the same selections as v7 on all 18 comparison-swap patches | consistent |
| Board screenshot (208.3 s) | 206.153 simulated + 2.17 CPU = 208.323, which rounds to 208.3 per SCORING.md | arithmetic CONFIRMED |
| v9 `arg_types` rule is sound | 10 **new** `arg_types` edits on random expression classes (flip required, drop key, add key, reorder keys; patches in `verification/argtypes_mutations/`). Full-suite ground truth: **0 misses**. 6 edits broke 2–15 tests; all were selected (2–45 of 1620 selected) | CONFIRMED on this sample |
| Generic `cls.arg_types` readers (the possible hole) | Every variable-based reader in sqlglot either instantiates the class (`from_arg_list`) or reads through an instance, so the "tests that created C" set covers it. No test reads `arg_types` generically | CONFIRMED by code reading |
| Old mutations | **p_default (170 missed) and p_lazy (82 missed) still miss**; the other 10 are fine | UNCHANGED gap |

### Expensive / slow tests (all test durations multiplied by k; scored with the official `score.py`)
| k | Full suite (serial) | Starter (run all, 3 workers) | v9 | v9 misses | Oracle | v9 / oracle |
|---|---|---|---|---|---|---|
| 1 | 103.0 s | 1210.5 | 119.7 | 0 | 94.4 | 1.27 |
| 5 | 515.2 s | 5332.4 | 362.7 | 0 | 301.7 | 1.20 |
| 10 | 1030.5 s | 10484.7 | 660.8 | 0 | 557.4 | 1.19 |
| 30 | 3091.4 s | 31094.1 | 1850.2 | 0 | 1580.1 | 1.17 |

- **Selection doesn't depend on durations**, and the worker split re-plans from `tests.json`, so v9 stays close to the oracle as tests get slower.
- **The run-everything fallback stops paying off when tests are slow.** On 8 workers it costs 36.8 s per commit at ×1, 152 s at ×5, 296 s at ×10, and 584 s at ×20 (more than a 300 s miss). One test dominates: `test_parser.py::TestParser::test_max_nodes` is 28.8 s of the suite's 103 s. The README's reasoning ("a run-all (~37 s) is far cheaper than a miss (300 s)") holds only at the recorded durations, and the code has no cost check. v9 never falls back to run-everything on the sample. Suggestion: compute the run-all cost from `tests.json` and, above about 300 s, fall back to the file-level set instead of every test.
- **Slow machine:** a 70-commit batch (sample + all my mutation sets) took 2.8 s wall at 2 CPUs, 4.2 s at 0.5 CPU and 9.0 s at 0.25 CPU, with about 2.1 s CPU. The limit is 180 s (270 s in the final), so headroom is large. The server charged 2.17 s CPU on practice.
