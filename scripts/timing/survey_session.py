#!/usr/bin/env python3
"""Survey a fetched raw session: what is actually in the feeds.

VALIDATION TOOLING ONLY — not the runtime path. The production decode is a Mojo
kernel; this exists to establish what the raw archive contains and to answer open
questions (channel semantics, record counts, coverage) before features depend on it.

Usage:
    python3 scripts/timing/survey_session.py \
        --dir ~/.algenta/f1/raw/2026/2026-07-26_Hungarian_Grand_Prix/2026-07-26_Race
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import zlib
from collections import Counter, defaultdict
from pathlib import Path

TS = re.compile(rb"^(\d{2}:\d{2}:\d{2}\.\d{3})(.*)$", re.S)


def strip_bom(b: bytes) -> bytes:
    return b[3:] if b[:3] == b"\xef\xbb\xbf" else b


def records(path: Path):
    """Yield (timestamp, payload_bytes) for each CRLF-separated stream record."""
    body = strip_bom(path.read_bytes())
    for line in body.split(b"\r\n"):
        if not line.strip():
            continue
        m = TS.match(line)
        if not m:
            continue
        yield m.group(1).decode(), m.group(2)


def inflate(payload: bytes):
    """A .z payload is a quoted base64 string over raw deflate."""
    s = payload.strip()
    if s[:1] == b'"' and s[-1:] == b'"':
        s = s[1:-1]
    return json.loads(zlib.decompress(base64.b64decode(s), -zlib.MAX_WBITS))


def as_json(payload: bytes):
    return json.loads(payload)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    args = ap.parse_args()
    d = Path(args.dir).expanduser()

    def sect(t):
        print(f"\n{'=' * 74}\n{t}\n{'=' * 74}")

    # ---- record counts per feed ------------------------------------------------
    sect("RECORD COUNTS + TIME SPAN PER FEED")
    print(f"{'feed':<26}{'records':>10}{'first':>15}{'last':>15}")
    for f in sorted(d.glob("*.jsonStream")):
        rs = list(records(f))
        if rs:
            print(f"{f.name.replace('.jsonStream',''):<26}{len(rs):>10,}{rs[0][0]:>15}{rs[-1][0]:>15}")
        else:
            print(f"{f.name.replace('.jsonStream',''):<26}{0:>10}")

    # ---- session identity ------------------------------------------------------
    sect("SESSION")
    si = json.loads(strip_bom((d / "SessionInfo.json").read_bytes()))
    m = si.get("Meeting", {})
    print(f"  {m.get('OfficialName')}")
    print(f"  circuit  : {m.get('Circuit', {}).get('ShortName')} | country {m.get('Country', {}).get('Name')}")
    print(f"  session  : {si.get('Name')} ({si.get('Type')}) key={si.get('Key')}")
    print(f"  start    : {si.get('StartDate')}  gmt_offset {si.get('GmtOffset')}")
    print(f"  path     : {si.get('Path')}")

    dl = json.loads(strip_bom((d / "DriverList.json").read_bytes()))
    drivers = {k: v for k, v in dl.items() if k.isdigit()}
    print(f"  drivers  : {len(drivers)}")
    for num, v in sorted(drivers.items(), key=lambda kv: int(kv[0]))[:5]:
        print(f"      #{num:<3} {v.get('Tla')} {v.get('FullName'):<22} {v.get('TeamName')}")
    print(f"      … {len(drivers) - 5} more")

    lc = list(records(d / "LapCount.jsonStream"))
    tot = None
    for _, p in lc:
        try:
            j = as_json(p)
            tot = j.get("TotalLaps", tot)
        except Exception:
            pass
    print(f"  laps     : total={tot}, LapCount updates={len(lc)}")

    # ---- tyre stints -----------------------------------------------------------
    sect("TYRE STINTS (TyreStintSeries keyframe)")
    ts = json.loads(strip_bom((d / "TyreStintSeries.json").read_bytes()))
    stints = ts.get("Stints", {})
    shown = 0
    for num in sorted(stints, key=lambda x: int(x) if str(x).isdigit() else 999):
        v = stints[num]
        items = list(v.values()) if isinstance(v, dict) else v
        tla = drivers.get(str(num), {}).get("Tla", num)
        desc = " → ".join(
            f"{s.get('Compound','?')[:4]}({s.get('TotalLaps','?')}L{',new' if s.get('New')=='true' or s.get('New') is True else ''})"
            for s in items if isinstance(s, dict)
        )
        if desc and shown < 8:
            print(f"  {tla:<5} {desc}")
            shown += 1
    print(f"  … {max(0, len(stints) - shown)} more drivers")

    # ---- pit stops -------------------------------------------------------------
    sect("PIT STOPS (PitStopSeries keyframe)")
    ps = json.loads(strip_bom((d / "PitStopSeries.json").read_bytes()))
    n = 0
    for num, series in sorted(ps.get("PitTimes", {}).items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 999):
        tla = drivers.get(str(num), {}).get("Tla", num)
        for _, stop in (series.items() if isinstance(series, dict) else []):
            p = stop.get("PitStop", stop)
            print(f"  {tla:<5} lap {str(p.get('Lap','?')):>3}  pit_lane={p.get('PitlaneTime','?'):>7}s  stop={p.get('PitStopTime','?')}")
            n += 1
            if n >= 8:
                break
        if n >= 8:
            break
    print(f"  (showing first {n})")

    # ---- overtakes -------------------------------------------------------------
    sect("OVERTAKES (OvertakeSeries keyframe) — labelled events")
    ov = json.loads(strip_bom((d / "OvertakeSeries.json").read_bytes()))
    def walk(o, acc):
        if isinstance(o, dict):
            if {"Overtaking", "Overtaken"} & set(o):
                acc.append(o)
            for v in o.values():
                walk(v, acc)
        elif isinstance(o, list):
            for v in o:
                walk(v, acc)
    evs: list = []
    walk(ov, evs)
    print(f"  events in keyframe: {len(evs)}")
    for e in evs[:8]:
        a = drivers.get(str(e.get("Overtaking")), {}).get("Tla", e.get("Overtaking"))
        b = drivers.get(str(e.get("Overtaken")), {}).get("Tla", e.get("Overtaken"))
        print(f"    lap {str(e.get('Lap','?')):>3}: {a} passed {b}")

    # ---- track status ----------------------------------------------------------
    sect("TRACK STATUS (SC / VSC / flags)")
    for t, p in records(d / "TrackStatus.jsonStream"):
        try:
            j = as_json(p)
            print(f"  {t}  status={j.get('Status')}  {j.get('Message')}")
        except Exception:
            pass

    sect("RACE CONTROL MESSAGES (first 10)")
    rcm = json.loads(strip_bom((d / "RaceControlMessages.json").read_bytes()))
    msgs = rcm.get("Messages", [])
    msgs = list(msgs.values()) if isinstance(msgs, dict) else msgs
    print(f"  total: {len(msgs)}")
    for msg in msgs[:10]:
        print(f"    lap {str(msg.get('Lap','-')):>3} [{msg.get('Category','')}] {str(msg.get('Message',''))[:82]}")

    # ---- weather ---------------------------------------------------------------
    sect("WEATHER")
    wx = list(records(d / "WeatherData.jsonStream"))
    print(f"  samples: {len(wx)}")
    for t, p in wx[:3]:
        print(f"    {t}  {as_json(p)}")

    # ---- car telemetry ---------------------------------------------------------
    sect("CAR TELEMETRY (CarData.z) — full decode")
    frames = 0
    entries = 0
    samples = 0
    per_car: Counter = Counter()
    chan_present: Counter = Counter()
    chan_vals: dict[str, list] = defaultdict(list)
    first_utc = last_utc = None
    for _, p in records(d / "CarData.z.jsonStream"):
        try:
            j = inflate(p)
        except Exception:
            continue
        frames += 1
        for e in j.get("Entries", []):
            entries += 1
            u = e.get("Utc")
            if first_utc is None:
                first_utc = u
            last_utc = u
            for car, cd in e.get("Cars", {}).items():
                samples += 1
                per_car[car] += 1
                for ch, val in cd.get("Channels", {}).items():
                    chan_present[ch] += 1
                    if len(chan_vals[ch]) < 200_000:
                        chan_vals[ch].append(val)
    print(f"  frames={frames:,}  entries={entries:,}  car-samples={samples:,}")
    print(f"  utc span: {first_utc} → {last_utc}")
    print(f"  cars: {len(per_car)}  samples/car: min={min(per_car.values()):,} max={max(per_car.values()):,}")
    print("\n  channel coverage and value range across the whole race:")
    names = {"0": "RPM?", "2": "Speed?", "3": "nGear?", "4": "Throttle?", "5": "Brake?", "45": "DRS?"}
    print(f"    {'ch':<5}{'guess':<11}{'count':>12}{'min':>8}{'max':>8}{'distinct':>10}  observed")
    for ch, cnt in sorted(chan_present.items(), key=lambda kv: int(kv[0])):
        v = chan_vals[ch]
        dis = sorted(set(v))
        head = str(dis[:6])[:30] if len(dis) <= 12 else ""
        print(f"    {ch:<5}{names.get(ch,'?'):<11}{cnt:>12,}{min(v):>8}{max(v):>8}{len(dis):>10}  {head}")

    sect("POSITION (Position.z) — full decode")
    pf = ps_ = 0
    for _, p in records(d / "Position.z.jsonStream"):
        try:
            j = inflate(p)
        except Exception:
            continue
        pf += 1
        for e in j.get("Position", []) if isinstance(j.get("Position"), list) else []:
            ps_ += len(e.get("Entries", {}))
    print(f"  frames={pf:,}  car-position-samples={ps_:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
