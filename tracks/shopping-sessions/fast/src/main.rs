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
/// Fast 64-bit hash of a short byte string. Collisions are always checked against the
/// original bytes by the callers, so this only has to be fast and well mixed.
#[inline]
fn h64(b: &[u8]) -> u64 {
    let mut h: u64 = 0x9E37_79B9_7F4A_7C15 ^ (b.len() as u64).wrapping_mul(0xA076_1D64_78BD_642F);
    let mut i = 0;
    while i + 8 <= b.len() {
        let w = u64::from_le_bytes(b[i..i + 8].try_into().unwrap());
        h = (h ^ w).wrapping_mul(0xFF51_AFD7_ED55_8CCD);
        h ^= h >> 32;
        i += 8;
    }
    let mut t = 0u64;
    for (k, &c) in b[i..].iter().enumerate() {
        t |= (c as u64) << (8 * k);
    }
    h = (h ^ t).wrapping_mul(0xC4CE_B9FE_1A85_EC53);
    h ^= h >> 29;
    h = h.wrapping_mul(0x94D0_49BB_1331_11EB);
    h ^ (h >> 32)
}

#[inline]
fn shard_h(h: u64) -> usize {
    (h >> 55) as usize % NSH
}

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

/// One field, given whether it contains a double quote: Err = malformed; Ok(None) = null.
#[inline(always)]
fn field_q(f: B, quoted: bool) -> Result<Option<B>, ()> {
    if !quoted {
        return Ok(if f.is_empty() { None } else { Some(f) });
    }
    let n = f.len();
    if n < 2 || f[0] != b'"' || f[n - 1] != b'"' {
        return Err(());
    }
    let inner = &f[1..n - 1];
    if inner.contains(&b'"') {
        return Err(());
    }
    Ok(if inner.is_empty() { None } else { Some(inner) })
}

