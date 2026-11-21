"""Track configuration for Machina CAD De-ID.

Machina's practice board is **2 submissions/hour**, so you cannot probe the
hidden set -- each submission must be chosen by a trusted local validation
split, not hope. The local case count can still be modest because the generator
is deterministic per seed.

The headline is the **pass rate** over files. The invariant is strict: a file
passes only if it parses, its geometry is unchanged, AND no identifier leaks
anywhere (including inside STEP ``\\X2\\`` unicode escapes). Because all
conditions must hold at once, a *leak* OR a *corruption* (or lost required data)
each score that file zero -- so the scorer tracks leak/broken/lost separately,
and climbing the pass rate means avoiding both opposite failure modes at once.
"""
from __future__ import annotations

from dataclasses import dataclass

from buildathon_core import DEFAULT_N, DEV_SEED, HIDDEN_SEED


@dataclass(frozen=True)
class MachinaDeidConfig:
    n: int = DEFAULT_N
    dev_seed: int = DEV_SEED
    hidden_seed: int = HIDDEN_SEED
    # The published metric ranks on pass rate; leak/broken/lost/retained ride
    # along as measured scalars so neither failure mode is ever hidden.
    headline_metric: str = "pass_rate"
    baseline_name: str = "v0 do nothing"
