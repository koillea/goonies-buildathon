"""Fixtures for the Machina CAD De-ID track tests."""
from __future__ import annotations

import pytest

from machina_deid.data import dataset
from machina_deid.model import MachinaDeidModel


@pytest.fixture
def model() -> MachinaDeidModel:
    return MachinaDeidModel()


@pytest.fixture
def dev_cases():
    return dataset(20, seed=1)


@pytest.fixture
def hidden_cases():
    return dataset(20, seed=9001)
