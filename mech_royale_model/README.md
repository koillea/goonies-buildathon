# mech_royale

The Builders **Mech Royale** practice track, packaged as an installable
`TrackSpec` on the shared `buildathon_core` contract. It mirrors the layout of
`rwx_blast_radius_model`: a track owns its data generator, its scorer and its
weak→strong ladder internally, and exposes only the uniform surface the shared
harness drives.

## 1. Purpose

Anticipate the Builders "Mech Royale" track: you submit a **bot**, it fights
other teams' bots in a battle-royale arena, and the score is how well it
**places** over many hidden matches. The real rules are unknown, so this is a
stand-in arena with the mechanics such games usually share (a shrinking safe
zone, ranged attacks that fall off with distance, healing, simultaneous turns).
The point of the package is the *workflow*: reproduce the metric locally, climb
it on a held-out split, and trust the local validation set — not the
leaderboard. When the real brief drops, swap the arena and the metric and keep
everything else.

## 2. Architecture

| Module | Role |
| --- | --- |
| `mech_royale/data.py` | The arena. `play(bots, seed)` runs one match; `evaluate(candidate, field, n_matches, seed)` plays a candidate against a field over many seeded matches and returns `(mean points, win rate, top-2 rate)`. Plus `dist`, `zone_radius`, `in_zone`, `hit_chance`, `PLACE_POINTS` and the `SIZE / N_MECHS / MAX_TURNS / RANGE` constants. Copied verbatim from the track's `bench.py`. |
| `mech_royale/solvers.py` | The bots (`b_random`, `b_aggro`, `b_camper`, `v2_zone_focus`, `v3_survivor`, `v4_lookahead`), the baseline `FIELD`, the `STRONG_FIELD`, and the `ALL` weak→strong ladder. Verbatim from `solutions.py` (only the import is rebound to `.data`). |
| `mech_royale/evaluation.py` | `score_candidate(...)` runs `data.evaluate` and packages its tuple into a `buildathon_core.ScoreCard` (headline = top-2 rate; `metrics` also carry mean points and win rate). |
| `mech_royale/config.py` | Frozen `MechRoyaleConfig`: `n` (matches per cell), dev/hidden seeds, `headline_metric="top2_rate"`, `baseline_name="v0 random"`. |
| `mech_royale/model.py` | `MechRoyaleModel`, the `TrackSpec`: `name`, `metric_name`, `baseline_name`, a `ladder`, and `evaluate(...) -> TrackReport`. Registers `MODEL` on import. |
| `mech_royale/cli.py`, `__main__.py` | `python -m mech_royale` — score the ladder dev-vs-hidden, table or JSON. |

## 3. How it reasons — the ladder

The ladder climbs by *modelling the game*, not reacting to the surface. Each rung
is scored against the strong field (the better bots, including copies of bots
that are themselves on the ladder):

| Rung | Idea | Hidden top-2 vs strong field |
| --- | --- | --- |
| `v0 random` | move or shoot at random (the Baseline row) | 12% |
| `v1 chase and shoot nearest` | chase the nearest enemy, fire in range | 29% |
| `v1b camp the centre` | sit in the middle and shoot | 16% |
| `v2 zone-aware, focus weakest` | never leave the next zone; focus the target you can finish | 32% |
| `v3 survivor: avoid fights, finish kills` | let others trade damage; duel only in the endgame | 37% |
| `v4 one-step lookahead on expected damage` | score every action by expected damage dealt minus taken | **47%** |

(Numbers from 300 matches per cell — the original `run.py`. At the small `n`
tests and the CLI default use, match-sampling noise can reorder `v3` and `v4`;
the wide gap above *random* is what is stable.)

## 4. Quick start

Python:

```python
from buildathon_core import Harness, get_track, render_report
import mech_royale                       # registers the track on import

report = Harness(n=100).run(get_track("mech_royale"))
print(render_report(report))             # the same table shape as every RESULTS.md
print(report.best.solution.name)
```

CLI:

```bash
# from the repo root, with the package on PYTHONPATH
PYTHONPATH="common:mech_royale_model" python -m mech_royale --n 100
PYTHONPATH="common:mech_royale_model" python -m mech_royale --n 50 --json
```

`--n` is the number of matches per cell; `--dev-seed` / `--hidden-seed` pick the
two splits; `--json` emits the report as JSON; `--offline` is accepted and is a
no-op (everything is already offline).

## 5. Configuration

