#!/usr/bin/env python3
"""Build the canonical append-only event log for one session.

This is the substrate Invariant 4 requires: every decision snapshot in a backtest is reconstructed by
replaying this log in order, never by reading final post-race tables. It is also what the live path
appends to, so replay and live share one representation.

Boundary: this is DESERIALIZATION, not modelled derivation. It splits stream records, base64-decodes,
inflates via audited zlib, parses JSON, and merges feeds into one deterministically ordered sequence.
It derives no race state -- no laps, no stints, no pace estimates. Those come from Mojo kernels reading
this log.

Ordering, which matters more than it looks:
  * feed timestamps are relative (HH:MM:SS.mmm from session start) and MANY records share one value
  * so the merge key is (feed_timestamp, topic, within-feed index) -- a total order, deterministic
    across runs and independent of filesystem or dict iteration order
  * source_sequence is assigned from that order and becomes the stable tie-break everything downstream
    relies on. Without it, replay could reorder equal-timestamp records between runs.

Keyframes are emitted first (sequence before any stream record) because they are the initial state a
delta stream applies onto. TimingData in particular sends only CHANGED fields per record.

Usage:
    python3 scripts/timing/build_event_log.py \
        --dir ~/.algenta/f1/raw/2026/2026-07-26_Hungarian_Grand_Prix/2026-07-26_Race
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import zlib
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

TS_RE = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d{3})(.*)$", re.S)

# Feeds carried into the log, in a fixed order so the merge tie-break is stable.
TOPICS = (
    "SessionInfo", "SessionStatus", "SessionData", "ArchiveStatus",
    "DriverList", "LapCount", "LapSeries",
    "TimingData", "TimingDataF1", "TimingAppData", "TimingStats",
    "CurrentTyres", "TyreStintSeries",
    "PitStop", "PitStopSeries", "PitLaneTimeCollection",
    "OvertakeSeries", "TrackStatus", "RaceControlMessages",
    "WeatherData", "WeatherDataSeries", "DriverRaceInfo",
    "ExtrapolatedClock", "Heartbeat",
    "CarData.z", "Position.z",
)
COMPRESSED = {"CarData.z", "Position.z"}
TOPIC_ORDER = {t: i for i, t in enumerate(TOPICS)}


def strip_bom(b: bytes) -> bytes:
    return b[3:] if b[:3] == b"\xef\xbb\xbf" else b


def inflate_payload(text: str) -> str:
    """A .z payload is a quoted base64 string over raw deflate. Uses stdlib zlib deliberately --
    writing a DEFLATE decoder buys no claim and carries real security surface."""
    s = text.strip()
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    return zlib.decompress(base64.b64decode(s), -zlib.MAX_WBITS).decode("utf-8")


def ts_to_ms(ts: str) -> int:
    """HH:MM:SS.mmm -> milliseconds since session feed start."""
    hh, mm, rest = ts.split(":")
    ss, ms = rest.split(".")
    return ((int(hh) * 60 + int(mm)) * 60 + int(ss)) * 1000 + int(ms)


def read_stream(path: Path, topic: str) -> list[tuple[str, str]]:
    """Yield (feed_timestamp, payload_json_text) for each record, in file order."""
    out: list[tuple[str, str]] = []
    body = strip_bom(path.read_bytes()).decode("utf-8", errors="replace")
    for line in body.split("\r\n"):
        if not line.strip():
            continue
        m = TS_RE.match(line)
        if not m:
            continue
        ts, payload = m.group(1), m.group(2)
        if topic in COMPRESSED:
            try:
                payload = inflate_payload(payload)
            except Exception:
                continue
        else:
            payload = payload.strip()
            if not payload:
                continue
            try:
                json.loads(payload)
            except Exception:
                continue
        out.append((ts, payload))
    return out


def build(session_dir: Path) -> dict:
    rows: list[dict] = []

    # keyframes first: the base state a delta stream applies onto
    for topic in TOPICS:
        kf = session_dir / f"{topic}.json"
        if not kf.exists():
            continue
        raw = strip_bom(kf.read_bytes()).decode("utf-8", errors="replace").strip()
        if not raw:
            continue
        try:
            json.loads(raw)
        except Exception:
            continue
        rows.append({
            "sort_key": (-1, TOPIC_ORDER[topic], 0),
            "feed_timestamp": "00:00:00.000",
            "event_ms": 0,
            "topic": topic,
            "is_keyframe": True,
            "payload": raw,
        })

    for topic in TOPICS:
        sf = session_dir / f"{topic}.jsonStream"
        if not sf.exists():
            continue
        for idx, (ts, payload) in enumerate(read_stream(sf, topic)):
            rows.append({
                "sort_key": (ts_to_ms(ts), TOPIC_ORDER[topic], idx),
                "feed_timestamp": ts,
                "event_ms": ts_to_ms(ts),
                "topic": topic,
                "is_keyframe": False,
                "payload": payload,
            })

    rows.sort(key=lambda r: r["sort_key"])

    session_info = {}
    for r in rows:
        if r["topic"] == "SessionInfo":
            try:
                session_info = json.loads(r["payload"])
                break
            except Exception:
                pass
    session_key = int(session_info.get("Key") or 0)
    start_date = str(session_info.get("StartDate") or "")
    season = int(start_date[:4]) if start_date[:4].isdigit() else 0

    table = pa.table({
        "source_sequence": pa.array(range(1, len(rows) + 1), pa.uint64()),
        "season": pa.array([season] * len(rows), pa.uint16()),
        "session_key": pa.array([session_key] * len(rows), pa.uint32()),
        "event_ms": pa.array([r["event_ms"] for r in rows], pa.int64()),
        "feed_timestamp": pa.array([r["feed_timestamp"] for r in rows], pa.string()),
        "topic": pa.array([r["topic"] for r in rows], pa.string()),
        "is_keyframe": pa.array([r["is_keyframe"] for r in rows], pa.bool_()),
        "payload": pa.array([r["payload"] for r in rows], pa.string()),
    })

    out = session_dir / "_event_log.parquet"
    pq.write_table(table, out, compression="zstd")

    # A digest over (sequence, timestamp, topic, payload) -- the canonical logical digest for this
    # log. Byte-level file comparison would be unstable across Parquet writer versions; this is not.
    h = hashlib.sha256()
    for i, r in enumerate(rows, 1):
        h.update(f"{i}\x1f{r['feed_timestamp']}\x1f{r['topic']}\x1f".encode())
        h.update(r["payload"].encode())
        h.update(b"\x1e")

    by_topic: dict[str, int] = {}
    for r in rows:
        by_topic[r["topic"]] = by_topic.get(r["topic"], 0) + 1

    return {
        "session_key": session_key,
        "season": season,
        "events": len(rows),
        "span_ms": rows[-1]["event_ms"] if rows else 0,
        "topics": by_topic,
        "logical_digest": h.hexdigest(),
        "parquet_bytes": out.stat().st_size,
        "path": str(out),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    args = ap.parse_args()
    d = Path(args.dir).expanduser()

    info = build(d)
    print(f"session_key     {info['session_key']}  season {info['season']}")
    print(f"events          {info['events']:,}")
    print(f"span            {info['span_ms'] / 1000:,.0f} s")
    print(f"parquet         {info['parquet_bytes']:,} B")
    print(f"logical_digest  {info['logical_digest']}")
    print("\nevents per topic:")
    for topic, n in sorted(info["topics"].items(), key=lambda kv: -kv[1]):
        print(f"  {topic:<24} {n:>8,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
