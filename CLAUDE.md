# Goonies — Builders Buildathon agent guide

Scoreboard buildathon (Ohio State, Nov 20–22 2026). Each of four tracks has one metric scored on hidden tests; the top score wins $5,000; submissions are rate-limited (Databricks and Machina 2/hour, Builders 4/hour, RWX 100/hour). There are no judges and no demo. The only output that counts is a higher number on hidden data. Strategy is in `PLAYBOOK.md`; the per-track domain playbook is in the `track-adaptation` skill.

## Workflow (slash commands)
- `/kickoff` — briefs dropped: triage all tracks in parallel and pick where to spend time.
- `/adapt-track <slug>` — brief → `tracks/<slug>/` harness: exact scorer, holdout that looks like the hidden set, v0 baseline.
- `/check-assumption <slug> <claim>` — measure a data fact before building on it.
- `/iterate <slug> [idea]` — one idea, one new version, decided by holdout score.
- `/submit-check <slug>` — gate before spending a submission.

## Layout and commands
- `practice/<track>/` — pre-kickoff rehearsals on synthetic data (seeds 1 and 9001). Reference only; do not adapt in place.
- `tracks/<slug>/` — the real tracks, copied from `.claude/templates/_track_skeleton/`. The interface is `load_cases()`, `split()`, `score()` in `bench.py`, and `SOLUTIONS` in `solutions.py`.
- `briefs/<slug>.md` — the real briefs, saved verbatim.
- Run a track with `python3 tracks/<slug>/run.py`. It prints the dev and holdout table, the noise band, and a final `SCORE=… SPLIT=holdout` line, and writes `RESULTS.md`.
- Practice: `python3 practice/<folder>/run.py`. App tests: `python3 -m pytest app/blastradius` (or `python3 app/blastradius/test_blastradius.py`).
- Use the Python standard library only, unless a brief explicitly allows more. The grader may run our code.

## Rules
1. Reproduce the official metric exactly before writing any solution, and confirm it with one baseline submission: local and board must agree. If they disagree, fix the scorer or the split first.
2. Make every decision on holdout, never on dev or on the leaderboard. Look only at the holdout aggregate. Do not read individual holdout examples.
3. Holdout differences smaller than the noise band (printed by `run.py`) are ties. Keep the simpler version and do not submit for a tie.
4. Make one change per version. Append `vN_<idea>` to `SOLUTIONS`, and never edit or delete a version that has scored, so you can always fall back.
5. Measure an assumption before building on it. Our practice run lost 13 points of Recall@20 to one assumption nobody checked.
6. A simple, correct version beats a clever, fragile one on hidden data. Add complexity only once the simple version has stopped improving.
7. Claims need evidence. Before saying something "improved" or is "done," quote the `SCORE=` line from a fresh run. If something crashed or was skipped, say so.
8. Log every submission (time, version, local holdout, board score) in `tracks/<slug>/NOTES.md`, and check that log before recommending another submission.
9. Submissions are made by a human on the event site. Prepare and validate the file; never claim it was submitted.

## Subagents
- `track-scout` — triage one brief (run in parallel from `/kickoff`).
- `metric-auditor` — fresh-eyes check of scorer, split, and format. Run it after `/adapt-track` and whenever board and local disagree.
- `solution-researcher` — proven approaches for the problem type, when the ladder stalls.
Use subagents for parallel or fresh-eyes work only. One agent and one loop does the climbing.
