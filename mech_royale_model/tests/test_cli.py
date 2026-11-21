"""The CLI runs and emits both a table and JSON."""
from __future__ import annotations

import json

from mech_royale.cli import main


def test_cli_table(capsys):
    assert main(["--n", "10"]) == 0
    out = capsys.readouterr().out
    assert "mech_royale (practice) - results" in out
    assert "Hidden top2_rate" in out


def test_cli_json(capsys):
    assert main(["--n", "10", "--json", "--offline"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["track"] == "mech_royale"
    assert payload["metric"] == "top2_rate"
    assert len(payload["results"]) == 6
