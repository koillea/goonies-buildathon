# rwx_blast_radius (practice) - results

100 dev cases (seed 1) and 100 hidden cases (seed 9001). Headline metric: **accuracy** (higher is better). Synthetic data; the real task format is unknown.

Headline is culprit-finding accuracy; impact F1 and exact-match ride along as the second task's measures.

| Approach | Dev accuracy | Dev f1 | Dev exact | Hidden accuracy | Hidden f1 | Hidden exact | Generalizes | Status |
|---|---|---|---|---|---|---|---|---|
| v0 latest / run-all | 0.220 | 0.335 | 0.040 | 0.270 | 0.368 | 0.000 | NO | baseline |
| v1 surface text / name match | 0.270 | 0.679 | 0.510 | 0.330 | 0.663 | 0.460 | NO | beats |
| v2 static import cone | 0.170 | 0.832 | 0.650 | 0.150 | 0.867 | 0.610 | yes | below |
| v3 symbol from error + re-exports | 0.780 | 0.886 | 0.730 | 0.750 | 0.916 | 0.730 | yes | beats |
| v4 full graph + semantic diff | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | yes | **best** |
