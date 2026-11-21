"""Compact Inventor OLE summary: property-set strings (UTF-16), UFRxDoc refs, paths, thumbnail presence. Args: files..."""
import sys, re, os, olefile
PATH = re.compile(r'([A-Za-z]:\\|\\\\[\w.]|/Users/|/home/)[^\x00<>"|]{3,}')
def u16(raw, n=3): return [m.decode('utf-16le', 'replace') for m in re.findall(rb'(?:[^\x00][\x00-\x04]|[\x00-\xff][\x04]){%d,}' % n, raw)]
def asc(raw, n=4): return [m.decode('latin-1') for m in re.findall(rb'[\x20-\x7e\xc0-\xff]{%d,}' % n, raw)]
for f in sys.argv[1:]:
    try: ole = olefile.OleFileIO(f)
    except Exception: continue
    print('#####', os.path.basename(f), os.path.getsize(f))
    streams = ole.listdir(streams=True, storages=False)
    for s in streams:
        if s[-1].startswith('\x05'):
            raw = ole.openstream(s).read()
            ss = [x for x in u16(raw) + asc(raw) if len(x.strip()) > 2 and not re.fullmatch(r'[\W\d_]+', x)]
            # first string is the set name for Inventor sets
            if ss: print('  PS %-30s' % s[-1][1:][:28], ss[:16])
    paths = {}
    for s in streams:
        raw = ole.openstream(s).read()
        for t in u16(raw, 5) + asc(raw, 5):
            for m in PATH.finditer(t): paths.setdefault(m.group(0)[:150], set()).add(s[-1][:12])
    for p in sorted(paths)[:14]: print('   PATH', p, '<-', ','.join(sorted(paths[p]))[:60])
    if len(paths) > 14: print('   ... %d paths' % len(paths))
    names = ['/'.join(s) for s in streams]
    print('   thumb:', [n for n in names if 'Thumb' in n or 'Preview' in n or n.startswith('\x05Summary') or n.startswith('\x05Document')][:4], 'UFRxDoc' in names)
