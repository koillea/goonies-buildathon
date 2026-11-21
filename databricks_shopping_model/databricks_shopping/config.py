"""Track configuration for Databricks Shopping Sessions.

Databricks is a **2-submissions-per-hour** track: you cannot probe the
leaderboard to iterate. Local validation is the only way to make progress -- the
dev/hidden split here, and the time-based split inside the training data that
v4/v6 tune on, are what stands in for the leaderboard. Never tune on hidden.
"""
from __future__ import annotations

from dataclasses import dataclass

from buildathon_core import DEFAULT_N, DEV_SEED, HIDDEN_SEED


@dataclass(frozen=True)
class DatabricksShoppingConfig:
    # ``n`` is the number of evaluation cases per split (dev, hidden). dev_seed
    # and hidden_seed seed the two eval splits -- they MUST differ so hidden
    # stands in for unseen sessions.
    n: int = DEFAULT_N
    dev_seed: int = DEV_SEED
    hidden_seed: int = HIDDEN_SEED
    k: int = 20
    # The published metric ranks on Recall@20; MRR@20 rides along as a second
    # measured scalar so neither is lost.
    headline_metric: str = "recall@20"
    baseline_name: str = "v0 all-time popularity"

    # ---- mapping the harness (n, seeds) onto the original make() parameters ----
    # The synthetic world is fixed (its items, categories and popularity drift);
    # only the sampling of train/dev/hidden sessions moves with the seeds.
    world_seed: int = 7
    # Training sessions per week scale with n so small ``--n`` runs finish fast
    # while keeping the fit-then-recommend shape (original ran per_week == 3*n_eval).
    per_week_factor: int = 3
    # Cap on the time-split validation cases v4/v6 grid-search against.
    val_cap: int = 1500
