# Goonies — Builders Buildathon

## RWX Blast Radius submission (this repo's top level)

`Dockerfile`, `selector.py` and `maps/maps.json` at the top of this repository are our entry for the RWX **Blast Radius** track: for each sqlglot patch, choose which tests to run and split them over up to 8 workers, minimising simulated CI seconds (busiest worker + 2 s per worker + 300 s per missed failing commit + CPU time).

**How it decides** (`selector.py`):
1. Parse the patch into the pinned-commit line numbers it touches.
2. Map each line to its innermost function. Run only the tests that executed that function's body when the maps were built. A change that a test never reaches cannot alter that test's run.
3. Lines outside any function (class attributes such as a dialect's `WEEK_OFFSET`, module tables) select every test that executed the file *or* instantiated a class defined there or in its bases. Code that runs only at import time selects the whole file's tests.
4. Fixture edits run the tests that opened that fixture. Test-method edits run that test. Anything the maps cannot vouch for (new or deleted files, test helpers, unknown files) runs every test, because a run-all (~37 s) is far cheaper than a miss (300 s).
5. Split the chosen tests longest-first over the worker count (1–8) that minimises busiest-worker time + 2 s per worker.

**The maps** (`build/`) are built once from sqlglot at the pinned commit `eb11aec`, and committed. They hold:
- per-test coverage, recorded with each test's own coverage context;
- the sqlglot classes each test instantiates, with their bases;
- the fixture files each test opens.

The suite's process pools run in-process during the build, with every task pickled and unpickled as a real process boundary would, so work done "in a worker" is credited to its test and `serde` (sqlglot's pickling) counts as used. Nothing is derived from any patch. Rebuild with `bash build/rebuild_maps.sh <tests.json>`.

**Local results on the 30 sample commits:**

| Selector | Simulated seconds | Misses |
|---|---|---|
| Starter (run every test, 3 workers) | 1210.5 | 0 |
| File-level coverage only | 1489.8 | 3 |
| This selector | **248.1** | **0** |
| Perfect oracle (only the failing tests) | 94.4 | 0 |

Selector CPU is about 0.12 s per batch. It uses the Python standard library only.

The submission files stay at the repository top because the RWX scorer expects them there and the `Dockerfile` copies them verbatim; they are the shipped *product* (the analog of `examples/enterprise_pipeline.py` in the reference repo), kept working while the practice harnesses below adopt the shared workflow.

---

## The workflow (mirrored from `prebuilt-ai-technique-models`)

This repo follows the workflow of the reference repo
[`KennethLei1492/prebuilt-ai-technique-models`](https://github.com/KennethLei1492/prebuilt-ai-technique-models):
many heterogeneous units bound to **one shared contract** so a single harness
can drive, score and compare them. There, the units are six LLM pipeline models
on `common/pipeline_core`, each a folder with a package + README + `examples/` +
`tests/`, gated by `tools/quality_gate.py` and documented in `docs/`. Here, the
units are the four buildathon tracks on `common/buildathon_core`, in exactly that
shape.

| Track folder | Package | What it does | Headline metric | Submit rate |
|---|---|---|---|---|
| [`rwx_blast_radius_model/`](rwx_blast_radius_model/README.md) | `rwx_blast_radius` | find the commit that broke the build / which tests a change impacts | accuracy (+ F1) | 100/hr |
| [`databricks_shopping_model/`](databricks_shopping_model/README.md) | `databricks_shopping` | predict the next item in an e-commerce session | Recall@20 (+ MRR@20) | 2/hr |
| [`machina_deid_model/`](machina_deid_model/README.md) | `machina_deid` | strip identifying data from CAD files, keep geometry valid | file pass rate | 2/hr |
| [`mech_royale_model/`](mech_royale_model/README.md) | `mech_royale` | submit a bot for a battle-royale arena | placement over matches | 4/hr |

Everything sits on [`common/buildathon_core`](common/README.md): the result
contract (`ScoreCard`, `Solution`, `TrackReport`, `Status`), the `TrackSpec`
protocol, the registry, and the `Harness` that scores a dev-vs-hidden split and
renders each `RESULTS.md`. The binding contract is
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md); the way the tracks compose into
one workflow is in [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md); the kickoff
checklist is [`PLAYBOOK.md`](PLAYBOOK.md).

