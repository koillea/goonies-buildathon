"""machina_deid: the Machina CAD De-ID practice track as a TrackSpec.

Importing the package registers the track with ``buildathon_core`` so the shared
harness and the quality gate discover it by name.
"""
from __future__ import annotations

from .config import MachinaDeidConfig
from .model import MODEL, MachinaDeidModel

__all__ = ["MachinaDeidConfig", "MachinaDeidModel", "MODEL"]
