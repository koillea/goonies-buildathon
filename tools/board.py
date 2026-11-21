#!/usr/bin/env python3
"""Print the current standings for buildathon tracks from the public leaderboard.

Usage: python3 tools/board.py [track ...]    (default: shopping-sessions machina-deid)

The pages are server-rendered HTML; this strips tags and prints the standings
region (from the "Baseline" / rank rows) so changes are easy to diff between runs.
"""
import html
import re
import sys
import urllib.request

BASE = "https://www.joinbuilders.org/buildathon"


def text_lines(url):
    raw = urllib.request.urlopen(url, timeout=30).read().decode("utf-8", "replace")
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    raw = html.unescape(re.sub(r"<[^>]+>", "\n", raw))
    return [l.strip() for l in raw.splitlines() if l.strip()]


def standings(lines):
    """Lines from the first standings marker to the end of the table-ish block."""
    for i, l in enumerate(lines):
        if re.search(r"(?i)no scores yet|^rank$|^#$|^team$|baseline row|^1$", l):
            return lines[i:i + 120]
    return []


def main():
    tracks = sys.argv[1:] or ["shopping-sessions", "machina-deid"]
    board = text_lines(f"{BASE}/leaderboard")
    for t in tracks:
        print(f"===== {t}")
        page = text_lines(f"{BASE}/tracks/{t}")
        s = standings(page)
        print(" | ".join(s) if s else "(no standings block found on track page)")
    print("===== leaderboard page")
    s = standings(board)
    print(" | ".join(s[:200]) if s else "(no standings block found)")


if __name__ == "__main__":
    main()
