"""Ground truth: apply patch to a fresh copy of pinned sqlglot, run full pytest in the labeling image,
return failing test ids. usage: gt.py <patch> <outprefix>"""
import subprocess, sys, os, re, shutil, tempfile, json
patch, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
w = tempfile.mkdtemp(dir="/tmp/claude-0/work")
subprocess.run(f"cd /tmp/claude-0/gt/sqlglot && git archive HEAD | tar -x -C {w}", shell=True, check=True)
if os.path.getsize(patch):
    r = subprocess.run(["git", "apply", "--unsafe-paths", "--directory=.", patch], cwd=w, capture_output=True, text=True)
    if r.returncode:
        open(out + ".fail", "w").write("APPLYFAIL " + r.stderr); sys.exit(0)
os.system(f"chmod -R a+rwX {w}")
r = subprocess.run(["docker", "run", "--rm", "--network", "none", "--cpus", "1", "-v", f"{w}:/sqlglot", "br-gt",
    "python", "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider", "-rfE", "--timeout=120", "--continue-on-collection-errors"],
    capture_output=True, text=True)
log = r.stdout + r.stderr
open(out + ".log", "w").write(log)
summ = log.split("short test summary info", 1)[1] if "short test summary info" in log else ""
ids = sorted(set(re.findall(r"(tests/\S+?\.py(?:::[^\s\[]+)*)", summ)))
open(out + ".fail", "w").write("\n".join(ids) + "\n")
shutil.rmtree(w, ignore_errors=True)
print(os.path.basename(out), len(ids), log.strip().splitlines()[-1][:120])
