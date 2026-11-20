"""Practice benchmark for the anticipated Databricks "Shopping Sessions" track.

Guess: session-based recommendation on e-commerce clickstream (the shape of RecSys
Challenge 2015 / Kaggle OTTO / KDD Cup 2023): given the start of a session, predict
what the shopper interacts with next. Metric here: Recall@20 and MRR@20.

Synthetic shoppers with the effects that matter in real data: long-tail popularity,
popularity drift over time (test week is later than train), within-category browsing,
complementary items, and re-visiting items already seen in the session.
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


def make(seed: int = 7, per_week: int = 6000, n_eval: int = 2000):
    """Return (train, dev, hidden). train = [(week, events)], eval = [(prefix_events, next_item)]."""
    w = World(seed)
    rng = random.Random(seed + 1)
    train = [(wk, w.session(rng, wk)) for wk in range(WEEKS - 1) for _ in range(per_week)]

    def eval_set(s):
        r = random.Random(s)
        out = []
        while len(out) < n_eval:
            sess = w.session(r, WEEKS - 1)
            if len(sess) < 2:
                continue
            k = r.randint(1, len(sess) - 1)
            out.append((sess[:k], sess[k][0]))
        return out

    return train, eval_set(seed + 100), eval_set(seed + 9001)


def score(recommend, cases, k: int = 20) -> tuple[float, float]:
    hit, mrr = 0, 0.0
    for prefix, truth in cases:
        recs = list(recommend(prefix))[:k]
        if truth in recs:
            hit += 1
            mrr += 1.0 / (recs.index(truth) + 1)
    return hit / len(cases), mrr / len(cases)
