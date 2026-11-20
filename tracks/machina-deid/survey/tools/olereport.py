"""Summarize OLE2 CAD files (old SolidWorks, Inventor): streams, Summary/DocSummary props, paths/strings. Args: files..."""
import sys, re, os, olefile, zlib
PATH = re.compile(r'([A-Za-z]:\\|\\\\[\w.]|/Users/|/home/)[^\x00<>"]{3,}')
EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+')
def strs(raw):
    a = [m.decode('latin-1') for m in re.findall(rb'[\x20-\x7e]{5,}', raw)]
    u = [m.decode('utf-16le', 'replace') for m in re.findall(rb'(?:[\x20-\x7e][\x00]){5,}', raw)]
    return a + u
for f in sys.argv[1:]:
    try: ole = olefile.OleFileIO(f)
    except Exception as e: continue
    print('#####', os.path.basename(f), os.path.getsize(f))
    streams = ['/'.join(s) for s in ole.listdir(streams=True, storages=False)]
    print('  streams(%d):' % len(streams), ', '.join(streams)[:700])
    m = ole.get_metadata()
    md = {k: getattr(m, k) for k in m.SUMMARY_ATTRIBS + m.DOCSUM_ATTRIBS if getattr(m, k) not in (None, b'', 0)}
    md = {k: (v.decode('latin-1', 'replace') if isinstance(v, bytes) else v) for k, v in md.items() if k not in ('codepage', 'codepage_doc', 'thumbnail', 'security')}
    print('  meta:', {k: str(v)[:80] for k, v in md.items()})
    # property sets of any kind (Inventor uses many \x05 streams)
    for s in streams:
        if s.split('/')[-1].startswith('\x05') and 'SummaryInformation' not in s:
            try:
                props = ole.getproperties(s.split('/'), convert_time=True)
                vals = [str(v)[:70] for v in props.values() if isinstance(v, (str, bytes)) and v]
                vals = [v.decode('latin-1') if isinstance(v, bytes) else v for v in vals]
                if vals: print('  propset %r:' % s, vals[:18])
            except Exception as e: pass
    paths, emails = {}, set()
    for s in streams:
        raw = ole.openstream(s).read()
        for t in strs(raw):
            for mm in PATH.finditer(t): paths.setdefault(mm.group(0)[:160], set()).add(s.split('/')[-1][:25])
            for mm in EMAIL.finditer(t): emails.add(mm.group(0))
    for p in sorted(paths)[:18]: print('   PATH', p, '<-', ','.join(sorted(paths[p]))[:80])
    if len(paths) > 18: print('   ... %d paths' % len(paths))
    if emails: print('   EMAIL', sorted(emails)[:8])
