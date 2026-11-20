# Databricks Shopping Sessions — reasoning

**Anticipated problem.** Slug `shopping-sessions`; Databricks sells the data+ML platform. Almost certainly session-based recommendation on e-commerce clickstream (the shape of RecSys 2015 / Kaggle OTTO / KDD Cup 2023 Amazon sessions): given the start of a session, predict the next item(s). Metric likely Recall@K or MRR@K.

**Why it's a real company problem.** Next-item prediction drives "customers also viewed / bought" and directly moves conversion revenue; it's the canonical Databricks-platform workload.

**What moved the score (hidden Recall@20):**
- All-time popularity: 0.32. Recent (time-decayed) popularity: 0.32.
- Directional next-item bigram + popularity fill: **0.68**.
- Symmetric session co-visitation, recency-weighted: 0.61 (worse than the bigram — symmetry throws away direction).
- Hybrid (directional bigram from the last item + weaker votes from earlier items + revisit bonus): **0.73**.

**The costly mistake (and the lesson).** The first co-visitation versions *excluded the item the shopper is currently on*, assuming the next event is never the same item. Measuring the data showed it's the next item **14%** of the time. That one wrong assumption held the hybrid at 0.59 — losing to the trivial bigram — until removed, after which it jumped to 0.73. **Always measure an assumption before building on it.** (`python3 -c` three-liners against `bench.make()` do this.)

**When the real brief drops:** replace `World`/`make` with the real session logs and the real metric (watch for separate click/cart/order weighting, and whether it's next-item or next-basket). Keep the directional co-occurrence + recency + revisit structure and the **time-based** validation split (train on earlier weeks, validate on the latest) — a random split leaks future popularity. Next lifts on real data: a gradient-boosted re-ranker over these candidates, item metadata (category/price), and matrix factorization as an extra candidate source.
