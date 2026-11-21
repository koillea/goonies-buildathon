#!/usr/bin/env bash
# Differential test: the fast pipeline vs the Python reference on generated seeds.
#
# Needs: `generate` on PATH (the track's generator.zip), `cargo build --release`
# done at the repo root, python3 with pyarrow + polars, and the starter kit's
# scripts/compare.py (set COMPARE=path/to/compare.py; it imports run_fixtures.py
# from its own folder).
#
# Usage: shopping-tools/difftest.sh EVENTS SEED...
set -u
cd "$(dirname "$0")/.."
: "${COMPARE:?set COMPARE to scripts/compare.py from the starter kit}"
EV=$1; shift
W=$(mktemp -d)
fail=0
for s in "$@"; do
  generate --seed "$s" --events "$EV" --clicks $((EV / 4)) --output "$W/d$s" >/dev/null 2>&1
  python3 shopping-tools/reference.py "$W/d$s" "$W/o$s" >/dev/null
  target/release/sessions "$W/d$s" "$W/f$s" 2>/dev/null
  r=$(python3 "$COMPARE" "$W/f$s" "$W/o$s" | tail -1)
  echo "seed $s: $r"
  [ "$r" = MATCH ] || fail=1
done
rm -rf "$W"
exit $fail
