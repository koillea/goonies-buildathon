# Methodology — how the tracks compose into a workflow

His repo has `COMPOSITION_PATTERNS.md`: how the six models combine, with the
literature behind each edge. This repo's "composition" is the **workflow** every
track runs through — the scoreboard-buildathon loop — plus how the four tracks
plug into one harness. The kickoff checklist lives in
[`../PLAYBOOK.md`](../PLAYBOOK.md); this file is the standing method.

## The one loop every track runs

```
read brief  →  reproduce the metric locally  →  split a hidden-style validation set
      →  baseline on the board  →  [ improve → measure on dev AND hidden → if both
         move together, submit → record the board delta ]  →  repeat → lock the best
```

`buildathon_core` encodes the middle of this loop so no track reimplements it:

- **reproduce the metric** → each track's `evaluation.py` returns a `ScoreCard`
  whose `headline` is the published metric.
- **split a hidden-style set** → `Harness` always scores `dev_seed` and a
  different `hidden_seed`; `SolutionResult.generalizes` is the "dev and hidden
  agree" gate.
- **keep every version** → the `ladder` is a first-class `list[Solution]`.
- **one table** → `render_report` writes the `RESULTS.md` shape for every track.

## The standing rules (why each is in the contract)

1. **Check assumptions against the data before building on them.** The biggest
   practice-run error (Databricks, −13 pts) was one unverified assumption. The
   dev/hidden split makes a wrong assumption show up as dev-and-hidden
   disagreement before it costs a submission.
2. **Simple-and-correct beats clever-and-fragile on hidden data.** The ladder
   starts at the dumbest baseline and only adds complexity when a simpler rung
   is measurably maxed out. The `Status` roll-up shows whether the extra rung
   actually beat the baseline on *hidden*, not dev.
3. **Model the real dependency, don't pattern-match the surface.** RWX went 26%
   → 100% by following the import/dependency graph instead of the log text.
4. **Hold the invariant.** Machina only scores if the file still parses and the
   geometry is unchanged — a de-identifier that leaks OR that corrupts both
   score zero. Every pass condition is measured separately in the `ScoreCard`
   metrics, not collapsed into one pass/fail.
5. **Tune on a split inside your own data, never on the leaderboard.** The
   hidden split is the practice test; the board is the final exam.
6. **Make it a company could use.** Each track is a real company's real problem;
   the winning number is also a hiring conversation. The package layout, README
   and tests are written to be shown to the sponsor.

## How the four tracks plug into one harness

```python
# examples/buildathon_harness.py
import rwx_blast_radius, databricks_shopping, machina_deid, mech_royale  # register on import
from buildathon_core import Harness, all_tracks, render_report

for spec in all_tracks():
    print(render_report(Harness(n=50).run(spec)))
```

Each `import` registers a `TrackSpec`; `all_tracks()` discovers them; one
`Harness` scores them the same way. That is the direct analog of his
`EnterprisePipeline` wiring all six models through one `Tracer` — here, one
harness drives all four tracks through one contract.

## Picking a track by points-per-hour

Two people, ~40 build hours, four tracks, winner-takes-all per track. Favor a
track where you can (a) reproduce the exact metric locally — every track here
already does — (b) see a clear ladder of improvements — the `ladder` is that
ladder — and (c) submit enough to matter (RWX 100/hr tolerates probing;
Databricks and Machina at 2/hr demand that you trust the hidden split).
