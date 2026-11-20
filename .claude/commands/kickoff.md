---
description: Briefs just dropped — triage all four tracks and pick where to spend the weekend
argument-hint: [path to briefs file, or paste the briefs after the command]
---

The real buildathon briefs are out. Run the first-30-minutes procedure from `PLAYBOOK.md`. **Write no solution code in this step.**

Briefs: $ARGUMENTS
(If that is empty, look for brief files the user added under `briefs/` or the repo root, or ask the user to paste them.)

1. **Save the briefs verbatim** to `briefs/<track_slug>.md`, one file per track, so every later step and subagent reads the same text.
2. **Triage in parallel**: start one `track-scout` subagent per track, all in a single message, each given its brief file path. Each one returns a points-per-hour score card.
3. **Compare against our practice guess** for each track (`practice/<folder>/NOTES.md`): did the real problem match? Which practice code (scorer, graph builder, split, bot loop) can be reused as-is?
4. **Recommend** a ranked track order and a team split (who owns the scorer, who owns modeling — see PLAYBOOK "Division of labor"). Show it as one table: track, metric, submit rate, can we reproduce the metric exactly (y/n/partial), size of the improvement ladder, reusable practice code, expected points per hour, and a recommendation.
5. Finish with the exact next command, for example `/adapt-track shopping-sessions`.

Be blunt. If a track's metric cannot be reproduced locally, say so — that track is a trap on a 2/hour budget.
