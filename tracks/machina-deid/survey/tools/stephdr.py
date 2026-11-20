"""Print STEP FILE_NAME/FILE_DESCRIPTION, comments, distinct PRODUCT/name strings. Args: files..."""
import sys, re
for f in sys.argv[1:]:
    b = open(f, 'rb').read()
    t = b.decode('latin-1')
    h = t[:t.find('ENDSEC')+6] if 'ENDSEC' in t else t[:3000]
    h = re.sub(r'\s+', ' ', h)
    print('====', f.split('/')[-1], len(b), 'CRLF' if b'\r\n' in b[:2000] else '')
    m = re.search(r'FILE_NAME\s*\((.*?)\)\s*;\s*FILE_SCHEMA', h)
    print(' FILE_NAME:', (m.group(1) if m else h[:400])[:500])
    m = re.search(r'FILE_DESCRIPTION\s*\((.*?)\)\s*;', h); print(' FILE_DESC:', m.group(1)[:200] if m else None)
    cm = re.findall(r'/\*(.*?)\*/', t[:20000], re.S)
    cm = [c.strip()[:150] for c in cm if not re.match(r'\s*(name|time_stamp|author|organization|preprocessor_version|originating_system|authorization|description|implementation_level|schema_identifiers)\s*$', c.strip())]
    if cm: print(' COMMENTS:', cm[:4])
    prods = set(re.findall(r"PRODUCT\s*\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'", t))
    print(' PRODUCTS(%d):' % len(prods), list(prods)[:6])
    for ent in ['PERSON', 'ORGANIZATION', 'PERSON_AND_ORGANIZATION', 'APPROVAL_PERSON_ORGANIZATION', 'DOCUMENT', 'APPLIED_PERSON_AND_ORGANIZATION_ASSIGNMENT', 'DESCRIPTIVE_REPRESENTATION_ITEM','PROPERTY_DEFINITION','DATE_AND_TIME']:
        xs = re.findall(r"=\s*%s\s*\(([^;]*)\)\s*;" % ent, t)
        if xs: print(' %s(%d):' % (ent, len(xs)), [x[:120] for x in xs[:4]])
    x2 = re.findall(r'\\X2\\[0-9A-F]+\\X0\\', t); x = re.findall(r"\\X\\[0-9A-F]{2}", t)
    if x2 or x: print(' X2:', len(x2), x2[:2], 'X:', len(x))
    nonascii = sum(1 for c in b if c > 127)
    if nonascii: print(' raw non-ascii bytes:', nonascii)
