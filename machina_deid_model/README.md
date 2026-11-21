# machina_deid — Machina CAD De-ID

The Machina CAD De-ID practice track, restructured as an installable package on
the shared [`buildathon_core`](../common/README.md) contract. It mirrors the
layout of [`rwx_blast_radius_model`](../rwx_blast_radius_model) exactly.

## 1. Purpose

Strip everything that identifies the customer, people, part or programme from a
CAD file while leaving the geometry valid and useful engineering data intact —
so the file can be shared or fed to ML without a compliance leak. Here the files
are synthetic STEP (ISO 10303-21) text. The published metric is the **file pass
rate**: a file passes only if it still parses, its geometry is unchanged, *and*
no identifier leaks anywhere.

Why it is a real company problem: Machina works in CAD/manufacturing, and
manufacturers cannot share CAD or train on it without leaking who the customer
is, what programme it is for, and who designed it. A reliable de-identifier
removes a concrete compliance blocker.

## 2. Architecture (module table)

| Module | Role |
| --- | --- |
| `machina_deid/data.py` | Synthetic STEP generator (`make_case`, `dataset`, `COMPANIES`/`PEOPLE`/…) + STEP parsing helpers a scorer needs (`parse`, `decode_x2`, `geometry_signature`, the record/number/string regexes). Pure data. |
| `machina_deid/evaluation.py` | The strict scorer: `check` (one file) and `score` (rates over cases), the `retained` harmless-label proxy, and `deid_card` → a `ScoreCard`. |
| `machina_deid/solvers.py` | The de-identifiers `v0`…`v5` and the `ALL` weak→strong ladder. |
| `machina_deid/config.py` | Frozen `MachinaDeidConfig` (n, seeds, `headline_metric="pass_rate"`, `baseline_name="v0 do nothing"`). |
| `machina_deid/model.py` | `MachinaDeidModel` — the `TrackSpec`. `evaluate(n, dev_seed, hidden_seed) → TrackReport`; `MODEL = register_track(...)`. |
| `machina_deid/cli.py`, `__main__.py` | `python -m machina_deid` → the dev-vs-hidden table (or `--json`). |

## 3. How it reasons / the ladder

A redactor fails two *opposite* ways — **leak** (scrub too little) and
**destroy** (scrub too much) — and the pass condition forbids both at once. The
ladder climbs out of that trap:

| Rung | Idea | Hidden pass |
| --- | --- | --- |
| v0 do nothing | baseline; pass the file through | 0% (leaks everywhere) |
| v1 scrub header only | blank header strings | 0% (leaks into labels/comments/escapes) |
| v2 + PERSON/ORG/PRODUCT + comments | blank the identity records too | 0% (leaks in geometry labels and `\X2\` escapes) |
| v3 blank every string | no leaks — the other failure | 0% (destroys schema name + units) |
| v4 schema allowlist | blank all but schema/unit records + safe keys | **100%** (but drops harmless labels) |
| v5 seed-and-propagate | learn the file's own identity tokens, remove exactly those everywhere | **100%** (and keeps harmless labels) |

v5 is the lesson: learning the identifiers from the document itself beats both a
fixed denylist (misses novel names) and a blanket blank (breaks the file), and
it decodes `\X2\` unicode escapes before matching so escaped names cannot hide.

## 4. Quick start

Python:

```python
from buildathon_core import Harness, get_track, render_report
import machina_deid            # registers the track on import

report = Harness(n=100).run(get_track("machina_deid"))
print(render_report(report))   # the same table shape as every RESULTS.md
```

CLI:

```bash
PYTHONPATH="common:machina_deid_model" python3 -m machina_deid --n 100
PYTHONPATH="common:machina_deid_model" python3 -m machina_deid --n 100 --json
```

## 5. Configuration

`MachinaDeidConfig` (frozen dataclass): `n`, `dev_seed`, `hidden_seed`,
`headline_metric="pass_rate"`, `baseline_name="v0 do nothing"`. Machina's board
is **2 submissions/hour**, so you cannot probe the hidden set — every submission
must be chosen by a trusted local validation split. The invariant is strict:
parses + geometry unchanged + no leak + required data kept, all at once, so a
*leak* OR a *corruption* each score a file zero.

## 6. Techniques

- STEP record parsing with regexes (`#id=TYPE(...)`), string-literal blanking,
  and `\X2\…\X0\` unicode-escape decoding before any identifier match.
- Separate scoring of the two failure modes (leak vs. broken) plus a `retained`
  proxy for harmless-label survival, so you see *why* a file failed.
- Seed-and-propagate: derive identity tokens from the file's own header /
  PERSON / ORGANIZATION / PRODUCT records, then remove exactly those tokens
  everywhere while preserving schema strings, units and the material.

## 7. Adapting to the real brief

When the real brief drops at kickoff, the harness does not change — only the
data and the metric do. Three edits (see `examples/real_brief_example.py`):

1. Replace `data.py` so a "case" is the brief's real file format (could be
   DXF / IGES / native CAD or a metadata JSON) with the real truth set.
2. Replace `evaluation.py` so `check` matches the brief's real pass conditions
   (add identifier classes: addresses, phone numbers, GD&T notes), still
   reporting leak / broken / lost separately.
3. Keep `solvers.py` (seed-and-propagate) and the ladder.

## 8. Composing (how it sits on buildathon_core)

`MachinaDeidModel` implements the `TrackSpec` protocol — `name`, `metric_name`,
`baseline_name`, a `ladder`, and `evaluate(...)`. Importing the package calls
`register_track(MachinaDeidModel())`, so the shared `Harness` and
`tools/quality_gate.py` discover the track by name without importing this
package directly. Each rung reports one uniform `ScoreCard` (headline = pass
rate; `metrics` = pass_rate/leak/broken/lost/retained), scored on a dev split
and a different-seed hidden split, then rolled up by `TrackReport.finalize()`.

## 9. Evaluation

`evaluate` scores every rung on `dataset(n, dev_seed)` and
`dataset(n, hidden_seed)` (a different seed = the held-out "hidden" split). The
headline is the pass rate; `leak`, `broken`, `lost` and `retained` ride along.
`render_report` emits the markdown table; `generalizes` flags dev and hidden
agreeing — the submission gate. On this synthetic generator the climb is
0% → 100%; on the real hidden set those ceilings stand for "the modelling is
right," not "solved."

## 10. Limitations

- Synthetic STEP text with a knowable generator: the 100% ceiling is a property
  of that generator, not proof the real task is solved.
- The scorer's "sensitive" set and "required strings" are the practice guess;
  the real brief will differ.
- Pure stdlib only; no real STEP kernel, so geometry validity is checked by
  entity-id/type order and a numeric signature, not by a CAD engine.

## 11. How it was built

Lifted behaviour-preserving from `practice/machina_cad_deid/` (`bench.py`,
`solutions.py`, `run.py`): data generation + STEP parsing → `data.py`, the
`check`/`score` scorer + the `retained` metric from `run.py` → `evaluation.py`,
the v0→v5 ladder → `solvers.py`. Scores match the original `run.py`
(`RESULTS.md`). Pure Python standard library only; the one non-stdlib import is
`buildathon_core`.
