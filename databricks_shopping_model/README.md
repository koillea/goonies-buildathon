# databricks_shopping

The Databricks **Shopping Sessions** practice track, restructured as an
installable package that sits on [`buildathon_core`](../common/README.md). It
mirrors the layout of [`rwx_blast_radius`](../rwx_blast_radius_model/) exactly:
the track owns its data generator, its scorer and its weak→strong ladder, and
exposes one uniform `TrackSpec` surface the shared harness drives.

## 1. Purpose

Predict what a shopper interacts with **next** from the start of their session —
the engine behind "customers also viewed / bought." Databricks sells the data +
ML platform, and session-based next-item recommendation on e-commerce
clickstream (the shape of RecSys 2015 / Kaggle OTTO / KDD Cup 2023) is a
canonical, revenue-driving workload that runs on exactly that platform. The real
brief opens at kickoff; until then this reproduces the task on synthetic
shoppers so the metric and the ladder can be built and validated offline.

Headline metric: **Recall@20**, with **MRR@20** measured alongside.

## 2. Architecture

| Module | Responsibility |
| --- | --- |
| `data.py` | The synthetic `World` + session simulator and the `make` / `build_train` / `eval_set` splitters. Long-tail popularity, week-to-week popularity drift, within-category browsing, complementary items, revisits. Copied verbatim from the original `bench.py`. |
| `evaluation.py` | `score(recommend, cases, k=20) -> (recall, mrr)` (verbatim) plus `recommend_card`, which returns a `buildathon_core.ScoreCard` with `headline = recall` and `metrics = {"recall", "mrr"}`. |
| `solvers.py` | The builder functions `v0`…`v6`: each takes `train` and returns `recommend(prefix) -> ranked items`. Verbatim from `solutions.py`. |
| `config.py` | Frozen `DatabricksShoppingConfig`: `n`, seeds, `k=20`, `headline_metric="recall@20"`, `baseline_name`, plus the world seed and the `n → make()` scaling. |
| `model.py` | `DatabricksShoppingModel` (the `TrackSpec`): `ladder`, `evaluate`, `run`; registers `MODEL` on import. |
| `cli.py` / `__main__.py` | `python -m databricks_shopping` — table or JSON, always offline. |

## 3. How it reasons — the ladder

This is a **fit-then-recommend** track: a builder fits on the training sessions,
then recommends the next item for the prefix of an unseen session. The ladder
climbs by modelling the real transition signal, not by leaning on popularity:

| Rung | Idea |
| --- | --- |
| v0 all-time popularity | most-frequent items overall — the **Baseline** row. |
| v1 recent popularity | time-decayed popularity; drift makes recency help a little. |
| v2 next-item bigram | what usually comes right after the last item; popularity fill. |
| v3 session co-visitation | symmetric co-occurrence over a window from every session item. |
| v4 v3 tuned | grid-search v3's knobs on a time split inside train, then refit. |
| v5 hybrid | directional next-item counts from the last item + weaker votes from earlier items + a revisit bonus. |
| v6 v5 tuned | grid-search the hybrid's knobs on the time split, then refit. |

Nothing that scored is ever deleted (PLAYBOOK) — every rung stays in the ladder.

## 4. Quick start

Python:

```python
from buildathon_core import Harness, get_track, render_report
import databricks_shopping            # registers the track on import

report = Harness(n=100).run(get_track("databricks_shopping"))
print(render_report(report))
```

CLI:

```bash
PYTHONPATH="common:databricks_shopping_model" python -m databricks_shopping --n 100
PYTHONPATH="common:databricks_shopping_model" python -m databricks_shopping --n 100 --json
```

Flags: `--n`, `--dev-seed`, `--hidden-seed`, `--json`, `--offline` (a no-op; the
track is always offline on seeded synthetic data).

## 5. Configuration

`DatabricksShoppingConfig` (frozen dataclass):

* `n` — eval cases per split (default `DEFAULT_N` = 100).
* `dev_seed` / `hidden_seed` — seed the two eval splits; they **must differ** so
  hidden stands in for unseen sessions (defaults 1 / 9001 from `buildathon_core`).
* `k = 20`, `headline_metric = "recall@20"`, `baseline_name = "v0 all-time popularity"`.
* `world_seed = 7`, `per_week_factor = 3`, `val_cap = 1500` — how the harness
  `n`/seeds map onto the original `make()` (see §9).

