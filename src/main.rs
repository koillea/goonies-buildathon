//! Shopping Sessions: fast exact pipeline.
//!
//! Design: read every CSV into memory in parallel, parse chunks in parallel with
//! hand-written parsers that follow rules.md exactly, then shard records by hash so
//! each worker owns a disjoint set of keys (event_id for dedup, person for
//! sessionizing) and needs no locks. Verified against oracle/reference.py.

mod pq;
mod recycle;

#[global_allocator]
static GLOBAL: recycle::Recycler = recycle::Recycler;

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
const SH_BITS: u32 = 10; // shard count = 2^SH_BITS
const NSH: usize = 1 << SH_BITS;
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
    (h >> (64 - SH_BITS)) as usize
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

/// Exact match of event_type against view / cart / purchase with integer compares.
#[inline(always)]
fn event_kind(et: Option<&[u8]>) -> u8 {
    match et {
        Some(b) if b.len() == 4 => {
            let w = u32::from_le_bytes([b[0], b[1], b[2], b[3]]);
            if w == u32::from_le_bytes(*b"view") {
                0
            } else if w == u32::from_le_bytes(*b"cart") {
                1
            } else {
                3
            }
        }
        Some(b) if b.len() == 8 && u64::from_le_bytes(b.try_into().unwrap()) == u64::from_le_bytes(*b"purchase") => 2,
        _ => 3,
    }
}

