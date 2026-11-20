# Goonies — Builders Buildathon prep

Preparation for the [Builders Buildathon](https://www.joinbuilders.org/buildathon) (Ohio State, Nov 20–22, 2026). The four real problems are released at kickoff, **Fri Nov 20, 6:00 PM ET**. This repo is the dry run we do *before* then: read how the event scores, anticipate each track, and build a benchmark-and-iterate harness so that when the real brief drops we already have the workflow, the fallbacks, and the instincts.

## How this buildathon actually scores (from the site)

- **No judging panel. A scoreboard.** "Nothing here is a matter of opinion." Each track is one company problem with one published metric; highest score wins; ties go to the earlier submission.
- **Hidden tests.** "Your code runs on test cases you have never seen." You cannot overfit to examples you can read.
- **Winner takes all.** $5,000 per track, four tracks, second place gets nothing. Four separate races, not one overall winner.
- **Submission budget is tight.** Rate limits per track per hour (Databricks and Machina: **2/hour**; Builders: 4/hour; RWX: 100/hour), one submission scoring at a time. You cannot probe the hidden set; you must trust a **local validation set**.
- **Practice vs final.** The board shows practice standings until each track's final is published; only the final pays.

### What this means for strategy (the whole playbook)

1. **Build your own scorer first.** Before optimizing anything, reproduce the track's metric locally on data you generate, with a held-out split the way the hidden set is held out. Every track folder here is that pattern: `bench.py` (data + scorer), `solutions.py` (approaches weak→strong), `run.py` (scores all on dev **and** a different-seed hidden split).
2. **Beat the baseline, then climb.** Every board has a "Baseline row". Clear it first for a submission on the board, then iterate.
3. **Iterate locally, submit rarely.** With 2 submissions/hour, each one must be chosen by local validation, not hope. Dev and hidden scores agreeing is the signal that a change generalizes.
4. **Check your assumptions against the data.** In the Databricks practice track, one wrong assumption (that the next item is never the one you're on) cost 13 points of Recall@20 and made the fancy model lose to a trivial one. Measure, don't guess.
5. **Simple and correct beats clever and fragile.** The directional bigram beat symmetric co-visitation; the allowlist de-identifier beat both "scrub the header" (leaks) and "blank everything" (destroys the file).
6. **Pick the track by expected points per hour.** Two people, ~40 build hours, four tracks. Favor a track where you can (a) reproduce the metric exactly, (b) see a clear ladder of improvements, and (c) submit enough to matter.

## The four tracks (problem text is TBA until kickoff; these are anticipations)

| Folder | Track | Sponsor | Anticipated problem | Anticipated metric | Submit rate |
|---|---|---|---|---|---|
| `practice/rwx_blast_radius` | Blast Radius | RWX | Find which commit broke a CI build / which tests a change impacts | accuracy over 100 cases | 100/hr |
| `practice/databricks_shopping_sessions` | Shopping Sessions | Databricks | Predict the next item in an e-commerce session from clickstream | Recall@20 / MRR@20 | 2/hr |
| `practice/machina_cad_deid` | CAD De-ID | Machina | Strip identifying data from CAD files, keep geometry valid | pass rate over files | 2/hr |
| `practice/builders_mech_royale` | Mech Royale | Builders | Submit a bot for a battle-royale arena | placement over many matches | 4/hr |

**Why these guesses:** the track slugs and names on the site (`blast-radius`, `shopping-sessions`, `machina-deid`, `builders`/"Mech Royale") plus the one worked example the site gives ("find the cause of a failed build: accuracy on the same 100 test cases"). RWX makes developer CI/automation tooling; Databricks is data/ML; Machina works in CAD/manufacturing; "Mech Royale" reads like a bot arena. **When the real briefs drop, replace each `bench.py` with the real format and metric and keep the same harness.**

Each company and why its problem is real:
- **RWX** builds CI/automation tooling; "which change broke the build / what must I re-test" is a genuine cost in any large monorepo.
- **Databricks** sells the data+ML platform; session-based recommendation is a canonical revenue-driving workload.
- **Machina** works in CAD/manufacturing; sharing CAD data or using it to train models without leaking customer/program identity is a real compliance blocker.
- **Builders** (the host) — a bot arena that ranks purely by a scoreboard.

## Results at a glance (synthetic data, held-out "hidden" split)

Run any track with `python3 practice/<folder>/run.py`; each writes its own `RESULTS.md`.

- **RWX:** culprit-finding climbs 26% → 76% → 100% as we use the error symbol and the real dependency graph. Test-impact F1 climbs to exact once dynamic imports and data-file reads are modeled.
- **Databricks:** hidden Recall@20 0.32 (popularity) → 0.68 (bigram) → **0.73** (hybrid), after catching a costly wrong assumption.
- **Machina:** file pass-rate 0% (leaks) → 100%, by learning the file's own identity tokens and removing them everywhere while keeping schema strings and useful engineering data.
- **Mech Royale:** vs a strong field, hidden top-2 rate 12% (random) → **47%** (one-step lookahead on expected damage).

The 100%/exact ceilings are a property of *synthetic* data with a knowable generator; on the real hidden sets they stand for "the modeling is right," not "solved." See `PLAYBOOK.md` for the kickoff checklist and `practice/<folder>/NOTES.md` for each track's reasoning and what to do when the real brief differs.

## Note on scope
These are **practice harnesses on invented data**, written before the real problems were released, to rehearse the workflow. They are not the real submissions. Nothing here is affiliated with Builders or the sponsors.
