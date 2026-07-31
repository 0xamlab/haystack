#!/usr/bin/env python3
"""Load one session's car telemetry into ClickHouse via Parquet, and report codec effectiveness.

GATE 0 VALIDATION TOOLING. This proves the storage design end to end — decode, Parquet handoff,
ClickHouse ingest, compression — and measures whether the frozen codec choices actually pay. The
production path replaces the Python decode with a Mojo kernel (Gate 1); the Parquet handoff and the
ClickHouse writer stay.

Applies the frozen semantics:
  * 104 -> NULL for throttle and brake ONLY (per-frame staleness marker for those two channels)
  * 104 left intact for speed, where it is a legitimate km/h value
  * repeat_run_length derived, so downstream can distinguish a stale repeated value from a
    genuinely constant one -- rpm/speed/gear carry no staleness marker of their own

Usage:
    python3 scripts/timing/load_telemetry.py \
        --dir ~/.algenta/f1/raw/2026/2026-07-26_Hungarian_Grand_Prix/2026-07-26_Race \
        --season 2026 --session-key 11342
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import urllib.request
import zlib
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

TS = re.compile(rb"^(\d{2}:\d{2}:\d{2}\.\d{3})(.*)$", re.S)
STALE = 104
CH_URL = "http://127.0.0.1:8123/"


def _ch(sql: str, body: bytes | None = None, *, user: str = "algenta", pw: str = "algenta_local_dev") -> str:
    import urllib.parse

    qs = urllib.parse.urlencode({"user": user, "password": pw, "query": sql})
    req = urllib.request.Request(f"{CH_URL}?{qs}", data=body if body is not None else b"")
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read().decode()


def _strip_bom(b: bytes) -> bytes:
    return b[3:] if b[:3] == b"\xef\xbb\xbf" else b


def decode_car_data(path: Path) -> dict[str, list]:
    cols: dict[str, list] = {k: [] for k in (
        "car_number", "event_time", "source_sequence",
        "rpm", "speed_kph", "gear", "throttle_pct", "brake", "repeat_run_length",
    )}
    # per-car run length over the (rpm, speed, gear) triple — the channels with no staleness marker
    last: dict[int, tuple] = {}
    run: dict[int, int] = {}
    seq = 0

    for line in _strip_bom(path.read_bytes()).split(b"\r\n"):
        if not line.strip():
            continue
        m = TS.match(line)
        if not m:
            continue
        payload = m.group(2).strip()
        if payload[:1] == b'"':
            payload = payload[1:-1]
        try:
            frame = json.loads(zlib.decompress(base64.b64decode(payload), -zlib.MAX_WBITS))
        except Exception:
            continue

        for entry in frame.get("Entries", []):
            utc = entry.get("Utc")
            # 7 fractional digits -> keep 9 (ns) so nothing truncates
            ts = utc.rstrip("Z")
            if "." in ts:
                head, frac = ts.split(".")
                ts = f"{head}.{frac[:9].ljust(9, '0')}"
            for car_s, cd in entry.get("Cars", {}).items():
                ch = cd.get("Channels", {})
                car = int(car_s)
                rpm = int(ch.get("0", 0))
                spd = int(ch.get("2", 0))
                gear = int(ch.get("3", 0))
                thr = ch.get("4")
                brk = ch.get("5")

                triple = (rpm, spd, gear)
                run[car] = run.get(car, 0) + 1 if last.get(car) == triple else 0
                last[car] = triple

                seq += 1
                cols["car_number"].append(car)
                cols["event_time"].append(ts)
                cols["source_sequence"].append(seq)
                cols["rpm"].append(rpm)
                cols["speed_kph"].append(spd)          # 104 is a real speed — never masked
                cols["gear"].append(gear)
                cols["throttle_pct"].append(None if thr is None or int(thr) == STALE else int(thr))
                cols["brake"].append(None if brk is None or int(brk) == STALE else int(brk))
                cols["repeat_run_length"].append(min(run[car], 255))
    return cols


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--session-key", type=int, required=True)
    ap.add_argument("--table", default="f1_current.car_telemetry")
    args = ap.parse_args()

    d = Path(args.dir).expanduser()
    print(f"decoding {d.name} …")
    cols = decode_car_data(d / "CarData.z.jsonStream")
    n = len(cols["car_number"])
    stale_thr = sum(1 for v in cols["throttle_pct"] if v is None)
    stale_brk = sum(1 for v in cols["brake"] if v is None)
    repeats = sum(1 for v in cols["repeat_run_length"] if v > 0)
    print(f"  rows                 {n:,}")
    print(f"  throttle stale (NULL) {stale_thr:,} ({stale_thr / n:.1%})")
    print(f"  brake    stale (NULL) {stale_brk:,} ({stale_brk / n:.1%})")
    print(f"  repeated (rpm,spd,gr) {repeats:,} ({repeats / n:.1%})  <- invisible staleness")

    table = pa.table({
        "season": pa.array([args.season] * n, pa.uint16()),
        "session_key": pa.array([args.session_key] * n, pa.uint32()),
        "car_number": pa.array(cols["car_number"], pa.uint16()),
        "event_time": pa.array(cols["event_time"], pa.string()),
        "source_sequence": pa.array(cols["source_sequence"], pa.uint64()),
        "rpm": pa.array(cols["rpm"], pa.uint16()),
        "speed_kph": pa.array(cols["speed_kph"], pa.uint16()),
        "gear": pa.array(cols["gear"], pa.uint8()),
        "throttle_pct": pa.array(cols["throttle_pct"], pa.uint8()),
        "brake": pa.array(cols["brake"], pa.uint8()),
        "repeat_run_length": pa.array(cols["repeat_run_length"], pa.uint8()),
    })

    out = Path("/tmp") / f"car_telemetry_{args.session_key}.parquet"
    pq.write_table(table, out, compression="zstd")
    print(f"  parquet              {out.stat().st_size:,} B")

    collist = ", ".join(table.column_names)
    _ch(f"ALTER TABLE {args.table} DROP PARTITION ({args.season}, {args.session_key})")
    _ch(f"INSERT INTO {args.table} ({collist}) FORMAT Parquet", out.read_bytes())

    print("\nClickHouse:")
    print(_ch(
        f"SELECT count() AS rows, uniqExact(car_number) AS cars, "
        f"min(event_time) AS t0, max(event_time) AS t1 "
        f"FROM {args.table} WHERE season={args.season} AND session_key={args.session_key} "
        f"FORMAT Vertical"
    ))
    print("per-column compression (ClickHouse, this partition):")
    print(_ch(
        f"SELECT name, formatReadableSize(sum(data_compressed_bytes)) AS comp, "
        f"formatReadableSize(sum(data_uncompressed_bytes)) AS uncomp, "
        f"round(sum(data_uncompressed_bytes)/greatest(sum(data_compressed_bytes),1),1) AS ratio "
        f"FROM system.columns c JOIN system.parts_columns pc USING (database, table, name) "
        f"WHERE pc.database='f1_current' AND pc.table='car_telemetry' AND pc.active "
        f"GROUP BY name ORDER BY sum(data_compressed_bytes) DESC FORMAT PrettyCompactMonoBlock"
    ))
    print(_ch(
        "SELECT formatReadableSize(sum(data_compressed_bytes)) AS total_compressed, "
        "formatReadableSize(sum(data_uncompressed_bytes)) AS total_uncompressed, "
        "round(sum(data_uncompressed_bytes)/greatest(sum(data_compressed_bytes),1),2) AS ratio "
        "FROM system.parts_columns WHERE database='f1_current' AND table='car_telemetry' AND active "
        "FORMAT Vertical"
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
