"""Download a spread of small samples per extension. Usage: sample.py manifest outdir ext1,ext2 n maxbytes [seed]"""
import sys, os, random, urllib.request, urllib.parse, hashlib, collections
man, out, exts, n, maxb = sys.argv[1], sys.argv[2], sys.argv[3].split(','), int(sys.argv[4]), int(sys.argv[5])
seed = int(sys.argv[6]) if len(sys.argv) > 6 else 1
BASE = "https://machina-deid-v1-challenge.s3.us-west-2.amazonaws.com/releases/v1/corpus/"
rows = [l.rstrip('\n').split('\t') for l in open(man)]
rnd = random.Random(seed)
idx = open(os.path.join(out, 'index.tsv'), 'a')
for ext in exts:
    cands = [r for r in rows if r[0].lower().endswith(ext) and 0 < int(r[1]) <= maxb]
    groups = collections.defaultdict(list)
    for r in cands:
        p = r[0].split('/'); groups['/'.join(p[:3])].append(r)
    keys = list(groups); rnd.shuffle(keys)
    picked = []
    # prefer spread across sources: round-robin over source top dirs
    bysrc = collections.defaultdict(list)
    for g in keys: bysrc[g.split('/')[1] if g.startswith('sources') else 'archives'].append(g)
    order = []
    while any(bysrc.values()):
        for s in list(bysrc):
            if bysrc[s]: order.append(bysrc[s].pop())
    for g in order[:n]:
        picked.append(rnd.choice(groups[g]))
    d = os.path.join(out, ext.strip('.').replace('/', '_')); os.makedirs(d, exist_ok=True)
    for k, s, e in picked:
        fn = hashlib.md5(k.encode()).hexdigest()[:10] + '_' + os.path.basename(k)[-60:]
        dest = os.path.join(d, fn)
        if not os.path.exists(dest):
            try:
                urllib.request.urlretrieve(BASE + urllib.parse.quote(k), dest)
            except Exception as ex:
                print('FAIL', k, ex); continue
        idx.write(f"{dest}\t{k}\t{s}\n"); print(ext, s, k)
