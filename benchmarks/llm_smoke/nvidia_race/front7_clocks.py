#!/usr/bin/env python3
"""front7_clocks.py -- per-cell zero-drift attribution at 200 ms resolution (FRONT 7).

WHY THIS EXISTS. FRONT 6 disclosed a ZERO-DRIFT BREACH it could not resolve: 203/4814 off-pin
samples in stage 1 (4.22%), min 1230 MHz, "inside 14 cell windows", attributed to the 400 W power
cap against draws to 532.9 W. Its sampler ran at 1 Hz. A RAG-4096 cell is 20 x 267 ms = 5.3 s of
GPU work, so a 1 Hz sampler puts ~5 samples in a cell and cannot say how much of the cell was
throttled, only that some sample near it was. That is why FRONT 6 had to bound the breach with an
argument (interleaved arms, a baseline reproducing to 0.044% across three prompts) instead of a
measurement.

FRONT 7 samples clocks.sm, power.draw, temperature and utilisation every 200 ms for the whole
stage, and run_ab_7b_front7.sh prints `CELL_WINDOW <arm><tag> <t0> <t1>` in epoch seconds around
every cell. This script joins the two, so for each cell it can report:
  * how many samples fall inside it, and how many of those are off the pinned clock;
  * the MINIMUM clock and the fraction of the cell's wall time spent off-pin;
  * mean/median/max power draw and max temperature, i.e. whether the cause is the power cap
    (draw at or above the limit while off-pin) or thermal (temperature at the slowdown point);
  * a per-cell verdict at a threshold the caller sets, so "this cell is clean" and "this cell
    carries X% off-pin time" are both statements about that cell rather than about the stage.

Nothing here is a lever. It is the drift armor the owner's protocol asks for, at a resolution that
can actually bound a claim.

Usage: front7_clocks.py <clocks.csv> <stage.log> [--pin 1410] [--thresh 0.5]
       front7_clocks.py <clocks.csv> <stage.log> --json out.json
"""

from __future__ import annotations

import csv
import json
import re
import statistics
import sys
from datetime import datetime

CELL_RX = re.compile(r"^CELL_WINDOW\s+(\S+)\s+([0-9.]+)\s+([0-9.]+)\s*$")


def parse_ts(s: str) -> float:
    """nvidia-smi's `2026/09/16 21:04:04.123` (local) -> epoch seconds, comparable with the
    `date +%s.%N` the harness prints. Naive parsing assumes local time, which is what nvidia-smi
    writes, so both sides are in the same frame."""
    s = s.strip()
    for fmt in ("%Y/%m/%d %H:%M:%S.%f", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).timestamp()
        except ValueError:
            continue
    raise ValueError(f"unparseable nvidia-smi timestamp: {s!r}")


def num(s: str) -> float:
    m = re.search(r"-?[0-9]+(?:\.[0-9]+)?", s or "")
    return float(m.group(0)) if m else float("nan")


def load_samples(path: str):
    rows = []
    with open(path, newline="") as fh:
        first = fh.readline()
        fh.seek(0)
        # the CSV has a header when --format=csv is used without noheader
        has_header = "timestamp" in first.lower()
        rdr = csv.reader(fh)
        for r in rdr:
            if len(r) < 5:
                continue
            if has_header and "timestamp" in r[0].lower():
                continue
            try:
                t = parse_ts(r[0])
            except ValueError:
                continue
            rows.append({
                "t": t,
                "clock": num(r[1]),
                "power": num(r[2]),
                "temp": num(r[3]),
                "util": num(r[4]),
            })
    rows.sort(key=lambda x: x["t"])
    return rows


