"""Parse SolidWorks 2015+ (non-OLE) container: sections marked 14 00 06 00 08 00, nibble-swapped names, raw-deflate payloads.
Usage: swnew.py file [--dump outdir] [--grep]"""
import sys, zlib, struct, re, os
MARK = b'\x14\x00\x06\x00\x08\x00'
def swap(bs): return bytes(((c >> 4) | (c << 4)) & 0xFF for c in bs)
def sections(b):
    i = 0
    while True:
        i = b.find(MARK, i)
        if i < 0: return
        try:
            crc, unk, csz, usz, nl = struct.unpack_from('<IIIII', b, i + 6)
        except struct.error: return
        if 0 < nl < 512:
            name = swap(b[i + 26:i + 26 + nl]).decode('latin-1')
            ds = i + 26 + nl
            data = b[ds:ds + csz]
            try:
                raw = zlib.decompressobj(-15).decompress(data) if csz else b''
            except zlib.error:
                raw = None
            yield i, name, csz, usz, raw
        i += 6
if __name__ == '__main__':
    f = sys.argv[1]; b = open(f, 'rb').read()
    dump = sys.argv[sys.argv.index('--dump') + 1] if '--dump' in sys.argv else None
    for off, name, csz, usz, raw in sections(b):
        st = 'ERR' if raw is None else len(raw)
        print(f'{off:>9} {csz:>8} {usz:>8} {st!s:>8} {name}')
        if dump and raw:
            p = os.path.join(dump, re.sub(r'[^A-Za-z0-9_.-]', '_', name)[:100]); open(p, 'wb').write(raw)
