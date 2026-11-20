---
description: Measure a data assumption with a tiny script before building on it
argument-hint: <track_slug> <assumption in plain words>
---

Assumption to check for `$ARGUMENTS` (the first word is the track slug; the rest is the assumption).

1. State the assumption as something you can measure: "fraction of sessions where next item == current item", "share of failing logs that contain a file path".
2. Write the smallest script that measures it on the REAL training data via `bench.load_cases()`, using `python3 -c` or a throwaway file in the scratchpad — not in the repo. Print the number and 2–3 counterexamples.
3. Measure it on **both** dev and holdout, but print counterexamples from dev only. On holdout, look at the aggregate number and never at individual items: reading holdout examples leaks them into your ideas and makes the holdout untrustworthy. A fact that holds on one split and not the other is itself a finding.
4. Verdict: **holds** (safe to build on), **mostly** (build on it, but cover the exceptions: give the %), or **false** (do not build on it).
5. Add one line to the "Assumptions measured" list in `tracks/<slug>/NOTES.md`: assumption → value → kept/dropped.

Do not change `solutions.py` in this step. This step only produces a measurement.
