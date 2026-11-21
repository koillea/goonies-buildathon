# Architecture — the binding contract

This repo follows the workflow of the reference repo
[`prebuilt-ai-technique-models`](https://github.com/KennethLei1492/prebuilt-ai-technique-models):
many heterogeneous units bound to **one shared contract** so a single harness can
drive, score and compare them. There, the units are six LLM pipeline models on
`pipeline_core`. Here, the units are the four Builders Buildathon tracks on
`buildathon_core`.

This document is the contract a track must satisfy. `tools/quality_gate.py`
enforces the static half of it.

## 1. One result, many internals

Every track owns its data generator, its scorer and its weak→strong ladder —
and these differ by nature:

| Track | Internal shape | Headline metric |
| --- | --- | --- |
| RWX Blast Radius | classification over synthetic repos | culprit accuracy (+ impact F1) |
| Databricks Shopping Sessions | fit-then-recommend from clickstream | Recall@20 (+ MRR@20) |
| Machina CAD De-ID | invariant-preserving transform | file pass rate (+ leak/broken/lost) |
| Builders Mech Royale | competitive tournament | top-2 placement rate (+ mean points) |

What they share is the **output**: a `ScoreCard` (headline + named metrics),
scored on a dev split and a different-seed hidden split, rolled into a
`TrackReport` with a status per rung. This is the same "uniform `TaskResult`,
heterogeneous models" rule his `pipeline_core` enforces.

## 2. The `TrackSpec` protocol (section the gate checks)

A track package MUST:

1. Expose a class implementing `buildathon_core.TrackSpec`:
   - attributes `name: str`, `metric_name: str`, `baseline_name: str`;
   - a `ladder: list[Solution]` property (weakest first);
   - `evaluate(*, n: int, dev_seed: int, hidden_seed: int) -> TrackReport`.
2. Register its instance on import: `MODEL = register_track(<Model>())`.
3. Score the **dev** split from `dev_seed` and the **hidden** split from a
   *different* `hidden_seed`. Never tune on the hidden split.
4. Lay out its package the same way (`data.py`, `evaluation.py`, `solvers.py`,
   `config.py`, `model.py`, `cli.py`, `__main__.py`, `__init__.py`), plus
   `README.md` (the 11-section template), `examples/`, and `tests/`.

## 3. Invariants (the static gate)

`tools/quality_gate.py` fails the build if any track package:

- **imports a third-party module.** Pure Python standard library only (plus
  `buildathon_core`). The scorer fleet runs untrusted code in a minimal sandbox,
  so this is a hard rule (PLAYBOOK). *(Deviation from his `pipeline_core`, which
  uses pydantic + anthropic; see `common/README.md`.)*
- **calls `print(` inside a package module.** CLIs (`cli.py`, `__main__.py`)
  print; package logic returns values the harness renders. This keeps every
  track composable and testable without capturing stdout.

The dynamic gate additionally runs the full pytest suite, every track CLI, and
every example offline.

## 4. Why this shape

- **Reproduce the metric locally first.** The contract forces a dev/hidden split
  on every track, which is the buildathon's entire strategy (see
  [`METHODOLOGY.md`](METHODOLOGY.md)).
- **Keep every version.** The ladder is a first-class list; nothing that scored
  is deleted, so a regression always has a fallback.
- **One harness, one table.** `Harness.run(spec)` + `render_report(report)` is
  the single path from a track to its `RESULTS.md`, the way
  `examples/enterprise_pipeline.py` is the single wiring in his repo.
- **Swappable when the brief drops.** Because the metric and data live behind
  the contract, adapting to the real brief is three edits (`data.py`,
  `evaluation.py`, keep `solvers.py`), not a rewrite.
