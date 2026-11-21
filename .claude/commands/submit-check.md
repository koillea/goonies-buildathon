---
description: Gate before spending a scarce submission — is this version really a new best?
argument-hint: <track_slug> [version name]
---

Pre-submission gate for `$ARGUMENTS`. Submissions are limited (Databricks and Machina 2/hour, Builders 4/hour, RWX 100/hour), so treat each one like money. Answer every check with evidence, not memory:

1. **Fresh run**: run `python3 tracks/<slug>/run.py` now. Quote the row for the candidate version and for the best version already submitted, taken from the `NOTES.md` submissions log.
2. **Real improvement**: is the candidate's holdout score higher than the best submitted score by more than the noise band? If not, **do not submit**.
3. **Generalizes**: no overfit warning, and the dev-to-holdout gap is no worse than earlier versions.
4. **Valid output**: generate the submission file from scratch and validate it against the brief's format: every required id present, no extras, right types, right file name and encoding. Run any validator the starter kit provides.
5. **Runtime limits**: if the grader runs our code, confirm it stays within the time and memory caps on a holdout-sized input, and that it only uses allowed dependencies (the default here is the standard library only).
6. **Budget**: how many submissions are left this hour? Is there a better candidate coming within the hour that is worth waiting for?

Verdict: **SUBMIT** (give the exact file and version) or **HOLD** (give the reason). After the user submits, ask for the board score and add it to the submissions log. If the board score moved the opposite way from local, say clearly that the holdout does not match the hidden set and that `split()` must be fixed before anything else.
