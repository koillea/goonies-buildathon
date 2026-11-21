"""Fixtures for the RWX track tests."""
from __future__ import annotations

import pytest

from rwx_blast_radius.data import dataset
from rwx_blast_radius.model import RWXBlastRadiusModel


@pytest.fixture
def model() -> RWXBlastRadiusModel:
    return RWXBlastRadiusModel()


@pytest.fixture
def culprit_cases():
    return dataset("culprit", 20, seed=1)


@pytest.fixture
def impact_cases():
    return dataset("impact", 20, seed=1)
