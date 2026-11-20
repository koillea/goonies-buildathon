---
description: One iteration of the climb — add a single idea, measure it on holdout, decide
argument-hint: <track_slug> [idea to try]
---

One turn of the improvement loop for `$ARGUMENTS` (the first word is the track slug; the rest, if any, is the idea to try).

1. **Read the state**: `tracks/<slug>/RESULTS.md`, `NOTES.md` (assumptions, what moved the score, submissions log), and the current best version in `solutions.py`.
2. **Pick ONE idea.** If none was given, propose the 3 most promising ideas with the expected gain and the risk of each, and choose the highest expected gain for the least complexity. If the ladder is flat or you need domain ideas, start the `solution-researcher` subagent.
3. **Measure the assumption first.** If the idea relies on a fact about the data ("the next item is never the current one", "every failing log names a file"), check it with `/check-assumption` before building. Our practice run lost 13 points to one assumption nobody measured.
4. **Add a new version** `vN_<idea>` that builds on the current best. Do not edit versions that already scored. Append it to `SOLUTIONS`.
5. **Run** `python3 tracks/<slug>/run.py`.
6. **Decide by holdout:**
   - Better by more than the noise band, and no overfit warning → new best; recommend `/submit-check`.
   - Inside the noise band → a tie: keep the simpler version and do not submit for it.
   - Worse, or an overfit warning → keep the code, record why it failed, and move on.
7. **Record** the version, idea, holdout score, and change in the `NOTES.md` "What moved the score" table.

Report in three lines: what you tried, the holdout change compared with the noise band, and the decision.
