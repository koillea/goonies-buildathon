"""The strict multi-part scorer, plus a thin wrapper that returns a ScoreCard.

The published metric is **pass rate**: a file passes only if ALL hold at once --
no sensitive token leaks anywhere (including inside STEP ``\\X2\\`` unicode
escapes), the file still parses with the same entity ids and types in the same
order, every geometry number is unchanged, and required strings (schema name,
units, enumerations, the material) are kept. A leak OR a corruption OR lost data
each score the file zero, so the scorer also reports the separate failure rates
(leak / broken / lost).

``check`` and ``score`` are kept identical to the original ``bench.py`` so
results do not move; ``retained`` is the harmless-label survival proxy from
``run.py``; ``deid_card`` adapts them to the shared ``ScoreCard`` contract.
"""
from __future__ import annotations

from typing import Callable

from buildathon_core import ScoreCard

from .data import decode_x2, geometry_signature, parse


def check(original: str, cleaned: str, truth: dict) -> dict:
    res = {"leak": False, "valid": True, "geometry": True, "kept": True}
    hay = decode_x2(cleaned).lower()
    res["leak"] = any(tok.lower() in hay for tok in truth["sensitive"])
    a, b = parse(original), parse(cleaned)
    if b is None or [(i, t) for i, t, _ in a] != [(i, t) for i, t, _ in b]:
        res["valid"] = False
        res["geometry"] = False
    elif geometry_signature(a) != geometry_signature(b):
        res["geometry"] = False
    needed = ["AUTOMOTIVE_DESIGN", "'mechanical'", ".MILLI.,.METRE.", "'automotive_design'", truth["material"]]
    res["kept"] = all(k in cleaned for k in needed)
    res["pass"] = (not res["leak"]) and res["valid"] and res["geometry"] and res["kept"]
    return res


def score(deid, cases) -> dict:
    tot = {"pass": 0, "leak": 0, "broken": 0, "lost": 0}
    for text, truth in cases:
        try:
            r = check(text, deid(text), truth)
        except Exception:
            r = {"pass": False, "leak": True, "valid": False, "geometry": False, "kept": False}
        tot["pass"] += r["pass"]
        tot["leak"] += r["leak"]
        tot["broken"] += not (r["valid"] and r["geometry"])
        tot["lost"] += not r["kept"]
    return {k: v / len(cases) for k, v in tot.items()}


def retained(deid, cases) -> float:
    """Share of harmless labels ('datum A') that survive: a proxy for kept usefulness."""
    kept = total = 0
    for text, _ in cases:
        total += text.count("'datum ")
        kept += deid(text).count("'datum ")
    return kept / total if total else 1.0


def deid_card(deid: Callable, cases) -> ScoreCard:
    """Score one de-identifier over ``cases`` as a uniform ScoreCard.

    Headline is the pass rate; ``metrics`` carries the full breakdown reported by
    ``score()`` (pass/leak/broken/lost) plus the ``retained`` harmless-label proxy.
    """
    s = score(deid, cases)
    ret = retained(deid, cases)
    return ScoreCard(headline=s["pass"], metrics={
        "pass_rate": s["pass"], "leak": s["leak"], "broken": s["broken"],
        "lost": s["lost"], "retained": ret,
    })
