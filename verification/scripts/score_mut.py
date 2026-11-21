import json, sys, glob, os
tests=json.load(open('/tmp/claude-0/kits/br/sample/tests.json'))['tests']
num={t['id']:t['number'] for t in tests}; byfile={}
for t in tests: byfile.setdefault(t['file'],set()).add(t['number'])
sel={}
for l in open(sys.argv[1]):
    d=json.loads(l); sel[d['commit']]=set(x for w in d['workers'] for x in w)
for f in sorted(glob.glob('/tmp/claude-0/mutout/*.fail')):
    c=os.path.basename(f)[:-5]
    if c not in sel: continue
    fail=set()
    for i in open(f).read().split():
        if i in num: fail.add(num[i])
        elif i in byfile: fail|=byfile[i]          # file could not be imported
        elif '::' in i and i.split('::')[0] in byfile:
            fail|={num[k] for k in num if k.startswith(i+'::')} or set()
    miss=fail-sel[c]
    print(f"{c:10s} failing={len(fail):4d} selected={len(sel[c]):4d} missed={len(miss):4d} {'MISS' if miss else 'ok'}")
