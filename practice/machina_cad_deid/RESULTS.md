# Machina CAD De-ID (practice) - results

100 dev and 100 hidden synthetic STEP files. A file passes only with zero leaked identifiers, unchanged geometry, a valid file, and required strings kept. The real task format is unknown.

| Approach | Dev pass | Hidden pass | Hidden leak | Hidden broken | Hidden lost needed data | Harmless labels kept |
|---|---|---|---|---|---|---|
| v0 do nothing | 0% | 0% | 100% | 0% | 0% | 100% |
| v1 scrub header only | 0% | 0% | 100% | 0% | 0% | 100% |
| v2 + person / organization / product records, comments | 0% | 0% | 100% | 0% | 0% | 100% |
| v3 blank every string | 0% | 0% | 0% | 0% | 100% | 0% |
| v4 blank all except schema records and safe properties | 100% | 100% | 0% | 0% | 0% | 0% |
| v5 learn identity tokens, remove them everywhere | 100% | 100% | 0% | 0% | 0% | 100% |