`MechRoyaleConfig` (frozen dataclass) holds the defaults, pulled from
`buildathon_core` so every track shares the same seeds:

- `n` — matches per cell (default `DEFAULT_N`). The tournament is **stochastic**,
  so this is a sample size: raise it for a steadier headline, lower it for speed.
- `dev_seed` / `hidden_seed` — the dev split and the far-apart hidden split. The
  hidden seed stands in for match schedules you have never seen. Never tune on it.
- `headline_metric = "top2_rate"` — what `run.py` ranks on.
- `baseline_name = "v0 random"` — the board's Baseline row (the v0 rung).

Submission budget: the **Builders board allows 4 submissions/hour** — looser
than Databricks/Machina (2/hour), tighter than RWX (100/hour) — so a few probes
are affordable, but a local validation set still decides what to submit.

## 6. Techniques

- **Not dying beats killing until the endgame.** The survivor and lookahead bots
  win by letting others trade damage first (`v3`, `v4`).
- **An explicit expected-value calculation beats hand-tuned rules.** `v4` scores
  each legal action by *hit chance × damage dealt* minus *expected incoming*,
  with caution that drops as enemies die — that single change lifts hidden top-2
  from 37% to 47%.
- **Always respect the shrinking zone.** Standing outside the next safe zone is
  free self-damage; every smart rung refuses to leave it.
- **Keep every version.** The `ALL` ladder is the weak→strong record; nothing
  that scored is deleted, so a fallback is always one rung away.

## 7. Adapting to the real brief

When the kickoff brief lands, three edits (see `examples/real_brief_example.py`):

1. **Replace `data.py`** so `play` runs the real game engine and `evaluate` runs
   the real match/scoring protocol (grid or continuous, the real action set, the
   real win condition, the per-turn compute cap).
2. **Replace `evaluation.py`** so `score_candidate` packages the brief's real
   headline metric into a `ScoreCard`.
3. **Keep `solvers.py` and `model.py`** — re-point the bots at the real action
   set and keep the weak→strong climb and the self-play strong field.

## 8. Composing on buildathon_core

The track never imports the harness; it registers a `TrackSpec` and the harness
consumes it. `MechRoyaleModel` implements `name`, `metric_name`, `baseline_name`,
a `ladder` property returning `list[Solution]`, and
`evaluate(*, n, dev_seed, hidden_seed) -> TrackReport`. On import,
`register_track(MechRoyaleModel())` publishes it so `get_track("mech_royale")`
and `tools/quality_gate.py` discover it by name. Each rung's result is a
`SolutionResult(Solution, dev_card, hidden_card)`; `ScoreCard.headline` is the
top-2 rate and `metrics` carry the secondary scalars. `report.finalize()` assigns
each rung a `Status` (BASELINE / BEATS_BASELINE / BELOW_BASELINE / BEST).

## 9. Evaluation

`evaluate` plays every rung against the strong field over `n` matches with the
dev seed, then again with a different hidden seed. A rung "generalizes" when its
dev and hidden headlines agree within tolerance — the submission gate. Headline
numbers reproduce the original `run.py` within match-sampling noise; at 300
matches per cell the hidden top-2 climb is 12% → 29% → 32% → 37% → 47%.

## 10. Limitations

- **The arena is invented.** Until the real brief drops, these are anticipated
  mechanics, not the real game; the ladder's *shape* is the asset, not its exact
  numbers.
- **Stochastic metric.** Top-2 rate is a sample statistic; at small `n` the
  ordering of the top rungs is noisy, so the CLI/tests assert the climb above
  random rather than a single winner.
- **`b_random` carries a module-global RNG.** It is copied verbatim and so its
  score shifts slightly with call order — harmless noise for a baseline, but it
  is why `v0 random` can read a few points off the original run.
- **No search deeper than one ply.** `v4` is a one-step lookahead; a real engine
  may reward (or time out) a deeper expectimax.

## 11. How it was built

Lifted from `practice/builders_mech_royale/` (`bench.py`, `solutions.py`,
`run.py`, `NOTES.md`) and restructured to match `rwx_blast_radius_model` exactly:
the arena and scorer went into `data.py` verbatim, the bots and ladder into
`solvers.py`, the metric-to-`ScoreCard` adapter into `evaluation.py`, and the
`run.py` logic (score the ladder against the strong field on dev + hidden) into
`MechRoyaleModel.evaluate`. Pure Python standard library only, plus
`buildathon_core` — the scorer-fleet invariant the PLAYBOOK requires.
