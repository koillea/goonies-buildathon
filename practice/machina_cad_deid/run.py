"""Score every approach on dev and held-out hidden STEP files."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from bench import dataset, score  # noqa: E402
from solutions import ALL  # noqa: E402

DEV, HIDDEN, N = 1, 9001, 100


def retained(deid, cases) -> float:
    """Share of harmless labels ('datum A') that survive: a proxy for kept usefulness."""
    kept = total = 0
    for text, _ in cases:
        total += text.count("'datum ")
        kept += deid(text).count("'datum ")
    return kept / total if total else 1.0


def main():
    dev, hid = dataset(N, DEV), dataset(N, HIDDEN)
    out = ["# Machina CAD De-ID (practice) - results", "",
           f"{N} dev and {N} hidden synthetic STEP files. A file passes only with zero leaked identifiers, unchanged geometry, a valid file, and required strings kept. The real task format is unknown.", "",
           "| Approach | Dev pass | Hidden pass | Hidden leak | Hidden broken | Hidden lost needed data | Harmless labels kept |", "|---|---|---|---|---|---|---|"]
    for name, fn in ALL:
        d, h = score(fn, dev), score(fn, hid)
        out.append(f"| {name} | {d['pass']:.0%} | {h['pass']:.0%} | {h['leak']:.0%} | {h['broken']:.0%} | {h['lost']:.0%} | {retained(fn, hid):.0%} |")
    text = "\n".join(out) + "\n"
    print(text)
    with open(os.path.join(os.path.dirname(__file__), "RESULTS.md"), "w") as f:
        f.write(text)


if __name__ == "__main__":
    main()
