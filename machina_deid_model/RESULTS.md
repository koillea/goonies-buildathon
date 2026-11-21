# machina_deid (practice) - results

100 dev cases (seed 1) and 100 hidden cases (seed 9001). Headline metric: **pass_rate** (higher is better). Synthetic data; the real task format is unknown.

Headline is the file pass rate (parses + geometry unchanged + no leak + required data kept). leak / broken / lost and the harmless-label retained rate ride along so both failure modes show.

| Approach | Dev pass_rate | Dev leak | Dev broken | Dev lost | Dev retained | Hidden pass_rate | Hidden leak | Hidden broken | Hidden lost | Hidden retained | Generalizes | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v0 do nothing | 0.000 | 1.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 | 0.000 | 1.000 | yes | baseline |
| v1 scrub header only | 0.000 | 1.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 | 0.000 | 1.000 | yes | beats |
| v2 + person / organization / product records, comments | 0.000 | 1.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 | 0.000 | 1.000 | yes | beats |
| v3 blank every string | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | yes | beats |
| v4 blank all except schema records and safe properties | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | yes | **best** |
| v5 learn identity tokens, remove them everywhere | 1.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.000 | yes | beats |
