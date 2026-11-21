#!/usr/bin/env bash
# Best-of-N timing on the 20M set (CAD job paused if running). Usage: tools/bench.sh [BIN] [RUNS]
cd "$(dirname "$0")/.."
BIN=${1:-fast/target/release/sessions}; RUNS=${2:-5}
export GLIBC_TUNABLES=glibc.malloc.hugetlb=1
best=999; bestline=""
for i in $(seq $RUNS); do
  rm -rf out/p20m
  line=$("$BIN" data/p20m out/p20m 2>&1 | tr '\n' ' ' | sed 's/  */ /g')
  t=$(echo "$line" | grep -oE '[0-9.]+s written' | grep -oE '[0-9.]+')
  if (( $(echo "$t < $best" | bc) )); then best=$t; bestline=$line; fi
done
echo "BEST $best s | $bestline"
