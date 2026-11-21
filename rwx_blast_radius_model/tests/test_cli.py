"""The CLI runs and emits both a table and JSON."""
from __future__ import annotations

import json

from rwx_blast_radius.cli import main


def test_cli_table(capsys):
    assert main(["--n", "6"]) == 0
    out = capsys.readouterr().out
    assert "rwx_blast_radius (practice) - results" in out
    assert "Hidden accuracy" in out


def test_cli_json(capsys):
    assert main(["--n", "6", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["track"] == "rwx_blast_radius"
    assert len(payload["results"]) == 5
