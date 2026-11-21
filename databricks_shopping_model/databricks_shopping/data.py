"""Synthetic shopper world and the session datasets.

Lifted verbatim (behaviour-preserving) from the original
``practice/databricks_shopping_sessions/bench.py``. We do not know the real
Databricks "Shopping Sessions" format yet; this generates the effects that make
session-based recommendation hard on real clickstream: long-tail popularity,
popularity drift over time (the eval week is later than the train weeks),
within-category browsing, complementary items, and re-visiting items already
seen in the session.

The task is "fit-then-recommend": a *train* split (weeks of sessions) is what a
solver fits on; a *dev* and a *hidden* eval split (prefixes of later-week
sessions, each paired with the true next item) are what it is scored on. The
hidden split is generated from a **different seed** so it stands in for sessions
the model has never seen.

The ``World`` class, the session simulator, and ``make`` are copied unchanged
from the original benchmark; ``build_train`` and ``eval_set`` are the two halves
of the original ``make`` pulled out as reusable module functions (so the harness
can drive train once and build dev/hidden from independent seeds) -- ``make``
still composes them in exactly the original order, so its output is identical.
"""
from __future__ import annotations

import random
from bisect import bisect

N_ITEMS, N_CATS, WEEKS = 600, 30, 5


class World:
    def __init__(self, seed: int = 7):
        rng = random.Random(seed)
        self.cat = [rng.randrange(N_CATS) for _ in range(N_ITEMS)]
        self.by_cat: dict[int, list[int]] = {}
        for i, c in enumerate(self.cat):
            self.by_cat.setdefault(c, []).append(i)
        base = [1.0 / (r + 1) ** 0.8 for r in range(N_ITEMS)]
        rng.shuffle(base)
        # popularity random-walks week to week (trends appear and fade)
        self.pop = [base]
        for _ in range(WEEKS - 1):
            prev = self.pop[-1]
            self.pop.append([p * rng.choice([0.5, 0.8, 1.0, 1.0, 1.25, 2.5]) for p in prev])
        self.comp = {i: rng.sample([j for j in range(N_ITEMS) if self.cat[j] != self.cat[i]], 3) for i in range(N_ITEMS)}
        self._cum: dict[tuple, tuple[list[int], list[float]]] = {}

    def _sample(self, rng, week, pool_key, pool):
        key = (week, pool_key)
        if key not in self._cum:
            acc, cum = 0.0, []
            for i in pool:
                acc += self.pop[week][i]
                cum.append(acc)
            self._cum[key] = (pool, cum)
        pool, cum = self._cum[key]
        return pool[min(bisect(cum, rng.random() * cum[-1]), len(pool) - 1)]

    def session(self, rng: random.Random, week: int) -> list[tuple[int, str]]:
        allitems = list(range(N_ITEMS))
        cur = self._sample(rng, week, "all", allitems)
        items = [cur]
        while len(items) < 15 and rng.random() < 0.78:
            r = rng.random()
            if r < 0.15 and len(items) > 1:
                cur = rng.choice(items[:-1])                      # go back to something seen
            elif r < 0.60:
                c = self.cat[cur]
                cur = self._sample(rng, week, ("cat", c), self.by_cat[c])  # browse the category
            elif r < 0.80:
                cur = rng.choice(self.comp[rng.choice(items[-3:])])        # complement
            else:
                cur = self._sample(rng, week, "all", allitems)             # wander
            items.append(cur)
        out = []
        for it in items:
            r = rng.random()
            out.append((it, "purchase" if r < 0.05 else "cart" if r < 0.2 else "view"))
        return out


def build_train(world: World, seed: int, per_week: int):
    """The training split: ``per_week`` sessions for each of the first WEEKS-1 weeks.

    Same construction (single shared RNG seeded at ``seed + 1``, week-major order)
    as the original ``make``.
    """
    rng = random.Random(seed + 1)
    return [(wk, world.session(rng, wk)) for wk in range(WEEKS - 1) for _ in range(per_week)]


def eval_set(world: World, seed: int, n_eval: int):
    """``n_eval`` evaluation cases from the final (later) week.

    Each case is ``(prefix_events, next_item)``: a random prefix of a session and
    the item that actually came next. Identical logic to the inner ``eval_set``
    of the original ``make``.
    """
    r = random.Random(seed)
    out = []
    while len(out) < n_eval:
        sess = world.session(r, WEEKS - 1)
        if len(sess) < 2:
            continue
        k = r.randint(1, len(sess) - 1)
        out.append((sess[:k], sess[k][0]))
    return out


def make(seed: int = 7, per_week: int = 6000, n_eval: int = 2000):
    """Return (train, dev, hidden). train = [(week, events)], eval = [(prefix_events, next_item)].

    Behaviour-identical to the original benchmark's ``make``: dev comes from
    ``seed + 100`` and hidden from ``seed + 9001`` (different seeds, so hidden is
    unseen data).
    """
    w = World(seed)
    train = build_train(w, seed, per_week)
    return train, eval_set(w, seed + 100, n_eval), eval_set(w, seed + 9001, n_eval)