Databricks is a **2-submissions-per-hour** track: you cannot probe the
leaderboard to iterate. The dev/hidden split, and the time-based split v4/v6 tune
on, are the only way to make progress. Never tune on hidden.

## 6. Techniques

What actually moved the score (on the full-scale original run):

* **Direction beats symmetry.** A *directional* next-item count (v2, v5, v6)
  beats *symmetric* session co-visitation (v3, v4): symmetry throws away the
  order of events.
* **A wrong assumption cost 13 points of Recall@20.** The first co-visitation
  versions *excluded the item the shopper is currently on*, assuming the next
  event is never the same item. Measuring the data showed it is the next item
  **~14%** of the time. That one assumption held the hybrid at 0.59 (losing to
  the trivial bigram's 0.68) until removed, after which it jumped to 0.73.
  **Always measure an assumption before building on it.**
* **Tune on a time-based split inside the training data.** v4/v6 grid-search on
  the latest *train* week (a random split would leak future popularity), then
  refit on everything. Dev and hidden scores agreeing is the signal the tuning
  generalises.

## 7. Adapting to the real brief

When the kickoff brief drops, the harness does not change — only the data loader
and the metric do. Three edits (see `examples/real_brief_example.py`):

1. Replace `data.py` so `train` is the real session logs and a case is a real
   `(prefix, next_item)` from a later time period.
2. Replace `evaluation.py` so the metric matches the brief exactly (watch for
   separate click / cart / order weighting, or next-basket instead of next-item).
3. Keep `solvers.py` (directional co-occurrence + recency + revisit) and the
   ladder — that structure is what transfers to real clickstream.

Biggest next lifts on real data: a gradient-boosted re-ranker over these
candidates, item metadata (category, price), and matrix factorization as an
extra candidate source.

## 8. Composing on buildathon_core

The track implements the `TrackSpec` protocol — `name`, `metric_name`,
`baseline_name`, a `ladder` of `Solution`s, and `evaluate(n, dev_seed,
hidden_seed) -> TrackReport`. Importing the package calls `register_track`, so
the shared `Harness` and `tools/quality_gate.py` discover it by name without
importing it directly. The harness scores dev + hidden, `finalize()` rolls up
statuses relative to the baseline and the best rung, and `render_report` emits
the one markdown table every `RESULTS.md` uses. Pure Python standard library
only; the sole non-stdlib import is `buildathon_core`.

## 9. Evaluation

`evaluate` builds one fixed synthetic `World` (`world_seed`), fits every rung on
one training split, and scores each on a dev eval split (`dev_seed`) and a
hidden eval split (`hidden_seed`). The two eval splits come from **different
seeds**, so hidden is unseen data — exactly as `rwx_blast_radius` generates its
dev and hidden datasets from different seeds.

The harness `n` maps onto the original `make()` parameters: `n` is the eval
cases per split, and training sessions per week scale with it
(`per_week = per_week_factor * n`, matching the original `per_week == 3 ·
n_eval`) so small `--n` runs finish in well under a second while keeping the
fit-then-recommend shape. v4/v6 tune on a time-based split inside `train`
(weeks `< WEEKS-2` fit, the last train week validates), capped at `val_cap`.

Each `ScoreCard` has Recall@20 as the headline and both Recall@20 and MRR@20 in
`metrics`. On the full-scale original data the hidden climb is **popularity
0.32 → bigram 0.68 → hybrid 0.73**; at the package's default `n=100` (a smaller
train) the same ordering holds at a lower absolute level.

## 10. Limitations

* The synthetic world is a stand-in; the real session format and metric are
  unknown until kickoff (click/cart/order weighting, next-item vs next-basket).
* Candidate generation only — no learned re-ranker, no item metadata. These are
  the documented next lifts, not implemented here.
* Absolute scores scale with the training size chosen for `n`; the **ordering**
  of the ladder is what is behaviour-preserving, not the exact numbers at small
  `n`. Use `--n 100`+ for numbers comparable to the original.

## 11. How it was built

Restructured from `practice/databricks_shopping_sessions/` (`bench.py`,
`solutions.py`, `run.py`). The data generator, the scorer and the `v0`…`v6`
builders are copied verbatim so behaviour is preserved; `run.py`'s hand-rolled
dev/hidden loop, the time-split tuning for v4/v6, and the results table were
lifted onto `buildathon_core`'s shared harness, contract and renderer. The only
new surface is the `TrackSpec` wiring in `model.py` and the `n → make()` mapping
in `config.py`.
