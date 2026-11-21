"""mech_royale: the Builders Mech Royale practice track as a TrackSpec.

Importing the package registers the track with ``buildathon_core`` so the shared
harness and the quality gate discover it by name.
"""
from __future__ import annotations

from .config import MechRoyaleConfig
from .model import MODEL, MechRoyaleModel

__all__ = ["MechRoyaleConfig", "MechRoyaleModel", "MODEL"]