/// 64-byte block masks: (commas, newlines, quotes), bit i = byte i.
#[inline(always)]
fn block_masks(p: &[u8]) -> (u64, u64, u64) {
    #[cfg(target_feature = "avx512bw")]
    unsafe {
        use std::arch::x86_64::*;
        let v = _mm512_loadu_si512(p.as_ptr() as *const _);
        return (
            _mm512_cmpeq_epi8_mask(v, _mm512_set1_epi8(b',' as i8)),
            _mm512_cmpeq_epi8_mask(v, _mm512_set1_epi8(b'\n' as i8)),
            _mm512_cmpeq_epi8_mask(v, _mm512_set1_epi8(b'"' as i8)),
        );
    }
    #[cfg(all(target_feature = "avx2", not(target_feature = "avx512bw")))]
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

/// (commas, quotes) masks for a 64-byte window.
#[inline(always)]
fn cq_masks(p: &[u8]) -> (u64, u64) {
    #[cfg(target_feature = "avx512bw")]
    unsafe {
        use std::arch::x86_64::*;
        let v = _mm512_loadu_si512(p.as_ptr() as *const _);
        return (_mm512_cmpeq_epi8_mask(v, _mm512_set1_epi8(b',' as i8)), _mm512_cmpeq_epi8_mask(v, _mm512_set1_epi8(b'"' as i8)));
    }
    #[allow(unreachable_code)]
    {
        let (c, _, q) = block_masks(p);
        (c, q)
    }
}

/// Per-line scanner: line ends from one streaming newline search, then each line's commas and
/// quotes from two 64-byte compares. Same results as scan_lines (checked by SELFTEST).
#[inline]
fn scan_lines2<'a, const N: usize>(chunk: &'a [u8], mut f: impl FnMut(Option<[Option<&'a [u8]>; N]>)) {
    let n = chunk.len();
    let mut start = 0usize;
    let mut it = memchr::memchr_iter(b'\n', chunk);
    let mut pad = [0u8; 128];
    let mut commas = [0usize; 16];
    loop {
        if start >= n {
            return;
        }
        let end = it.next().unwrap_or(n);
        let len = end - start;
        if len <= 128 {
            // two 64-byte windows; copy to a padded buffer when they would run past the chunk
            let w: &[u8] = if start + 128 <= n {
                &chunk[start..start + 128]
            } else {
                pad = [0u8; 128];
                pad[..n - start].copy_from_slice(&chunk[start..]);
                &pad
            };
            let (c0, q0) = cq_masks(&w[..64]);
            let (c1, q1) = cq_masks(&w[64..128]);
            let keep0 = if len >= 64 { u64::MAX } else { (1u64 << len) - 1 };
            let keep1 = if len >= 128 { u64::MAX } else if len > 64 { (1u64 << (len - 64)) - 1 } else { 0 };
            let (c0, c1) = (c0 & keep0, c1 & keep1);
            let nq = (q0 & keep0).count_ones() + (q1 & keep1).count_ones();
            let nc = (c0.count_ones() + c1.count_ones()) as usize;
            if nc != N - 1 {
                f(if len == 0 { None } else { None });
            } else {
                let mut m = c0;
                let mut k = 0;
                while m != 0 {
                    commas[k] = start + m.trailing_zeros() as usize;
                    m &= m - 1;
                    k += 1;
                }
                let mut m = c1;
                while m != 0 {
                    commas[k] = start + 64 + m.trailing_zeros() as usize;
                    m &= m - 1;
                    k += 1;
                }
                f(finish_line::<N>(chunk, start, end, &commas[..k], nq));
            }
        } else {
            // long line: count commas/quotes directly
            let line = &chunk[start..end];
            let mut k = 0;
            let mut nq = 0u32;
            for (i, &b) in line.iter().enumerate() {
                if b == b',' {
                    if k < 16 {
                        commas[k] = start + i;
                    }
                    k += 1;
                } else if b == b'"' {
                    nq += 1;
                }
            }
            f(if k == N - 1 { finish_line::<N>(chunk, start, end, &commas[..k], nq) } else { None });
        }
        start = end + 1;
    }
}

/// Dedicated event-chunk parser: per-line SIMD comma/quote masks, field extraction and
/// validation in one loop (same semantics as scan_lines::<7> + the generic event closure).
#[allow(clippy::too_many_arguments)]
fn parse_event_chunk(
    chunk: &'static [u8],
    ci: usize,
    ws: i64,
    we: i64,
    products: &FxHashMap<B, u32>,
) -> (Vec<PEv>, Vec<DKey>, Vec<u32>) {
    let cap = chunk.len() / 64 + 16;
    let mut pay: Vec<PEv> = Vec::with_capacity(cap);
    let mut keys: Vec<DKey> = Vec::with_capacity(cap);
    let mut kcount = vec![0u32; NSH];
    let n = chunk.len();
    let mut start = 0usize;
    let mut it = memchr::memchr_iter(b'\n', chunk);
    let mut pad = [0u8; 128];
    let mut cm = [0usize; 8];
    while start < n {
        let end = it.next().unwrap_or(n);
        let len = end - start;
        let line_start = start;
        start = end + 1;
        // comma positions (exactly 6) and quote count
        let nq;
        if len <= 128 {
            let w: &[u8] = if line_start + 128 <= n {
                &chunk[line_start..line_start + 128]
            } else {
                pad = [0u8; 128];
                pad[..n - line_start].copy_from_slice(&chunk[line_start..]);
                &pad
            };
            let (c0, q0) = cq_masks(&w[..64]);
            let (c1, q1) = cq_masks(&w[64..128]);
            let keep0 = if len >= 64 { u64::MAX } else { (1u64 << len) - 1 };
            let keep1 = if len >= 128 { u64::MAX } else if len > 64 { (1u64 << (len - 64)) - 1 } else { 0 };
            let (c0, c1) = (c0 & keep0, c1 & keep1);
            if c0.count_ones() + c1.count_ones() != 6 {
                continue; // wrong field count (also empty lines)
            }
            nq = (q0 & keep0).count_ones() + (q1 & keep1).count_ones();
            let mut k = 0;
            let mut m = c0;
            while m != 0 {
                cm[k] = line_start + m.trailing_zeros() as usize;
                m &= m - 1;
                k += 1;
            }
            let mut m = c1;
            while m != 0 {
                cm[k] = line_start + 64 + m.trailing_zeros() as usize;
                m &= m - 1;
                k += 1;
            }
        } else {
            let mut k = 0;
            let mut q = 0u32;
            for (i, &b) in chunk[line_start..end].iter().enumerate() {
                if b == b',' {
                    if k < 8 {
                        cm[k] = line_start + i;
                    }
                    k += 1;
                } else if b == b'"' {
                    q += 1;
                }
            }
            if k != 6 {
                continue;
            }
            nq = q;
        }
        // field k spans [fs_k, fe_k); strip quotes around whole fields; validate the quote count
        let mut fb = [(0usize, 0usize); 7];
        let mut pairs = 0u32;
        let mut fs = line_start;
        for k in 0..7 {
            let fe = if k < 6 { cm[k] } else { end };
            let flen = fe - fs;
            let first = *chunk.get(fs).unwrap_or(&0);
            let last = *chunk.get(fe.wrapping_sub(1).max(fs)).unwrap_or(&0);
            let isq = ((nq > 0) & (flen >= 2) & (first == b'"') & (last == b'"')) as usize;
            pairs += isq as u32;
            fb[k] = (fs + isq, fe - isq);
            fs = fe + 1;
        }
        if nq != 2 * pairs {
            continue; // a quote that is not around a whole field
        }
        let field = |k: usize| -> Option<B> {
            let (a, b) = fb[k];
            if a < b { Some(&chunk[a..b]) } else { None }
        };
        let Some(eid) = field(0) else { continue };
        let ing = parse_ts(field(3));
        let ts = parse_ts(field(2));
        let uid = field(1);
        let kind = event_kind(field(4));
        let pid = field(5);
        let mut ok = uid.is_some() && pid.is_some() && kind < 3 && ts != BAD && ts >= ws && ts < we;
        let mut p = 0u32;
        let mut cat = 0u16;
        if ok && kind == 2 {
            match parse_price(field(6)) {
                Some(v) => {
                    p = v as u32;
                    cat = match products.get(pid.unwrap()) {
                        Some(&c) => c as u16,
                        None => u16::MAX,
                    };
                }
                None => ok = false,
            }
        }
        if ok && ing - ts > DAY {
            ok = false;
        }
        let mut idx = u32::MAX as u64;
        let mut ush = 0u64;
        if ok {
            let u = uid.unwrap();
            idx = pay.len() as u64;
            let (uh, uh2) = h12(u);
            ush = shard_h(uh) as u64;
            pay.push(PEv { pk: uh, pk2: uh2, nptr: u.as_ptr() as usize, nlen: u.len() as u32, ts: (ts - ws) as u32, price: p, cat });
        }
        let (eh, eh2) = h12(eid);
        kcount[shard_h(eh)] += 1;
        keys.push(DKey { eh, eh2, ing, loc: (ush << 48) | ((ci as u64) << 32) | idx });
    }
    let _ = pad;
    (pay, keys, kcount)
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

thread_local! {
    // one-entry cache: exact "YYYY-MM-" bytes -> (days at day 1, days in month); month 0 = invalid
    static MONTH: std::cell::Cell<(u64, i64, i64)> = const { std::cell::Cell::new((u64::MAX, 0, 0)) };
}

/// Fast exact "YYYY-MM-DDTHH:MM:SS" prefix -> epoch ms (same results as civil()).
#[inline(always)]
fn civil_fast(b: &[u8]) -> Option<i64> {
    if b[10] != b'T' || b[13] != b':' || b[16] != b':' {
        return None;
    }
    let (h, mi, s) = (d2(b, 11)?, d2(b, 14)?, d2(b, 17)?);
    if h > 23 || mi > 59 || s > 59 {
        return None;
    }
    let key = u64::from_le_bytes(b[0..8].try_into().unwrap());
    let (k, base, mlen) = MONTH.with(|c| c.get());
    let (base, mlen) = if k == key {
        (base, mlen)
    } else {
        let r = (|| {
            if b[4] != b'-' || b[7] != b'-' {
                return None;
            }
            let y = d2(b, 0)? * 100 + d2(b, 2)?;
            let mo = d2(b, 5)?;
            if !(1..=12).contains(&mo) {
                return None;
            }
            let leap = y % 4 == 0 && (y % 100 != 0 || y % 400 == 0);
            let ml = [31, if leap { 29 } else { 28 }, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][(mo - 1) as usize];
            Some((days_from_civil(y, mo, 1), ml))
        })();
        let (bs, ml) = r.unwrap_or((0, 0));
        MONTH.with(|c| c.set((key, bs, ml)));
        (bs, ml)
    };
    let d = d2(b, 8)?;
    if d < 1 || d > mlen {
        return None;
    }
    Some((((base + d - 1) * 24 + h) * 60 + mi) * 60_000 + s * 1000)
}

/// Fast parse_ts: identical results to parse_ts_ref (fuzz-checked by SELFTEST=1).
#[inline(always)]
fn parse_ts(v: Option<B>) -> i64 {
    let Some(b) = v else { return BAD };
    let n = b.len();
    if n == 20 && b[19] == b'Z' {
        return civil_fast(b).unwrap_or(BAD);
    }
    if n == 25 && (b[19] == b'+' || b[19] == b'-') && b[22] == b':' {
        let (Some(base), Some(oh), Some(om)) = (civil_fast(b), d2(b, 20), d2(b, 23)) else { return BAD };
        if oh > 23 || om > 59 {
            return BAD;
        }
        let off = (oh * 60 + om) * 60_000;
        return if b[19] == b'+' { base - off } else { base + off };
    }
    // F3: digits only; leading zeros allowed; more than 18 significant digits cannot fit
    let mut i = 0;
    while i < n && b[i] == b'0' {
        i += 1;
    }
    if n - i > 18 {
        return if b.iter().all(|c| c.is_ascii_digit()) { parse_ts_ref(Some(b)) } else { BAD };
    }
    let mut x: i64 = 0;
    for &c in &b[i..] {
        let d = c.wrapping_sub(b'0');
        if d >= 10 {
            return BAD;
        }
        x = x * 10 + d as i64;
    }
    x
}

#[inline]
fn parse_ts_ref(v: Option<B>) -> i64 {
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

/// Before person resolution (pk, pk2, name) hold the user_id's hashes and bytes.
type UEv = PEv;

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
    pk: u64, // (h64, h2) of user_id
    pk2: u64,
    nptr: usize, // user_id bytes inside the memory-mapped input (mapped for the whole run)
    nlen: u32,
    ts: u32, // ts - window_start (valid events lie inside the window)
    price: u32, // > 0 exactly for purchases
    cat: u16,
}

impl PEv {
    #[inline]
    fn name(&self) -> B {
        // SAFETY: points into an input mapping that is never unmapped
        unsafe { std::slice::from_raw_parts(self.nptr as *const u8, self.nlen as usize) }
    }
}

/// Event after person resolution: key = person id << 32 | (ts - window_start).
#[derive(Clone, Copy)]
struct PR {
    key: u64,
    price: u32, // > 0 exactly for purchases
    cat: u32,
}

/// Click after person resolution: key = person id << 32 | (ts - (window_start - 7 days)).
#[derive(Clone, Copy)]
struct CR {
    key: u64,
    camp: u32,
    cid: B,
}

#[inline]
fn shard_pid(pid: u32) -> usize {
    ((pid as u64).wrapping_mul(0x9E37_79B9_7F4A_7C15) >> (64 - SH_BITS)) as usize
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
fn sorted_by_pk_ts<T: Copy>(v: &[T], base: i64, pk: impl Fn(&T) -> u64, ts: impl Fn(&T) -> i64) -> Vec<T> {
    let mut k: Vec<u128> = v
        .iter()
        .enumerate()
        .map(|(i, x)| ((pk(x) as u128) << 64) | (((ts(x) - base) as u32 as u128) << 32) | i as u128)
        .collect();
    k.sort_unstable();
    k.iter().map(|&x| v[x as u32 as usize]).collect()
}

struct SendPtr<T>(*mut T);
unsafe impl<T> Send for SendPtr<T> {}
unsafe impl<T> Sync for SendPtr<T> {}

/// Radix partition: every record is written exactly once into one contiguous array,
/// grouped by shard. Returns the array and NSH+1 shard offsets.
fn partition<T: Copy + Send + Sync>(parts: Vec<Vec<T>>, key: impl Fn(&T) -> usize + Sync) -> (Vec<T>, Vec<usize>) {
    let refs: Vec<&[T]> = parts.iter().map(|v| v.as_slice()).collect();
    partition_keep(&refs, |_, _| true, key)
}

/// Radix partition of the records of several parts for which keep(part, index) holds.
fn partition_keep<T: Copy + Send + Sync>(
    parts: &[&[T]],
    keep: impl Fn(usize, usize) -> bool + Sync,
    key: impl Fn(&T) -> usize + Sync,
) -> (Vec<T>, Vec<usize>) {
    partition_counted(parts, None, keep, key)
}

/// Like partition_keep; `known` supplies per-part shard counts already gathered by the producer.
fn partition_counted<T: Copy + Send + Sync>(
    parts: &[&[T]],
    known: Option<Vec<Vec<u32>>>,
    keep: impl Fn(usize, usize) -> bool + Sync,
    key: impl Fn(&T) -> usize + Sync,
) -> (Vec<T>, Vec<usize>) {
    let counts: Vec<Vec<usize>> = if let Some(k) = known {
        k.into_iter().map(|v| v.into_iter().map(|x| x as usize).collect()).collect()
    } else {
        parts
        .par_iter()
        .enumerate()
        .map(|(pi, v)| {
            let mut c = vec![0usize; NSH];
            for (i, x) in v.iter().enumerate() {
                if keep(pi, i) {
                    c[key(x)] += 1;
                }
            }
            c
        })
        .collect()
    };
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
    parts.par_iter().zip(starts.into_par_iter()).enumerate().for_each(|(pi, (v, mut pos))| {
        for (i, x) in v.iter().enumerate() {
            if !keep(pi, i) {
                continue;
            }
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
    assert!(cat_names.len() < u16::MAX as usize, "more than 65534 product categories");
    let mut camp_ids: Vec<B> = vec![];
    let mut camp_chan: Vec<B> = vec![];
    let mut campaigns: FxHashMap<B, u32> = FxHashMap::default();
    for (cid, ch) in small_table(&data.join("campaigns.csv")) {
        campaigns.insert(cid, camp_ids.len() as u32);
        camp_ids.push(cid);
        camp_chan.push(ch);
    }

    // links run on their own thread, overlapping event parsing and dedup (nothing there needs them)
    let ln_bufs2 = ln_bufs.clone();
    let links_job = std::thread::spawn(move || {
    // links: union-find, root kept as byte-wise smallest ID
    let pairs: Vec<(B, B)> = chunks(&ln_bufs2)
        .iter()
        .flat_map(|&c| {
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
    let mut lk: FxHashMap<u64, (u64, u32)> = FxHashMap::default();
    lk.reserve(it.names.len());
    let mut lk_clash = it.clash;
    for (i, &n) in it.names.iter().enumerate() {
        let r = rootv[i] as usize;
        let v = (h2(n), r as u32);
        if lk.insert(it.hashes[i], v).is_some() {
            lk_clash = true; // two linked IDs share a 64-bit hash: use the exact path
        }
    }
    // the same table split by uid-hash shard, so each shard's lookups stay in cache
    let lks: Vec<FxHashMap<u64, (u64, u32)>> = {
        let mut parts: Vec<Vec<(u64, (u64, u32))>> = (0..NSH).map(|_| Vec::new()).collect();
        for (&k, &v) in &lk {
            parts[shard_h(k)].push((k, v));
        }
        parts.into_iter().map(|v| v.into_iter().collect()).collect()
    };
    drop(lk);
        (it, rootv, lk_clash, lks)
    });

    // events: parse + validate each copy, scatter by event_id
    let ev_chunks = chunks(&ev_bufs);
    if std::env::var("SELFTEST").is_ok() {
        let mut seed: u64 = 0x1234_5678_9ABC_DEF0;
        let mut rnd = || {
            seed ^= seed << 13;
            seed ^= seed >> 7;
            seed ^= seed << 17;
            seed
        };
        let alphabet = b"0123456789-+:TZtz .";
        let templates: [&[u8]; 6] = [
            b"2026-10-03T23:58:10Z",
            b"2028-02-29T00:00:00Z",
            b"2026-10-03T19:58:10-04:00",
            b"1791071890000",
            b"0001791071890000",
            b"2027-12-31T23:59:59+23:59",
        ];
        let mut checked = 0u64;
        for _ in 0..3_000_000 {
            let mut t: Vec<u8> = templates[(rnd() % 6) as usize].to_vec();
            // mutate 0-3 random positions, sometimes change length
            for _ in 0..(rnd() % 4) {
                let i = (rnd() as usize) % t.len();
                t[i] = alphabet[(rnd() as usize) % alphabet.len()];
            }
            if rnd() % 10 == 0 {
                t.truncate((rnd() as usize) % t.len() + 1);
            }
            if rnd() % 20 == 0 {
                let k = (rnd() % 12) as usize;
                t = std::iter::repeat_n(b'0', k).chain(t).collect();
            }
            let tb: &'static [u8] = Box::leak(t.into_boxed_slice());
            assert_eq!(parse_ts(Some(tb)), parse_ts_ref(Some(tb)), "mismatch on {:?}", String::from_utf8_lossy(tb));
            checked += 1;
        }
        // every calendar day across leap and non-leap years, at both ends of the day
        for y in [1999i64, 2000, 2024, 2025, 2026, 2027, 2028, 2100] {
            for mo in 1..=13 {
                for d in 0..=32 {
                    for hms in ["00:00:00", "23:59:59", "24:00:00", "12:60:00"] {
                        let t = format!("{y:04}-{mo:02}-{d:02}T{hms}Z");
                        let tb: &'static [u8] = Box::leak(t.into_bytes().into_boxed_slice());
                        assert_eq!(parse_ts(Some(tb)), parse_ts_ref(Some(tb)), "mismatch on {:?}", String::from_utf8_lossy(tb));
                        checked += 1;
                    }
                }
            }
        }
        eprintln!("SELFTEST ok: {checked} timestamps identical");
        // scanners must agree on every line (all event, click and link chunks, plus synthetic lines)
        let synth: &'static [u8] = Box::leak(
            br#"a,b,c,d,e,f,g

"a","",c,d,e,f,g
x,"y"z,c,d,e,f,g
""",b,c,d,e,f,g
a,b,c,d,e,f
a,b,c,d,e,f,g,h
"
,,,,,,
a,b,c,d,e,f,"g"
last,b,c,d,e,f,g"#
                .to_vec()
                .into_boxed_slice(),
        );
        let mut lines_checked = 0u64;
        let mut bad = 0u64;
        let all: Vec<B> = chunks(&ev_bufs).into_iter().chain(chunks(&cl_bufs)).chain(chunks(&ln_bufs)).chain([synth]).collect();
        for c in all {
            for len_cut in [c.len(), c.len().saturating_sub(1), c.len().saturating_sub(37)] {
                let c = &c[..len_cut];
                let (mut a7, mut b7): (Vec<_>, Vec<_>) = (vec![], vec![]);
                scan_lines::<7>(c, |r| a7.push(r));
                scan_lines2::<7>(c, |r| b7.push(r));
                let (mut a4, mut b4): (Vec<_>, Vec<_>) = (vec![], vec![]);
                scan_lines::<4>(c, |r| a4.push(r));
                scan_lines2::<4>(c, |r| b4.push(r));
                lines_checked += a7.len() as u64;
                if a7 != b7 || a4 != b4 {
                    bad += 1;
                }
            }
        }
        assert_eq!(bad, 0, "scanner mismatch");
        eprintln!("SELFTEST ok: scanners agree on {lines_checked} lines (x2 widths, 3 truncations per chunk)");
        std::process::exit(0);
    }
    if let Ok(level) = std::env::var("PARSEBENCH") {
        // single-threaded cost ladder over all event lines; prints ns/line per level
        let level: u32 = level.parse().unwrap();
        let ev_chunks: Vec<B> = if std::env::var("COPYIN").is_ok() {
            // same bytes, but in anonymous (huge-page eligible) heap memory instead of the file mapping
            ev_chunks.iter().map(|c| &*Box::leak(c.to_vec().into_boxed_slice())).collect()
        } else {
            ev_chunks.clone()
        };
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
    let per_chunk: Vec<(Vec<UEv>, Vec<DKey>, Vec<u32>)> = ev_chunks
        .par_iter()
        .enumerate()
        .map(|(ci, &c)| parse_event_chunk(c, ci, ws, we, &products))
        .collect();
    lap("  parse lines");
    let mut pays: Vec<Vec<UEv>> = Vec::with_capacity(per_chunk.len());
    let mut keys: Vec<Vec<DKey>> = Vec::with_capacity(per_chunk.len());
    let mut kcounts: Vec<Vec<u32>> = Vec::with_capacity(per_chunk.len());
    for (a, b, c) in per_chunk {
        pays.push(a);
        keys.push(b);
        kcounts.push(c);
    }
    let key_refs: Vec<&[DKey]> = keys.iter().map(|v| v.as_slice()).collect();
    let (key_all, key_off) = partition_counted(&key_refs, Some(kcounts), |_, _| true, |k: &DKey| shard_h(k.eh));
    drop(key_refs);
    drop(keys);
    lap("events parsed");

    // dedup within each event shard, keep surviving events, re-scatter by person
    lap("  pre-bitmaps");
    // winner bitmaps, one per chunk, over that chunk's valid payloads
    let wcount: Vec<Vec<std::sync::atomic::AtomicU32>> =
        pays.iter().map(|_| (0..NSH).map(|_| std::sync::atomic::AtomicU32::new(0)).collect()).collect();
    let bits: Vec<Vec<std::sync::atomic::AtomicU64>> =
        pays.iter().map(|v| (0..v.len() / 64 + 1).map(|_| std::sync::atomic::AtomicU64::new(0)).collect()).collect();
    // per-thread open-addressing table (reused across shards): slot -> index of the best copy
    (0..NSH).into_par_iter().for_each_init(
        || (Vec::<u64>::new(), Vec::<u32>::new()),
        |(tk, tv), shi| {
            let ks = &key_all[key_off[shi]..key_off[shi + 1]];
            if ks.is_empty() {
                return;
            }
            let cap = (ks.len() * 2).next_power_of_two();
            let mask = cap - 1;
            tk.clear();
            tk.resize(cap, 0);
            tv.resize(cap, 0);
            for (i, k) in ks.iter().enumerate() {
                let tag = k.eh | 1; // 0 marks an empty slot
                let mut slot = (k.eh.wrapping_mul(0x9E37_79B9_7F4A_7C15) >> 20) as usize & mask;
                loop {
                    let t = tk[slot];
                    if t == 0 {
                        tk[slot] = tag;
                        tv[slot] = i as u32;
                        break;
                    }
                    if t == tag {
                        let j = tv[slot] as usize;
                        if ks[j].eh == k.eh && ks[j].eh2 == k.eh2 {
                            // same event: keep the earliest ingest (equal ingest => identical copies)
                            if k.ing < ks[j].ing {
                                tv[slot] = i as u32;
                            }
                            break;
                        }
                    }
                    slot = (slot + 1) & mask;
                }
            }
            for slot in 0..cap {
                if tk[slot] != 0 {
                    let loc = ks[tv[slot] as usize].loc;
                    let idx = (loc & 0xFFFF_FFFF) as usize;
                    let chunk = ((loc >> 32) & 0xFFFF) as usize;
                    if idx != u32::MAX as usize {
                        bits[chunk][idx / 64].fetch_or(1 << (idx % 64), std::sync::atomic::Ordering::Relaxed);
                        wcount[chunk][(loc >> 48) as usize].fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                    }
                }
            }
        },
    );
    lap("  dedup table");
    drop(key_all);
    lap("  drop keys");
    lap("events deduped");
    let pay_refs: Vec<&[UEv]> = pays.iter().map(|v| v.as_slice()).collect();
    let is_winner = |c: usize, i: usize| bits[c][i / 64].load(std::sync::atomic::Ordering::Relaxed) >> (i % 64) & 1 == 1;
    let wc: Vec<Vec<u32>> = wcount.into_iter().map(|v| v.into_iter().map(|a| a.into_inner()).collect()).collect();
    let (mut uev_all, uev_off) = partition_counted(&pay_refs, Some(wc), is_winner, |e: &UEv| shard_h(e.pk));
    drop(pay_refs);
    drop(pays);
    // clicks: copies are identical, so duplicates cannot change credit or assists
    let cl_chunks = chunks(&cl_bufs);
    let per_chunk: Vec<(Vec<UCl>, Vec<u32>)> = cl_chunks
        .par_iter()
        .map(|&c| {
            let mut sh: Vec<UCl> = Vec::with_capacity(c.len() / 40 + 16);
            let mut cc = vec![0u32; NSH];
            scan_lines2::<4>(c, |r| {
                let Some([Some(cid), Some(uid), Some(camp), ts]) = r else { return };
                let Some(&camp) = campaigns.get(camp) else { return };
                let ts = parse_ts(ts);
                if ts == BAD || ts < ws - WEEK || ts >= we {
                    return;
                }
                let (uh, uh2) = h12(uid);
                cc[shard_h(uh)] += 1;
                sh.push(UCl { uh, uh2, uid, ts, cid, camp });
            });
            (sh, cc)
        })
        .collect();
    let (ucls, ccounts): (Vec<Vec<UCl>>, Vec<Vec<u32>>) = per_chunk.into_iter().unzip();
    let ucl_refs: Vec<&[UCl]> = ucls.iter().map(|v| v.as_slice()).collect();
    let (ucl_all, ucl_off) = partition_counted(&ucl_refs, Some(ccounts), |_, _| true, |c: &UCl| shard_h(c.uh));
    drop(ucl_refs);
    drop(ucls);
    lap("clicks parsed");
    let (it, rootv, lk_clash, lks) = links_job.join().expect("links thread");
    lap("links joined");
    // Resolve users to exact person ids, one uid-hash shard at a time (its tables fit in cache).
    // Linked user -> root index (< 2^31). Unlinked user -> 1<<31 | shard<<22 | local index.
    let resolved: Vec<(Vec<PR>, Vec<CR>, Vec<B>, Vec<u32>, Vec<u32>)> = (0..NSH)
        .into_par_iter()
        .map(|shi| {
            let lkm = &lks[shi];
            let mut unl: FxHashMap<(u64, u64), u32> = FxHashMap::default();
            let mut unl_names: Vec<B> = Vec::new();
            let mut pid_of = |u: B, uh: u64, u2: u64| -> u32 {
                let linked = if !lk_clash {
                    match lkm.get(&uh) {
                        Some(&(lu2, r)) if lu2 == u2 => Some(r),
                        _ => None,
                    }
                } else {
                    it.get(u, uh).map(|i| rootv[i as usize])
                };
                if let Some(r) = linked {
                    return r;
                }
                let n = unl_names.len() as u32;
                let local = *unl.entry((uh, u2)).or_insert_with(|| {
                    unl_names.push(u);
                    n
                });
                assert!(local < (1 << (31 - SH_BITS)), "too many unlinked users in one shard");
                (1u32 << 31) | ((shi as u32) << (31 - SH_BITS)) | local
            };
            let evs = &uev_all[uev_off[shi]..uev_off[shi + 1]];
            let prs: Vec<PR> = evs
                .iter()
                .map(|e| PR {
                    key: ((pid_of(e.name(), e.pk, e.pk2) as u64) << 32) | e.ts as u64,
                    price: e.price,
                    cat: if e.cat == u16::MAX { UNKNOWN_CAT } else { e.cat as u32 },
                })
                .collect();
            let cls = &ucl_all[ucl_off[shi]..ucl_off[shi + 1]];
            let crs: Vec<CR> = cls
                .iter()
                .map(|c| CR {
                    key: ((pid_of(c.uid, c.uh, c.uh2) as u64) << 32) | (c.ts - (ws - WEEK)) as u32 as u64,
                    camp: c.camp,
                    cid: c.cid,
                })
                .collect();
            let mut pc = vec![0u32; NSH];
            for r in &prs {
                pc[shard_pid((r.key >> 32) as u32)] += 1;
            }
            let mut cc = vec![0u32; NSH];
            for c in &crs {
                cc[shard_pid((c.key >> 32) as u32)] += 1;
            }
            (prs, crs, unl_names, pc, cc)
        })
        .collect();
    drop(uev_all);
    drop(ucl_all);
    let mut prs_parts = Vec::with_capacity(NSH);
    let mut crs_parts = Vec::with_capacity(NSH);
    let mut unl_names_by_shard: Vec<Vec<B>> = Vec::with_capacity(NSH);
    let mut pcs = Vec::with_capacity(NSH);
    let mut ccs = Vec::with_capacity(NSH);
    for (a, b, c, d, e) in resolved {
        prs_parts.push(a);
        crs_parts.push(b);
        unl_names_by_shard.push(c);
        pcs.push(d);
        ccs.push(e);
    }
    drop(pcs);
    drop(ccs);
    // Dense person ids: linked people keep their root index (< R); unlinked users get
    // R + (their uid shard's offset) + local index. Person shards own contiguous id ranges,
    // so sessionizing can index people with arithmetic instead of hashing.
    let r_count = it.names.len() as u32;
    let mut uprefix = vec![0u32; NSH];
    let mut run = r_count;
    for sh in 0..NSH {
        uprefix[sh] = run;
        run += unl_names_by_shard[sh].len() as u32;
    }
    let total_p = run.max(1);
    let span = (total_p as usize).div_ceil(NSH) as u32;
    let dense = |pid: u32| -> u32 {
        if pid < (1 << 31) {
            pid
        } else {
            uprefix[((pid >> (31 - SH_BITS)) as usize) & (NSH - 1)] + (pid & ((1 << (31 - SH_BITS)) - 1))
        }
    };
    let pshard = |d: u32| -> usize { (d / span) as usize };
    let pcs: Vec<Vec<u32>> = prs_parts
        .par_iter_mut()
        .map(|v| {
            let mut c = vec![0u32; NSH];
            for r in v.iter_mut() {
                let d = dense((r.key >> 32) as u32);
                r.key = ((d as u64) << 32) | (r.key & 0xFFFF_FFFF);
                c[pshard(d)] += 1;
            }
            c
        })
        .collect();
    let ccs: Vec<Vec<u32>> = crs_parts
        .par_iter_mut()
        .map(|v| {
            let mut c = vec![0u32; NSH];
            for x in v.iter_mut() {
                let d = dense((x.key >> 32) as u32);
                x.key = ((d as u64) << 32) | (x.key & 0xFFFF_FFFF);
                c[pshard(d)] += 1;
            }
            c
        })
        .collect();
    let unl_flat: Vec<B> = unl_names_by_shard.into_iter().flatten().collect();
    let name_of_pid = |d: u32| -> B { if d < r_count { it.names[d as usize] } else { unl_flat[(d - r_count) as usize] } };
    let (mut pev_all, pev_off) = {
        let refs: Vec<&[PR]> = prs_parts.iter().map(|v| v.as_slice()).collect();
        partition_counted(&refs, Some(pcs), |_, _| true, |r: &PR| pshard((r.key >> 32) as u32))
    };
    drop(prs_parts);
    let (mut pcl_all, pcl_off) = {
        let refs: Vec<&[CR]> = crs_parts.iter().map(|v| v.as_slice()).collect();
        partition_counted(&refs, Some(ccs), |_, _| true, |c: &CR| pshard((c.key >> 32) as u32))
    };
    drop(crs_parts);
    lap("events regrouped");
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
    let cbase = ws - WEEK;
    let results: Vec<(Vec<URow>, Vec<[i64; 4]>)> = pev_slices
        .into_par_iter()
        .zip(pcl_slices.into_par_iter())
        .enumerate()
        .fold(|| (Vec::<URow>::new(), vec![[0i64; 4]; ncamp * ndays]), |(mut urows, mut camp), (sh, (evs, cls))| {
            // group by person with a counting sort over the shard's contiguous id range, then sort
            // each person's (few) events by time; clicks are grouped the same way
            let base = sh as u32 * span;
            let np = span as usize;
            let li = |key: u64| -> usize { ((key >> 32) as u32 - base) as usize };
            let mut eoff = vec![0u32; np + 1];
            for r in evs.iter() {
                eoff[li(r.key) + 1] += 1;
            }
            for p in 0..np {
                eoff[p + 1] += eoff[p];
            }
            let mut eg: Vec<PR> = Vec::with_capacity(evs.len());
            let mut pos = eoff.clone();
            // SAFETY: every slot in 0..evs.len() is written exactly once below
            unsafe { eg.set_len(evs.len()) };
            for r in evs.iter() {
                let l = li(r.key);
                eg[pos[l] as usize] = *r;
                pos[l] += 1;
            }
            let mut coff = vec![0u32; np + 1];
            for c in cls.iter() {
                coff[li(c.key) + 1] += 1;
            }
            for p in 0..np {
                coff[p + 1] += coff[p];
            }
            let ncl = cls.len();
            let mut cg: Vec<CR> = Vec::with_capacity(ncl);
            // SAFETY: every slot in 0..ncl is written exactly once below
            unsafe { cg.set_len(ncl) };
            let mut cpos = coff.clone();
            for c in cls.iter() {
                let l = li(c.key);
                cg[cpos[l] as usize] = *c;
                cpos[l] += 1;
            }
            let mut cats: Vec<(u32, i64)> = vec![];
            let mut active: Vec<(u32, u32)> = Vec::new(); // (campaign, clicks in window)
            for p in 0..np {
                if eoff[p] == eoff[p + 1] {
                    continue; // no events: this person has no sessions
                }
                let evs = &mut eg[eoff[p] as usize..eoff[p + 1] as usize];
                evs.sort_unstable_by_key(|r| r.key);
                let pcl = &mut cg[coff[p] as usize..coff[p + 1] as usize];
                // by ts ascending; equal ts ordered by click_id DESCENDING so the last eligible
                // click is the winner (latest ts, then smallest click_id)
                pcl.sort_unstable_by(|x, y| x.key.cmp(&y.key).then_with(|| y.cid.cmp(x.cid)));
                let pcl = &*pcl;
                let pid = base + p as u32;
                let (i, j) = (0usize, evs.len());
                let name = name_of_pid(pid);
                let ets = |x: &PR| ws + (x.key & 0xFFFF_FFFF) as i64;
                let cts = |x: &CR| cbase + (x.key & 0xFFFF_FFFF) as i64;
                // sliding window [lo, hi) over this person's clicks
                let (mut lo, mut hi) = (0usize, 0usize);
                active.clear();
                let mut cur_day = i32::MIN;
                let mut row: Option<URow> = None;
                let mut k = i;
                while k < j {
                    // one session: extend while gap between distinct timestamps <= GAP
                    let start = ets(&evs[k]);
                    let mut prev = start;
                    let mut e = k;
                    let (mut n, mut rev, mut purch) = (0i64, 0i64, false);
                    while e < j {
                        let t = ets(&evs[e]);
                        if !(t == prev || t - prev <= GAP) {
                            break;
                        }
                        prev = t;
                        n += 1;
                        if evs[e].price > 0 {
                            purch = true;
                            rev += evs[e].price as i64;
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
                        if x.price > 0 {
                            match cats.iter_mut().find(|c| c.0 == x.cat) {
                                Some(c) => c.1 += x.price as i64,
                                None => cats.push((x.cat, x.price as i64)),
                            }
                        }
                    }
                    // attribution window: start - WEEK <= click.ts <= start
                    while hi < pcl.len() && cts(&pcl[hi]) <= start {
                        let c = pcl[hi].camp;
                        match active.iter_mut().find(|x| x.0 == c) {
                            Some(x) => x.1 += 1,
                            None => active.push((c, 1)),
                        }
                        hi += 1;
                    }
                    while lo < hi && cts(&pcl[lo]) < start - WEEK {
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
