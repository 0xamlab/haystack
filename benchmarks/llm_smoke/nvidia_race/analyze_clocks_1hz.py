#!/usr/bin/env python3
"""analyze_clocks_1hz.py — turn the FRONT-3 1 Hz clock/power capture into throttle windows.

The campaign's integrity rule is that the pinned clock is verified DURING the timed regions, not
only bracketing them. This is the tool that makes that checkable: it reports every contiguous
window below the pinned clock, its depth, the peak power that caused it, and which compute
process was resident — so a contested comparison can be shown to have run at the pin (or the
report has to say it did not).

What it found on the FRONT-3 capture (~/trtllm/front3/clocks_1hz.csv, 1730 samples over
01:26:23-01:57:01 UTC): 28 samples (1.6%) below 1410 MHz, min 1320 MHz, peak 424.2 W against a
400 W limit, max 62 C, in 15 windows confined to the SUSTAINED phases (the _d1 RAG-4096 run and
the _d8 nsys capture). The contested TensorRT-LLM re-race window was 0.0% below 1410 MHz, so
power throttling cannot explain the pp1024 flip in either direction.

usage: analyze_clocks_1hz.py [clocks_1hz.csv]
"""

import collections
import csv
import sys

PINNED = 1410


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "/home/angel/trtllm/front3/clocks_1hz.csv"
    with open(path) as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        print(f"no samples in {path}")
        return 1
    cl = [int(r["clocks_sm_mhz"]) for r in rows]
    pw = [float(r["power_w"]) for r in rows]
    below = [r for r in rows if int(r["clocks_sm_mhz"]) < PINNED]
    print(f"total 1Hz samples: {len(rows)}  span {rows[0]['ts_utc']} .. {rows[-1]['ts_utc']}")
    print(f"samples below {PINNED} MHz: {len(below)} ({100.0 * len(below) / len(rows):.1f}%)")
    print(
        f"min clock {min(cl)} MHz | max power {max(pw):.1f} W (limit {rows[0]['power_limit_w']} W)"
        f" | max temp {max(int(r['temp_c']) for r in rows)} C"
    )

    win: list = []
    cur = None
    for r in rows:
        c = int(r["clocks_sm_mhz"])
        if c < PINNED:
            if cur is None:
                cur = [r, r, 1, c, float(r["power_w"])]
            else:
                cur[1] = r
                cur[2] += 1
                cur[3] = min(cur[3], c)
                cur[4] = max(cur[4], float(r["power_w"]))
        elif cur:
            win.append(cur)
            cur = None
    if cur:
        win.append(cur)

    print(f"\n{len(win)} contiguous throttle window(s):")
    for a, b, n, mn, mxw in win:
        print(
            f"  {a['ts_utc'][11:]} .. {b['ts_utc'][11:]}  {n:>4}s  min {mn} MHz  "
            f"peak {mxw:.0f} W  apps={a['compute_apps'][:20]}"
        )

    per: dict = collections.defaultdict(lambda: [0, 0, 0.0, ""])
    for r in rows:
        k = r["ts_utc"][11:16]
        per[k][1] += 1
        per[k][2] = max(per[k][2], float(r["power_w"]))
        per[k][3] = r["compute_apps"][:14]
        if int(r["clocks_sm_mhz"]) < PINNED:
            per[k][0] += 1
    print(f"\nper-minute throttle duty (below {PINNED} MHz):")
    for k in sorted(per):
        b, t, mxw, apps = per[k]
        print(f"  {k}  {100.0 * b / t:5.1f}% ({b}/{t})  peak {mxw:.0f} W  apps={apps}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
