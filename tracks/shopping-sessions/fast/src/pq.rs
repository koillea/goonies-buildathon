//! Minimal Parquet writer: one row group, one uncompressed PLAIN data page (v1) per
//! column, flat schema. Supports REQUIRED/OPTIONAL BYTE_ARRAY (UTF8), INT32 (DATE)
//! and INT64. Metadata is Thrift compact protocol, hand-encoded.

use std::io::Write;

pub enum Col<'a> {
    /// UTF8 string column; `None` entries are nulls (column must be optional).
    Str(Vec<Option<&'a [u8]>>, bool /* optional */),
    Date(Vec<i32>),
    I64(Vec<i64>),
}

// ---- Thrift compact protocol
struct T {
    b: Vec<u8>,
    last: Vec<i16>,
}
impl T {
    fn new() -> Self {
        T { b: Vec::new(), last: vec![0] }
    }
    fn varint(&mut self, mut v: u64) {
        while v >= 0x80 {
            self.b.push((v as u8) | 0x80);
            v >>= 7;
        }
        self.b.push(v as u8);
    }
    fn zz(&mut self, v: i64) {
        self.varint(((v << 1) ^ (v >> 63)) as u64);
    }
    fn fh(&mut self, id: i16, ty: u8) {
        let d = id - *self.last.last().unwrap();
        if d > 0 && d <= 15 {
            self.b.push(((d as u8) << 4) | ty);
        } else {
            self.b.push(ty);
            self.zz(id as i64);
        }
        *self.last.last_mut().unwrap() = id;
    }
    fn i32(&mut self, id: i16, v: i32) {
        self.fh(id, 5);
        self.zz(v as i64);
    }
    fn i64(&mut self, id: i16, v: i64) {
        self.fh(id, 6);
        self.zz(v);
    }
    fn bin(&mut self, id: i16, v: &[u8]) {
        self.fh(id, 8);
        self.varint(v.len() as u64);
        self.b.extend_from_slice(v);
    }
    fn begin(&mut self, id: i16) {
        self.fh(id, 12);
        self.last.push(0);
    }
    fn end(&mut self) {
        self.b.push(0);
        self.last.pop();
    }
    fn list(&mut self, id: i16, n: usize, elem: u8) {
        self.fh(id, 9);
        self.list_hdr(n, elem);
    }
    fn list_hdr(&mut self, n: usize, elem: u8) {
        if n < 15 {
            self.b.push(((n as u8) << 4) | elem);
        } else {
            self.b.push(0xF0 | elem);
            self.varint(n as u64);
        }
    }
    // a struct that is a list element: no field header
    fn elem_begin(&mut self) {
        self.last.push(0);
    }
}

/// RLE/bit-packed hybrid, bit width 1, as RLE runs only.
fn def_levels(defs: &[bool]) -> Vec<u8> {
    let mut out = Vec::new();
    let mut i = 0;
    while i < defs.len() {
        let v = defs[i];
        let mut j = i;
        while j < defs.len() && defs[j] == v {
            j += 1;
        }
        let mut h = ((j - i) as u64) << 1;
        while h >= 0x80 {
            out.push((h as u8) | 0x80);
            h >>= 7;
        }
        out.push(h as u8);
        out.push(v as u8);
        i = j;
    }
    out
}

pub fn write(path: &std::path::Path, cols: &[(&str, Col)]) -> std::io::Result<()> {
    let nrows = match &cols[0].1 {
        Col::Str(v, _) => v.len(),
        Col::Date(v) => v.len(),
        Col::I64(v) => v.len(),
    };
    let mut f = std::io::BufWriter::with_capacity(1 << 20, std::fs::File::create(path)?);
    f.write_all(b"PAR1")?;
    let mut off: i64 = 4;
    let mut metas: Vec<(i64, i64, i32 /*type*/)> = vec![]; // (page offset, chunk size, type)
    for (_, col) in cols {
        let mut page = Vec::new();
        let ty;
        match col {
            Col::Str(v, optional) => {
                ty = 6; // BYTE_ARRAY
                if *optional {
                    let defs: Vec<bool> = v.iter().map(|x| x.is_some()).collect();
                    let enc = def_levels(&defs);
                    page.extend_from_slice(&(enc.len() as u32).to_le_bytes());
                    page.extend_from_slice(&enc);
                }
                for s in v.iter().flatten() {
                    page.extend_from_slice(&(s.len() as u32).to_le_bytes());
                    page.extend_from_slice(s);
                }
            }
            Col::Date(v) => {
                ty = 1; // INT32
                for x in v {
                    page.extend_from_slice(&x.to_le_bytes());
                }
            }
            Col::I64(v) => {
                ty = 2; // INT64
                for x in v {
                    page.extend_from_slice(&x.to_le_bytes());
                }
            }
        }
        let mut h = T::new();
        h.i32(1, 0); // DATA_PAGE
        h.i32(2, page.len() as i32);
        h.i32(3, page.len() as i32);
        h.begin(5); // DataPageHeader
        h.i32(1, nrows as i32);
        h.i32(2, 0); // PLAIN
        h.i32(3, 3); // RLE
        h.i32(4, 3); // RLE
        h.end();
        h.b.push(0);
        f.write_all(&h.b)?;
        f.write_all(&page)?;
        let size = (h.b.len() + page.len()) as i64;
        metas.push((off, size, ty));
        off += size;
    }
    // FileMetaData
    let mut m = T::new();
    m.i32(1, 1); // version
    m.list(2, cols.len() + 1, 12);
    m.elem_begin();
    m.bin(4, b"schema");
    m.i32(5, cols.len() as i32);
    m.end();
    for (name, col) in cols {
        m.elem_begin();
        let (ty, opt) = match col {
            Col::Str(_, o) => (6, *o),
            Col::Date(_) => (1, false),
            Col::I64(_) => (2, false),
        };
        m.i32(1, ty);
        m.i32(3, if opt { 1 } else { 0 });
        m.bin(4, name.as_bytes());
        match col {
            Col::Str(..) => {
                m.i32(6, 0); // converted UTF8
                m.begin(10); // LogicalType
                m.begin(1); // STRING
                m.end();
                m.end();
            }
            Col::Date(_) => {
                m.i32(6, 6); // converted DATE
                m.begin(10);
                m.begin(6); // DATE
                m.end();
                m.end();
            }
            Col::I64(_) => {}
        }
        m.end();
    }
    m.i64(3, nrows as i64);
    m.list(4, 1, 12);
    m.elem_begin(); // RowGroup
    m.list(1, cols.len(), 12);
    let total: i64 = metas.iter().map(|x| x.1).sum();
    for ((name, _), (poff, size, ty)) in cols.iter().zip(&metas) {
        m.elem_begin(); // ColumnChunk
        m.i64(2, *poff);
        m.begin(3); // ColumnMetaData
        m.i32(1, *ty);
        m.list(2, 2, 5);
        m.zz(0); // PLAIN
        m.zz(3); // RLE
        m.list(3, 1, 8);
        m.varint(name.len() as u64);
        m.b.extend_from_slice(name.as_bytes());
        m.i32(4, 0); // UNCOMPRESSED
        m.i64(5, nrows as i64);
        m.i64(6, *size);
        m.i64(7, *size);
        m.i64(9, *poff);
        m.end();
        m.end();
    }
    m.i64(2, total);
    m.i64(3, nrows as i64);
    m.end();
    m.bin(6, b"goonies-sessions");
    m.b.push(0);
    f.write_all(&m.b)?;
    f.write_all(&(m.b.len() as u32).to_le_bytes())?;
    f.write_all(b"PAR1")?;
    f.flush()
}
