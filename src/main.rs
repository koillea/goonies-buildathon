//! Shopping Sessions: fast exact pipeline.
//!
//! Design: read every CSV into memory in parallel, parse chunks in parallel with
//! hand-written parsers that follow rules.md exactly, then shard records by hash so
//! each worker owns a disjoint set of keys (event_id for dedup, person for
//! sessionizing) and needs no locks. Verified against oracle/reference.py.

mod pq;

use rayon::prelude::*;
use rustc_hash::{FxHashMap, FxHasher};
use std::hash::{Hash, Hasher};
use std::path::{Path, PathBuf};
use std::time::Instant;

const DAY: i64 = 86_400_000;
const GAP: i64 = 1_800_000;
const WEEK: i64 = 7 * DAY;
const BAD: i64 = i64::MIN; // unparseable timestamp
const HUGE: i64 = i64::MAX; // F3 too long for i64: valid form, outside every window
const NSH: usize = 512; // shards
const CHUNK: usize = 8 << 20; // bytes per parse task
const ORGANIC: u32 = u32::MAX;
const UNKNOWN_CAT: u32 = u32::MAX;

type B = &'static [u8];

// ------------------------------------------------------------------ helpers
#[inline]
fn shard_of(b: &[u8]) -> usize {
    let mut h = FxHasher::default();
    b.hash(&mut h);
    ((h.finish().wrapping_mul(0x9E37_79B9_7F4A_7C15) >> 32) as usize) % NSH
}

/// One CSV field: Err = malformed; Ok(None) = null.
#[inline]
fn field(f: B) -> Result<Option<B>, ()> {
    let v = if memchr::memchr(b'"', f).is_some() {
        let n = f.len();
        if n < 2 || f[0] != b'"' || f[n - 1] != b'"' {
            return Err(());
        }
        let inner = &f[1..n - 1];
        if memchr::memchr(b'"', inner).is_some() {
            return Err(());
        }
        inner
    } else {
        f
    };
    Ok(if v.is_empty() { None } else { Some(v) })
}

/// Split a line into exactly N fields; None if malformed.
#[inline]
fn fields<const N: usize>(line: B) -> Option<[Option<B>; N]> {
    if line.is_empty() {
        return None;
    }
    let mut out = [None; N];
    let mut idx = 0;
    let mut start = 0;
    for p in memchr::memchr_iter(b',', line) {
        if idx >= N - 1 {
            return None;
        }
        out[idx] = field(&line[start..p]).ok()?;
        idx += 1;
        start = p + 1;
    }
    if idx != N - 1 {
        return None;
    }
    out[N - 1] = field(&line[start..]).ok()?;
    Some(out)
}

