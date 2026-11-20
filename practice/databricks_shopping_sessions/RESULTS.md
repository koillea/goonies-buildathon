# Databricks Shopping Sessions (practice) - results

24000 training sessions over 4 weeks; 2,000 dev and 2,000 hidden sessions from the following week. Synthetic data; the real task and metric are unknown.

| Approach | Dev Recall@20 | Dev MRR@20 | Hidden Recall@20 | Hidden MRR@20 |
|---|---|---|---|---|
| v0 all-time popularity | 0.304 | 0.095 | 0.318 | 0.102 |
| v1 recent popularity (time-decayed) | 0.312 | 0.101 | 0.321 | 0.106 |
| v2 next-item bigram + popularity fill | 0.660 | 0.310 | 0.680 | 0.313 |
| v3 session co-visitation, recency-weighted | 0.588 | 0.221 | 0.606 | 0.225 |
| v4 v3 tuned on a time split | 0.633 | 0.266 | 0.645 | 0.277 |
| v5 hybrid: bigram + earlier items + revisit bonus | 0.720 | 0.330 | 0.726 | 0.336 |
| v6 v5 tuned on a time split | 0.712 | 0.334 | 0.715 | 0.337 |

v4 chose `{'window': 4, 'decay': 0.5, 'time_decay': 0.6, 'recency': 0.8, 'revisit': 0.4}` (validation MRR@20 0.265).

v6 chose `{'alpha': 0.1, 'revisit': 0.15, 'time_decay': 0.5, 'back': 0.8}` (validation MRR@20 0.323).

## What iterating showed

1. **A wrong assumption cost 13 points of Recall@20.** v3 to v6 first excluded the item the shopper is currently on, assuming the next event is never the same item. In this data it is the next item 14% of the time. With the exclusion the hybrid (v5) scored 0.591 hidden Recall@20 and lost to the plain bigram (0.680); without it, 0.726. Check every assumption against the data before building on it.
2. **Direction matters.** Symmetric co-occurrence (v3/v4) is weaker than directional next-item counts (v2, v5, v6).
3. **Tune on a time-based split inside the training data, never on the leaderboard.** Dev and hidden scores agree, which is the sign the tuning generalises. With 2 submissions an hour on this track, local validation is the only way to iterate.
4. Next steps that usually add the most on real data: a learned re-ranker (gradient-boosted trees) over these candidates, item metadata (category, price), and separate handling of clicks, carts and orders if the metric weights them.