def main() -> int:
    argv = sys.argv[1:]
    args, opts = [], {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            key = a[2:]
            if "=" in key:                        # --json=path
                k, v = key.split("=", 1)
                opts[k] = v
            elif i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                opts[key] = argv[i + 1]           # --json path  (the form the harness uses)
                i += 1
            else:
                opts[key] = None                  # a bare flag
        else:
            args.append(a)
        i += 1
    # Both spellings are accepted because the first version of this script parsed ONLY
    # `--key=value`, so the harness's `--json path` silently produced no JSON and the
    # summarizer's clock section dropped out with "clock JSON unreadable" while the printed
    # per-cell table still looked complete. A flag that is silently ignored is worse than one
    # that errors: the missing artifact was the machine-readable one both downstream scripts read.
    if len(args) < 2:
        print(__doc__)
        return 2
    pin = float(opts.get("pin") or 1410.0)
    thresh = float(opts.get("thresh") or 0.5)     # % of a cell's samples off-pin before FLAG
    samples = load_samples(args[0])
    if not samples:
        print(f"NO SAMPLES parsed from {args[0]}")
        return 1
    span = samples[-1]["t"] - samples[0]["t"]
    print(f"== {len(samples)} samples over {span:.1f} s "
          f"({len(samples) / max(span, 1e-9):.2f} per s, interval "
          f"{1000.0 * span / max(len(samples) - 1, 1):.0f} ms), pin = {pin:.0f} MHz")
    off = [s for s in samples if s["clock"] < pin - 0.5]
    print(f"== STAGE: {len(off)} off-pin samples ({100.0 * len(off) / len(samples):.3f}%), "
          f"min clock {min(s['clock'] for s in samples):.0f} MHz, "
          f"max power {max(s['power'] for s in samples):.1f} W, "
          f"max temp {max(s['temp'] for s in samples):.0f} C")

    cells = []
    with open(args[1], errors="replace") as fh:
        for line in fh:
            m = CELL_RX.match(line.strip())
            if m:
                cells.append((m.group(1), float(m.group(2)), float(m.group(3))))
    if not cells:
        print("NO CELL_WINDOW lines in the stage log -- nothing to attribute")
        return 1

    # off-pin time per cell, in ms, using the sample interval as the weight of each sample
    interval = span / max(len(samples) - 1, 1)
    out = []
    print(f"\n{'cell':28s} {'wall_s':>7s} {'n':>4s} {'off':>4s} {'off%':>6s} {'off_ms':>7s} "
          f"{'minMHz':>7s} {'meanW':>7s} {'maxW':>7s} {'maxC':>5s} verdict")
    for name, t0, t1 in cells:
        inside = [s for s in samples if t0 <= s["t"] <= t1]
        if not inside:
            print(f"{name:28s} {t1 - t0:7.1f} {0:4d} {'-':>4s} {'-':>6s} {'-':>7s} "
                  f"{'-':>7s} {'-':>7s} {'-':>7s} {'-':>5s} NO SAMPLES (window shorter than the"
                  f" sample interval?)")
            continue
        offc = [s for s in inside if s["clock"] < pin - 0.5]
        pct = 100.0 * len(offc) / len(inside)
        off_ms = len(offc) * interval * 1000.0
        verdict = "CLEAN" if pct <= thresh else f"OFF-PIN {pct:.2f}% of samples"
        row = {
            "cell": name, "wall_s": t1 - t0, "n_samples": len(inside),
            "off_pin": len(offc), "off_pin_pct": pct, "off_pin_ms": off_ms,
            "min_clock_mhz": min(s["clock"] for s in inside),
            "mean_power_w": statistics.fmean(s["power"] for s in inside),
            "median_power_w": statistics.median(s["power"] for s in inside),
            "max_power_w": max(s["power"] for s in inside),
            "max_temp_c": max(s["temp"] for s in inside),
            "verdict": verdict,
        }
        out.append(row)
        print(f"{name:28s} {row['wall_s']:7.1f} {row['n_samples']:4d} {row['off_pin']:4d} "
              f"{pct:6.2f} {off_ms:7.0f} {row['min_clock_mhz']:7.0f} "
              f"{row['mean_power_w']:7.1f} {row['max_power_w']:7.1f} {row['max_temp_c']:5.0f} "
              f"{verdict}")

    bad = [r for r in out if r["off_pin_pct"] > thresh]
    print(f"\n== {len(bad)} of {len(out)} cells carry off-pin time above {thresh}%")
    if bad:
        worst = max(bad, key=lambda r: r["off_pin_pct"])
        print(f"== worst: {worst['cell']} at {worst['off_pin_pct']:.2f}% of samples "
              f"({worst['off_pin_ms']:.0f} ms) min {worst['min_clock_mhz']:.0f} MHz, "
              f"max draw {worst['max_power_w']:.1f} W, max {worst['max_temp_c']:.0f} C")
        # the attribution the owner's protocol asks for: power cap or thermal?
        at_cap = [r for r in bad if r["max_power_w"] >= 395.0]
        print(f"== {len(at_cap)} of those reach >= 395 W of a 400 W cap -> POWER-CAP throttle, "
              f"not thermal (max temp across them "
              f"{max((r['max_temp_c'] for r in at_cap), default=0):.0f} C)")
    if "json" in opts and opts["json"]:
        with open(opts["json"], "w") as fh:
            json.dump({"pin_mhz": pin, "n_samples": len(samples), "stage_off_pin": len(off),
                       "cells": out}, fh, indent=1)
        print(f"== wrote {opts['json']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
