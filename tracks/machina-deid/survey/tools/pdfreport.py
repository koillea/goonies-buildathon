"""PDF identity report: Info, XMP fields, attachments, annotations/links, page-1 text excerpt, image count. Args: files..."""
import sys, os, re, pikepdf
from pypdf import PdfReader
EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+'); URL = re.compile(r'(?:https?://|www\.)[^\s)>\]]+')
for f in sys.argv[1:]:
    print('#####', os.path.basename(f), os.path.getsize(f))
    try:
        pdf = pikepdf.open(f)
    except Exception as e:
        print('  OPEN FAIL', e); continue
    info = {str(k): str(v)[:100] for k, v in pdf.docinfo.items()}
    print('  Info:', info)
    try:
        with pdf.open_metadata() as m:
            xm = {k.split('}')[-1]: str(v)[:80] for k, v in m.items() if not k.endswith(('ModifyDate', 'CreateDate', 'MetadataDate'))}
        print('  XMP:', xm)
    except Exception as e: print('  XMP err', e)
    att = list(pdf.attachments.keys())
    if att: print('  ATTACH:', att)
    links, nimg, nannot = set(), 0, 0
    for p in pdf.pages:
        for a in p.get('/Annots', []) or []:
            nannot += 1
            try:
                uri = a.get('/A', {}).get('/URI')
                if uri: links.add(str(uri)[:80])
            except Exception: pass
        try: nimg += len(p.images)
        except Exception: pass
    print('  pages', len(pdf.pages), 'images', nimg, 'annots', nannot, 'links', sorted(links)[:5])
    try:
        r = PdfReader(f)
        txt = ' '.join((r.pages[i].extract_text() or '') for i in range(min(3, len(r.pages))))
        txt = re.sub(r'\s+', ' ', txt)
        print('  emails:', sorted(set(EMAIL.findall(txt)))[:6], 'urls:', sorted(set(URL.findall(txt)))[:6])
        print('  TEXT:', txt[:450])
    except Exception as e: print('  text err', e)
