"""The CLI runs and emits both a table and JSON."""
from __future__ import annotations

import json

from machina_deid.cli import main


def test_cli_table(capsys):
    assert main(["--n", "6"]) == 0
    out = capsys.readouterr().out
    assert "machina_deid (practice) - results" in out
    assert "Hidden pass_rate" in out


def test_cli_json(capsys):
    assert main(["--n", "6", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["track"] == "machina_deid"
    assert payload["metric"] == "pass_rate"
    assert len(payload["results"]) == 6
