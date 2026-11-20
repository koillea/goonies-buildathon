# Databricks — Shopping Sessions

**Idea:** predict what a shopper interacts with next from the start of their session — the engine behind "customers also viewed / bought."

**Sponsor & why it's real:** Databricks sells the data+ML platform. Session-based next-item recommendation is a canonical, revenue-driving workload that runs on exactly that kind of platform.

**Anticipated problem / metric** (real brief opens at kickoff): given the beginning of an e-commerce session (clickstream), predict the next item(s). Likely Recall@K / MRR@K on hidden sessions from a later time period.

## Run it
```bash
python3 practice/databricks_shopping_sessions/run.py   # ~15s (small grid search), writes RESULTS.md
```

## Current practice results (synthetic data, held-out "hidden" split)
Hidden **Recall@20**: all-time popularity 0.32 → next-item bigram 0.68 → **hybrid (directional bigram + earlier-item votes + revisit bonus) 0.73**.

Two lessons (full detail in `NOTES.md`):
1. **A wrong assumption cost 13 points.** Early versions excluded the item the shopper is currently on; measuring showed it's the next item 14% of the time. Always check an assumption against the data before building on it.
2. **Direction beats symmetry** — a directional next-item count beats symmetric co-visitation.

## Files
`bench.py` (synthetic shoppers + scorer) · `solutions.py` (v0→v6) · `run.py` (scores dev + hidden, tunes on a time split) · `NOTES.md` · `RESULTS.md`.

## When the real brief drops
Swap in the real session logs and metric (watch for separate click/cart/order weighting). Keep the directional co-occurrence + recency + revisit structure and the **time-based** validation split (a random split leaks future popularity). Biggest next lift on real data: a gradient-boosted re-ranker over these candidates plus item metadata.
