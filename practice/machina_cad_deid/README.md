# Machina — CAD De-ID

**Idea:** strip everything that identifies the customer, people, part or programme from a CAD file, while leaving the geometry valid and useful engineering data intact — so the file can be shared or used to train models.

**Sponsor & why it's real:** Machina works in CAD/manufacturing. Manufacturers can't share CAD or feed it to ML without leaking who the customer is, what program it's for, and who designed it — a concrete compliance blocker a reliable de-identifier removes.

**Anticipated problem / metric** (real brief opens at kickoff): de-identify CAD files (here STEP / ISO 10303-21 text); a file passes only if it has zero leaked identifiers, still parses, geometry is unchanged, and required strings are kept. Score = share of hidden files that pass.

## Run it
```bash
python3 practice/machina_cad_deid/run.py   # writes RESULTS.md
```

## Current practice results (synthetic data, held-out "hidden" split)
Hidden **pass rate**: scrub-the-header 0% (identifiers leak into labels, comments, unicode escapes) → blank-everything 0% the other way (destroys the file) → **learn the file's own identity tokens and remove them everywhere, keeping schema + useful data: 100%**.

The lesson (full detail in `NOTES.md`): a redactor fails two opposite ways — **leak** vs **destroy** — so test both. Learning the identifiers from the document itself beats a fixed denylist (misses new names) and a blanket blank (breaks the file). The scorer reports leak-rate and geometry-damage-rate separately, not just pass/fail.

## Files
`bench.py` (synthetic STEP files + strict multi-part scorer) · `solutions.py` (v0→v5) · `run.py` · `NOTES.md` · `RESULTS.md`.

## When the real brief drops
Swap in the real file format (could be DXF/IGES/native CAD or metadata JSON) and the real pass conditions. Keep the seed-and-propagate idea and add any identifier classes the real data has (addresses, phone numbers, GD&T notes); re-test leak-rate and geometry-damage separately.
