# What past winners did, and what their agents had

Researched 2026-11-20 (kickoff day). Scope: earlier Builders events, similar scoreboard contests,
and AI-agent systems that won or placed. Each entry is marked **[verified]** (primary page or repo
read), **[secondary]** (press, search summaries or abstracts only), or **[unverified]**.
Some hosts were blocked from this session (sakana.ai, arxiv.org, morling.dev), so those
details come from secondary sources.

---

## 1. Builders (joinbuilders.org): earlier events and results

- **No published Buildathon winners or write-ups found.** joinbuilders.org/buildathon says nothing
  about earlier editions, and its "2nd place, 0 users" post is satire, not a result. Web searches
  for "Builders Buildathon winners" found only unrelated events (AI Fund, Airtable, Arbitrum).
  **[verified: page read]**
- **Builders "Night Shift: Food Truck Wars"** (nightshift.joinbuilders.org) appears to be an
  earlier overnight bot challenge with live API games. Practice days ran every 15 min, the final
  ran at 8:30 AM, and bots had to answer in under 2 s. Organizers changed the rules during the night.
  - Repo `Peezy0/nightshift-food-truck` is one team's setup. Placement unknown **[unverified]**.
  - Their bot used no LLM at runtime. It was a simulator-based planner that learned from finished days.
  - Tooling around the bot:
    - CLAUDE.md, AGENTS.md and HANDOFF.md.
    - `.claude/agents/strategy-builder.md`, a subagent limited to editing strategy.
    - A watchdog `run.py` that hot-reloads `bot.py`.
    - dashboard/status/analyze scripts and a `tests/` folder.
    - A Monitor that polls game state for rule-change announcements and proposes changes, but never deploys them.
  - Also `nicholasravakhah/5guysburgers` (API client for the same game).
  - Lesson: organizers change rules mid-event, so re-read the brief and watch the announcements.
- **Facts that change strategy, from the official brief (2026 edition)** **[verified]**:
  - Second place wins nothing ($5k per track, winner only).
  - Ties go to the earlier submission.
  - Organizers verify top results before announcing winners.
  - Shopping Sessions:
    - Rate limit is 2 submissions per hour.
    - Hidden-data feedback is only the exit code, OOM status and missing/extra/differing row counts.
    - Machine variance is about 20%.
    - The final is the median of 3 runs on about 60M events with a 3-min cap. The top 5 or more are re-timed 5 times on an idle machine.
    - Practice times over about 60 s risk timing out in the final.
  - CAD De-ID:
    - 20 scored attempts in total.
    - Feedback is per-category counts only.
    - The scorer finds files by content and path, and a check it cannot decide counts as failed.
    - The final ranking uses the last grader, which may be stricter.
    - Copying the input unchanged scores 292.
- **Other teams' public repos for this event already exist**:
  - jacobcorbett/buildathon-cad-deid
  - jacobcorbett/buildathon-shopping-sessions
  - jacobcorbett/buildathon-mech-royale
  - jacobcorbett/buildathon-blast-radius

  All were created today and we cannot read them from this session. The MIT and public-repo rules
  mean every team's Shopping and Blast Radius code is public, ours included.

## 2. Comparable scoreboard contests

### 1 Billion Row Challenge (gunnarmorling/1brc), the closest match to Shopping Sessions
- **Results** **[verified, README]**:
  - 1st place: Thomas Wuerthinger, Quan Anh Mai and Alfonso Peterssen, 1.535 s (8 cores of EPYC 7502P), GraalVM native image plus Unsafe.
  - 2nd: Artsiom Korzun, 1.587 s. 3rd: Jaromir Hamala (jerrinot), 1.608 s.
  - Timing: hyperfine, 5 runs, drop the fastest and slowest, average the rest, file on a RAM disk.
  - Every entry first had to pass `test.sh` against fixed expected outputs.
  - Rules required support for any valid input: names up to 100 bytes and up to 10k keys.
