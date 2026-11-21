import json, os, subprocess, sys
K = [1, 5, 10, 30]
S = "/tmp/claude-0/kits/br/sample"
ans = json.load(open(S + "/answers.json"))["commits"]
base = json.load(open(S + "/tests.json"))
SEL = "/home/user/koillea/rwx-blast-radius-v1/selector.py"
STARTER = open("/tmp/claude-0/kits/br/selector.py").read()

def split(nums, dur):
    order = sorted(nums, key=lambda n: dur[n], reverse=True); best = None
    for k in range(1, 9):
        loads = [0]*k; ws = [[] for _ in range(k)]
        for n in order:
            i = loads.index(min(loads)); ws[i].append(n); loads[i] += dur[n]
        c = max(loads) + 2000*sum(1 for w in ws if w)
        if best is None or c < best[0]: best = (c, [w for w in ws if w])
    return best[1] if nums else []

def score(d, out):
    r = subprocess.run(["python3", "-I", "/tmp/claude-0/kits/br/score.py", d, S + "/answers.json", out], capture_output=True, text=True).stdout
    sim = [l for l in r.splitlines() if l.startswith("Simulated")][0].split()[1]
    miss = [l for l in r.splitlines() if l.startswith("Misses")][0].split()[1]
    return float(sim), int(miss)

print(f"{'x':>3} {'run-all total s':>15} {'starter':>9} {'v9':>9} {'v9 miss':>7} {'oracle':>8} {'v9/oracle':>9} {'v9 fallbacks':>12}")
for k in K:
    d = f"/tmp/claude-0/scale/x{k}"; os.makedirs(d, exist_ok=True)
    if not os.path.exists(d + "/commits"): os.symlink(S + "/commits", d + "/commits")
    t = json.loads(json.dumps(base))
    for x in t["tests"]: x["seconds"] = round(x["seconds"] * k, 3)
    json.dump(t, open(d + "/tests.json", "w"))
    dur = {x["number"]: round(x["seconds"]*1000) for x in t["tests"]}
    # v9
    env = dict(os.environ, DATA_DIR=d)
    out = subprocess.run(["python3", "-I", SEL], env=env, capture_output=True, text=True).stdout
    open(d + "/v9.jsonl", "w").write(out)
    nall = sum(1 for l in out.splitlines() if sum(len(w) for w in json.loads(l)["workers"]) == len(dur))
    # starter (official code, /data swapped)
    st = subprocess.run(["python3", "-I", "-c", STARTER.replace('Path("/data")', f'Path("{d}")')], capture_output=True, text=True).stdout
    open(d + "/starter.jsonl", "w").write(st)
    # oracle
    with open(d + "/oracle.jsonl", "w") as fh:
        for c, v in ans.items(): fh.write(json.dumps({"commit": c, "workers": split(v["failing"], dur)}) + "\n")
    a = score(d, d + "/v9.jsonl"); b = score(d, d + "/starter.jsonl"); o = score(d, d + "/oracle.jsonl")
    print(f"{k:>3} {sum(dur.values())/1000:>15.1f} {b[0]:>9.1f} {a[0]:>9.1f} {a[1]:>7} {o[0]:>8.1f} {a[0]/o[0]:>9.2f} {nall:>12}")
