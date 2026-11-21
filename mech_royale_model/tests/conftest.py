"""Fixtures for the Mech Royale track tests."""
from __future__ import annotations

import pytest

from mech_royale.model import MechRoyaleModel


@pytest.fixture
def model() -> MechRoyaleModel:
    return MechRoyaleModel()
