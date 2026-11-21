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
    h64s(b, 0x9E37_79B9_7F4A_7C15)
}

/// Both hashes in one pass over the bytes: (h64(b), h2(b)).
#[inline]
fn h12(b: &[u8]) -> (u64, u64) {
    let len = (b.len() as u64).wrapping_mul(0xA076_1D64_78BD_642F);
    let mut x: u64 = 0x9E37_79B9_7F4A_7C15 ^ len;
    let mut y: u64 = 0xD6E8_FEB8_6659_FD93 ^ len;
    let mut i = 0;
    while i + 8 <= b.len() {
        let w = u64::from_le_bytes(b[i..i + 8].try_into().unwrap());
        x = (x ^ w).wrapping_mul(0xFF51_AFD7_ED55_8CCD);
        x ^= x >> 32;
        y = (y ^ w).wrapping_mul(0xFF51_AFD7_ED55_8CCD);
        y ^= y >> 32;
        i += 8;
    }
    let mut t = 0u64;
    for (k, &c) in b[i..].iter().enumerate() {
        t |= (c as u64) << (8 * k);
    }
    let fin = |mut h: u64| {
        h = (h ^ t).wrapping_mul(0xC4CE_B9FE_1A85_EC53);
        h ^= h >> 29;
        h = h.wrapping_mul(0x94D0_49BB_1331_11EB);
        h ^ (h >> 32)
    };
    (fin(x), fin(y))
}

/// Independent second hash: (h64, h2) together identify a string (2^-128 collision odds).
#[inline]
fn h2(b: &[u8]) -> u64 {
    h64s(b, 0xD6E8_FEB8_6659_FD93)
}

#[inline]
fn h64s(b: &[u8], seed: u64) -> u64 {
    let mut h: u64 = seed ^ (b.len() as u64).wrapping_mul(0xA076_1D64_78BD_642F);
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

/// 64-byte block masks: (commas, newlines, quotes), bit i = byte i.
#[inline(always)]
fn block_masks(p: &[u8]) -> (u64, u64, u64) {
    #[cfg(target_feature = "avx2")]
    unsafe {
        use std::arch::x86_64::*;
        let a = _mm256_loadu_si256(p.as_ptr() as *const __m256i);
        let b = _mm256_loadu_si256(p.as_ptr().add(32) as *const __m256i);
        let m = |v: __m256i, c: u8| -> u32 { _mm256_movemask_epi8(_mm256_cmpeq_epi8(v, _mm256_set1_epi8(c as i8))) as u32 };
        let j = |lo: u32, hi: u32| -> u64 { lo as u64 | ((hi as u64) << 32) };
        return (j(m(a, b','), m(b, b',')), j(m(a, b'\n'), m(b, b'\n')), j(m(a, b'"'), m(b, b'"')));
    }
    #[allow(unreachable_code)]
    {
        let (mut c, mut n, mut q) = (0u64, 0u64, 0u64);
        for (i, &x) in p[..64].iter().enumerate() {
            c |= ((x == b',') as u64) << i;
            n |= ((x == b'\n') as u64) << i;
            q |= ((x == b'"') as u64) << i;
        }
        (c, n, q)
    }
}

/// Finish one line given its comma positions and quote count (rules.md CSV dialect).
#[inline(always)]
fn finish_line<'a, const N: usize>(chunk: &'a [u8], start: usize, end: usize, commas: &[usize], nq: u32) -> Option<[Option<&'a [u8]>; N]> {
    if end == start || commas.len() != N - 1 {
        return None; // empty line or wrong field count
    }
    let mut out = [None; N];
    let mut fs = start;
    let mut quoted_pairs = 0u32;
    for k in 0..N {
        let fe = if k < N - 1 { commas[k] } else { end };
        let len = fe - fs;
        // quoted = field is at least 2 bytes and starts and ends with '"' (computed without branches)
        // both reads stay inside the buffer even for an empty last field with no trailing newline
        let first = *chunk.get(fs).unwrap_or(&0);
        let last = *chunk.get(fe.wrapping_sub(1).max(fs)).unwrap_or(&0);
        let isq = ((nq > 0) & (len >= 2) & (first == b'"') & (last == b'"')) as usize;
        quoted_pairs += isq as u32;
        let v = &chunk[fs + isq..fe - isq];
        out[k] = if v.is_empty() { None } else { Some(v) };
        fs = fe + 1;
    }
    // every quote must be one of the two around a whole field
    if nq != 2 * quoted_pairs {
        return None;
    }
    Some(out)
}