## Quick start

```bash
pip install -e ".[dev]"                 # installs buildathon_core and all four track packages
python -m pytest -q                     # every suite, fully offline (pure stdlib)
python tools/quality_gate.py            # tests + CLIs + examples + static invariant checks
```

Run any track from the command line (pure stdlib, always offline). After
`pip install -e .` every package is importable:

```bash
python -m rwx_blast_radius --n 100
python -m databricks_shopping --n 100
python -m machina_deid --n 100
python -m mech_royale --n 50
```

Without installing, put `common` and the track folder on `PYTHONPATH`
(Windows splits on `;`, not `:`):

```bash
PYTHONPATH="common:rwx_blast_radius_model" python -m rwx_blast_radius --n 100
```

Run all four through the one harness (the analog of his `enterprise_pipeline.py`):

```bash
PYTHONPATH="common:rwx_blast_radius_model:databricks_shopping_model:machina_deid_model:mech_royale_model" \
  python examples/buildathon_harness.py --n 50 --write     # --write refreshes each RESULTS.md
```

## Why this design

1. **Reproduce the metric locally first.** Every track scores a dev split and a
   different-seed hidden split through the shared `Harness`, so a change only
   earns a submission when both move together — the buildathon's whole strategy.
2. **One contract, four implementations.** Classification, fit-then-recommend,
   invariant-preserving transform and competitive tournament all return the same
   `ScoreCard`/`TrackReport`, so the harness and the results table never change.
3. **Composition through a protocol, not imports.** A track never imports
   another; it implements `TrackSpec` and registers itself. The harness
   discovers it by name.
4. **Keep every version.** The weak→strong `ladder` is first-class, so a
   regression always has a fallback.
5. **Runs offline, pure stdlib.** No credentials, no third-party deps — the
   scorer-fleet invariant, enforced statically by `tools/quality_gate.py`.
6. **Swappable when the brief drops.** Adapting to a real brief is three edits
   (`data.py`, `evaluation.py`, keep `solvers.py` + ladder), not a rewrite.

## Results at a glance (synthetic data, held-out "hidden" split)

Run `python -m <track> --n 100` or `python examples/buildathon_harness.py --write`.

- **RWX:** culprit-finding climbs 26% → 76% → 100% as we use the error symbol and the real dependency graph; test-impact F1 climbs to exact once dynamic imports and data-file reads are modeled.
- **Databricks:** hidden Recall@20 0.32 (popularity) → 0.68 (bigram) → **0.73** (hybrid), after catching a costly wrong assumption.
- **Machina:** file pass-rate 0% (leaks) → 100%, by learning the file's own identity tokens and removing them everywhere while keeping schema strings and useful engineering data.
- **Mech Royale:** vs a strong field, hidden top-2 rate 12% (random) → **47%** (one-step lookahead on expected damage).

The 100%/exact ceilings are a property of *synthetic* data with a knowable generator; on the real hidden sets they stand for "the modeling is right," not "solved." See `docs/METHODOLOGY.md` and each track's README (section 11, *How it was built*).

## Repository layout

```
common/buildathon_core/        shared contract, protocol, registry, harness, telemetry
rwx_blast_radius_model/        package rwx_blast_radius   + README, examples, tests
databricks_shopping_model/     package databricks_shopping+ README, examples, tests
machina_deid_model/            package machina_deid       + README, examples, tests
mech_royale_model/             package mech_royale        + README, examples, tests
examples/buildathon_harness.py all four tracks wired together; examples/tests/ proves the wiring
docs/ARCHITECTURE.md           the binding contract (TrackSpec + invariants)
docs/METHODOLOGY.md            how the tracks compose into the buildathon loop
tools/quality_gate.py          CI gate: tests, CLIs, examples, static invariant checks
PLAYBOOK.md                    kickoff checklist for when the real briefs drop
selector.py, Dockerfile, maps/, build/   the live RWX Blast Radius submission (see top)
app/blastradius/               a standalone test-impact tool (git-aware), its own package
```

## Note on scope
These are **practice harnesses on invented data**, written before the real problems were released, to rehearse the workflow. They are not the real submissions. Nothing here is affiliated with Builders or the sponsors.
