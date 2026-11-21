"""Fixtures for the Databricks Shopping Sessions track tests."""
from __future__ import annotations

import pytest

from databricks_shopping.data import World, build_train, eval_set
from databricks_shopping.model import DatabricksShoppingModel


@pytest.fixture
def model() -> DatabricksShoppingModel:
    return DatabricksShoppingModel()


@pytest.fixture
def splits():
    """A small (train, dev, hidden) built from one world; dev/hidden differ by seed."""
    world = World(7)
    train = build_train(world, 7, per_week=60)
    dev = eval_set(world, 1, 200)
    hidden = eval_set(world, 9001, 200)
    return train, dev, hidden
