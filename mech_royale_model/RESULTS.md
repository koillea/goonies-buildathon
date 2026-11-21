# mech_royale (practice) - results

100 dev cases (seed 1) and 100 hidden cases (seed 9001). Headline metric: **top2_rate** (higher is better). Synthetic data; the real task format is unknown.

Headline is the hidden top-2 rate against the strong field; mean points and win rate ride along. The hidden seed stands in for unseen match schedules.

| Approach | Dev top2_rate | Dev mean_points | Dev win_rate | Hidden top2_rate | Hidden mean_points | Hidden win_rate | Generalizes | Status |
|---|---|---|---|---|---|---|---|---|
| v0 random | 0.100 | 2.31 | 0.010 | 0.110 | 2.23 | 0.010 | yes | baseline |
| v1 chase and shoot nearest | 0.370 | 4.86 | 0.120 | 0.340 | 4.96 | 0.140 | yes | beats |
| v1b camp the centre | 0.150 | 3.18 | 0.150 | 0.190 | 3.47 | 0.180 | yes | beats |
| v2 zone-aware, focus weakest | 0.350 | 5.10 | 0.160 | 0.390 | 5.13 | 0.120 | yes | beats |
| v3 survivor: avoid fights, finish kills | 0.430 | 4.90 | 0.210 | 0.410 | 4.87 | 0.220 | yes | beats |
| v4 one-step lookahead on expected damage | 0.540 | 5.79 | 0.210 | 0.500 | 5.94 | 0.250 | yes | **best** |
