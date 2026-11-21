"""The arena simulation: the battle-royale engine and its match scorer.

Lifted verbatim (behaviour-preserving) from the original
``practice/builders_mech_royale/bench.py``. The real "Mech Royale" rules are
unknown; this is a stand-in with the mechanics such games usually share: a
shrinking safe zone, ranged attacks that are less accurate at distance, healing,
and simultaneous turns.

Rules here: SIZE x SIZE grid, 6 mechs, 100 HP each. Every turn each mech picks
one action:

* ``("move", dx, dy)``  one step (4 directions)
* ``("shoot", id)``     range <= 5 (Manhattan); hit chance 0.95 - 0.13 * distance; 22 damage
* ``("repair",)``       +9 HP, only if nobody shot you last turn
* ``("wait",)``

Moves resolve first, then shots. The zone shrinks every 6 turns; outside it you
lose 12 HP a turn. Points by placement: 10 / 6 / 4 / 2 / 1 / 0, plus 1 per kill.
"""
from __future__ import annotations

import random

SIZE, N_MECHS, MAX_TURNS, RANGE = 13, 6, 120, 5
PLACE_POINTS = [10, 6, 4, 2, 1, 0]


def dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def zone_radius(turn: int) -> int:
    return max(1, SIZE // 2 + 1 - turn // 6)


def in_zone(pos, turn: int) -> bool:
    c = SIZE // 2
    return max(abs(pos[0] - c), abs(pos[1] - c)) <= zone_radius(turn)


def hit_chance(d: int) -> float:
    return max(0.0, 0.95 - 0.13 * d)


def play(bots, seed: int):
    """bots: list of callables bot(view) -> action. Returns points per bot index."""
    rng = random.Random(seed)
    cells = [(x, y) for x in range(SIZE) for y in range(SIZE)]
    starts = rng.sample(cells, len(bots))
    mechs = [{"id": i, "pos": starts[i], "hp": 100, "alive": True, "hit_last": False, "kills": 0} for i in range(len(bots))]
    order_out: list[int] = []
    for turn in range(MAX_TURNS):
        alive = [m for m in mechs if m["alive"]]
        if len(alive) <= 1:
            break
        actions = {}
        for m in alive:
            view = {"turn": turn, "me": dict(m), "radius": zone_radius(turn), "next_radius": zone_radius(turn + 1),
                    "enemies": [dict(e) for e in alive if e["id"] != m["id"]], "size": SIZE}
            try:
                actions[m["id"]] = bots[m["id"]](view)
            except Exception:
                actions[m["id"]] = ("wait",)
        for m in alive:  # moves
            a = actions[m["id"]]
            if a and a[0] == "move":
                dx, dy = max(-1, min(1, a[1])), max(-1, min(1, a[2]))
                if abs(dx) + abs(dy) == 1:
                    nx, ny = m["pos"][0] + dx, m["pos"][1] + dy
                    if 0 <= nx < SIZE and 0 <= ny < SIZE:
                        m["pos"] = (nx, ny)
        hit_now = set()
        dmg: dict[int, list[int]] = {}
        for m in alive:  # shots (simultaneous)
            a = actions[m["id"]]
            if a and a[0] == "shoot":
                t = next((e for e in alive if e["id"] == a[1] and e["id"] != m["id"]), None)
                if t and dist(m["pos"], t["pos"]) <= RANGE and rng.random() < hit_chance(dist(m["pos"], t["pos"])):
                    dmg.setdefault(t["id"], []).append(m["id"])
                    hit_now.add(t["id"])
        for m in alive:
            a = actions[m["id"]]
            if a and a[0] == "repair" and not m["hit_last"] and m["id"] not in hit_now:
                m["hp"] = min(100, m["hp"] + 9)
        for tid, shooters in dmg.items():
            t = mechs[tid]
            t["hp"] -= 22 * len(shooters)
            if t["hp"] <= 0:
                mechs[rng.choice(shooters)]["kills"] += 1
        for m in alive:
            if not in_zone(m["pos"], turn):
                m["hp"] -= 12
            m["hit_last"] = m["id"] in hit_now
        dead = [m for m in alive if m["hp"] <= 0]
        rng.shuffle(dead)
        for m in dead:
            m["alive"] = False
            order_out.append(m["id"])
    survivors = sorted((m for m in mechs if m["alive"]), key=lambda m: m["hp"])
    order_out += [m["id"] for m in survivors]
    ranking = order_out[::-1]  # best first
    pts = [0.0] * len(bots)
    for place, i in enumerate(ranking):
        pts[i] = PLACE_POINTS[place] + mechs[i]["kills"]
    return pts, ranking


def evaluate(candidate, field, n_matches: int, seed: int):
    """Candidate vs 5 opponents drawn from `field`. Returns (mean points, win rate, top-2 rate)."""
    rng = random.Random(seed)
    total = wins = top2 = 0
    for k in range(n_matches):
        opp = [rng.choice(field) for _ in range(N_MECHS - 1)]
        slot = rng.randrange(N_MECHS)
        bots = opp[:slot] + [candidate] + opp[slot:]
        pts, ranking = play(bots, seed * 100003 + k)
        total += pts[slot]
        wins += ranking[0] == slot
        top2 += slot in ranking[:2]
    return total / n_matches, wins / n_matches, top2 / n_matches
