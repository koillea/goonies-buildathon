# databricks_shopping (practice) - results

100 dev cases (seed 1) and 100 hidden cases (seed 9001). Headline metric: **recall@20** (higher is better). Synthetic data; the real task format is unknown.

v4 chose `{'window': 2, 'decay': 0.5, 'time_decay': 0.6, 'recency': 0.8, 'revisit': 0.4}` (validation MRR@20 0.228); v6 chose `{'alpha': 0.3, 'revisit': 0.3, 'time_decay': 1.0, 'back': 0.4}` (validation MRR@20 0.293). Databricks allows 2 submissions/hour, so this dev-vs-hidden split (and the time-based split v4/v6 tune on) is the only way to iterate -- never tune on the leaderboard.

| Approach | Dev recall | Dev mrr | Hidden recall | Hidden mrr | Generalizes | Status |
|---|---|---|---|---|---|---|
| v0 all-time popularity | 0.420 | 0.122 | 0.300 | 0.124 | NO | baseline |
| v1 recent popularity (time-decayed) | 0.420 | 0.127 | 0.310 | 0.129 | NO | beats |
| v2 next-item bigram + popularity fill | 0.590 | 0.288 | 0.440 | 0.238 | NO | beats |
| v3 session co-visitation, recency-weighted | 0.470 | 0.206 | 0.440 | 0.191 | yes | beats |
| v4 v3 tuned on a time split | 0.490 | 0.241 | 0.530 | 0.250 | yes | beats |
| v5 hybrid: bigram + earlier items + revisit bonus | 0.580 | 0.293 | 0.540 | 0.276 | yes | beats |
| v6 v5 tuned on a time split | 0.580 | 0.295 | 0.550 | 0.285 | yes | **best** |