/// Split a line into exactly N fields; None if malformed. One pass over the bytes.
#[inline]
fn fields<const N: usize>(line: B) -> Option<[Option<B>; N]> {
    if line.is_empty() {
        return None;
    }
    let mut out = [None; N];
    let mut idx = 0;
    let mut start = 0;
    let mut quoted = false;
    for (i, &c) in line.iter().enumerate() {
        if c == b',' {
            if idx >= N - 1 {
                return None;
            }
            out[idx] = field_q(&line[start..i], quoted).ok()?;
            idx += 1;
            start = i + 1;
            quoted = false;
        } else if c == b'"' {
            quoted = true;
        }
    }
    if idx != N - 1 {
        return None;
    }
    out[N - 1] = field_q(&line[start..], quoted).ok()?;
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

/// "YYYY-MM-DD" -> days since epoch, with full calendar validation (None if impossible).
fn date_days(b: &[u8]) -> Option<i64> {
    if b[4] != b'-' || b[7] != b'-' {
        return None;
    }
    let y = d2(b, 0)? * 100 + d2(b, 2)?;
    let (mo, d) = (d2(b, 5)?, d2(b, 8)?);
    if !(1..=12).contains(&mo) {
        return None;
    }
    let leap = y % 4 == 0 && (y % 100 != 0 || y % 400 == 0);
    let md = [31, if leap { 29 } else { 28 }, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][(mo - 1) as usize];
    if d < 1 || d > md {
        return None;
    }
    Some(days_from_civil(y, mo, d))
}

thread_local! {
    // direct-mapped cache: exact 10-byte date key -> days (i64::MIN = invalid date)
    static DATES: std::cell::RefCell<[(u64, u16, i64); 64]> = const { std::cell::RefCell::new([(u64::MAX, 0, 0); 64]) };
}

#[inline]
fn cached_days(b: &[u8]) -> Option<i64> {
    let k1 = u64::from_le_bytes(b[0..8].try_into().unwrap());
    let k2 = u16::from_le_bytes(b[8..10].try_into().unwrap());
    let slot = ((k1 ^ (k1 >> 29) ^ (k2 as u64) * 0x9E37) as usize) & 63;
    DATES.with(|c| {
        let mut c = c.borrow_mut();
        let e = c[slot];
        if e.0 == k1 && e.1 == k2 {
            return if e.2 == i64::MIN { None } else { Some(e.2) };
        }
        let r = date_days(b);
        c[slot] = (k1, k2, r.unwrap_or(i64::MIN));
        r
    })
}

/// "YYYY-MM-DDTHH:MM:SS" prefix -> epoch ms, validating the calendar.
#[inline]
fn civil(b: &[u8]) -> Option<i64> {
    if b[10] != b'T' || b[13] != b':' || b[16] != b':' {
        return None;
    }
    let (h, mi, s) = (d2(b, 11)?, d2(b, 14)?, d2(b, 17)?);
    if h > 23 || mi > 59 || s > 59 {
        return None;
    }
    let days = cached_days(b)?;
    Some(((days * 24 + h) * 60 + mi) * 60_000 + s * 1000)
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
    let mut it = memchr::memchr_iter(b'\n', chunk);
    std::iter::from_fn(move || {
        if start >= n {
            return None;
        }
        let end = it.next().unwrap_or(n);
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
    eh: u64, // h64(event_id)
    eid: B,
    uid: B,
    ing: i64,
    ts: i64,
    price: i32,
    cat: u32, // category of a purchase (UNKNOWN_CAT if not in products.csv)
    ok: bool,
    purchase: bool,
}

#[derive(Clone, Copy)]
struct PEv {
    pk: u64, // h64(person name); ties broken on `name`, so collisions cannot merge people
    name: B,
    ts: i64,
    price: i32, // 0 unless purchase
    cat: u32,
    purchase: bool,
}

#[derive(Clone, Copy)]
struct PCl {
    pk: u64,
    name: B,
    ts: i64,
    cid: B,
    camp: u32,
}

/// per_chunk[c][s] -> shards[s] as a list of the chunks' vectors (no copying).
fn transpose<T: Send>(per_chunk: Vec<Vec<Vec<T>>>) -> Vec<Vec<Vec<T>>> {
    let mut cols: Vec<Vec<Vec<T>>> = (0..NSH).map(|_| Vec::with_capacity(per_chunk.len())).collect();
    for chunk in per_chunk {
        for (s, v) in chunk.into_iter().enumerate() {
            if !v.is_empty() {
                cols[s].push(v);
            }
        }
    }
    cols
}

fn scatter<T: Send>(per_chunk: Vec<Vec<Vec<T>>>) -> Vec<Vec<T>> {
    // per_chunk[c][s] -> shards[s]
    let mut cols: Vec<Vec<Vec<T>>> = (0..NSH).map(|_| Vec::with_capacity(per_chunk.len())).collect();
    for chunk in per_chunk {
        for (s, v) in chunk.into_iter().enumerate() {
            cols[s].push(v);
        }
    }
    cols.into_par_iter()
        .map(|vs| {
            let mut out = Vec::with_capacity(vs.iter().map(|v| v.len()).sum());
            for v in vs {
                out.extend(v);
            }
            out
        })
        .collect()
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
    // uid hash -> (uid, person name, person hash); every hit is verified against the bytes
    let mut link_h: FxHashMap<u64, (B, B, u64)> = FxHashMap::default();
    link_h.reserve(link_name.len());
    let mut link_h_clash = false;
    for (&u, &r) in &link_name {
        if let Some(prev) = link_h.insert(h64(u), (u, r, h64(r))) {
            if prev.0 != u {
                link_h_clash = true;
            }
        }
    }
    let person = |u: B, uh: u64| -> (B, u64) {
        if !link_h_clash {
            match link_h.get(&uh) {
                Some(&(lu, r, rh)) if lu == u => return (r, rh),
                Some(_) => {}
                None => return (u, uh),
            }
        }
        match link_name.get(u) {
            Some(&r) => (r, h64(r)),
            None => (u, uh),
        }
    };
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
                let mut cat = 0;
                if ok && kind == 2 {
                    match parse_price(price) {
                        Some(v) => {
                            p = v as i32;
                            cat = products.get(pid.unwrap()).copied().unwrap_or(UNKNOWN_CAT);
                        }
                        None => ok = false,
                    }
                }
                if ok && ing - ts > DAY {
                    ok = false;
                }
                let eh = h64(eid);
                sh[shard_h(eh)].push(Ev {
                    eh,
                    eid,
                    uid: uid.unwrap_or(b""),
                    ing,
                    ts,
                    price: p,
                    cat,
                    ok,
                    purchase: kind == 2,
                });
            }
            sh
        })
        .collect();
    let ev_shards = transpose(per_chunk);
    lap("events parsed");

    // dedup within each event shard, keep surviving events, re-scatter by person
    let per_shard: Vec<Vec<Vec<PEv>>> = ev_shards
        .into_par_iter()
        .map(|parts: Vec<Vec<Ev>>| {
            let evs: Vec<&Ev> = parts.iter().flatten().collect(); // 8-byte refs, not 72-byte copies
            let mut best: FxHashMap<u64, u32> = FxHashMap::default();
            best.reserve(evs.len());
            let mut slow: FxHashMap<B, u32> = FxHashMap::default(); // eids whose hash collides
            for (i, e) in evs.iter().enumerate() {
                let i = i as u32;
                if !slow.is_empty() {
                    if let Some(j) = slow.get_mut(e.eid) {
                        if e.ing < evs[*j as usize].ing {
                            *j = i;
                        }
                        continue;
                    }
                }
                match best.entry(e.eh) {
                    std::collections::hash_map::Entry::Vacant(v) => {
                        v.insert(i);
                    }
                    std::collections::hash_map::Entry::Occupied(mut o) => {
                        let j = *o.get() as usize;
                        if evs[j].eid == e.eid {
                            if e.ing < evs[j].ing {
                                o.insert(i);
                            }
                        } else {
                            slow.insert(e.eid, i); // different event, same hash
                        }
                    }
                }
            }
            let mut sh: Vec<Vec<PEv>> = (0..NSH).map(|_| Vec::new()).collect();
            for &i in best.values().chain(slow.values()) {
                let e = evs[i as usize];
                if !e.ok {
                    continue;
                }
                let (name, pk) = person(e.uid, h64(e.uid));
                sh[shard_h(pk)].push(PEv { pk, name, ts: e.ts, price: e.price, cat: e.cat, purchase: e.purchase });
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
                let (name, pk) = person(uid, h64(uid));
                sh[shard_h(pk)].push(PCl { pk, name, ts, cid, camp });
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
            // (pk, name) groups one person even if two names share a hash
            evs.sort_unstable_by_key(|e| (e.pk, e.ts));
            // a person hash shared by two different names would interleave them: detect and re-sort exactly
            if evs.windows(2).any(|w| w[0].pk == w[1].pk && w[0].name != w[1].name) {
                evs.sort_unstable_by(|a, b| a.pk.cmp(&b.pk).then_with(|| a.name.cmp(b.name)).then(a.ts.cmp(&b.ts)));
            }
            // by ts ascending, then click_id DESCENDING: the last eligible click is the winner
            cls.sort_unstable_by(|a, b| {
                a.pk.cmp(&b.pk).then(a.ts.cmp(&b.ts)).then_with(|| b.cid.cmp(a.cid))
            });
            if cls.windows(2).any(|w| w[0].pk == w[1].pk && w[0].name != w[1].name) {
                cls.sort_unstable_by(|a, b| {
                    a.pk.cmp(&b.pk).then_with(|| a.name.cmp(b.name)).then(a.ts.cmp(&b.ts)).then_with(|| b.cid.cmp(a.cid))
                });
            }
            let mut urows: Vec<URow> = vec![];
            let mut camp: FxHashMap<(u32, i32), [i64; 4]> = FxHashMap::default();
            let mut ci = 0usize;
            let mut i = 0usize;
            let mut cats: Vec<(u32, i64)> = vec![];
            let mut active: FxHashMap<u32, u32> = FxHashMap::default();
            while i < evs.len() {
                let (pk, name) = (evs[i].pk, evs[i].name);
                let mut j = i;
                while j < evs.len() && evs[j].pk == pk && evs[j].name == name {
                    j += 1;
                }
                while ci < cls.len() && (cls[ci].pk, cls[ci].name) < (pk, name) {
                    ci += 1;
                }
                let mut cj = ci;
                while cj < cls.len() && cls[cj].pk == pk && cls[cj].name == name {
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
                            rev += x.price as i64;
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
                                Some(c) => c.1 += x.price as i64,
                                None => cats.push((x.cat, x.price as i64)),
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
