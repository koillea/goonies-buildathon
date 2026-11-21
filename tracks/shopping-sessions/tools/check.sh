#!/usr/bin/env bash
# Full correctness gate for fast/target/release/sessions: fixtures, dev answer, oracle on seeds.
cd "$(dirname "$0")/.."
BIN=$PWD/fast/target/release/sessions; K=kit/starter-duckdb/starter-duckdb
f=$(cd $K && python3 scripts/run_fixtures.py fixtures -- $BIN 2>&1 | tail -1)
rm -rf out/chk-dev; $BIN data/dev out/chk-dev 2>/dev/null
d=$(cd $K/scripts && python3 compare.py ../../../../out/chk-dev ../../../dev-answer/dev-answer | tail -1)
s=$(tools/difftest.sh 300000 41 42 43 44 | tr '\n' ' ')
echo "fixtures: $f | dev: $d | oracle: $s"
[[ "$f" == "36/36 fixtures passed" && "$d" == MATCH && "$s" != *DIFFER* ]] && echo GATE PASS || { echo GATE FAIL; exit 1; }
