#!/usr/bin/env bash
# Interleaved A/B timing on the 20M set: alternate binaries, report each one's best. Usage: tools/ab.sh A B [ROUNDS]
cd "$(dirname "$0")/.."
A=$1; B=$2; R=${3:-6}
export GLIBC_TUNABLES=glibc.malloc.hugetlb=1:glibc.malloc.mmap_threshold=33554432:glibc.malloc.trim_threshold=17179869184
ba=99; bb=99
t() { rm -rf out/ab; "$1" data/p20m out/ab 2>&1 | grep -oE '[0-9.]+s written' | grep -oE '[0-9.]+'; }
for i in $(seq $R); do
  x=$(t $A); y=$(t $B)
  ba=$(echo "if ($x < $ba) $x else $ba" | bc); bb=$(echo "if ($y < $bb) $y else $bb" | bc)
done
echo "A best $ba | B best $bb"
