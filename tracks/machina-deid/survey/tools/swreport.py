"""Summarize identity-bearing content of SolidWorks new-format files. Args: files..."""
import sys, re, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from swnew import sections
def strings(raw, n=4):
    a = [m.decode('latin-1') for m in re.findall(rb'[\x20-\x7e]{%d,}' % n, raw)]
    u = [m.decode('utf-16le', 'replace') for m in re.findall(rb'(?:[\x20-\x7e\x80-\xff][\x00-\x04]){%d,}' % n, raw)]
    return a + u
PATH = re.compile(r'([A-Za-z]:\\|\\\\[\w.]|/Users/|/home/)[^\x00]*', re.I)
OTHER = re.compile(r'(@[\w-]+\.\w+|https?://\S+|www\.\S+)')
for f in sys.argv[1:]:
    b = open(f, "rb").read()
    if b[4:8] != b"\x00\x00\x00\x04": continue
    print('#####', os.path.basename(f), len(b))
    paths, other, names = set(), set(), set()
    for o, n, c, u, raw in sections(b):
        if raw is None or not n.isprintable(): continue
        names.add(n)
        if n in ('docProps/core.xml', 'docProps/app.xml'):
            t = raw.decode('utf-8', 'replace')
            print('  [%s]' % n, [v for v in re.findall(r'<([\w:]+)[^>]*>([^<]{1,200})</', t) if v[0] not in ('dcterms:created','dcterms:modified','DocSecurity','LinksUpToDate','SharedDoc','HyperlinksChanged','TotalTime','Template','ScaleCrop')])
        elif n == 'docProps/custom.xml' or (n.startswith('docProps/Config-') and n.endswith('Properties.xml')):
            t = raw.decode('utf-8', 'replace')
            kv = re.findall(r'name="([^"]+)"[^>]*>\s*<vt:\w+>([^<]*)<', t)
            if kv: print('  [%s]' % n, kv[:20])
        elif n == 'docProps/ISolidWorksInformation.xml':
            t = raw.decode('utf-8', 'replace')
            kv = re.findall(r'name="([^"]+)"[^>]*>\s*<vt:\w+>([^<]*)<', t)
            print('  [ISWInfo]', [x for x in kv if re.search('author|saved|user|company|path|title|subject|keyword|comment', x[0], re.I)][:12])
        if n.startswith('Preview') or n.endswith('Partition'): continue
        for s in strings(raw):
            for m in PATH.finditer(s): paths.add((m.group(0)[:200], n.split('/')[-1]))
            for m in OTHER.finditer(s): other.add(m.group(0)[:100])
    pp = {}
    for p, n in paths: pp.setdefault(p, set()).add(n)
    for p in sorted(pp)[:25]: print('   PATH', p, '<-', ','.join(sorted(pp[p]))[:120])
    if len(pp) > 25: print('   ... %d paths' % len(pp))
    if other: print('   OTHER', sorted(other)[:10])
    print('   has:', 'PreviewPNG' in names, 'Preview' in names, [n for n in names if 'Third' in n or 'Ole' in n][:6])
