#!/usr/bin/env bash
# Append a Shopping Sessions standings snapshot every 10 minutes. Log: /home/user/board.log
cd /home/user/goonies-buildathon
while true; do
  python3 -I - >> /home/user/board.log 2>&1 <<'PY'
import sys, re, time; sys.path.insert(0, "tools")
import board
try:
    L = board.text_lines(board.BASE + "/tracks/shopping-sessions")
    i = next(i for i, l in enumerate(L) if l.startswith("Shopping Sessions") and L[i+1].startswith("by "))
    blk = L[i:i+600]; end = next((j for j, l in enumerate(blk) if l in ("See all", "Rules", "Chat")), len(blk)); blk = blk[:end]
    rows = sorted(((blk[j+1], float(re.match(r"[\d.]+", blk[j+2]).group())) for j in range(3, len(blk)-2) if re.fullmatch(r"\d{2,3}", blk[j])), key=lambda r: r[1])
    ours = [(k+1, t) for k, (n, t) in enumerate(rows) if re.search(r"(?i)goonies", n)]
    print(time.strftime("%H:%M UTC", time.gmtime()), "|", blk[1].split("·")[-1].strip(), "|", " ".join(f"{n[:12]} {t}" for n, t in rows[:6]), "| us:", ours or "not in shown rows")
except Exception as e:
    print(time.strftime("%H:%M UTC", time.gmtime()), "board fetch failed:", e)
PY
  sleep 600
done
