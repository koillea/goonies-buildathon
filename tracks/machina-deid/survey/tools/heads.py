"""Fetch first N bytes of random files per extension via HTTP Range. Usage: heads.py manifest outdir ext1,ext2 per_ext nbytes"""
import sys, os, random, urllib.request, urllib.parse, hashlib, collections
man, out, exts, per, nb = sys.argv[1], sys.argv[2], sys.argv[3].split(','), int(sys.argv[4]), int(sys.argv[5])
BASE = "https://machina-deid-v1-challenge.s3.us-west-2.amazonaws.com/releases/v1/corpus/"
rows = [l.rstrip('\n').split('\t') for l in open(man)]
rnd = random.Random(7)
os.makedirs(out, exist_ok=True)
idx = open(os.path.join(out, 'index.tsv'), 'a')
for ext in exts:
    c = [r for r in rows if r[0].lower().endswith(ext) and int(r[1]) > 0]
    by = collections.defaultdict(list)
    for r in c: by[r[0].split('/')[2]].append(r)
    gs = list(by); rnd.shuffle(gs)
    for g in gs[:per]:
        k, s, e = rnd.choice(by[g])
        dest = os.path.join(out, ext.strip('.') + '_' + hashlib.md5(k.encode()).hexdigest()[:8] + '.head')
        req = urllib.request.Request(BASE + urllib.parse.quote(k), headers={'Range': 'bytes=0-%d' % (nb - 1)})
        try: open(dest, 'wb').write(urllib.request.urlopen(req, timeout=60).read())
        except Exception as ex: print('FAIL', k, ex); continue
        idx.write(f'{dest}\t{k}\t{s}\n')