/// Scan a chunk of lines (each ending in '\n', the last one may not) and call `f` with each
/// line's N fields, or None for a malformed line. Equivalent to lines() + fields::<N>().
#[inline]
fn scan_lines<'a, const N: usize>(chunk: &'a [u8], mut f: impl FnMut(Option<[Option<&'a [u8]>; N]>)) {
    let n = chunk.len();
    let mut start = 0usize;
    let mut commas: [usize; 16] = [0; 16];
    let mut nc = 0usize; // commas seen in the current line (capped)
    let mut nq = 0u32;
    let mut base = 0usize;
    let mut pad = [0u8; 64];
    while base < n {
        let (c, nl, q) = if base + 64 <= n {
            block_masks(&chunk[base..base + 64])
        } else {
            pad = [0u8; 64];
            pad[..n - base].copy_from_slice(&chunk[base..]);
            block_masks(&pad)
        };
        let mut m = c | nl;
        let mut qleft = q; // quotes in this block not yet assigned to a line
        while m != 0 {
            let b = m.trailing_zeros();
            m &= m - 1;
            let bit = 1u64 << b;
            let pos = base + b as usize;
            if nl & bit != 0 {
                let before = qleft & (bit - 1);
                nq += before.count_ones();
                qleft &= !(bit | (bit - 1));
                f(if nc <= 15 { finish_line::<N>(chunk, start, pos, &commas[..nc], nq) } else { None });
                start = pos + 1;
                nc = 0;
                nq = 0;
            } else {
                if nc < 16 {
                    commas[nc] = pos;
                }
                nc += 1;
            }
        }
        nq += qleft.count_ones();
        base += 64;
    }
    let _ = pad;
    if start < n {
        f(if nc <= 15 { finish_line::<N>(chunk, start, n, &commas[..nc], nq) } else { None });
    }
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
    // SWAR: find ',' and '"' 8 bytes at a time
    const LO: u64 = 0x0101_0101_0101_0101;
    const HI: u64 = 0x8080_8080_8080_8080;
    let n = line.len();
    let mut base = 0;
    while base < n {
        let w = if base + 8 <= n {
            u64::from_le_bytes(line[base..base + 8].try_into().unwrap())
        } else {
            let mut t = [0u8; 8];
            t[..n - base].copy_from_slice(&line[base..]);
            u64::from_le_bytes(t)
        };
        let xc = w ^ (LO * b',' as u64);
        let xq = w ^ (LO * b'"' as u64);
        // exact zero-byte masks (no false positives from borrows)
        let zc = !(((xc & !HI) + !HI) | xc | !HI);
        let zq = !(((xq & !HI) + !HI) | xq | !HI);
        let mut m = zc | zq;
        if base + 8 > n {
            m &= (1u64 << ((n - base) * 8)) - 1;
        }
        while m != 0 {
            let i = base + (m.trailing_zeros() / 8) as usize;
            m &= m - 1;
            if line[i] == b',' {
                if idx >= N - 1 {
                    return None;
                }
                out[idx] = field_q(&line[start..i], quoted).ok()?;
                idx += 1;
                start = i + 1;
                quoted = false;
            } else {
                quoted = true;
            }
        }
        base += 8;
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
    let slot = ((k1 ^ ((k2 as u64) << 48)).wrapping_mul(0x9E37_79B9_7F4A_7C15) >> 58) as usize;
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

unsafe extern "C" {
    fn mmap(addr: *mut u8, len: usize, prot: i32, flags: i32, fd: i32, off: i64) -> *mut u8;
}

/// Map a file read-only (no copy, no allocation); falls back to reading it.
fn map_file(p: &Path) -> B {
    use std::os::fd::AsRawFd;
    let f = std::fs::File::open(p).expect("open");
    let len = f.metadata().expect("stat").len() as usize;
    if len == 0 {
        return &[];
    }
    // PROT_READ=1, MAP_PRIVATE=2, MAP_POPULATE=0x8000
    let ptr = unsafe { mmap(std::ptr::null_mut(), len, 1, 2 | 0x8000, f.as_raw_fd(), 0) };
    if ptr as isize == -1 || ptr.is_null() {
        return Box::leak(std::fs::read(p).expect("read").into_boxed_slice());
    }
    // the mapping outlives the File handle and is never unmapped (process exits)
    unsafe { std::slice::from_raw_parts(ptr, len) }
}

fn load(paths: &[PathBuf]) -> Vec<B> {
    paths.par_iter().map(|p| map_file(p)).collect()
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
struct DKey {
    eh: u64, // (h64, h2) of event_id: 128-bit identity for dedup
    eh2: u64,
    ing: i64,
    loc: u64, // chunk << 32 | index of the valid payload in that chunk (u32::MAX if the copy is invalid)
}

#[derive(Clone, Copy)]
struct UEv {
    uh: u64,
    uh2: u64,
    uid: B,
    ts: i64,
    price: i32,
    cat: u32,
    purchase: bool,
}

#[derive(Clone, Copy)]
struct UCl {
    uh: u64,
    uh2: u64,
    uid: B,
    ts: i64,
    cid: B,
    camp: u32,
}

#[derive(Clone, Copy)]
struct PEv {
    pk: u64, // (pk, pk2) = (h64, h2) of the person's name
    pk2: u64,
    name: B,
    ts: i64,
    price: i32, // 0 unless purchase
    cat: u32,
    purchase: bool,
}

#[derive(Clone, Copy)]
struct PCl {
    pk: u64,
    pk2: u64,
    name: B,
    ts: i64,
    cid: B,
    camp: u32,
}

/// Sort records by (pk, ts) through packed 128-bit keys (pk | ts-base | index): one integer
/// compare per step and 16-byte moves, then a single gather into order.
fn sort_by_pk_ts<T: Copy>(v: &mut [T], base: i64, pk: impl Fn(&T) -> u64, ts: impl Fn(&T) -> i64) {
    let mut k: Vec<u128> = v
        .iter()
        .enumerate()
        .map(|(i, x)| ((pk(x) as u128) << 64) | (((ts(x) - base) as u32 as u128) << 32) | i as u128)
        .collect();
    k.sort_unstable();
    let tmp: Vec<T> = k.iter().map(|&x| v[x as u32 as usize]).collect();
    v.copy_from_slice(&tmp);
}

struct SendPtr<T>(*mut T);
unsafe impl<T> Send for SendPtr<T> {}
unsafe impl<T> Sync for SendPtr<T> {}

/// Radix partition: every record is written exactly once into one contiguous array,
/// grouped by shard. Returns the array and NSH+1 shard offsets.
fn partition<T: Copy + Send + Sync>(parts: Vec<Vec<T>>, key: impl Fn(&T) -> usize + Sync) -> (Vec<T>, Vec<usize>) {
    let counts: Vec<Vec<usize>> = parts
        .par_iter()
        .map(|v| {
            let mut c = vec![0usize; NSH];
            for x in v {
                c[key(x)] += 1;
            }
            c
        })
        .collect();
    let mut starts: Vec<Vec<usize>> = vec![vec![0; NSH]; parts.len()];
    let mut off = vec![0usize; NSH + 1];
    let mut run = 0;
    for sh in 0..NSH {
        off[sh] = run;
        for c in 0..parts.len() {
            starts[c][sh] = run;
            run += counts[c][sh];
        }
    }
    off[NSH] = run;
    let mut out: Vec<T> = Vec::with_capacity(run);
    let ptr = SendPtr(out.as_mut_ptr());
    let ptr = &ptr;
    parts.par_iter().zip(starts.into_par_iter()).for_each(|(v, mut pos)| {
        for x in v {
            let k = key(x);
            // SAFETY: each (chunk, shard) owns the disjoint range [starts, starts+count)
            unsafe { ptr.0.add(pos[k]).write(*x) };
            pos[k] += 1;
        }
    });
    // SAFETY: all `run` slots were written above
    unsafe { out.set_len(run) };
    (out, off)
}

/// Split a partitioned array into disjoint mutable shard slices.
fn shard_slices<'a, T>(mut all: &'a mut [T], off: &[usize]) -> Vec<&'a mut [T]> {
    let mut v = Vec::with_capacity(NSH);
    for sh in 0..NSH {
        let (a, b) = all.split_at_mut(off[sh + 1] - off[sh]);
        v.push(a);
        all = b;
    }
    v
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
    for t in [&b""[..], b"a", b"u1", b"e42huhoug", b"0123456789abcdefXYZ"] {
        assert_eq!(h12(t), (h64(t), h2(t)), "hash self-check");
    }

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
    // intern link IDs by 64-bit hash; if two different IDs ever share a hash, switch to exact string interning
    struct Intern {
        ih: FxHashMap<u64, u32>,
        names: Vec<B>,
        hashes: Vec<u64>,
        parent: Vec<u32>,
        clash: bool,
        slow: FxHashMap<B, u32>,
    }
    impl Intern {
        fn new_id(&mut self, s: B, h: u64) -> u32 {
            let i = self.names.len() as u32;
            self.names.push(s);
            self.hashes.push(h);
            self.parent.push(i);
            if self.clash {
                self.slow.insert(s, i);
            }
            i
        }
        fn id(&mut self, s: B) -> u32 {
            let h = h64(s);
            if self.clash {
                if let Some(&i) = self.slow.get(s) {
                    return i;
                }
            }
            match self.ih.get(&h) {
                None => {
                    let i = self.new_id(s, h);
                    self.ih.insert(h, i);
                    i
                }
                Some(&i) if self.names[i as usize] == s => i,
                Some(_) => {
                    if !self.clash {
                        self.clash = true;
                        self.slow = self.names.iter().enumerate().map(|(i, &n)| (n, i as u32)).collect();
                    }
                    match self.slow.get(s) {
                        Some(&j) => j,
                        None => self.new_id(s, h),
                    }
                }
            }
        }
        fn get(&self, s: B, h: u64) -> Option<u32> {
            if self.clash {
                return self.slow.get(s).copied();
            }
            self.ih.get(&h).copied().filter(|&i| self.names[i as usize] == s)
        }
        fn find(&mut self, mut x: u32) -> u32 {
            let p = &mut self.parent;
            let mut r = x;
            while p[r as usize] != r {
                r = p[r as usize];
            }
            while p[x as usize] != r {
                let n = p[x as usize];
                p[x as usize] = r;
                x = n;
            }
            r
        }
    }
    let mut it = Intern {
        ih: FxHashMap::default(),
        names: vec![],
        hashes: vec![],
        parent: vec![],
        clash: false,
        slow: FxHashMap::default(),
    };
    it.ih.reserve(pairs.len());
    for &(a, b) in &pairs {
        let (ia, ib) = (it.id(a), it.id(b));
        let (ra, rb) = (it.find(ia), it.find(ib));
        if ra != rb {
            let (lo, hi) = if it.names[ra as usize] <= it.names[rb as usize] { (ra, rb) } else { (rb, ra) };
            it.parent[hi as usize] = lo;
        }
    }
    let rootv: Vec<u32> = (0..it.names.len() as u32).map(|i| it.find(i)).collect();
    let it = it;
    // linked uid h64 -> (uid h2, root h64, root h2, root index): one cache miss per lookup
    let mut lk: FxHashMap<u64, (u64, u64, u64, u32)> = FxHashMap::default();
    lk.reserve(it.names.len());
    let mut lk_clash = it.clash;
    for (i, &n) in it.names.iter().enumerate() {
        let r = rootv[i] as usize;
        let v = (h2(n), it.hashes[r], h2(it.names[r]), r as u32);
        if lk.insert(it.hashes[i], v).is_some() {
            lk_clash = true; // two linked IDs share a 64-bit hash: use the exact path
        }
    }
    // the same table split by uid-hash shard, so each shard's lookups stay in cache
    let lks: Vec<FxHashMap<u64, (u64, u64, u64, u32)>> = {
        let mut parts: Vec<Vec<(u64, (u64, u64, u64, u32))>> = (0..NSH).map(|_| Vec::new()).collect();
        for (&k, &v) in &lk {
            parts[shard_h(k)].push((k, v));
        }
        parts.into_par_iter().map(|v| v.into_iter().collect()).collect()
    };
    drop(lk);
    // uid (with its two hashes) -> (person h64, person h2, person name)
    let person_in = |lkm: &FxHashMap<u64, (u64, u64, u64, u32)>, u: B, uh: u64, u2: u64| -> (u64, u64, B) {
        if !lk_clash {
            return match lkm.get(&uh) {
                Some(&(lu2, rh, r2, r)) if lu2 == u2 => (rh, r2, it.names[r as usize]),
                _ => (uh, u2, u),
            };
        }
        match it.get(u, uh) {
            Some(i) => {
                let r = rootv[i as usize] as usize;
                (it.hashes[r], h2(it.names[r]), it.names[r])
            }
            None => (uh, u2, u),
        }
    };
    lap("links");

    // events: parse + validate each copy, scatter by event_id
    let ev_chunks = chunks(&ev_bufs);
    if let Ok(level) = std::env::var("PARSEBENCH") {
        // single-threaded cost ladder over all event lines; prints ns/line per level
        let level: u32 = level.parse().unwrap();
        let t = Instant::now();
        let (mut n, mut acc) = (0u64, 0u64);
        let mut pay: Vec<(u64, u64, i64, i64)> = Vec::with_capacity(1 << 20);
        if level >= 5 {
            for &c in &ev_chunks {
                scan_lines::<7>(c, |r| {
                    n += 1;
                    if let Some([eid, uid, ts, ing, _, _, _]) = r {
                        acc += eid.map_or(0, |x| x.len()) as u64;
                        if level >= 6 {
                            acc = acc.wrapping_add((parse_ts(ts) ^ parse_ts(ing)) as u64);
                        }
                        if level >= 7 {
                            acc = acc.wrapping_add(h12(eid.unwrap_or(b"")).0 ^ h12(uid.unwrap_or(b"")).1);
                        }
                    }
                });
            }
            let el = t.elapsed().as_secs_f64();
            eprintln!("PARSEBENCH level {level}: {n} lines, {:.1} ns/line (acc {acc})", el * 1e9 / n as f64);
            std::process::exit(0);
        }
        for &c in &ev_chunks {
            for l in lines(c) {
                n += 1;
                if level == 0 {
                    acc += l.len() as u64;
                    continue;
                }
                let Some([eid, uid, ts, ing, et, _pid, _price]) = fields::<7>(l) else { continue };
                if level == 1 {
                    acc += eid.map_or(0, |x| x.len()) as u64 + et.map_or(0, |x| x[0]) as u64;
                    continue;
                }
                let (tsv, ingv) = (parse_ts(ts), parse_ts(ing));
                if level == 2 {
                    acc = acc.wrapping_add(tsv as u64 ^ ingv as u64);
                    continue;
                }
                let (a, b) = h12(eid.unwrap_or(b""));
                let (c2, d) = h12(uid.unwrap_or(b""));
                if level == 3 {
                    acc = acc.wrapping_add(a ^ b ^ c2 ^ d ^ tsv as u64);
                    continue;
                }
                pay.push((a, c2, tsv, ingv));
                if pay.len() == pay.capacity() {
                    acc += pay.len() as u64;
                    pay.clear();
                }
                let _ = (b, d);
            }
        }
        let el = t.elapsed().as_secs_f64();
        eprintln!("PARSEBENCH level {level}: {n} lines, {:.1} ns/line, {:.2}s (acc {acc})", el * 1e9 / n as f64, el);
        std::process::exit(0);
    }
    let per_chunk: Vec<(Vec<UEv>, Vec<DKey>)> = ev_chunks
        .par_iter()
        .enumerate()
        .map(|(ci, &c)| {
            let cap = c.len() / 64 + 16;
            let mut pay: Vec<UEv> = Vec::with_capacity(cap);
            let mut keys: Vec<DKey> = Vec::with_capacity(cap);
            scan_lines::<7>(c, |r| {
                let Some([eid, uid, ts, ing, et, pid, price]) = r else { return };
                let Some(eid) = eid else { return };
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
                let mut idx = u32::MAX as u64;
                if ok {
                    let u = uid.unwrap();
                    idx = pay.len() as u64;
                    let (uh, uh2) = h12(u);
                    pay.push(UEv { uh, uh2, uid: u, ts, price: p, cat, purchase: kind == 2 });
                }
                let (eh, eh2) = h12(eid);
                keys.push(DKey { eh, eh2, ing, loc: ((ci as u64) << 32) | idx });
            });
            (pay, keys)
        })
        .collect();
    let (pays, keys): (Vec<Vec<UEv>>, Vec<Vec<DKey>>) = per_chunk.into_iter().unzip();
    let (key_all, key_off) = partition(keys, |k: &DKey| shard_h(k.eh));
    lap("events parsed");

    // dedup within each event shard, keep surviving events, re-scatter by person
    // winner bitmaps, one per chunk, over that chunk's valid payloads
    let bits: Vec<Vec<std::sync::atomic::AtomicU64>> =
        pays.iter().map(|v| (0..v.len() / 64 + 1).map(|_| std::sync::atomic::AtomicU64::new(0)).collect()).collect();
    (0..NSH).into_par_iter().for_each(|shi| {
        let ks = &key_all[key_off[shi]..key_off[shi + 1]];
        // earliest ingest per event (identical ingest => identical copies, either is fine)
        let mut best: FxHashMap<(u64, u64), u32> = FxHashMap::default();
        best.reserve(ks.len());
        for (i, k) in ks.iter().enumerate() {
            best.entry((k.eh, k.eh2))
                .and_modify(|j| {
                    if k.ing < ks[*j as usize].ing {
                        *j = i as u32
                    }
                })
                .or_insert(i as u32);
        }
        for &i in best.values() {
            let loc = ks[i as usize].loc;
            let idx = (loc & 0xFFFF_FFFF) as usize;
            if idx != u32::MAX as usize {
                bits[(loc >> 32) as usize][idx / 64].fetch_or(1 << (idx % 64), std::sync::atomic::Ordering::Relaxed);
            }
        }
    });
    drop(key_all);
    let per_shard: Vec<Vec<UEv>> = pays
        .par_iter()
        .zip(bits.par_iter())
        .map(|(v, b)| {
            v.iter()
                .enumerate()
                .filter(|(i, _)| b[i / 64].load(std::sync::atomic::Ordering::Relaxed) >> (i % 64) & 1 == 1)
                .map(|(_, e)| *e)
                .collect()
        })
        .collect();
    lap("events deduped");
    drop(pays);
    let (uev_all, uev_off) = partition(per_shard, |e: &UEv| shard_h(e.uh));
    let resolved: Vec<Vec<PEv>> = (0..NSH)
        .into_par_iter()
        .map(|shi| {
            let lkm = &lks[shi];
            uev_all[uev_off[shi]..uev_off[shi + 1]]
                .iter()
                .map(|e| {
                    let (pk, pk2, name) = person_in(lkm, e.uid, e.uh, e.uh2);
                    PEv { pk, pk2, name, ts: e.ts, price: e.price, cat: e.cat, purchase: e.purchase }
                })
                .collect()
        })
        .collect();
    drop(uev_all);
    let (mut pev_all, pev_off) = partition(resolved, |e: &PEv| shard_h(e.pk));
    lap("events regrouped");

    // clicks: copies are identical, so duplicates cannot change credit or assists
    let cl_chunks = chunks(&cl_bufs);
    let per_chunk: Vec<Vec<UCl>> = cl_chunks
        .par_iter()
        .map(|&c| {
            let mut sh: Vec<UCl> = Vec::with_capacity(c.len() / 40 + 16);
            scan_lines::<4>(c, |r| {
                let Some([Some(cid), Some(uid), Some(camp), ts]) = r else { return };
                let Some(&camp) = campaigns.get(camp) else { return };
                let ts = parse_ts(ts);
                if ts == BAD || ts < ws - WEEK || ts >= we {
                    return;
                }
                let (uh, uh2) = h12(uid);
                sh.push(UCl { uh, uh2, uid, ts, cid, camp });
            });
            sh
        })
        .collect();
    let (ucl_all, ucl_off) = partition(per_chunk, |c: &UCl| shard_h(c.uh));
    let resolved: Vec<Vec<PCl>> = (0..NSH)
        .into_par_iter()
        .map(|shi| {
            let lkm = &lks[shi];
            ucl_all[ucl_off[shi]..ucl_off[shi + 1]]
                .iter()
                .map(|c| {
                    let (pk, pk2, name) = person_in(lkm, c.uid, c.uh, c.uh2);
                    PCl { pk, pk2, name, ts: c.ts, cid: c.cid, camp: c.camp }
                })
                .collect()
        })
        .collect();
    drop(ucl_all);
    let (mut pcl_all, pcl_off) = partition(resolved, |c: &PCl| shard_h(c.pk));
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
    let pev_slices = shard_slices(&mut pev_all, &pev_off);
    let pcl_slices = shard_slices(&mut pcl_all, &pcl_off);
    // dense campaign x day accumulators (sessions start inside the window, so days are bounded)
    let day0 = ws.div_euclid(DAY) as i32;
    let ndays = ((we - 1).div_euclid(DAY) as i32 - day0 + 1) as usize;
    let ncamp = camp_ids.len() + 1; // last slot = organic
    let cidx = |c: u32, day: i32| -> usize {
        let c = if c == ORGANIC { ncamp - 1 } else { c as usize };
        c * ndays + (day - day0) as usize
    };
    let results: Vec<(Vec<URow>, Vec<[i64; 4]>)> = pev_slices
        .into_par_iter()
        .zip(pcl_slices.into_par_iter())
        .fold(|| (Vec::<URow>::new(), vec![[0i64; 4]; ncamp * ndays]), |(mut urows, mut camp), (evs, cls)| {
            // (pk, name) groups one person even if two names share a hash
            // valid events lie in [ws, we): ts - ws fits in 32 bits
            sort_by_pk_ts(evs, ws, |e| e.pk, |e| e.ts);
            // a person hash shared by two different names would interleave them: detect and re-sort exactly
            if evs.windows(2).any(|w| w[0].pk == w[1].pk && w[0].pk2 != w[1].pk2) {
                evs.sort_unstable_by_key(|e| (e.pk, e.pk2, e.ts));
            }
            // by ts ascending, then click_id DESCENDING: the last eligible click is the winner
            // valid clicks lie in [ws - 7d, we): ts - base fits in 32 bits
            sort_by_pk_ts(cls, ws - WEEK, |c| c.pk, |c| c.ts);
            // equal (pk, ts) runs are rare: order them by click_id descending (exact tie rule)
            let mut a = 0;
            while a < cls.len() {
                let mut b = a + 1;
                while b < cls.len() && cls[b].pk == cls[a].pk && cls[b].ts == cls[a].ts {
                    b += 1;
                }
                if b - a > 1 {
                    cls[a..b].sort_unstable_by(|x, y| y.cid.cmp(x.cid));
                }
                a = b;
            }
            if cls.windows(2).any(|w| w[0].pk == w[1].pk && w[0].pk2 != w[1].pk2) {
                cls.sort_unstable_by(|a, b| {
                    (a.pk, a.pk2, a.ts).cmp(&(b.pk, b.pk2, b.ts)).then_with(|| b.cid.cmp(a.cid))
                });
            }
            let mut ci = 0usize;
            let mut i = 0usize;
            let mut cats: Vec<(u32, i64)> = vec![];
            let mut active: Vec<(u32, u32)> = Vec::new(); // (campaign, clicks in window)
            while i < evs.len() {
                let (pk, pk2, name) = (evs[i].pk, evs[i].pk2, evs[i].name);
                let mut j = i;
                while j < evs.len() && evs[j].pk == pk && evs[j].pk2 == pk2 {
                    j += 1;
                }
                while ci < cls.len() && (cls[ci].pk, cls[ci].pk2) < (pk, pk2) {
                    ci += 1;
                }
                let mut cj = ci;
                while cj < cls.len() && cls[cj].pk == pk && cls[cj].pk2 == pk2 {
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
                        let c = pcl[hi].camp;
                        match active.iter_mut().find(|x| x.0 == c) {
                            Some(x) => x.1 += 1,
                            None => active.push((c, 1)),
                        }
                        hi += 1;
                    }
                    while lo < hi && pcl[lo].ts < start - WEEK {
                        let c = pcl[lo].camp;
                        let k = active.iter().position(|x| x.0 == c).unwrap();
                        active[k].1 -= 1;
                        if active[k].1 == 0 {
                            active.swap_remove(k);
                        }
                        lo += 1;
                    }
                    let credit = if hi > lo { pcl[hi - 1].camp } else { ORGANIC };
                    let a = &mut camp[cidx(credit, day)];
                    a[0] += 1;
                    a[1] += purch as i64;
                    a[2] += rev;
                    for &(c, _) in &active {
                        camp[cidx(c, day)][3] += 1;
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
    let mut dense = vec![[0i64; 4]; ncamp * ndays];
    let mut user_parts: Vec<Vec<URow>> = vec![];
    for (u, c) in results {
        user_parts.push(u);
        for (a, v) in dense.iter_mut().zip(c) {
            for t in 0..4 {
                a[t] += v[t];
            }
        }
    }
    // a (campaign, day) row exists when it was credited or assisted at least once
    let mut camp_all: FxHashMap<(u32, i32), [i64; 4]> = FxHashMap::default();
    for (i, v) in dense.iter().enumerate() {
        if v[0] > 0 || v[3] > 0 {
            let c = i / ndays;
            let c = if c == ncamp - 1 { ORGANIC } else { c as u32 };
            camp_all.insert((c, day0 + (i % ndays) as i32), *v);
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
