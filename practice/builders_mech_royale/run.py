"""Score every bot over many seeded matches against two opponent fields."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from bench import evaluate  # noqa: E402
import solutions as S  # noqa: E402

DEV, HIDDEN, N = 1, 9001, 300


def main():
    strong_field = [S.b_aggro, S.b_camper, S.v2_zone_focus, S.v3_survivor, S.v4_lookahead]
    out = ["# Builders Mech Royale (practice) - results", "",
           f"{N} matches per cell, 6 mechs a match. Points: 10/6/4/2/1/0 by placement, +1 per kill. The real game rules are unknown.", "",
           "## Against the baseline field (random, chaser, camper)", "",
           "| Bot | Dev points | Hidden points | Hidden win rate | Hidden top-2 |", "|---|---|---|---|---|"]
    for name, bot in S.ALL:
        d, _, _ = evaluate(bot, S.FIELD, N, DEV)
        h, w, t2 = evaluate(bot, S.FIELD, N, HIDDEN)
        out.append(f"| {name} | {d:.2f} | {h:.2f} | {w:.0%} | {t2:.0%} |")
    out += ["", "## Against a strong field (the better bots, including copies of itself)", "",
            "| Bot | Hidden points | Hidden win rate | Hidden top-2 |", "|---|---|---|---|"]
    for name, bot in S.ALL:
        h, w, t2 = evaluate(bot, strong_field, N, HIDDEN)
        out.append(f"| {name} | {h:.2f} | {w:.0%} | {t2:.0%} |")
    text = "\n".join(out) + "\n"
    print(text)
    with open(os.path.join(os.path.dirname(__file__), "RESULTS.md"), "w") as f:
        f.write(text)


if __name__ == "__main__":
    main()
