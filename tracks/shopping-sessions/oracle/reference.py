#!/usr/bin/env python3
"""Shopping Sessions: slow, literal reference implementation of rules.md.

This is the correctness ORACLE. It favors being an obvious line-by-line reading of
the rules over speed. Every fast implementation is diffed against it on many
generated seeds. Writes Parquet via pyarrow (oracle only; not the submission).

Usage: reference.py [DATA_DIR OUTPUT_DIR]   (or env DATA_DIR / OUTPUT_DIR)
"""
import datetime as dt
import glob
import json
import os
import re
import sys

DAY_MS = 86_400_000
GAP_MS = 1_800_000
WEEK_MS = 7 * DAY_MS

# ---------------------------------------------------------------- CSV dialect
_QUOTED = re.compile(r'^"([^"]*)"$')


def parse_line(line, nfields):
    """Return a list of values (None for null) or None if the line is malformed."""
    if line == "":
        return None  # an empty line is malformed
    parts = line.split(",")
    if len(parts) != nfields:
        return None
    out = []
    for p in parts:
        if '"' in p:
            m = _QUOTED.match(p)
            if not m:
                return None  # a quote anywhere except around a whole field
            p = m.group(1)
        out.append(p if p != "" else None)
    return out


def read_rows(path, nfields):
    with open(path, "rb") as f:
        text = f.read().decode("utf-8")
    pieces = text.split("\n")
    if text.endswith("\n"):
        pieces.pop()  # the empty piece after a final newline is not a line
    for line in pieces[1:]:  # first line is the header
        row = parse_line(line, nfields)
        if row is not None:
            yield row


def read_dir(data, sub, nfields):
    for path in sorted(glob.glob(os.path.join(data, sub, "*.csv"))):
        yield from read_rows(path, nfields)


# ---------------------------------------------------------------- timestamps
_D = "[0-9]"
F1 = re.compile(rf"^({_D}{{4}})-({_D}{{2}})-({_D}{{2}})T({_D}{{2}}):({_D}{{2}}):({_D}{{2}})Z$")
F2 = re.compile(rf"^({_D}{{4}})-({_D}{{2}})-({_D}{{2}})T({_D}{{2}}):({_D}{{2}}):({_D}{{2}})([+-])({_D}{{2}}):({_D}{{2}})$")
F3 = re.compile(rf"^{_D}+$")


def days_from_civil(y, m, d):
    """Days since 1970-01-01 for a proleptic Gregorian date (Howard Hinnant)."""
    y -= m <= 2
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def _leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def _civil_ms(y, mo, d, h, mi, s):
    if not (1 <= mo <= 12):
        return None
    mdays = [31, 29 if _leap(y) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1]
    if not (1 <= d <= mdays) or h > 23 or mi > 59 or s > 59:
        return None
    return ((days_from_civil(y, mo, d) * 24 + h) * 60 + mi) * 60_000 + s * 1000


def parse_ts(v):
    """Epoch ms, or None if bad (format only; window checked by caller)."""
    if v is None:
        return None
    m = F1.match(v)
    if m:
        return _civil_ms(*map(int, m.groups()))
    m = F2.match(v)
    if m:
        y, mo, d, h, mi, s = map(int, m.groups()[:6])
        sign, oh, om = m.group(7), int(m.group(8)), int(m.group(9))
        if oh > 23 or om > 59:
            return None
        base = _civil_ms(y, mo, d, h, mi, s)
        if base is None:
            return None
        off = (oh * 60 + om) * 60_000
        return base - off if sign == "+" else base + off
    if F3.match(v):
        return int(v)
    return None


def iso_ms(s):
    return parse_ts(s.replace("+00:00", "Z")) if s.endswith("+00:00") else parse_ts(s)


# ---------------------------------------------------------------- linked IDs
class DSU:
    def __init__(self):
        self.p = {}

    def find(self, x):
        p = self.p
        if x not in p:
            return x
        root = x
        while p[root] != root:
            root = p[root]
        while p[x] != root:
            p[x], x = root, p[x]
        return root

    def add(self, x):
        self.p.setdefault(x, x)

    def union(self, a, b):
        self.add(a)
        self.add(b)
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            if rb < ra:
                ra, rb = rb, ra
            self.p[rb] = ra  # root is always the smallest ID of the component


