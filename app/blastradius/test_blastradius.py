"""Unit tests for the core analyses, using plain dicts (no git needed)."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from blastradius import core  # noqa: E402


SOURCES = {
    "pkg/__init__.py": "from pkg.rates import price\n",
    "pkg/rates.py": "def price(x):\n    return x * 2\n",
    "pkg/report.py": "from pkg.rates import price\n\ndef render(x):\n    return price(x)\n",
    "pkg/unrelated.py": "def noop():\n    return 0\n",
    "tests/test_rates.py": "from pkg.rates import price\n\ndef test_price():\n    assert price(1) == 2\n",
    "tests/test_report.py": "from pkg.report import render\n\ndef test_render():\n    assert render(1) == 2\n",
    "tests/test_unrelated.py": "from pkg.unrelated import noop\n\ndef test_noop():\n    assert noop() == 0\n",
}


def test_impact_direct():
    hit = core.impacted_tests(SOURCES, ["pkg/rates.py"])
    assert "tests/test_rates.py" in hit
    assert "tests/test_report.py" in hit        # transitive: report -> rates
    assert "tests/test_unrelated.py" not in hit


def test_impact_unrelated_change_runs_nothing_extra():
    assert core.impacted_tests(SOURCES, ["pkg/unrelated.py"]) == ["tests/test_unrelated.py"]


def test_impact_changed_test_always_runs():
    assert core.impacted_tests(SOURCES, ["tests/test_unrelated.py"]) == ["tests/test_unrelated.py"]


def test_culprit_symbol_match_wins():
    commits = [
        {"id": "aaa", "changes": {"pkg/unrelated.py": "def noop():\n    return 1\n"}, "before": {"pkg/unrelated.py": SOURCES["pkg/unrelated.py"]}},
        {"id": "bbb", "changes": {"pkg/rates.py": "def price_v2(x):\n    return x * 2\n"}, "before": {"pkg/rates.py": SOURCES["pkg/rates.py"]}},
        {"id": "ccc", "changes": {"pkg/report.py": SOURCES["pkg/report.py"] + "# touch\n"}, "before": {"pkg/report.py": SOURCES["pkg/report.py"]}},
    ]
    ranked = core.rank_culprits(SOURCES, "tests/test_rates.py", commits,
                                log="ImportError: cannot import name 'price' from 'pkg.rates'")
    assert ranked[0]["id"] == "bbb"
    assert ranked[0]["symbol_match"]
    assert "aaa" not in [r["id"] for r in ranked]  # not in the failing test's cone


def test_culprit_no_log_falls_back_to_nearest():
    commits = [
        {"id": "bbb", "changes": {"pkg/rates.py": "def price(x):\n    raise ValueError('x')\n"}, "before": {"pkg/rates.py": SOURCES["pkg/rates.py"]}},
    ]
    ranked = core.rank_culprits(SOURCES, "tests/test_rates.py", commits, log="")
    assert ranked[0]["id"] == "bbb"


def test_comment_only_change_is_not_a_symbol_match():
    commits = [
        {"id": "bbb", "changes": {"pkg/rates.py": "def price(x):\n    return x * 2  # noqa\n"}, "before": {"pkg/rates.py": SOURCES["pkg/rates.py"]}},
    ]
    ranked = core.rank_culprits(SOURCES, "tests/test_rates.py", commits, log="name 'price'")
    assert ranked[0]["symbol_match"] is False  # body unchanged after comments stripped


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"\n{len(fns)} passed")
