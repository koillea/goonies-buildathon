"""Magic-byte triage. Args: files..."""
import sys, os
def kind(h):
    if h[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1': return 'OLE2'
    if h[:4] == b'PK\x03\x04': return 'ZIP'
    if h[:4] == b'%PDF': return 'PDF'
    if h[:6] == b'7z\xbc\xaf\x27\x1c': return '7Z'
    if h[:2] == b'\x1f\x8b': return 'GZIP'
    if h[:4] == b'Rar!': return 'RAR'
    if h[:10] == b'ISO-10303-': return 'STEP'
    if h[:4] in (b'\x00\x00\x00\x00',) and len(h) > 4: return 'ZEROS'
    if h[:2] in (b'\x1f\x9d',): return 'UNIXCOMPRESS'
    if h[:4] == b'\x89PNG': return 'PNG'
    if h[:3] == b'\xff\xd8\xff': return 'JPEG'
    if h[:6] in (b'AC1015', b'AC1018', b'AC1021', b'AC1024', b'AC1027', b'AC1032', b'AC1014', b'AC1012', b'AC1009'): return 'DWG-' + h[:6].decode()
    if b'<svg' in h[:2000] or h[:5] == b'<?xml': return 'XML/SVG'
    if h[:5] == b'solid': return 'STL-ascii?'
    if h[:4] == b'#VRM': return 'VRML'
    if h[:2] == b'#U' or h[:4] == b'#UGC': return 'CREO-#UGC'
    if h[:3] in (b'400', b'700', b'200', b'210', b'220', b'250', b'260', b'270', b'280') or h[:5] == b'ACIS ': return 'ACIS-SAT'
    if h[:4] == b'\x00\x00\x00\x00': return 'ZEROS'
    if all(32 <= c < 127 or c in (9, 10, 13) for c in h[:200]): return 'TEXT:' + h[:40].decode('ascii', 'replace').replace('\n', '|').replace('\r', '')
    return 'BIN:' + h[:16].hex()
for f in sys.argv[1:]:
    h = open(f, 'rb').read(4096)
    print(f'{kind(h):40s} {os.path.getsize(f):>9} {f}')
