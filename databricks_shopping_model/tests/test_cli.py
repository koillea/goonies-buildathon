"""The CLI runs and emits both a table and JSON."""
from __future__ import annotations

import json

from databricks_shopping.cli import main


def test_cli_table(capsys):
    assert main(["--n", "10"]) == 0
    out = capsys.readouterr().out
    assert "databricks_shopping (practice) - results" in out
    assert "Hidden recall" in out
    assert "Hidden mrr" in out


def test_cli_json(capsys):
    assert main(["--n", "10", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["track"] == "databricks_shopping"
    assert payload["metric"] == "recall@20"
    assert len(payload["results"]) == 7


def test_cli_offline_is_noop(capsys):
    assert main(["--n", "8", "--offline", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["results"]) == 7
