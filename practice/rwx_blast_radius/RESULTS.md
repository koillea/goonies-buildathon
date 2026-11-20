# RWX Blast Radius (practice) - results

100 dev cases (seed 1) and 100 hidden cases (seed 9001). Synthetic data; the real task format is unknown.

## Task A: find the commit that broke the build (accuracy)

| Approach | Dev | Hidden |
|---|---|---|
| v0 latest commit | 22% | 27% |
| v1 file named in log | 27% | 33% |
| v2 static import cone | 17% | 15% |
| v3 symbol from error + cone | 78% | 75% |
| v4 full graph + semantic diff | 100% | 100% |

## Task B: which tests must re-run for a change (mean F1 / exact match)

| Approach | Dev F1 | Hidden F1 | Hidden exact |
|---|---|---|---|
| v0 run every test | 0.335 | 0.368 | 0% |
| v1 test named after file | 0.679 | 0.663 | 46% |
| v2 static import closure | 0.832 | 0.867 | 61% |
| v3 + package re-exports | 0.886 | 0.916 | 73% |
| v4 + dynamic imports + data files | 1.000 | 1.000 | 100% |
