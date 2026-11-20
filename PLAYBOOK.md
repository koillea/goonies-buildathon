# Kickoff playbook — what to do when the real briefs drop (Fri 6:00 PM ET)

A scoreboard buildathon is not a demo hackathon. There is no pitch, no slides, no judges to impress — only a number on hidden tests. The whole game is: reproduce the metric locally, climb it, submit the climb. This playbook is the first 90 minutes and the standing rules.

## First 30 minutes (before writing any solution)

1. **Read all four briefs. Pick the one with the best points-per-hour**, judged on:
   - Can we reproduce the exact metric locally? (If not, we're flying blind — deprioritize.)
   - Is there a visible ladder of improvements, or does it need one big risky model?
   - Submission rate: 100/hr (RWX) tolerates probing; 2/hr (Databricks, Machina) demands local validation.
   - Does the starter kit give training data / examples? More data = safer local validation.
2. **Copy the matching `practice/<folder>` as the starting skeleton.** Replace `bench.py`'s data loader and scorer with the *real* format and the *real* metric, exactly as the brief states them. Keep `run.py`'s dev-vs-hidden structure.
3. **Reproduce the baseline.** Implement the dumbest thing (predict the majority, recommend the most popular, return everything) and confirm your local score is sane. Submit it once to put a row on the board and confirm your local scorer agrees with theirs. If they disagree, your scorer is wrong — fix that before anything else.

## The loop (rest of the weekend)

```
read brief  →  reproduce metric locally  →  split a hidden-style validation set
      →  baseline on the board  →  [ improve → measure locally → if it beats
         validation, submit → record board delta ]  →  repeat → lock best pick
```

- **One change at a time, measured on validation.** If local says better but the board says worse, your validation set doesn't match the hidden distribution (often a time split vs random split, or a leak). Fix the split, not the model.
- **Keep every version and its score** (the `solutions.py` weak→strong list is exactly this). Never delete a version that scored; you may need to fall back.
- **Spend submissions like money.** On a 2/hr track, that's ~80 all weekend. Only submit a version your local score says is a new best.
- **Before the cutoff, explicitly pick the submission to enter in the final.** The site enters your best score by default, but confirm it.

## Standing rules (hard-won, see each track's NOTES.md)

1. **Check assumptions against the data before building on them.** The single biggest practice-run error (Databricks, −13 pts) was an unverified assumption. Write a 3-line script that measures the thing you're about to assume.
2. **Simple-and-correct beats clever-and-fragile** on hidden data. Add complexity only when a simpler version is measurably maxed out.
3. **Model the real dependency, don't pattern-match the surface.** RWX went from 26% to 100% by following the actual import/dependency graph instead of guessing from the log text.
4. **Hold the invariant.** Machina's task only scores if the file still parses and geometry is unchanged — a de-identifier that leaks OR that corrupts both score zero. Know every pass condition and test each separately (the scorer here reports leak / broken / lost-data rates, not just pass).
5. **Tune on a split inside your own data, never on the leaderboard.** The board is the final exam; the validation set is your practice test.
6. **Make it a company could use.** Every track is a real company's real problem. The winning number is also a hiring conversation — write code you'd show them (clear structure, a NOTES.md explaining the approach).

## Division of labor (team of 1–2)

- If 2 people: one owns the scorer + validation harness (the thing you trust), the other owns the modeling. They meet at `run.py`.
- If 1 person: get the harness trustworthy first; then you can iterate on the model with confidence while you're tired.

## What to run

```bash
python3 practice/rwx_blast_radius/run.py
python3 practice/databricks_shopping_sessions/run.py   # ~25s (grid search)
python3 practice/machina_cad_deid/run.py
python3 practice/builders_mech_royale/run.py
```

Pure Python standard library only (no numpy/sklearn needed), so it runs anywhere the scorer fleet might.