fn days_from_civil(y: i64, m: i64, d: i64) -> i64 {
    let y = if m <= 2 { y - 1 } else { y };
    let era = if y >= 0 { y } else { y - 399 } / 400;
    let yoe = y - era * 400;
    let doy = (153 * (m + if m > 2 { -3 } else { 9 }) + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146_097 + doe - 719_468
}

#[inline]
fn d2(b: &[u8], i: usize) -> Option<i64> {
    let a = b[i].wrapping_sub(b'0');
    let c = b[i + 1].wrapping_sub(b'0');
    if a < 10 && c < 10 { Some((a * 10 + c) as i64) } else { None }
}

/// "YYYY-MM-DDTHH:MM:SS" prefix -> epoch ms, validating the calendar.
#[inline]
fn civil(b: &[u8]) -> Option<i64> {
    if b[4] != b'-' || b[7] != b'-' || b[10] != b'T' || b[13] != b':' || b[16] != b':' {
        return None;
    }
    let y = d2(b, 0)? * 100 + d2(b, 2)?;
    let (mo, d, h, mi, s) = (d2(b, 5)?, d2(b, 8)?, d2(b, 11)?, d2(b, 14)?, d2(b, 17)?);
    if !(1..=12).contains(&mo) || h > 23 || mi > 59 || s > 59 {
        return None;
    }
    let leap = y % 4 == 0 && (y % 100 != 0 || y % 400 == 0);
    let md = [31, if leap { 29 } else { 28 }, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][(mo - 1) as usize];
    if d < 1 || d > md {
        return None;
    }
    Some(((days_from_civil(y, mo, d) * 24 + h) * 60 + mi) * 60_000 + s * 1000)
}

#[inline]
fn parse_ts(v: Option<B>) -> i64 {
    let Some(b) = v else { return BAD };
    if b.len() == 20 && b[19] == b'Z' {
        return civil(b).unwrap_or(BAD);
    }
    if b.len() == 25 && (b[19] == b'+' || b[19] == b'-') && b[22] == b':' {
        let (Some(base), Some(oh), Some(om)) = (civil(b), d2(b, 20), d2(b, 23)) else { return BAD };
        if oh > 23 || om > 59 {
            return BAD;
        }
        let off = (oh * 60 + om) * 60_000;
        return if b[19] == b'+' { base - off } else { base + off };
    }
    let mut v: i64 = 0;
    for &c in b {
        let d = c.wrapping_sub(b'0');
        if d >= 10 {
            return BAD;
        }
        v = match v.checked_mul(10).and_then(|x| x.checked_add(d as i64)) {
            Some(x) => x,
            None => {
                // keep validating that the rest are digits; the value is simply huge
                return if b.iter().all(|c| c.is_ascii_digit()) { HUGE } else { BAD };
            }
        };
    }
    v
}

/// Digits-only price in 1..=10_000_000, else None.
#[inline]
fn parse_price(v: Option<B>) -> Option<i64> {
    let b = v?;
    let mut x: i64 = 0;
    for &c in b {
        let d = c.wrapping_sub(b'0');
        if d >= 10 {
            return None;
        }
        x = x * 10 + d as i64;
        if x > 10_000_000 {
            // still must be all digits to be "bad price" vs anything else: both drop
            return None;
        }
    }
    if x >= 1 { Some(x) } else { None }
}

// ------------------------------------------------------------------ input
fn csv_files(dir: &Path) -> Vec<PathBuf> {
    let mut v: Vec<PathBuf> = match std::fs::read_dir(dir) {
        Ok(rd) => rd
            .filter_map(|e| e.ok().map(|e| e.path()))
            .filter(|p| p.extension().is_some_and(|x| x == "csv") && p.is_file())
            .collect(),
        Err(_) => vec![],
    };
    v.sort();
    v
}

fn load(paths: &[PathBuf]) -> Vec<B> {
    paths
        .par_iter()
        .map(|p| &*Box::leak(std::fs::read(p).expect("read").into_boxed_slice()))
        .collect()
}

/// Data region of each file (after the header line), cut into chunks that end on '\n'.
fn chunks(bufs: &[B]) -> Vec<B> {
    let mut out = vec![];
    for &buf in bufs {
        let Some(h) = memchr::memchr(b'\n', buf) else { continue };
        let mut rest = &buf[h + 1..];
        while rest.len() > CHUNK {
            let cut = match memchr::memchr(b'\n', &rest[CHUNK..]) {
                Some(i) => CHUNK + i + 1,
                None => rest.len(),
            };
            out.push(&rest[..cut]);
            rest = &rest[cut..];
        }
        if !rest.is_empty() {
            out.push(rest);
        }
    }
    out
}

/// Iterate the lines of a chunk ('\n' only; a final empty piece is not a line).
#[inline]
fn lines(chunk: B) -> impl Iterator<Item = B> {
    let n = chunk.len();
    let mut start = 0;
    std::iter::from_fn(move || {
        if start >= n {
            return None;
        }
        let end = memchr::memchr(b'\n', &chunk[start..]).map_or(n, |i| start + i);
        let line = &chunk[start..end];
        start = end + 1;
        Some(line)
    })
}

fn small_table(path: &Path) -> Vec<(B, B)> {
    let Ok(buf) = std::fs::read(path) else { return vec![] };
    let buf: B = Box::leak(buf.into_boxed_slice());
    let Some(h) = memchr::memchr(b'\n', buf) else { return vec![] };
    lines(&buf[h + 1..])
        .filter_map(|l| fields::<2>(l))
        .filter_map(|[a, b]| Some((a?, b.unwrap_or(b""))))
        .collect()
}

// ------------------------------------------------------------------ records
#[derive(Clone, Copy)]
struct Ev {
    eid: B,
    uid: B,
    pid: B,
    ing: i64,
    ts: i64,
    price: i64,
    ok: bool,
    kind: u8, // 0 view, 1 cart, 2 purchase
}

#[derive(Clone, Copy)]
struct PEv {
    name: B,
    ts: i64,
    price: i64, // 0 unless purchase
    cat: u32,
    purchase: bool,
}

#[derive(Clone, Copy)]
struct PCl {
    name: B,
    ts: i64,
    cid: B,
    camp: u32,
}

fn scatter<T: Send>(per_chunk: Vec<Vec<Vec<T>>>) -> Vec<Vec<T>> {
    // per_chunk[c][s] -> shards[s]
    let mut cols: Vec<Vec<Vec<T>>> = (0..NSH).map(|_| Vec::with_capacity(per_chunk.len())).collect();
    for chunk in per_chunk {
        for (s, v) in chunk.into_iter().enumerate() {
            cols[s].push(v);
        }
    }
    cols.into_par_iter().map(|vs| vs.into_iter().flatten().collect()).collect()
}

fn main() {
    let t0 = Instant::now();
    let args: Vec<String> = std::env::args().collect();
    let env = |k: &str, d: &str| std::env::var(k).unwrap_or_else(|_| d.to_string());
    let (data, out) = if args.len() >= 3 {
        (PathBuf::from(&args[1]), PathBuf::from(&args[2]))
    } else {
        (PathBuf::from(env("DATA_DIR", "/data")), PathBuf::from(env("OUTPUT_DIR", "/output")))
    };
    let ncpu: usize = env("NCPU", "0").parse().unwrap_or(0);
    let ncpu = if ncpu == 0 { std::thread::available_parallelism().map_or(8, |n| n.get()) } else { ncpu };
    rayon::ThreadPoolBuilder::new().num_threads(ncpu).build_global().ok();
    let lap = |what: &str| eprintln!("{:>8.3}s {what}", t0.elapsed().as_secs_f64());

    // manifest (tiny JSON): pull the two ISO strings out
    let man = std::fs::read_to_string(data.join("manifest.json")).expect("manifest");
    let grab = |key: &str| -> i64 {
        let i = man.find(key).expect("key") + key.len();
        let s = &man[i..];
        let a = s.find('"').unwrap() + 1;
        let s = &s[a..];
        let b = s.find('"').unwrap();
        let ts = parse_ts(Some(Box::leak(s[..b].as_bytes().to_vec().into_boxed_slice())));
        assert!(ts != BAD, "manifest timestamp");
        ts
    };
    let (ws, we) = (grab("\"window_start\""), grab("\"window_end\""));

    // read everything in parallel
    let (ev_files, cl_files, ln_files) =
        (csv_files(&data.join("events")), csv_files(&data.join("clicks")), csv_files(&data.join("links")));
    let ev_bufs = load(&ev_files);
    let cl_bufs = load(&cl_files);
    let ln_bufs = load(&ln_files);
    lap("read");

    // products / campaigns
    let mut cat_names: Vec<B> = vec![];
    let mut cat_idx: FxHashMap<B, u32> = FxHashMap::default();
    let mut products: FxHashMap<B, u32> = FxHashMap::default();
    for (pid, cat) in small_table(&data.join("products.csv")) {
        let n = cat_names.len() as u32;
        let ci = *cat_idx.entry(cat).or_insert_with(|| {
            cat_names.push(cat);
            n
        });
        products.insert(pid, ci);
    }
    let mut camp_ids: Vec<B> = vec![];
    let mut camp_chan: Vec<B> = vec![];
    let mut campaigns: FxHashMap<B, u32> = FxHashMap::default();
    for (cid, ch) in small_table(&data.join("campaigns.csv")) {
        campaigns.insert(cid, camp_ids.len() as u32);
        camp_ids.push(cid);
        camp_chan.push(ch);
    }

    // links: union-find, root kept as byte-wise smallest ID
    let pairs: Vec<(B, B)> = chunks(&ln_bufs)
        .par_iter()
        .flat_map_iter(|&c| {
            lines(c).filter_map(|l| match fields::<2>(l) {
                Some([Some(a), Some(b)]) => Some((a, b)),
                _ => None,
            })
        })
        .collect();
    let mut intern: FxHashMap<B, u32> = FxHashMap::default();
    let mut names: Vec<B> = vec![];
    let mut parent: Vec<u32> = vec![];
    let id_of = |s: B, intern: &mut FxHashMap<B, u32>, names: &mut Vec<B>, parent: &mut Vec<u32>| -> u32 {
        *intern.entry(s).or_insert_with(|| {
            let i = names.len() as u32;
            names.push(s);
            parent.push(i);
            i
        })
    };
    fn find(parent: &mut [u32], mut x: u32) -> u32 {
        let mut r = x;
        while parent[r as usize] != r {
            r = parent[r as usize];
        }
        while parent[x as usize] != r {
            let n = parent[x as usize];
            parent[x as usize] = r;
            x = n;
        }
        r
    }
    for &(a, b) in &pairs {
        let ia = id_of(a, &mut intern, &mut names, &mut parent);
        let ib = id_of(b, &mut intern, &mut names, &mut parent);
        let (ra, rb) = (find(&mut parent, ia), find(&mut parent, ib));
        if ra != rb {
            let (lo, hi) = if names[ra as usize] <= names[rb as usize] { (ra, rb) } else { (rb, ra) };
            parent[hi as usize] = lo;
        }
    }
    let mut link_name: FxHashMap<B, B> = FxHashMap::default();
    link_name.reserve(names.len());
    for i in 0..names.len() as u32 {
        let r = find(&mut parent, i);
        if r != i {
            link_name.insert(names[i as usize], names[r as usize]);
        }
    }
    let person = |u: B| -> B { link_name.get(u).copied().unwrap_or(u) };
    lap("links");

    // events: parse + validate each copy, scatter by event_id
    let ev_chunks = chunks(&ev_bufs);
    let per_chunk: Vec<Vec<Vec<Ev>>> = ev_chunks
        .par_iter()
        .map(|&c| {
            let mut sh: Vec<Vec<Ev>> = (0..NSH).map(|_| Vec::new()).collect();
            for l in lines(c) {
                let Some([eid, uid, ts, ing, et, pid, price]) = fields::<7>(l) else { continue };
                let Some(eid) = eid else { continue };
                let ing = parse_ts(ing);
                let ts = parse_ts(ts);
                let kind = match et {
                    Some(b"view") => 0,
                    Some(b"cart") => 1,
                    Some(b"purchase") => 2,
                    _ => 3,
                };
                let mut ok = uid.is_some() && pid.is_some() && kind < 3 && ts != BAD && ts >= ws && ts < we;
                let mut p = 0;
                if ok && kind == 2 {
                    match parse_price(price) {
                        Some(v) => p = v,
                        None => ok = false,
                    }
                }
                if ok && ing - ts > DAY {
                    ok = false;
                }
                sh[shard_of(eid)].push(Ev {
                    eid,
                    uid: uid.unwrap_or(b""),
                    pid: pid.unwrap_or(b""),
                    ing,
                    ts,
                    price: p,
                    ok,
                    kind,
                });
            }
            sh
        })
        .collect();
    let ev_shards = scatter(per_chunk);
    lap("events parsed");

    // dedup within each event shard, keep surviving events, re-scatter by person
    let per_shard: Vec<Vec<Vec<PEv>>> = ev_shards
        .into_par_iter()
        .map(|evs| {
            let mut best: FxHashMap<B, usize> = FxHashMap::default();
            best.reserve(evs.len());
            for (i, e) in evs.iter().enumerate() {
                best.entry(e.eid)
                    .and_modify(|j| {
                        if e.ing < evs[*j].ing {
                            *j = i
                        }
                    })
                    .or_insert(i);
            }
            let mut sh: Vec<Vec<PEv>> = (0..NSH).map(|_| Vec::new()).collect();
            for &i in best.values() {
                let e = &evs[i];
                if !e.ok {
                    continue;
                }
                let name = person(e.uid);
                let cat = if e.kind == 2 { products.get(e.pid).copied().unwrap_or(UNKNOWN_CAT) } else { 0 };
                sh[shard_of(name)].push(PEv { name, ts: e.ts, price: e.price, cat, purchase: e.kind == 2 });
            }
            sh
        })
        .collect();
    let pev_shards = scatter(per_shard);
    lap("events deduped");

    // clicks: copies are identical, so duplicates cannot change credit or assists
    let cl_chunks = chunks(&cl_bufs);
    let per_chunk: Vec<Vec<Vec<PCl>>> = cl_chunks
        .par_iter()
        .map(|&c| {
            let mut sh: Vec<Vec<PCl>> = (0..NSH).map(|_| Vec::new()).collect();
            for l in lines(c) {
                let Some([Some(cid), Some(uid), Some(camp), ts]) = fields::<4>(l) else { continue };
                let Some(&camp) = campaigns.get(camp) else { continue };
                let ts = parse_ts(ts);
                if ts == BAD || ts < ws - WEEK || ts >= we {
                    continue;
                }
                let name = person(uid);
                sh[shard_of(name)].push(PCl { name, ts, cid, camp });
            }
            sh
        })
        .collect();
    let pcl_shards = scatter(per_chunk);
    lap("clicks parsed");

    // per person-shard: sessionize, attribute, aggregate
    struct URow {
        name: B,
        day: i32,
        sessions: i64,
        events: i64,
        revenue: i64,
        top: Option<u32>,
    }
    let results: Vec<(Vec<URow>, FxHashMap<(u32, i32), [i64; 4]>)> = pev_shards
        .into_par_iter()
        .zip(pcl_shards.into_par_iter())
        .map(|(mut evs, mut cls)| {
            evs.sort_unstable_by(|a, b| a.name.cmp(b.name).then(a.ts.cmp(&b.ts)));
            // by ts ascending, then click_id DESCENDING: the last eligible click is the winner
            cls.sort_unstable_by(|a, b| a.name.cmp(b.name).then(a.ts.cmp(&b.ts)).then(b.cid.cmp(a.cid)));
            let mut urows: Vec<URow> = vec![];
            let mut camp: FxHashMap<(u32, i32), [i64; 4]> = FxHashMap::default();
            let mut ci = 0usize;
            let mut i = 0usize;
            let mut cats: Vec<(u32, i64)> = vec![];
            let mut active: FxHashMap<u32, u32> = FxHashMap::default();
            while i < evs.len() {
                let name = evs[i].name;
                let mut j = i;
                while j < evs.len() && evs[j].name == name {
                    j += 1;
                }
                while ci < cls.len() && cls[ci].name < name {
                    ci += 1;
                }
                let mut cj = ci;
                while cj < cls.len() && cls[cj].name == name {
                    cj += 1;
                }
                let pcl = &cls[ci..cj];
                // sliding window [lo, hi) over this person's clicks
                let (mut lo, mut hi) = (0usize, 0usize);
                active.clear();
                let mut cur_day = i32::MIN;
                let mut row: Option<URow> = None;
                let mut k = i;
                while k < j {
                    // one session: extend while gap between distinct timestamps <= GAP
                    let start = evs[k].ts;
                    let mut prev = start;
                    let mut e = k;
                    let (mut n, mut rev, mut purch) = (0i64, 0i64, false);
                    while e < j && (evs[e].ts == prev || evs[e].ts - prev <= GAP) {
                        let x = &evs[e];
                        prev = x.ts;
                        n += 1;
                        if x.purchase {
                            purch = true;
                            rev += x.price;
                        }
                        e += 1;
                    }
                    let day = start.div_euclid(DAY) as i32;
                    if day != cur_day {
                        if let Some(r) = row.take() {
                            urows.push(finish(r, &mut cats, &cat_names));
                        }
                        cur_day = day;
                        row = Some(URow { name, day, sessions: 0, events: 0, revenue: 0, top: None });
                    }
                    let r = row.as_mut().unwrap();
                    r.sessions += 1;
                    r.events += n;
                    r.revenue += rev;
                    for x in &evs[k..e] {
                        if x.purchase {
                            match cats.iter_mut().find(|c| c.0 == x.cat) {
                                Some(c) => c.1 += x.price,
                                None => cats.push((x.cat, x.price)),
                            }
                        }
                    }
                    // attribution window: start - WEEK <= click.ts <= start
                    while hi < pcl.len() && pcl[hi].ts <= start {
                        *active.entry(pcl[hi].camp).or_insert(0) += 1;
                        hi += 1;
                    }
                    while lo < hi && pcl[lo].ts < start - WEEK {
                        let c = active.get_mut(&pcl[lo].camp).unwrap();
                        *c -= 1;
                        if *c == 0 {
                            active.remove(&pcl[lo].camp);
                        }
                        lo += 1;
                    }
                    let credit = if hi > lo { pcl[hi - 1].camp } else { ORGANIC };
                    let a = camp.entry((credit, day)).or_insert([0; 4]);
                    a[0] += 1;
                    a[1] += purch as i64;
                    a[2] += rev;
                    for &c in active.keys() {
                        camp.entry((c, day)).or_insert([0; 4])[3] += 1;
                    }
                    k = e;
                }
                if let Some(r) = row.take() {
                    urows.push(finish(r, &mut cats, &cat_names));
                }
                i = j;
            }
            (urows, camp)
        })
        .collect();
    fn finish(mut r: URow, cats: &mut Vec<(u32, i64)>, cat_names: &[B]) -> URow {
        let name_of = |c: u32| -> &[u8] { if c == UNKNOWN_CAT { b"unknown" } else { cat_names[c as usize] } };
        let mut best: Option<(u32, i64)> = None;
        for &(c, v) in cats.iter() {
            best = match best {
                None => Some((c, v)),
                Some((bc, bv)) => {
                    if v > bv || (v == bv && name_of(c) < name_of(bc)) { Some((c, v)) } else { Some((bc, bv)) }
                }
            };
        }
        r.top = best.map(|b| b.0);
        cats.clear();
        r
    }
    lap("sessionized");

    // merge campaign partials
    let mut camp_all: FxHashMap<(u32, i32), [i64; 4]> = FxHashMap::default();
    let mut user_parts: Vec<Vec<URow>> = vec![];
    for (u, c) in results {
        user_parts.push(u);
        for (k, v) in c {
            let a = camp_all.entry(k).or_insert([0; 4]);
            for t in 0..4 {
                a[t] += v[t];
            }
        }
    }

    // write Parquet (minimal writer in pq.rs)
    let ud = out.join("user_daily");
    let cd = out.join("campaign_daily");
    std::fs::create_dir_all(&ud).unwrap();
    std::fs::create_dir_all(&cd).unwrap();
    let cat_name = |c: u32| -> B { if c == UNKNOWN_CAT { b"unknown" } else { cat_names[c as usize] } };
    let groups: Vec<Vec<Vec<URow>>> = {
        let mut g: Vec<Vec<Vec<URow>>> = (0..ncpu).map(|_| vec![]).collect();
        for (i, p) in user_parts.into_iter().enumerate() {
            g[i % ncpu].push(p);
        }
        g
    };
    groups.into_par_iter().enumerate().for_each(|(gi, parts)| {
        let rows: Vec<&URow> = parts.iter().flatten().collect();
        pq::write(
            &ud.join(format!("part-{gi}.parquet")),
            &[
                ("user_id", pq::Col::Str(rows.iter().map(|r| Some(r.name)).collect(), false)),
                ("day", pq::Col::Date(rows.iter().map(|r| r.day).collect())),
                ("sessions", pq::Col::I64(rows.iter().map(|r| r.sessions).collect())),
                ("events", pq::Col::I64(rows.iter().map(|r| r.events).collect())),
                ("revenue_cents", pq::Col::I64(rows.iter().map(|r| r.revenue).collect())),
                ("top_category", pq::Col::Str(rows.iter().map(|r| r.top.map(cat_name)).collect(), true)),
            ],
        )
        .expect("write user_daily");
    });
    let crows: Vec<((u32, i32), [i64; 4])> = camp_all.into_iter().collect();
    let cid = |cp: u32| -> B { if cp == ORGANIC { b"organic" } else { camp_ids[cp as usize] } };
    let cch = |cp: u32| -> B { if cp == ORGANIC { b"organic" } else { camp_chan[cp as usize] } };
    pq::write(
        &cd.join("part-0.parquet"),
        &[
            ("campaign_id", pq::Col::Str(crows.iter().map(|((c, _), _)| Some(cid(*c))).collect(), false)),
            ("channel", pq::Col::Str(crows.iter().map(|((c, _), _)| Some(cch(*c))).collect(), false)),
            ("day", pq::Col::Date(crows.iter().map(|((_, d), _)| *d).collect())),
            ("sessions", pq::Col::I64(crows.iter().map(|(_, a)| a[0]).collect())),
            ("purchasing_sessions", pq::Col::I64(crows.iter().map(|(_, a)| a[1]).collect())),
            ("revenue_cents", pq::Col::I64(crows.iter().map(|(_, a)| a[2]).collect())),
            ("assisted_sessions", pq::Col::I64(crows.iter().map(|(_, a)| a[3]).collect())),
        ],
    )
    .expect("write campaign_daily");
    lap("written");
    // skip freeing gigabytes of memory on the way out
    std::process::exit(0);
}
