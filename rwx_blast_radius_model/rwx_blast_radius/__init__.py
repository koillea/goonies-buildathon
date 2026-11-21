"""rwx_blast_radius: the RWX Blast Radius practice track as a TrackSpec.

Importing the package registers the track with ``buildathon_core`` so the shared
harness and the quality gate discover it by name.
"""
from __future__ import annotations

from .config import RWXConfig
from .model import MODEL, RWXBlastRadiusModel

__all__ = ["RWXConfig", "RWXBlastRadiusModel", "MODEL"]
