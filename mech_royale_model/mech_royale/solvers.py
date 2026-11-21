"""Bots for the Mech Royale arena, weakest to strongest.

Lifted verbatim (behaviour-preserving) from the original
``practice/builders_mech_royale/solutions.py``; only the import is rebound to the
package's ``data`` module. The ladder climbs by *modelling the game*, not
reacting to the surface: random -> chase-and-shoot -> camp the centre ->
zone-aware focus-fire -> a survivor that avoids fights until the endgame -> a
one-step lookahead that scores each action by expected damage dealt minus
expected damage taken. That climb (12% -> 47% hidden top-2 vs a strong field) is
the PLAYBOOK's "model the real dependency / simple-and-correct, then an explicit
expected-value calculation" in competitive form.
"""
from __future__ import annotations

import random

from .data import RANGE, SIZE, dist, hit_chance

_rng = random.Random(0)
DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
C = SIZE // 2


def _cheb_center(p):
    return max(abs(p[0] - C), abs(p[1] - C))


def _step_toward(me, target):
    dx, dy = target[0] - me[0], target[1] - me[1]
    if abs(dx) >= abs(dy) and dx:
        return ("move", 1 if dx > 0 else -1, 0)
    if dy:
        return ("move", 0, 1 if dy > 0 else -1)
    return ("wait",)


def _in_range(view):
    me = view["me"]
    return [e for e in view["enemies"] if dist(me["pos"], e["pos"]) <= RANGE]


def b_random(view):
    r = _rng.random()
    if r < 0.6:
        d = _rng.choice(DIRS)
        return ("move", d[0], d[1])
    t = _in_range(view)
    return ("shoot", _rng.choice(t)["id"]) if t else ("wait",)


def b_aggro(view):
    """Chase the nearest enemy and shoot whenever something is in range."""
    me = view["me"]
    near = min(view["enemies"], key=lambda e: dist(me["pos"], e["pos"]))
    if dist(me["pos"], near["pos"]) <= RANGE:
        return ("shoot", near["id"])
    return _step_toward(me["pos"], near["pos"])


def b_camper(view):
    """Walk to the centre, then shoot the nearest enemy in range."""
    me = view["me"]
    if _cheb_center(me["pos"]) > 1:
        return _step_toward(me["pos"], (C, C))
    t = _in_range(view)
    return ("shoot", min(t, key=lambda e: dist(me["pos"], e["pos"]))["id"]) if t else ("repair",)


def v2_zone_focus(view):
    """Never stand outside the next zone; shoot the target you are most likely to finish."""
    me = view["me"]
    if _cheb_center(me["pos"]) > view["next_radius"]:
        return _step_toward(me["pos"], (C, C))
    t = _in_range(view)
    if t:
        best = max(t, key=lambda e: hit_chance(dist(me["pos"], e["pos"])) * (2.0 if e["hp"] <= 22 else 1.0) / (e["hp"] + 20))
        return ("shoot", best["id"])
    near = min(view["enemies"], key=lambda e: dist(me["pos"], e["pos"]))
    return _step_toward(me["pos"], near["pos"])


def v3_survivor(view):
    """Let the others fight. Stay in the zone, keep away, repair, and only fight when
    cornered, when a kill is cheap, or when it is down to the last two."""
    me = view["me"]
    pos = me["pos"]
    enemies = view["enemies"]
    if _cheb_center(pos) > view["next_radius"]:
        return _step_toward(pos, (C, C))
    t = _in_range(view)
    endgame = len(enemies) == 1
    if t:
        weak = [e for e in t if e["hp"] <= 22 and hit_chance(dist(pos, e["pos"])) >= 0.5]
        if weak:
            return ("shoot", min(weak, key=lambda e: dist(pos, e["pos"]))["id"])
        if endgame or me["hit_last"]:
            tgt = max(t, key=lambda e: hit_chance(dist(pos, e["pos"])) / (e["hp"] + 20))
            if endgame and me["hp"] < enemies[0]["hp"] - 22 and not me["hit_last"]:
                pass  # losing the duel: fall through and try to disengage
            else:
                return ("shoot", tgt["id"])
    # move to the safest in-zone cell next to us
    best, best_val = ("repair",) if not t else ("wait",), None
    for dx, dy in DIRS + [(0, 0)]:
        p = (pos[0] + dx, pos[1] + dy)
        if not (0 <= p[0] < SIZE and 0 <= p[1] < SIZE) or _cheb_center(p) > view["next_radius"]:
            continue
        threat = sum(hit_chance(dist(p, e["pos"])) for e in enemies if dist(p, e["pos"]) <= RANGE + 1)
        val = -threat - 0.02 * _cheb_center(p)
        if best_val is None or val > best_val + 1e-9:
            best_val, best = val, (("move", dx, dy) if (dx, dy) != (0, 0) else (("repair",) if not t and me["hp"] < 100 else ("wait",)))
    return best


def v4_lookahead(view):
    """Score every legal action by expected damage dealt minus expected damage taken,
    assuming each enemy shoots whoever it is most likely to hit."""
    me = view["me"]
    pos = me["pos"]
    enemies = view["enemies"]
    n = len(enemies)
    caution = 1.6 if n >= 3 else 1.0 if n == 2 else 0.75  # fewer enemies -> fight harder

    def incoming(p):
        tot = 0.0
        for e in enemies:
            d = dist(p, e["pos"])
            if d > RANGE:
                continue
            others = [dist(e["pos"], o["pos"]) for o in enemies if o["id"] != e["id"]]
            closer = sum(1 for od in others if od < d)
            tot += hit_chance(d) * 22 / (1 + closer)  # it may prefer a closer target
        return tot

    def zone_pen(p):
        return 40.0 if _cheb_center(p) > view["next_radius"] else 0.0

    best, best_val = ("wait",), -1e9
    options = [("wait",), ("repair",)] + [("move", dx, dy) for dx, dy in DIRS] + [("shoot", e["id"]) for e in _in_range(view)]
    for a in options:
        p = pos
        gain = 0.0
        if a[0] == "move":
            p = (pos[0] + a[1], pos[1] + a[2])
            if not (0 <= p[0] < SIZE and 0 <= p[1] < SIZE):
                continue
        elif a[0] == "shoot":
            e = next(x for x in enemies if x["id"] == a[1])
            pc = hit_chance(dist(pos, e["pos"]))
            gain = pc * 22 * (1.0 + (1.5 if e["hp"] <= 22 else 0.0)) + (6.0 if e["hp"] <= 44 else 0.0) * pc
        elif a[0] == "repair":
            gain = 0.0 if me["hit_last"] else min(9, 100 - me["hp"]) * 1.2
        val = gain - caution * incoming(p) - zone_pen(p) - 0.05 * _cheb_center(p)
        if val > best_val:
            best_val, best = val, a
    return best


# The baseline opponent field: random, a chaser, a camper.
FIELD = [b_random, b_aggro, b_camper]

# The strong field run.py ranks against -- the better bots, including copies of
# bots that themselves appear on the ladder (so a candidate meets its own kind).
STRONG_FIELD = [b_aggro, b_camper, v2_zone_focus, v3_survivor, v4_lookahead]

# The weak->strong ladder: (name, bot). Nothing that scored is ever deleted.
ALL = [("v0 random", b_random),
       ("v1 chase and shoot nearest", b_aggro),
       ("v1b camp the centre", b_camper),
       ("v2 zone-aware, focus weakest", v2_zone_focus),
       ("v3 survivor: avoid fights, finish kills", v3_survivor),
       ("v4 one-step lookahead on expected damage", v4_lookahead)]
