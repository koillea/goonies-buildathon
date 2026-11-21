#!/usr/bin/env bash
# Differential test: fast pipeline vs oracle on generated seeds.
# Usage: tools/difftest.sh EVENTS SEED...
set -u
cd "$(dirname "$0")/.."
EV=$1; shift
CMP=kit/starter-duckdb/starter-duckdb/scripts
fail=0
for s in "$@"; do
  d=data/s$s-$EV; rm -rf $d out/o-$s out/f-$s
  generate --seed $s --events $EV --clicks $((EV/4)) --output $d >/dev/null 2>&1
  python3 oracle/reference.py $d out/o-$s >/dev/null
  fast/target/release/sessions $d out/f-$s 2>/dev/null
  r=$(cd $CMP && python3 compare.py ../../../../out/f-$s ../../../../out/o-$s | tail -1)
  echo "seed $s: $r"; [ "$r" = MATCH ] || fail=1
  [ "$r" = MATCH ] && rm -rf $d out/o-$s out/f-$s
done
exit $fail
