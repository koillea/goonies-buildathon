# Machina CAD De-ID — reasoning

**Anticipated problem.** Slug `machina-deid`; Machina works in CAD/manufacturing. Likely: de-identify CAD files (here STEP / ISO 10303-21 text) so they can be shared or used as training data — remove customer/person/program/part identifiers while keeping the geometry valid and useful engineering metadata (material, units) intact. Metric: share of files that pass a strict multi-part check.

**Why it's a real company problem.** Manufacturers can't share CAD or feed it to ML without leaking who the customer is, what program it's for, and who designed it. A reliable de-identifier unblocks data sharing and model training — a concrete compliance win.

**The task is pass/fail on four conditions at once**, which is what makes it hard: (1) no identifier leaks *anywhere* — including inside STEP `\X2\` unicode escapes, comments, file paths, emails, and geometry labels; (2) the file still parses with the same entities; (3) geometry numbers unchanged; (4) required strings (schema, units, enumerations) and useful data (material) kept. The scorer reports each failure mode separately.

**What moved the score (hidden pass rate):**
- Scrub the header only: 0% (identifiers leak into PRODUCT names, labels, comments).
- + PERSON/ORGANIZATION/PRODUCT records + comments: still 0% (leaks into geometry labels and `\X2\` escapes).
- Blank *every* string: 0% the other way — no leaks, but it destroys the schema name and units, so the file is no longer valid/useful.
- **Allowlist**: blank all strings except schema/unit records and known-safe keys: **100%**, but it drops harmless labels too.
- **Seed-and-propagate**: learn the file's own identity tokens from its PERSON/ORG/PRODUCT/header records, then remove *those tokens* everywhere (decoding `\X2\` first) while keeping harmless strings and useful data: **100%** and keeps harmless labels.

**Lesson:** a redactor has two opposite failure modes (leak vs. destroy); you must test both. Learning the identifiers from the document itself beats both a fixed denylist (misses novel names) and a blanket blank (destroys the file).

**When the real brief drops:** replace the STEP generator with the real file format (could be DXF, IGES, native CAD, or metadata JSON) and the real pass conditions. Keep the seed-and-propagate idea: find who the file belongs to, remove that everywhere including encoded forms, preserve the schema. Add any identifier classes the real data has (addresses, phone numbers, GD&T notes) and re-test leak-rate and geometry-damage-rate separately.
