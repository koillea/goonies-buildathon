"""Recommenders for the Shopping Sessions track, weakest to strongest.

Lifted verbatim (behaviour-preserving) from the original
``practice/databricks_shopping_sessions/solutions.py``. Each function is a
*builder*: it takes the training sessions and returns ``recommend(prefix) ->
ranked item list``. The ladder climbs by modelling the real transition signal in
a session, not by leaning on global popularity:

    global popularity -> recent popularity -> next-item bigram -> symmetric
    co-visitation -> (tuned) -> directional hybrid -> (tuned)

Two findings the climb encodes (see the track README): a *directional*
next-item count beats *symmetric* co-visitation, and the next event is the same
item the shopper is on ~14% of the time, so revisits must be allowed, not
excluded. ``v4_tuned``/``v6_hybrid_tuned`` grid-search on a time-based split
*inside* the training data -- never on the leaderboard.
"""
from __future__ import annotations

from collections import Counter, defaultdict

K = 20
TYPE_W = {"view": 1.0, "cart": 3.0, "purchase": 4.0}


def _fill(recs: list[int], fallback: list[int], k: int = K) -> list[int]:
    seen = set(recs)
    for i in fallback:
        if len(recs) >= k:
            break
        if i not in seen:
            recs.append(i)
            seen.add(i)
    return recs[:k]


def v0_global_popularity(train):
    pop = Counter(i for _, s in train for i, _ in s)
    top = [i for i, _ in pop.most_common(K * 3)]
    return lambda prefix: top[:K]


def _recent_pop(train, decay: float = 0.35):
    last = max(w for w, _ in train)
    pop: Counter = Counter()
    for w, s in train:
        wgt = decay ** (last - w)
        for i, _ in s:
            pop[i] += wgt
    return [i for i, _ in pop.most_common(K * 5)]


def v1_recent_popularity(train):
    top = _recent_pop(train)
    return lambda prefix: top[:K]


def v2_next_item_bigram(train):
    """What usually comes right after the last item; fill with recent popularity."""
    nxt: dict[int, Counter] = defaultdict(Counter)
    for _, s in train:
        for (a, _), (b, _) in zip(s, s[1:]):
            nxt[a][b] += 1
    top = _recent_pop(train)

    def rec(prefix):
        last = prefix[-1][0]
        return _fill([i for i, _ in nxt[last].most_common(K)], top)
    return rec


def _covisit(train, window: int = 3, decay: float = 1.0, time_decay: float = 1.0):
    last = max(w for w, _ in train)
    co: dict[int, Counter] = defaultdict(Counter)
    for w, s in train:
        tw = time_decay ** (last - w)
        for idx, (a, _) in enumerate(s):
            for off in range(1, window + 1):
                if idx + off < len(s):
                    b = s[idx + off][0]
                    if b != a:
                        co[a][b] += tw * decay ** (off - 1)
                        co[b][a] += 0.5 * tw * decay ** (off - 1)
    return co


def v3_covisit_session(train, window=3, decay=0.6, time_decay=1.0, recency=0.6, revisit=0.0, use_types=False, topn=40):
    """Score candidates from every item in the session, weighted by how recent it is."""
    co = _covisit(train, window, decay, time_decay)
    co_top = {a: c.most_common(topn) for a, c in co.items()}
    norm = {a: sum(v for _, v in lst) or 1.0 for a, lst in co_top.items()}
    top = _recent_pop(train)

    def rec(prefix):
        scores: Counter = Counter()
        n = len(prefix)
        for pos, (a, typ) in enumerate(prefix):
            w = recency ** (n - 1 - pos) * (TYPE_W[typ] if use_types else 1.0)
            for b, v in co_top.get(a, ()):
                scores[b] += w * v / norm[a]
            if revisit and pos < n - 1:
                scores[a] += revisit * w
        return _fill([i for i, _ in scores.most_common(K)], top)
    return rec


def v4_tuned(train, validate):
    """Grid-search v3's knobs on a time-based validation split, then refit on everything.

    `validate(build)` must return a score to maximise, computed without the hidden set.
    """
    best = (-1.0, None)
    for window in (2, 4):
        for decay in (0.5, 0.8):
            for time_decay in (0.6, 1.0):
                for recency in (0.5, 0.8):
                    for revisit in (0.0, 0.15, 0.4):
                        cfg = dict(window=window, decay=decay, time_decay=time_decay, recency=recency, revisit=revisit)
                        s = validate(lambda tr, cfg=cfg: v3_covisit_session(tr, **cfg))
                        if s > best[0]:
                            best = (s, cfg)
    return v3_covisit_session(train, **best[1]), best[1], best[0]


def v5_hybrid(train, alpha=0.3, revisit=0.2, time_decay=0.7, back=0.5):
    """Directional next-item counts from the last item (the strongest single signal),
    plus a weaker vote from earlier items, plus a bonus for items already seen."""
    last_wk = max(w for w, _ in train)
    nxt: dict[int, Counter] = defaultdict(Counter)
    for w, s in train:
        tw = time_decay ** (last_wk - w)
        for (a, _), (b, _) in zip(s, s[1:]):
            nxt[a][b] += tw
    nxt_top = {a: c.most_common(60) for a, c in nxt.items()}
    norm = {a: sum(v for _, v in lst) or 1.0 for a, lst in nxt_top.items()}
    top = _recent_pop(train)

    def rec(prefix):
        scores: Counter = Counter()
        n = len(prefix)
        last = prefix[-1][0]
        for b, v in nxt_top.get(last, ()):
            scores[b] += v / norm[last]
        for pos, (a, _) in enumerate(prefix[:-1]):
            w = alpha * back ** (n - 2 - pos)
            for b, v in nxt_top.get(a, ()):
                scores[b] += w * v / norm[a]
            scores[a] += revisit * back ** (n - 2 - pos)
        return _fill([i for i, _ in scores.most_common(K)], top)
    return rec


def v6_hybrid_tuned(train, validate):
    best = (-1.0, None)
    for alpha in (0.1, 0.3, 0.6):
        for revisit in (0.05, 0.15, 0.3):
            for time_decay in (0.5, 0.8, 1.0):
                for back in (0.4, 0.8):
                    cfg = dict(alpha=alpha, revisit=revisit, time_decay=time_decay, back=back)
                    s = validate(lambda tr, cfg=cfg: v5_hybrid(tr, **cfg))
                    if s > best[0]:
                        best = (s, cfg)
    return v5_hybrid(train, **best[1]), best[1], best[0]
