"""databricks_shopping: the Databricks Shopping Sessions practice track as a TrackSpec.

Importing the package registers the track with ``buildathon_core`` so the shared
harness and the quality gate discover it by name.
"""
from __future__ import annotations

from .config import DatabricksShoppingConfig
from .model import MODEL, DatabricksShoppingModel

__all__ = ["DatabricksShoppingConfig", "DatabricksShoppingModel", "MODEL"]
