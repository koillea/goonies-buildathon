# RWX Blast Radius (`rwx_blast_radius`)

Two tasks on synthetic Python monorepos: **culprit** (a CI build fails after a
batch of commits — name the commit that broke it; metric: accuracy over N cases,
the site's one worked example) and **impact** (given the files a change touches,
list the tests that must re-run; metric: mean F1, exact-match reported too). It
implements the `buildathon_core.TrackSpec` protocol, so the shared `Harness`
scores it, compares its ladder on a dev-vs-hidden split, and renders its
`RESULTS.md` unchanged.

Everything runs offline and pure-stdlib: seeded synthetic data, no network, no
dependencies — the scorer-fleet invariant.

---

## 1. Purpose

RWX builds CI/automation tooling; "which change broke the build / what must I
re-test" is a genuine cost in any large monorepo. The hard part is the
*dependency reality* a naive parser misses: transitive imports, re-exports
through `__init__`, data files opened by path, dynamic imports by string, benign
edits inside the dependency cone, and CI logs that name only the failing test.
This track reproduces the metric locally on data with a knowable generator, then
climbs it by modelling that reality rather than pattern-matching the log text.

## 2. Architecture

```
          dataset("culprit"|"impact", n, seed)            solvers.CULPRIT / solvers.IMPACT
                        │                                            │  weak -> strong
                        ▼                                            ▼
          data.make_repo(rng) ── files, deps, tests, defs     static_deps(files, packages?, dynamic?, data?)
                        │                                            │
                        ▼                                            ▼
          make_culprit_case / make_impact_case            closure(failing_test, deps)  ── import cone
                        │                                            │
                        └───────────────► evaluation.score_culprit / score_impact ◄──────┘
                                                        │
                                   model.RWXBlastRadiusModel.evaluate()  (pairs culprit+impact rungs by level)
                                                        │
                                   buildathon_core.Harness.run() ─► TrackReport ─► render_report
```

| Module | Contents |
| --- | --- |
| `data.py` | `make_repo`, `closure`, `make_culprit_case`, `make_impact_case`, `dataset(kind, n, seed)`; the synthetic monorepo generator with all the hidden edges |
| `solvers.py` | `static_deps` (optional package/dynamic/data edges), `closure`, `failing_test`, `strip_comments`; the `CULPRIT` and `IMPACT` ladders, weakest first |
| `evaluation.py` | `score_culprit` (accuracy), `score_impact` (mean F1 + exact), and `*_card` wrappers to `ScoreCard` |
| `config.py` | `RWXConfig` (n, seeds, headline metric, baseline name) |
| `model.py` | `RWXBlastRadiusModel` (the `TrackSpec`): `ladder`, `solve_culprit/solve_impact`, `evaluate`, `run`; registers the track |
| `cli.py` | `python -m rwx_blast_radius [--n] [--dev-seed] [--hidden-seed] [--json] [--offline]` |

## 3. How it reasons about the task (the ladder)

The ladder is the weak→strong list the PLAYBOOK says to keep (never delete a
version that scored). Culprit and impact climb in lock-step; each level adds the
same modelling insight, so one rung pairs them:

| Rung | Culprit | Impact | Insight |
| --- | --- | --- | --- |
| v0 latest / run-all | newest commit | every test | the board's Baseline row |
| v1 surface text / name match | commit whose file appears in the log | test named after the file | trust the log/convention — fragile |
| v2 static import cone | nearest commit in the failing test's static import closure | static import closure | follow imports |
| v3 symbol from error + re-exports | which commit changed the *symbol named in the error* | + package `__init__` re-exports | read the error, not just the path |
| v4 full graph + semantic diff | add dynamic imports + data-file reads; ignore comment-only diffs | same full graph | model the real dependency |

The headline is culprit **accuracy**; impact **F1** and **exact-match** ride
along in the same `ScoreCard` so the second task is never hidden.

## 4. Quick start

### Python

```python
from buildathon_core import Harness, get_track, render_report
import rwx_blast_radius                      # importing registers the track

report = Harness(n=100).run(get_track("rwx_blast_radius"))
print(render_report(report))                 # the RESULTS.md table
print(report.best.solution.name, report.best.hidden.headline)

# Direct solver API on one case:
from rwx_blast_radius import RWXBlastRadiusModel
m = RWXBlastRadiusModel()
m.solve_culprit(case, level=4)               # -> "c3"
m.solve_impact(case, level=4)                # -> ["tests/test_x.py", ...]
```

### CLI

