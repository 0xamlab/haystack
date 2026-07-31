#!/usr/bin/env python3
"""Reconcile pit stops across the three available sources and derive the inclusion rule.

Three sources disagreed on how many stops occurred in the Hungary 2026 race -- official PitStop 33,
OpenF1 /pit 44, Jolpica /pitstops 45 -- and that blocked fitting pit_loss, because fitting sigma_pit on
the official subset is only unbiased if the missing stops are missing at random. If the official feed
omits precisely the anomalous stops (drive-throughs, retirements in the pit lane, stops without a tyre
change) then the fitted slow-stop tail is truncated exactly where the model needs it, and the plan
optimizer systematically under-prices a stop.

So match per (car, lap) and classify every non-match rather than guessing.

Usage:
    python3 scripts/timing/reconcile_pitstops.py --dir <session> --session-key 11342 --round 11
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq

UA = "algenta-timing-ingest/0.1 (+research)"


def _get(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8-sig"))


def strip_bom(b: bytes) -> bytes:
    return b[3:] if b[:3] == b"\xef\xbb\xbf" else b


def official_stops(d: Path) -> list[dict]:
    """Every PitStop stream record, deduplicated on (car, lap)."""
    out: dict[tuple[int, int], dict] = {}
    ts = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d{3})(.*)$", re.S)
    p = d / "PitStop.jsonStream"
    if p.exists():
        for line in strip_bom(p.read_bytes()).decode("utf-8", "replace").split("\r\n"):
            m = ts.match(line) if line.strip() else None
            if not m:
                continue
            try:
                j = json.loads(m.group(2))
            except Exception:
                continue
            car = int(j.get("RacingNumber") or 0)
            lap = int(j.get("Lap") or 0)
            out[(car, lap)] = {
                "car": car, "lap": lap,
                "stationary": float(j.get("PitStopTime") or 0) or None,
                "pit_lane": float(j.get("PitLaneTime") or 0) or None,
            }
    return sorted(out.values(), key=lambda r: (r["car"], r["lap"]))


def lane_entries(d: Path) -> list[dict]:
    """PitLaneTimeCollection: every pit-lane ENTRY, including ones PitStop never reports."""
    out: dict[tuple[int, int], dict] = {}
    ts = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d{3})(.*)$", re.S)
    p = d / "PitLaneTimeCollection.jsonStream"
    if p.exists():
        for line in strip_bom(p.read_bytes()).decode("utf-8", "replace").split("\r\n"):
            m = ts.match(line) if line.strip() else None
            if not m:
                continue
            try:
                j = json.loads(m.group(2))
            except Exception:
                continue
            for car_s, v in (j.get("PitTimes") or {}).items():
                if car_s == "_deleted" or not isinstance(v, dict):
                    continue
                car = int(v.get("RacingNumber") or car_s or 0)
                lap = int(v.get("Lap") or 0)
                out[(car, lap)] = {"car": car, "lap": lap,
                                   "duration": float(v.get("Duration") or 0) or None}
    return sorted(out.values(), key=lambda r: (r["car"], r["lap"]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--session-key", type=int, required=True)
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--round", type=int, required=True)
    args = ap.parse_args()
    d = Path(args.dir).expanduser()

    off = official_stops(d)
    lane = lane_entries(d)
    of1 = _get(f"https://api.openf1.org/v1/pit?session_key={args.session_key}")
    jol_raw = _get(f"https://api.jolpi.ca/ergast/f1/{args.year}/{args.round}/pitstops/?limit=100")
    races = jol_raw["MRData"]["RaceTable"]["Races"]
    jol = races[0]["PitStops"] if races else []

    off_k = {(r["car"], r["lap"]) for r in off}
    lane_k = {(r["car"], r["lap"]) for r in lane}
    of1_k = {(int(r["driver_number"]), int(r["lap_number"])) for r in of1}
    jol_k = {(int(r["driverId"] if str(r.get("driverId", "")).isdigit() else 0),
              int(r["lap"])) for r in jol}
    # Jolpica keys drivers by id string, not number; map via number where present
    jol_by_lap: dict[int, int] = defaultdict(int)
    for r in jol:
        jol_by_lap[int(r["lap"])] += 1

    print(f"counts   official PitStop {len(off_k)}   PitLaneTimeCollection {len(lane_k)}   "
          f"OpenF1 /pit {len(of1_k)}   Jolpica {len(jol)}")

    # retirements, needed to classify the non-matches
    laps = pq.read_table(d / "_laps.parquet").to_pydict()
    rows = [dict(zip(laps.keys(), v)) for v in zip(*laps.values())]
    last_lap = defaultdict(int)
    retired = set()
    for r in rows:
        last_lap[r["car_number"]] = max(last_lap[r["car_number"]], r["lap_number"])
        if r["retired"]:
            retired.add(r["car_number"])
    leader_laps = max(last_lap.values()) if last_lap else 0

    print("\nOpenF1 stops the official PitStop feed does NOT report:")
    extra = sorted(of1_k - off_k)
    for car, lap in extra:
        rec = next((r for r in of1 if int(r["driver_number"]) == car
                    and int(r["lap_number"]) == lap), {})
        in_lane = (car, lap) in lane_k
        tags = []
        if car in retired and lap >= last_lap[car] - 1:
            tags.append("RETIRED here")
        if lap >= leader_laps - 1:
            tags.append("final lap")
        if in_lane:
            tags.append("in PitLaneTimeCollection")
        sd = rec.get("stop_duration")
        ld = rec.get("lane_duration") or rec.get("pit_duration")
        print(f"  car {car:>3} lap {lap:>3}  stop={sd}  lane={ld}  "
              f"{'  '.join(tags) if tags else 'no obvious cause'}")

    print("\nofficial stops OpenF1 does not report:")
    for car, lap in sorted(off_k - of1_k):
        print(f"  car {car:>3} lap {lap:>3}")

    # the decisive question: is the official subset biased on stationary time?
    matched = [r for r in off if (r["car"], r["lap"]) in of1_k and r["stationary"]]
    of1_stat = [float(r["stop_duration"]) for r in of1
                if r.get("stop_duration") not in (None, "")]
    off_stat = [r["stationary"] for r in off if r["stationary"]]
    extra_stat = [float(next((r["stop_duration"] for r in of1
                             if int(r["driver_number"]) == c and int(r["lap_number"]) == l
                             and r.get("stop_duration") not in (None, "")), 0) or 0)
                  for c, l in extra]
    extra_stat = [x for x in extra_stat if x > 0]

    def stats(xs: list[float], label: str) -> None:
        if not xs:
            print(f"  {label:<34} (none)")
            return
        s = sorted(xs)
        print(f"  {label:<34} n={len(s):>3}  min {s[0]:5.2f}  median {s[len(s)//2]:5.2f}  "
              f"max {s[-1]:5.2f}  mean {sum(s)/len(s):5.2f}")

    print("\nstationary-time distributions — the bias question:")
    stats(off_stat, "official PitStop")
    stats(of1_stat, "OpenF1 all")
    stats(extra_stat, "OpenF1 stops official omits")
    stats([r["stationary"] for r in matched], "matched pairs (official side)")

    print("\nverdict:")
    if extra_stat and off_stat:
        em = sum(extra_stat) / len(extra_stat)
        om = sum(off_stat) / len(off_stat)
        if em > om * 1.25:
            print("  The omitted stops are SLOWER on average. Fitting sigma_pit on the official")
            print("  subset would truncate the slow-stop tail and under-price a stop.")
            print("  -> fit on the UNION, provenance-tagged.")
        elif em < om * 0.8:
            print("  The omitted stops are FASTER on average (drive-throughs / no tyre change).")
            print("  Fitting stationary time on the official subset is defensible; the omitted")
            print("  records are not tyre-change stops and should be excluded from sigma_pit.")
        else:
            print("  No material difference in stationary time between the two sets, so the")
            print("  official subset is not biased on the quantity sigma_pit is fitted from.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
