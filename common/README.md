# buildathon_core

The shared contract every track sits on. It plays the role `pipeline_core` plays
in the reference repo [`prebuilt-ai-technique-models`](https://github.com/KennethLei1492/prebuilt-ai-technique-models):
one result contract, a protocol a track implements, a registry, and a harness
that scores a dev-vs-hidden split and renders one table.

## Why it exists

The buildathon is a scoreboard, not a demo (see [`docs/METHODOLOGY.md`](../docs/METHODOLOGY.md)).
The whole game is: reproduce the track's metric locally, climb it on a held-out
validation split, submit only a climb your local score trusts. Every track
repeated that loop by hand (`bench.py` + `solutions.py` + `run.py`). This core
lifts the shared half — the dev/hidden split, the weak→strong ladder, the
status roll-up, the markdown table — into one place, exactly as his repo lifts
the request/result/trace machinery into `pipeline_core`.

## The contract

| Type | Meaning |
| --- | --- |
| `ScoreCard` | One solution's score on one split: a `headline` (the published metric, higher-is-better), a `metrics` dict (every named scalar — recall *and* MRR, F1 *and* exact-match), and `extras` for audit data. |
| `Solution` | One rung of the ladder: a named, described approach. Nothing that scored is ever deleted (PLAYBOOK). |
| `SolutionResult` | A `Solution` scored on `dev` and `hidden`, with a `status` and a `generalizes` flag (dev and hidden agreeing within tolerance — the submission gate). |
| `TrackReport` | Every rung scored, plus the seeds and metric name needed to render `RESULTS.md`. `finalize()` assigns statuses. |
| `Status` | `BASELINE` / `BEATS_BASELINE` / `BELOW_BASELINE` / `BEST` — the scoreboard analog of his `SUCCESS`/`PARTIAL`/`NEEDS_REVIEW`/`FAILED`. |

## The protocol

A track implements `TrackSpec`: `name`, `metric_name`, `baseline_name`, a
`ladder`, and one method `evaluate(n, dev_seed, hidden_seed) -> TrackReport`.
Internals are the track's own (a classifier, a fit-then-recommend recommender,
an invariant-preserving transform, a competitive tournament); only the result
shape is shared. A package registers its spec on import with `register_track`,
and the harness discovers it by name — the same "register once, picked up
everywhere" move as `register_profile` in his core.

## Harness

```python
from buildathon_core import Harness, get_track, render_report
import rwx_blast_radius            # registers the track on import

report = Harness(n=100).run(get_track("rwx_blast_radius"))
print(render_report(report))       # the same table shape as every RESULTS.md
```

## Deviation from his core

Pure Python standard library only (dataclasses + enum, no pydantic). The scorer
fleet runs untrusted code in a minimal sandbox, so this repo keeps the
"stdlib only" invariant the PLAYBOOK requires. The *shape* is his; the
dependency surface is smaller on purpose.
