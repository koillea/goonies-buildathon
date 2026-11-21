"""Score every approach on dev and on a holdout that stands in for the hidden set.

Prints a table, marks the best-by-holdout, and WARNS when dev and holdout disagree —
the single most important signal that a change will not generalize to the hidden set.
Writes RESULTS.md. Deterministic: same code + same data => same numbers.

    python3 run.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import load_cases, score, split  # noqa: E402
from solutions import SOLUTIONS  # noqa: E402

# Dev minus holdout above this means "looks good locally, will likely drop on the board".
GAP_WARN = 0.03


def noise_band(n: int) -> float:
    """~95% sampling noise for a [0,1] mean-of-cases metric on n cases (1/sqrt(n)).

    Two versions closer than this on holdout are a tie, not an improvement — do not spend
    a scarce submission on the difference. Grow the holdout if the band is too wide.
    """
    return 1 / n ** 0.5 if n else 1.0


def main():
    cases = load_cases()
    dev, holdout = split(cases)
    rows = []
    for name, fn in SOLUTIONS:
        try:
            d, h = score(fn, dev), score(fn, holdout)
            rows.append((name, d, h, None))
        except Exception as e:  # a crashing version must not hide the others
            rows.append((name, None, None, f"{type(e).__name__}: {e}"))

    scored = [r for r in rows if r[2] is not None]
    best = max(scored, key=lambda r: r[2]) if scored else None
    noise = noise_band(len(holdout))
    warn_at = max(GAP_WARN, noise)

    out = ["# Results", "",
           f"{len(dev)} dev cases, {len(holdout)} holdout cases. "
           "Holdout stands in for the hidden set; pick submissions by HOLDOUT.",
           f"Noise band ±{noise:.3f}: holdout differences smaller than this are ties.", "",
           "| Approach | Dev | Holdout | Gap | Note |", "|---|---|---|---|---|"]
    for name, d, h, err in rows:
        if err:
            out.append(f"| {name} | - | - | - | CRASH {err} |")
            continue
        gap = d - h
        note = []
        if best and name == best[0]:
            note.append("**BEST**")
        elif best and best[2] - h < noise:
            note.append("tie with best (within noise)")
        if gap > warn_at:
            note.append(f"overfit? dev>holdout by {gap:.3f}")
        out.append(f"| {name} | {d:.4f} | {h:.4f} | {gap:+.4f} | {' '.join(note)} |")

    if best:
        out += ["", f"Submit candidate: **{best[0]}** (holdout {best[2]:.4f})."]
    text = "\n".join(out) + "\n"
    print(text)
    # One machine-readable line per run, so agents quote numbers instead of paraphrasing.
    if best:
        print(f"SCORE={best[2]:.4f} SPLIT=holdout N={len(holdout)} NOISE={noise:.4f} BEST={best[0]!r}")
    else:
        print(f"SCORE=none SPLIT=holdout N={len(holdout)} (every version crashed)")
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "RESULTS.md"), "w") as f:
        f.write(text)


if __name__ == "__main__":
    main()