- **The winner's own step-by-step log** in `thomaswue/1brc-steps` **[verified]** is the best guide to
  which optimizations pay off:
  1. Parallel segments + mmap + integer math (temps x10) + a custom hash table: 115 s to 5.67 s (-95%).
     **Almost all the gain is here: the right architecture, not micro-tuning.**
  2. Unsafe, no bounds checks: -25%.
  3. Scanning and comparing 8 bytes at a time: -27%.
  4. Branchless number parsing and SWAR delimiter search (merykitty's trick): -25%.
  5. Fast paths for names of 8 or 16 bytes or fewer: -7%.
  6. A smaller hash table and a tuned hash: -7.5%.
  7. **A subprocess so the parent exits without waiting for munmap**: -7.5%.
  8. 2 MB work-stealing chunks, 3 lines in flight per thread for instruction-level parallelism: -4%.
  9. Address-arithmetic tweaks: -3%.
  10. Always process 16 bytes with masks instead of branches: -15%.
- **lehuyduc C++ (discussion #138)** **[verified]**:
  - SIMD delimiter search and integer parsing.
  - Linear-probe table that always compares full keys.
  - Thread count compiled in as a constexpr.
  - munmap took over 50% of runtime at 128 threads.
  - Reviewers flagged entries that relied on assumptions about the data (table sized near the key
    cap, "all names appear in the first 100k bytes"). Those were ruled out of competition.

  Lesson for us: if the hidden data differs from the dev data, fast-but-assuming code scores zero.

### DuckDB / Polars / DataFusion speed **[secondary]**
- Ibis ran the same 1BRC code on DuckDB, Polars and DataFusion (ibis-project.org/posts/1brc).
  Engines are close on scans, but **memory differs on joins**: one write-up saw Polars use 10.5 GB on
  a join that DuckDB did in far less.
- codecentric found DuckDB and Polars close on large Parquet scans, with DuckDB slightly ahead.
  Forcing `POLARS_FORCE_ASYNC=1` made Polars slower, so keep defaults until you have measured.
- What matters for us: 24 GB with no swap, and an identity graph where shared devices tie thousands
  of IDs together. A naive join for ID resolution can blow up. Do union-find in plain code (or an
  iterative min-label propagation) rather than a recursive SQL CTE. The CTE part is our inference,
  not a published result.

### Kaggle grandmaster workflow **[secondary]**
- "Trust your CV." Shake-ups punish teams that tune to the public board. A sound local validation
  setup is "the great discriminator" (Kaggle Book lecture slides).
- Repeat CV with several seeds. Keep fold distributions the same as the test set's.
- Choose final submissions so one is the best local score and one is a different strong option.
- NVIDIA's grandmasters say they run every experiment through the same CV and GPU-speed pipeline, so they can try many ideas quickly.

### MIDI-B (MICCAI 2024 DICOM de-identification challenge), closest match to CAD De-ID **[secondary]**
- The scoring is very like ours: the percentage of required de-ID "actions" done correctly on
  hidden data. 10 teams finished. The winner is not confirmed here; the organizers' report is
  arXiv 2507.23608.
- **2nd place (Jiang/Xie/Wan, arXiv 2508.07538): 99.92%.**
  - Rule-based handling for each tag.
  - Pixel masking with OCR (Presidio).
  - Date shifting and hashing, text replacement and removal.
- **Haghiri et al. (arXiv 2509.00437): 99.91%.**
  - Custom rules and **private-tag handling**.
  - A RoBERTa NER model and PaddleOCR. The model handles free text only; rules do the rest.
- **Michie & Doran (XNAT-based): 97.91%, raised to 99.61% after the event** using the organizers'
  discrepancy reports. Close reading of the feedback added about 1.7 points.
- Takeaway: top teams combined **deterministic rules for each format** with ML or OCR only for free
  text and pixels, and covered private/vendor fields.

### CAD-specific facts **[secondary, vendor forums]**
- STEP files put the exporting user's real login name and the organization in `HEADER; FILE_NAME(...)`.
- DXF keeps author data in plain-text header variables. ezdxf can read the file back to check it.
- There is no common vendor-neutral scrubber. Native SolidWorks and Inventor files are OLE/compound
  documents with custom-property streams and preview thumbnails. That last point is from general
  knowledge, not a source checked here.

## 3. AI-agent systems that won or placed

### Sakana ALE-Agent: won AtCoder Heuristic Contest 058 (Dec 2025) **[secondary]**
- **Results:**
  - Placed 21st of about 1,000 in AHC047 (May 2025).
  - **Won AHC058 against 804 humans**, leading from hour 2 of 4.
  - Cost was about $1,300 in API calls (GPT-5.2 + Gemini 3 Pro). This figure comes from press, not checked against Sakana's post.
- **How it worked** (sakana.ai/ale-bench, NeurIPS slides, press):
  - **Domain knowledge in the prompt.** The prompt lists the standard toolbox: simulated annealing, beam search, neighborhood design.
  - **Inference-time scaling as a best-first tree search** over candidate programs. Each node is
    scored by actually running the program on local test cases.
  - **Large parallel search across several LLMs.** It generated and tested hundreds of solutions within 4 hours.
- **What won AHC058:**
  - A new heuristic idea ("virtual power").
  - A **fast simulator** with precomputed tables.
  - Large neighborhood moves.

  The lesson: the eval loop's speed limits how much search the agent can do.
- Benchmark: ALE-Bench (SakanaAI/ALE-Bench; arXiv 2506.09050), 40 AHC problems.

### OpenAI at the AtCoder World Tour Finals 2025 Heuristic: 2nd of 12 **[secondary]**
- Psyho (Przemysław Dębiak) won the 10-hour contest, about 9.5% ahead of OpenAI's custom
  model (reported as related to o3).
- One human with strong intuition and a fast iteration loop still beat the agent over 10 hours.
  The agent was very consistent, but did not find the best idea.

### AIDE (Weco AI; arXiv 2502.13138) on MLE-bench (75 Kaggle competitions) **[secondary]**
- **How it searches:**
  - Every attempt is a node in a **solution tree**.
  - A fixed search policy picks a node and asks the LLM to draft, debug or improve it.
  - The policy decides which node to work on next using **automatic evaluation scores**.
- **Results:**
  - **o1-preview + AIDE won medals on 16.9% of competitions**, about 4x the next agent.
  - Follow-up AIRA-dojo (arXiv 2507.02554): evolutionary and MCTS search raised MLE-bench Lite from 39.6% to 47.7%.
- **Key warning:** choosing the final answer by *test* rather than *validation* score inflated
  medal rates by 9–13 points. Search overfits the signal it is given, and the hidden set reveals it.

### AlphaCode / AlphaCode 2 (DeepMind) **[secondary]**
- **Pipeline:**
  1. Sample about 100k programs per problem (AlphaCode 2: about 1M).
  2. **Filter** them on the example tests.
  3. **Cluster by behaviour on generated inputs.** Programs that produce identical outputs are treated as one solution.
  4. Submit one program from each of the top 10 clusters.
- **Results:** AlphaCode was in the top 54% of humans; AlphaCode 2 beat about 85%.
- Lesson: when submissions are scarce, **spend them on behaviourally different candidates**,
  not on near-duplicates.

### SWE-bench test-time scaling (2026 papers) **[secondary]**
- **SWE-Lego (arXiv 2601.01426):** gains from running one agent longer stop at about 100–140 turns.
  After that, **parallel rollouts plus a generative verifier** do better than a single longer run.
- **Compact-trajectory scaling (arXiv 2604.16529):** summarizing earlier rollouts and starting new
  ones from those summaries took Claude 4.5 Opus from 70.9% to 77.6% on SWE-bench Verified.
  This is "notes from past attempts" memory.
- **SRC (NeurIPS 2026):** a pairwise tournament between candidates picks better than scoring each alone.

### Anthropic Claude Code hackathons (Opus 4.6 / 4.7 / 4.8 Build Day, 2026) **[secondary]**
- The winners were mostly domain experts: a lawyer (CrossBeam, building permits), a cardiologist,
  a carpenter, and others. Judges picked them for product impact.
- These were judged events, not scoreboards, so little carries over. The one shared lesson: deep domain
  understanding beat raw coding skill.
- `affaan-m/everything-claude-code` is often described as a "hackathon winner's config". The repo
  doesn't mention a win **[unverified claim]**. It contains:
  - Planner, tdd-guide and code-reviewer subagents.
  - `verification-loop` and `eval-harness` skills.
  - A memory vault, hooks that save state before compaction, and a context gate at 90%.

  These are plausible patterns, but nothing shows they caused a win.

---

## 4. Ten most transferable lessons, ranked for our two tracks
(DP = Shopping Sessions, fast exact pipeline. DI = CAD De-ID, 1,000 hidden checks.)

1. **Build the local scorer before anything else, and trust it over the board.** (DP, DI)
   - Sources: AIDE, ALE-Agent, Kaggle CV.
   - DP: run `make check-dev` plus the 36 fixtures plus our own adversarial fixtures, comparing row
     by row against `dev-answer.zip`.
   - DI: build our own checker for each category. It should search every extracted stream in every
     file (PDF metadata, OLE property streams, thumbnails, archive members, file names) for a
     list of original identifiers taken from the corpus.
   - The board gives only counts, so a scarce submission should only confirm what the local scorer already shows.
2. **Correctness first: one wrong row scores zero.** (DP)
   - Sources: 1BRC test.sh gate; entries that assumed things about the data were disqualified.
   - Never rely on the dev data's key counts, value ranges or ordering. Fuzz the dirty-record rules
     (three timestamp formats, late events, duplicates, long identity chains).
   - Keep a slow, obviously correct reference version and diff the fast one against it.
3. **Most of the speed comes from the architecture.** (DP)
   - Source: thomaswue's steps. v1 alone (parallel + mmap + integer math + custom table) gave 95%.
   - Choose the engine and data layout first:
     - Read CSV once.
     - Use typed columns, and integer time internally.
     - Do ID resolution with an in-memory union-find.
   - Only then micro-optimize, and measure every step.
4. **Profile, then make one change at a time with its measured delta.** (DP)
   - Source: the 1BRC step log is a model for this.
   - Measure the way the grader does: wall-clock from container start, with cold caches, image
     start-up, Parquet write and process exit (munmap/teardown cost 7.5% in 1BRC).
   - Treat differences under about 20% between practice-board runs as noise. Use medians.
5. **Deterministic rules for each format; ML/OCR only for free text and pixels.** (DI)
   - Source: MIDI-B top teams, 99.9%.
   - Write one handler per format: STEP header, DXF header variables, PDF info/XMP/attachments,
     OLE custom properties and previews, archive members done recursively, file and folder names.
   - **Cover vendor-private fields.** Haghiri's private-tag handling is the DICOM equivalent.
6. **One global identity map, built before any file is rewritten.** (DI)
   - Requirement from the brief (consistent and distinct pseudonyms).
   - Steps:
     1. Collect all identifiers across 188k files.
     2. Normalize variants (case, abbreviations, email/domain forms).
     3. Assign stable pseudonyms that look like real names.
     4. Then rewrite the files and update cross-references when renaming.

   - Avoid naive in-place string replacement. Binary formats have length and offset fields, and
     STEP has line-wrap rules.
7. **Don't break files: an undecidable check counts as a failure.** (DI)
   - Sources: brief; MIDI-B "required actions" scoring.
   - Re-open every output file with a real parser (ezdxf, a STEP reader, pypdf, an OLE reader) and keep extensions.
   - Document defects in README.txt instead of dropping files.
   - Note the baseline: 292 checks pass with no changes at all, so breaking files loses points.
8. **Use scarce submissions on different candidates, and submit early.** (DP, DI)
   - Sources: AlphaCode's 10 behaviour clusters; Kaggle's two-final-picks rule; ties go to the earlier submission.
   - CAD has 20 attempts in total. Each one should test a hypothesis about a category whose count
     moved, as the Michie & Doran team gained +1.7 points from discrepancy feedback.
   - Leave a margin for the stricter re-grade.
9. **Tree search or best-of-n over a fast eval loop, with parallel agents.** (DP, DI)
   - Sources: ALE-Agent, AIDE, SWE-Lego.
   - Run several agents in parallel on separate ideas (separate branches or worktrees), each scored
     by the same local harness. Keep a ranked log of attempts and expand the best one.
   - Once one agent's progress stalls, spend extra compute on more parallel attempts, not a longer single run.
10. **Notes and memory between attempts, plus a separate review pass before submitting.** (DP, DI)
    - Sources: compact-trajectory scaling (+6.7 points), the Night Shift HANDOFF and Monitor setup,
      the claim that organizers verify top results.
    - Keep a notes file of each idea and its measured delta, so later agents don't repeat failed ideas.
    - Have a reviewer subagent check each candidate against rules.md and the brief
      (licences named, no data in the repo, MIT licence) before using an attempt.
    - Re-read the brief for changes during the event.

## Sources
- https://www.joinbuilders.org/buildathon (+ /tracks/shopping-sessions, /tracks/machina-deid)
- https://github.com/Peezy0/nightshift-food-truck ; nightshift.joinbuilders.org
- https://github.com/gunnarmorling/1brc ; https://github.com/thomaswue/1brc-steps ;
  https://github.com/gunnarmorling/1brc/discussions/138 ; https://questdb.com/blog/1brc-merykittys-magic-swar/
- https://ibis-project.org/posts/1brc ; codecentric DuckDB vs Polars blog
- https://sakana.ai/ahc058/ ; https://sakana.ai/ale-bench/ ; arXiv 2506.09050 ; github.com/SakanaAI/ALE-Bench
- https://the-decoder.com/an-openai-ai-model-finished-second-in-the-atcoder-heuristics-world-finals/
- arXiv 2502.13138 (AIDE, github.com/WecoAI/aideml) ; arXiv 2507.02554 (AIRA-dojo)
- arXiv 2203.07814 (AlphaCode) ; deepmind.google/discover/blog/competitive-programming-with-alphacode/
- arXiv 2601.01426 (SWE-Lego), 2604.16529, 2601.22129 ; neurips.cc/virtual/2026/poster/152566 (SRC)
- arXiv 2507.23608 (MIDI-B report), 2508.07538, 2509.00437
- claude.com/blog/meet-the-winners-of-our-built-with-opus-4-6-claude-code-hackathon ;
  github.com/affaan-m/everything-claude-code
- Kaggle Book validation chapter summaries; NVIDIA Kaggle grandmasters blog
