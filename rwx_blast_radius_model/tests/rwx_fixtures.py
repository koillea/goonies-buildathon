"""A hand-built case for deterministic solver assertions (no RNG)."""
from __future__ import annotations

# A tiny repo: report -> rates (transitive), unrelated is isolated.
FILES = {
    "pkg/__init__.py": "",
    "pkg/rates.py": "def price(x, y=0):\n    return x\n",
    "pkg/report.py": "from pkg.rates import price\n\ndef render(x, y=0):\n    return x\n",
    "pkg/unrelated.py": "def noop(x, y=0):\n    return x\n",
    "tests/test_rates.py": "from pkg.rates import price\n\ndef test_price():\n    assert price(1) == 1\n",
    "tests/test_report.py": "from pkg.report import render\n\ndef test_render():\n    assert render(1) == 1\n",
    "tests/test_unrelated.py": "from pkg.unrelated import noop\n\ndef test_noop():\n    assert noop(1) == 1\n",
}

# A culprit case where commit c1 breaks `price`, and c0/c2 are benign tweaks.
CULPRIT_CASE = {
    "files": FILES,
    "commits": [
        {"id": "c0", "changes": {"pkg/unrelated.py": FILES["pkg/unrelated.py"] + "# tweak\n"}},
        {"id": "c1", "changes": {"pkg/rates.py": "def price(x, y, z):\n    return x\n"}},
        {"id": "c2", "changes": {"pkg/report.py": FILES["pkg/report.py"] + "# note\n"}},
    ],
    "log": "FAILED tests/test_rates.py\n  File \"pkg/rates.py\", line 1\n"
           "TypeError: price() missing 1 required positional argument: 'z'\n",
}
CULPRIT_TRUTH = "c1"