def main():
    data = sys.argv[1] if len(sys.argv) > 2 else os.environ.get("DATA_DIR", "/data")
    out = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("OUTPUT_DIR", "/output")
    with open(os.path.join(data, "manifest.json")) as f:
        man = json.load(f)
    ws, we = iso_ms(man["window_start"]), iso_ms(man["window_end"])

    # links: union-find; the root is kept as the byte-wise smallest ID (UTF-8 byte
    # order equals code point order, so str comparison is byte-wise)
    dsu = DSU()
    for a, b in read_dir(data, "links", 2):
        if a is None or b is None:
            continue
        dsu.union(a, b)
    person = dsu.find

    products = {r[0]: r[1] for r in read_rows(os.path.join(data, "products.csv"), 2) if r[0] is not None}
    campaigns = {r[0]: r[1] for r in read_rows(os.path.join(data, "campaigns.csv"), 2) if r[0] is not None}

    # ---- events: parse -> dedup (smallest ingest_ts) -> validate -> late
    kept = {}
    for row in read_dir(data, "events", 7):
        eid = row[0]
        if eid is None:
            continue
        ing = parse_ts(row[3])
        cur = kept.get(eid)
        if cur is None or ing < cur[0]:
            kept[eid] = (ing, row)
    events = []  # (person, ts, type, product, price)
    for ing, (eid, uid, ts_s, _ing_s, etype, pid, price_s) in kept.values():
        if uid is None or pid is None or etype not in ("view", "cart", "purchase"):
            continue
        ts = parse_ts(ts_s)
        if ts is None or not (ws <= ts < we):
            continue
        price = 0
        if etype == "purchase":
            if price_s is None or not re.fullmatch(r"[0-9]+", price_s):
                continue
            price = int(price_s)
            if not (1 <= price <= 10_000_000):
                continue
        if ing - ts > DAY_MS:
            continue
        events.append((person(uid), ts, etype, pid, price))

    # ---- clicks: parse -> dedup -> validate
    clicks = {}
    for cid, uid, camp, ts_s in read_dir(data, "clicks", 4):
        if cid is None or cid in clicks:
            continue
        clicks[cid] = (uid, camp, ts_s)
    by_person = {}
    for cid, (uid, camp, ts_s) in clicks.items():
        if uid is None or camp not in campaigns:
            continue
        ts = parse_ts(ts_s)
        if ts is None or not (ws - WEEK_MS <= ts < we):
            continue
        by_person.setdefault(person(uid), []).append((ts, cid, camp))

    # ---- sessionize per person
    per_person = {}
    for e in events:
        per_person.setdefault(e[0], []).append(e)
    user_rows = {}  # (person, day) -> [sessions, events, revenue, {cat: cents}]
    camp_rows = {}  # (campaign, day) -> [sessions, purchasing, revenue, assisted]
    for pers, evs in per_person.items():
        evs.sort(key=lambda e: e[1])
        sessions, cur, prev_ts = [], None, None
        for e in evs:
            if cur is None or (e[1] != prev_ts and e[1] - prev_ts > GAP_MS):
                cur = []
                sessions.append(cur)
            cur.append(e)
            prev_ts = e[1]
        pclicks = by_person.get(pers, [])
        for s in sessions:
            start = s[0][1]
            day = dt.date(1970, 1, 1) + dt.timedelta(days=start // DAY_MS)
            rev = sum(e[4] for e in s if e[2] == "purchase")
            has_purchase = any(e[2] == "purchase" for e in s)
            ur = user_rows.setdefault((pers, day), [0, 0, 0, {}])
            ur[0] += 1
            ur[1] += len(s)
            ur[2] += rev
            for e in s:
                if e[2] == "purchase":
                    cat = products.get(e[3], "unknown")
                    ur[3][cat] = ur[3].get(cat, 0) + e[4]
            # attribution
            elig = [c for c in pclicks if c[0] <= start and start - c[0] <= WEEK_MS]
            if elig:
                best = max(elig, key=lambda c: (c[0], _neg(c[1])))
                credit = best[2]
            else:
                credit = "organic"
            cr = camp_rows.setdefault((credit, day), [0, 0, 0, 0])
            cr[0] += 1
            cr[1] += 1 if has_purchase else 0
            cr[2] += rev
            for camp in {c[2] for c in elig}:
                camp_rows.setdefault((camp, day), [0, 0, 0, 0])[3] += 1

    write(out, user_rows, camp_rows, campaigns)


class _neg:
    """Order wrapper so max() picks the smallest click_id on a ts tie."""
    __slots__ = ("v",)

    def __init__(self, v):
        self.v = v

    def __lt__(self, o):
        return self.v > o.v

    def __eq__(self, o):
        return self.v == o.v


def write(out, user_rows, camp_rows, campaigns):
    import pyarrow as pa
    import pyarrow.parquet as pq

    u = {"user_id": [], "day": [], "sessions": [], "events": [], "revenue_cents": [], "top_category": []}
    for (pers, day), (s, n, rev, cats) in user_rows.items():
        top = min(cats, key=lambda c: (-cats[c], c)) if cats else None
        for k, v in zip(u, (pers, day, s, n, rev, top)):
            u[k].append(v)
    c = {"campaign_id": [], "channel": [], "day": [], "sessions": [], "purchasing_sessions": [],
         "revenue_cents": [], "assisted_sessions": []}
    for (camp, day), (s, ps, rev, a) in camp_rows.items():
        ch = "organic" if camp == "organic" else campaigns[camp]
        for k, v in zip(c, (camp, ch, day, s, ps, rev, a)):
            c[k].append(v)
    for name, cols in (("user_daily", u), ("campaign_daily", c)):
        os.makedirs(os.path.join(out, name), exist_ok=True)
        schema = pa.schema([(k, pa.date32() if k == "day" else
                             pa.string() if k in ("user_id", "top_category", "campaign_id", "channel")
                             else pa.int64()) for k in cols])
        pq.write_table(pa.table(cols, schema=schema), os.path.join(out, name, "part-0.parquet"))


if __name__ == "__main__":
    main()
