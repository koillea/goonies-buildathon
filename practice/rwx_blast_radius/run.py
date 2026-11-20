"""Score every approach on a dev set and a held-out "hidden" set (different seed)."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from bench import dataset, score_culprit, score_impact  # noqa: E402
from solutions import CULPRIT, IMPACT  # noqa: E402

DEV, HIDDEN, N = 1, 9001, 100


def main():
    out = ["# RWX Blast Radius (practice) - results", "",
           f"{N} dev cases (seed {DEV}) and {N} hidden cases (seed {HIDDEN}). Synthetic data; the real task format is unknown.", "",
           "## Task A: find the commit that broke the build (accuracy)", "",
           "| Approach | Dev | Hidden |", "|---|---|---|"]
    dev, hid = dataset("culprit", N, DEV), dataset("culprit", N, HIDDEN)
    for name, fn in CULPRIT:
        out.append(f"| {name} | {score_culprit(fn, dev):.0%} | {score_culprit(fn, hid):.0%} |")
    out += ["", "## Task B: which tests must re-run for a change (mean F1 / exact match)", "",
            "| Approach | Dev F1 | Hidden F1 | Hidden exact |", "|---|---|---|---|"]
    dev, hid = dataset("impact", N, DEV), dataset("impact", N, HIDDEN)
    for name, fn in IMPACT:
        d, _ = score_impact(fn, dev)
        h, ex = score_impact(fn, hid)
        out.append(f"| {name} | {d:.3f} | {h:.3f} | {ex:.0%} |")
    text = "\n".join(out) + "\n"
    print(text)
    with open(os.path.join(os.path.dirname(__file__), "RESULTS.md"), "w") as f:
        f.write(text)


if __name__ == "__main__":
    main()
