---
name: track-adaptation
description: Procedure and per-track domain playbook for turning a real buildathon brief into a trustworthy local harness. Load when adapting a track (/adapt-track), when a brief differs from our practice guess, or when local and board scores disagree.
---

# Turning a brief into a harness you can trust

## Order of work (each step is checked before the next one starts)
1. **Formats first.** Write the input format, output format, and metric definition into `NOTES.md` in the brief's own words. Resolve anything ambiguous by checking it against the starter-kit examples, or by asking the organizers. Do not guess.
2. **Scorer before solver.** Implement `score()` and check it against hand-computed tiny cases: perfect, empty, half-right, duplicates, more than K items. Every metric hides edge cases:
   - Recall@K / MRR@K: is there one target or many? Are predictions deduplicated? Is the denominator the number of targets or min(K, targets)? Are sessions with no target skipped or counted as 0?
   - Mean F1: how are empty prediction and empty truth handled (1.0 or 0)? Is it per-case mean or micro-averaged?
   - Pass-rate over conditions: is each condition a separate check? Report the failure rate per condition, not only the overall pass.
   - Placement / ELO: how many matches, which opponents, how are ties broken? How much does the result vary between seeds?
3. **Holdout like the hidden set.** Time split for anything ordered; group split for anything grouped. Make the holdout as large as you can afford, because the noise band is 1/sqrt(n).
4. **Baseline on the board.** Submit v0 once. If board and local disagree by more than the noise band, fix the scorer or the split before anything else.
5. **Climb**, using `/iterate`.

## Per-track playbook (our practice guesses — check each against the real brief)

**RWX Blast Radius** (`practice/rwx_blast_radius`, packaged as `app/blastradius`): culprit commit and test-impact set.
- What won: take the symbol named in the error and find which commit changed its definition; build the full dependency graph (re-exports, `importlib`, data-file reads); ignore diffs that only change comments.
- Reuse: `static_deps`, `closure`, `strip_comments`, the symbol regex.
- Trap: for the impact set, a missed test usually costs more than an extra one, so keep the graph conservative.
- 100/hour submissions: here you can probe the board cheaply, unlike the other tracks.

**Databricks Shopping Sessions** (`practice/databricks_shopping_sessions`): next item in a session.
- What won: directional bigram from the last item, weaker votes from earlier items, a bonus for revisits, and popularity to fill the rest.
- Trap: never exclude the current item without measuring it first (the next item was the same item 14% of the time).
- Use a time split. If the brief scores clicks, carts, and orders separately, weight them the way the metric does.
- Next ideas: a gradient-boosted re-ranker over the candidates (if dependencies are allowed), category and price features.

**Machina CAD De-ID** (`practice/machina_cad_deid`): remove identifiers and keep the file valid.
- What won: seed-and-propagate. Learn the file's own identity tokens from its PERSON, ORG, PRODUCT, and header records, then remove those tokens everywhere, decoding escapes such as `\X2\` first.
- Two opposite failures: leaking an identifier, and destroying the schema, units, or geometry. Test leak rate and damage rate separately.
- If the real format is not STEP (it could be DXF, IGES, or JSON metadata), keep the idea and rewrite the parser.

**Builders Mech Royale** (`practice/builders_mech_royale`): a bot for a battle-royale arena.
- What won: one-step lookahead on expected damage dealt minus damage taken, staying inside the zone, and avoiding fights until the endgame.
- Evaluate over many seeded matches against a field that includes our own earlier bots. Results vary a lot between matches, so use more matches than you think you need.
- Respect the per-turn compute limit. A bot that times out loses.
- If the track turns out to be "build a game" rather than "submit a bot", this harness does not apply. Say so early.

## When local and board disagree
In order of likelihood:
1. The split does not match the hidden set (time leak, group leak).
2. The scorer is off on an edge case (empty, duplicates, K).
3. The output format differs subtly (id types, ordering, encoding), so the grader reads it differently.
4. The hidden set has a different distribution. Make the holdout more like it, or give the decision more noise margin.