```bash
cd "<repo root>"
export PYTHONPATH="common:rwx_blast_radius_model"   # Windows: PYTHONPATH="common;rwx_blast_radius_model"
python -m rwx_blast_radius --n 100
python -m rwx_blast_radius --n 100 --json
```

## 5. Configuration (`RWXConfig`)

| Field | Default | Why |
| --- | --- | --- |
| `n` | `100` | cases per split; the site's worked example is "100 test cases" |
| `dev_seed` | `1` | the dev split you tune on |
| `hidden_seed` | `9001` | a far-apart seed so hidden stands in for unseen cases |
| `headline_metric` | `accuracy` | culprit-finding accuracy, the one published number |
| `baseline_name` | `v0 latest / run-all` | the board's Baseline row |

RWX allows **100 submissions/hour**, so this track tolerates probing — but local
validation is still cheaper than a submission.

## 6. Techniques implemented

| Technique | Where | Note |
| --- | --- | --- |
| Static import-graph construction from source text | `solvers.static_deps` | `from x import y`, `import x` |
| Package re-export edges (`__init__` forwarding) | `solvers.static_deps(packages=True)` | catches re-exports |
| Dynamic-import edges (`importlib.import_module("…")`) | `solvers.static_deps(dynamic=True)` | invisible to a naive parser |
| Data-file dependency edges (`open("…json")`) | `solvers.static_deps(data=True)` | data drives tests |
| Transitive closure with hop distance | `solvers.closure` | nearest-in-cone tie-break |
| Error-symbol extraction from the CI log | `solvers.culprit_v3_symbol_only` | read the traceback |
| Comment-only-diff filtering | `solvers.strip_comments` | ignore benign edits |
| Accuracy / F1 / exact-match scoring | `evaluation.py` | the two published metrics |

## 7. Adapting to the real brief

When the real RWX brief drops at kickoff, the harness does not change — only the
data loader and the metric do (three edits):

1. Replace `data.py` so a "case" is the brief's real repo + commit batch + log.
2. Replace `evaluation.py` so the metric matches the brief exactly (same
   tolerance, same averaging).
3. Keep `solvers.py` (the dependency-graph modelling) and the ladder; re-run the
   `Harness`, reproduce the baseline, climb.

`examples/real_brief_example.py` walks these edits on a single hand-built case.

## 8. Composing with the shared core

`RWXBlastRadiusModel` **is a** `buildathon_core.TrackSpec`: `name`,
`metric_name`, `baseline_name`, a `ladder`, and `evaluate(n, dev_seed,
hidden_seed) -> TrackReport`. It imports only `buildathon_core`, never another
track. The `Harness` finalizes statuses (baseline / beats / below / best) and
`render_report` renders the table every track's `RESULTS.md` shares.

## 9. Evaluation

```bash
python -m rwx_blast_radius --n 100
```

Local results on the synthetic generator: culprit accuracy climbs
26% → 76% → 100% as the solver uses the error symbol and then the full
dependency graph; impact F1 climbs to exact once dynamic imports and data-file
reads are modelled. The 100% ceiling is a property of *synthetic* data with a
knowable generator; on the real hidden set it stands for "the modelling is
right," not "solved."

## 10. Limitations and failure modes

- Synthetic data with a knowable generator makes a 100% ceiling reachable; the
  real hidden set will not be that clean. Treat the ceiling as "modelling is
  right," not "solved."
- `static_deps` is regex-based, not an AST import resolver; relative imports,
  aliased imports and conditional imports beyond the generated styles are not
  modelled. Swap in an AST pass for the real brief.
- The culprit heuristic assumes the breaking change is in the failing test's
  dependency cone; a flaky-infra failure or a test-data-only break would need a
  different signal.
- `strip_comments` treats any `#…` as a comment, including `#` inside a string
  literal — fine for the generator, worth hardening for real source.

## 11. How it was built

1. **Reproduce the metric** — a seeded synthetic monorepo generator with the
   hidden edges that make real blast-radius hard, scored by the site's own
   metric (accuracy; F1 for impact).
2. **Baseline, then climb** — v0 run-all/latest is the board's Baseline row;
   each rung adds one modelling insight (log text → import cone → error symbol →
   full graph), measured on dev and a different-seed hidden split so a gain has
   to generalize before it counts.
3. **Lift the shared half** — the dev/hidden split, the ladder, the status
   roll-up and the table moved into `buildathon_core`; this package keeps only
   the data, the metric, the solvers and the wiring.
4. **Gate it** — `tools/quality_gate.py` runs the suite, the CLI and the
   examples, and enforces the stdlib-only / packages-return-values invariants.
