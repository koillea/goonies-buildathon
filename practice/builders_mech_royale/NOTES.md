# Builders Mech Royale — reasoning

**Anticipated problem.** Track name "Mech Royale", hosted by Builders itself. Reads like a bot-arena / battle-royale: submit an agent, it competes against other teams' agents, score = placement over many matches. (If it turns out to be a *build-a-game* track instead, this harness is the wrong shape — but a competitive-bot track is the natural fit for a pure-scoreboard event.)

**Why a scoreboard loves it.** Bot-vs-bot placement is perfectly objective and needs no human judgment — exactly the event's "no judging panel, a scoreboard" ethos.

**What moved the score (hidden top-2 rate vs a strong field):**
- Random: 12%. Chase-and-shoot: 29%. Camp the centre: 16%.
- Zone-aware + focus the weakest in range: 32%.
- "Survivor" (avoid fights, stay in zone, finish cheap kills, duel only in the endgame): 37%.
- **One-step lookahead** scoring each action by expected damage dealt minus expected damage taken (with caution that drops as enemies die): **47%**.

**Lessons:** (1) in a battle royale, *not dying* outscores *killing* until the endgame — the survivor and lookahead bots win by letting others trade damage. (2) An explicit expected-value calculation (hit chance × damage, minus incoming) beats hand-tuned rules. (3) Always respect the shrinking zone — standing outside it is free damage to yourself.

**When the real brief drops:** replace `bench.py` with the real game's rules (grid/continuous, actions, damage, win condition) and the real match/scoring protocol. Keep the structure: a local arena, an opponent field that includes your own previous bots, and an evaluation over many seeded matches. Then: self-play to find the current best, and a small lookahead or expectimax over the real action set. Guard against timeouts — the real engine will cap per-turn compute.
