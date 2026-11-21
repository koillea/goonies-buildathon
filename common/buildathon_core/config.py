"""Repository-wide defaults for the validation protocol.

The whole buildathon strategy is "trust a local validation set, not the
leaderboard" (PLAYBOOK, rule 5). That means every track scores on a *dev* split
and a *hidden* split generated from a **different seed**, so a change only earns
a submission when both move together. These are the shared seeds; a track may
raise ``N`` in its own config when its metric is noisier.
"""
from __future__ import annotations

# A fixed dev seed and a far-apart hidden seed: the hidden split stands in for
# "test cases you have never seen" (the buildathon's words). Never tune on hidden.
DEV_SEED = 1
HIDDEN_SEED = 9001

# Cases per split. Big enough that a one-rung improvement clears the noise floor
# on the headline metric; small enough to iterate in seconds under stdlib-only.
DEFAULT_N = 100

# How close dev and hidden must sit for a result to count as "generalizing".
GENERALIZATION_ABS_TOL = 0.05
GENERALIZATION_REL_TOL = 0.20
