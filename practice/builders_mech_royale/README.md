# Builders — Mech Royale

**Idea:** submit a bot that fights other teams' bots in a battle-royale arena; the score is how well it places over many matches.

**Sponsor & why it's real:** Builders (the host) — a bot arena ranked purely by a scoreboard, which is exactly the event's "no judging panel, a scoreboard" ethos. (If the real track turns out to be *build-a-game* instead, this harness is the wrong shape and we pivot at kickoff.)

**Anticipated problem / metric** (real brief opens at kickoff): a bot plays many matches against a field of other bots; score = placement points (+ kills) summed over hidden matches.

## Run it
```bash
python3 practice/builders_mech_royale/run.py   # writes RESULTS.md
```

## Current practice results (synthetic arena, held-out "hidden" seeds)
Hidden **top-2 rate vs a strong field**: random 12% → chase-and-shoot 29% → survivor 37% → **one-step lookahead on expected damage 47%**.

Lessons (full detail in `NOTES.md`): in a battle royale, **not dying beats killing** until the endgame; an explicit expected-value calculation (hit-chance × damage minus incoming) beats hand-tuned rules; always respect the shrinking safe zone.

## Files
`bench.py` (arena engine + scorer) · `solutions.py` (bots v0→v4) · `run.py` (many seeded matches vs two fields) · `NOTES.md` · `RESULTS.md`.

## When the real brief drops
Replace `bench.py` with the real game's rules and scoring protocol. Keep the structure: a local arena, an opponent field that includes your own previous bots, evaluation over many seeded matches. Then: self-play to find the current best, and a lookahead/expectimax over the real action set. Guard against the engine's per-turn compute cap.
