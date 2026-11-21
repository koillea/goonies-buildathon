---
description: Turn a real brief into a working local harness (scorer + holdout + v0 baseline)
argument-hint: <track_slug>
---

Build the local harness for track `$ARGUMENTS`. Load the `track-adaptation` skill first and follow it. Done means `python3 tracks/$ARGUMENTS/run.py` prints a real v0 score — not "roughly done."

1. **Scaffold**: `cp -r .claude/templates/_track_skeleton tracks/$ARGUMENTS` (create `tracks/` if needed). If `practice/` has a close match, copy the reusable pieces (graph builder, split logic, bot loop) into the new `solutions.py` — keep the skeleton's `run.py`.
2. **Read** `briefs/$ARGUMENTS.md` and every starter-kit file. Write down the exact input format, output format, and metric definition in `NOTES.md` before you write code.
3. **`load_cases()`**: load the real data in the shape the grader uses. Print 2 examples and their truths, and check them against the brief.
4. **`score()`**: implement the official metric exactly. Hand-compute it on 2–3 tiny examples (perfect / empty / partly right) and assert that `score` matches. Edge cases: empty predictions, duplicates, ties, more than K items.
5. **`split()`**: make the holdout look like the hidden set (time or group split if the data has order or groups). Write the reason in `NOTES.md`.
6. **v0 baseline**: the dumbest valid answer. Run `run.py`.
7. **Independent audit**: start the `metric-auditor` subagent on `tracks/$ARGUMENTS`. Fix anything it confirms.
8. **Check the output format**: write the v0 predictions in exactly the submission format the brief specifies and validate them with any checker the starter kit includes.
9. Report: v0 holdout score, noise band, audit result, and the file ready to submit as the first board row. Tell the user to submit it and paste back the board score, so we can confirm local and board agree.
