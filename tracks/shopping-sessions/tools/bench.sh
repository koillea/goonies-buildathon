#!/usr/bin/env bash
# Time a pipeline binary on the 20M set with the CAD job paused. Usage: tools/bench.sh BIN [RUNS]
cd "$(dirname "$0")/.."
BIN=${1:-fast/target/release/sessions}; RUNS=${2:-3}
PIDS=$(pgrep -f "cad-de-id/run.py|run_shards.sh" | tr '\n' ' ')
[ -n "$PIDS" ] && kill -STOP $PIDS
sleep 1
for i in $(seq $RUNS); do rm -rf out/p20m; "$BIN" data/p20m out/p20m 2>&1 | tr '\n' ' ' | sed 's/  */ /g'; echo; done
[ -n "$PIDS" ] && kill -CONT $PIDS
