#!/usr/bin/env python3
"""Replay the append-only event log and extract canonical per-lap race records.

This is the as-of state tracker of Invariant 4: it walks the log strictly in
(source_sequence) order, carrying state forward, and can emit a snapshot at any point using only
records seen up to that point. It never reads final classifications or post-race corrections.

BOUNDARY. This applies deltas over OBSERVATIONS -- position, laps, compound, pit counts, track status.
That is state tracking, not modelled derivation: every value here is something the feed reported, merged
forward. The modelled quantities the strategy board depends on -- clean-air pace estimation, degradation
slope, gap projection, option evaluation -- are Mojo kernels reading these records. The line is drawn at
"is this a number the feed stated, or a number we inferred?".

DELTA SEMANTICS, which are easy to get wrong and fail silently:

  1. Arrays in a keyframe arrive as INDEX-KEYED OBJECTS in deltas:
         keyframe  "Stints": [ {...}, {...} ]
         delta     "Stints": { "0": {...} }
     A naive dict merge would replace the array with an object and lose every other stint.

  2. "_deleted": [k, ...] retracts keys. PitLaneTimeCollection adds a car then retracts it, so naive
     accumulation reports cars as permanently in the pit lane.

  3. Deltas are PARTIAL -- only changed fields appear. TimingData sends e.g.
         {"Lines":{"55":{"IntervalToPositionAhead":{"Value":"+6.231"}}}}
     so unstated fields must be preserved, not defaulted.

Usage:
    python3 scripts/timing/replay_state.py \
        --dir ~/.algenta/f1/raw/2026/2026-07-26_Hungarian_Grand_Prix/2026-07-26_Race
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

DELETED = "_deleted"


def merge_delta(target: Any, delta: Any) -> Any:
    """Merge a feed delta onto carried state, honouring array-as-index-object and _deleted."""
    if not isinstance(delta, dict):
        return delta

    # retraction
    if DELETED in delta:
        removed = delta[DELETED]
        if isinstance(target, dict) and isinstance(removed, list):
            for key in removed:
                target.pop(str(key), None)
        rest = {k: v for k, v in delta.items() if k != DELETED}
        if not rest:
            return target
        delta = rest

    # array target patched by index-keyed object
    if isinstance(target, list) and all(str(k).lstrip("-").isdigit() for k in delta):
        for k, v in delta.items():
            i = int(k)
            while len(target) <= i:
                target.append({})
            target[i] = merge_delta(target[i], v)
        return target

    if isinstance(target, dict):
        for k, v in delta.items():
            target[k] = merge_delta(target.get(k), v) if k in target else v
        return target

    return delta


def _f(v: Any) -> float | None:
    """Parse a timing string: '1:24.349' or '29.105' or '+6.231' -> seconds."""
    if v is None:
        return None
    s = str(v).strip().lstrip("+")
    if not s or s in {"-", "—"}:
        return None
    try:
        if ":" in s:
            mm, ss = s.split(":")
            return int(mm) * 60 + float(ss)
        return float(s)
    except ValueError:
        return None


# Topics whose keyframe is a genuine STATIC reference rather than accumulated state.
#
# For an archived COMPLETED session the keyframe of an evolving topic is the POST-SESSION snapshot: the
# TimingData keyframe for Bahrain 2019 carries NumberOfLaps=57 and Position=1 for the winner. Since
# build_event_log places keyframes at event_ms = 0 -- before everything -- feeding them to the state
# machine put the FINAL CLASSIFICATION into every as-of snapshot at every lap. Track position at 25%
# distance was the finishing position, which is why an in-race "current running order" baseline scored a
# Brier of exactly 0.00000 and a BSS of +1.000 across 117 held-out snapshots. Impossible numbers are the
# only reason it was caught.
#
# The keyframe stays IN the event log -- it is source truth, and it is a useful scorer-side cross-check
# against the official classification. It simply may not enter the as-of state path.
#
# Note this is a REPLAY-path rule. Live, a keyframe is state at connect time and is legitimate; there it
# must be stamped with the connect timestamp rather than zero.
KEYFRAME_SAFE = frozenset({"SessionInfo", "DriverList", "ArchiveStatus"})


def snapshot_hash(
    lap_rows: list[dict], stint_rows: list[dict], pit_rows: list[dict], regime_rows: list[dict]
) -> str:
    """Canonical hash of an as-of snapshot — the object Invariant 4's required test compares.

    Sorted by a stable logical key and serialised with sorted field names, so the hash is a function of
    the STATE and not of dict insertion order, row emission order, or a Parquet writer version. A hash
    that moved for any of those reasons would make the leakage test unusable.

    The log-position fields are EXCLUDED for the same reason. It is a position in the log, not a property of the
    modelled state: a duplicated frame -- which a live reconnect produces routinely -- renumbers every
    row after it while changing no content. Measured on one race, a resend of every seventh record moved
    `source_sequence` on all 938 lap rows and no other field at all. Leaving it in made the hash report a
    state change for every reconnect, which is exactly the alarm that trains an operator to ignore
    alarms. The ingest-sequence watermark is still carried on the snapshot itself per Invariant 3; it
    simply is not part of the state identity.
    """
    _LOG_POSITION_FIELDS = ("source_sequence", "first_seen_sequence", "last_update_sequence")
    h = hashlib.sha256()
    for name, rows, key in (
        ("laps", lap_rows, lambda r: (str(r.get("car_number")), r.get("lap_number") or 0)),
        ("stints", stint_rows, lambda r: (str(r.get("car_number")), r.get("stint_index") or 0)),
        ("pits", pit_rows, lambda r: (str(r.get("car_number")), r.get("lap_number") or 0,
                                      r.get("stationary_s") or 0.0)),
        ("regime", regime_rows, lambda r: (r.get("lap_number") or 0, str(r.get("message", "")))),
    ):
        h.update(f"\x1d{name}\x1d{len(rows)}".encode())
        for r in sorted(rows, key=key):
            body = {k: v for k, v in r.items() if k not in _LOG_POSITION_FIELDS}
            h.update(json.dumps(body, sort_keys=True, default=str, separators=(",", ":")).encode())
            h.update(b"\x1e")
    return h.hexdigest()


def replay(session_dir: Path, cutoff_ms: int | None = None, emit: bool = True) -> dict:
    """Rebuild derived state from the append-only event log.

    cutoff_ms is the AS-OF WATERMARK required by Invariant 4: records with event_ms above it are not
    consumed, so a snapshot reconstructed at T cannot see a correction that arrived after T. Passing
    None consumes the whole log, which is the scoring path.

    ONE loop serves both, deliberately. A separate as-of reconstruction would be a second
    implementation of the state machine, and the two would drift -- at which point the leakage test
    would be checking the wrong code.
    """
    log = pq.read_table(session_dir / "_event_log.parquet").to_pydict()
    n = len(log["source_sequence"])
    season = log["season"][0] if n else 0
    session_key = log["session_key"][0] if n else 0

    timing: dict[str, Any] = {}
    appdata: dict[str, Any] = {}
    drivers: dict[str, Any] = {}
    current_lap = 0
    total_laps = 0
    regime = 1
    regime_msg = "AllClear"

    lap_rows: list[dict] = []
    pit_rows: list[dict] = []
    regime_rows: list[dict] = []
    # last emitted lap per car, so one row per (car, lap)
    emitted: dict[str, int] = {}
    # Stints are their own entity, keyed (car, stint_index) and upserted as the feed revises them.
    # Deriving them from lap rows loses any stint that completed ZERO laps -- which happens when a car
    # pits again immediately or retires mid-stint, and cost 1/22 cars exact parity when stints were a
    # by-product of lap emission. first_seen_* preserves the as-of watermark of when the stint became
    # known, so Invariant 4 still holds.
    stint_state: dict[tuple[str, int], dict] = {}

    consumed = 0
    skipped_keyframes = 0
    for i in range(n):
        topic = log["topic"][i]
        seq = log["source_sequence"][i]
        ms = log["event_ms"][i]
        if cutoff_ms is not None and ms > cutoff_ms:
            continue
        if log["is_keyframe"][i] and topic not in KEYFRAME_SAFE:
            skipped_keyframes += 1
            continue
        consumed += 1
        try:
            payload = json.loads(log["payload"][i])
        except Exception:
            continue

        if topic == "DriverList":
            merge_delta(drivers, payload)

        elif topic == "LapCount":
            current_lap = payload.get("CurrentLap", current_lap)
            total_laps = payload.get("TotalLaps", total_laps)

        elif topic == "TrackStatus":
            new_code = int(payload.get("Status", regime) or regime)
            if new_code != regime:
                regime_rows.append({
                    "season": season, "session_key": session_key,
                    "source_sequence": seq, "event_ms": ms,
                    "lap_number": current_lap,
                    "status_code": new_code,
                    "message": str(payload.get("Message", "")),
                    # codes 3 and 5 have never been observed; surface, never silently map
                    "is_unknown_code": 1 if new_code not in (1, 2, 4, 6, 7) else 0,
                })
            regime = new_code
            regime_msg = str(payload.get("Message", regime_msg))

        elif topic == "PitStop":
            car = str(payload.get("RacingNumber", ""))
            if car:
                # 8 of 33 PitStop records in the probe race genuinely OMIT Lap -- the feed sends
                # {RacingNumber, PitStopTime, PitLaneTime} with no lap. Attribute from the car's
                # concurrent completed-lap count in the carried timing state; defaulting to 0 keyed
                # those stops to lap 0 and lost a quarter of the stationary-time sample.
                lap_field = payload.get("Lap")
                if lap_field:
                    lap_no = int(lap_field)
                else:
                    carried = timing.get(car, {}).get("NumberOfLaps")
                    lap_no = int(carried) if isinstance(carried, int) else current_lap
                pit_rows.append({
                    "season": season, "session_key": session_key,
                    "car_number": int(car), "lap_number": lap_no,
                    "source_sequence": seq, "event_ms": ms,
                    "provider": "official_pitstop",
                    "lap_attributed": 0 if lap_field else 1,
                    "stationary_s": _f(payload.get("PitStopTime")),
                    "pit_lane_s": _f(payload.get("PitLaneTime")),
                    "under_neutralisation": 1 if regime in (4, 6, 7) else 0,
                })

        elif topic == "PitLaneTimeCollection":
            # The complete set of pit-lane ENTRIES -- 45 against PitStop's 33, matching Jolpica's 45.
            # PitStop is not a lossy subset: it reports the stops with a measured STATIONARY time,
            # which is a different measurement. pit_loss is fitted from here, sigma_pit from PitStop.
            for car_s, v in (payload.get("PitTimes") or {}).items():
                if car_s == "_deleted" or not isinstance(v, dict):
                    continue
                cn = str(v.get("RacingNumber") or car_s)
                if not cn.isdigit():
                    continue
                pit_rows.append({
                    "season": season, "session_key": session_key,
                    "car_number": int(cn), "lap_number": int(v.get("Lap") or current_lap),
                    "source_sequence": seq, "event_ms": ms,
                    "provider": "official_pitlane",
                    "lap_attributed": 0 if v.get("Lap") else 1,
                    "stationary_s": None,
                    "pit_lane_s": _f(v.get("Duration")),
                    "under_neutralisation": 1 if regime in (4, 6, 7) else 0,
                })

        elif topic == "TimingAppData":
            merge_delta(appdata, payload.get("Lines", {}))
            # upsert every stint the feed currently reports, independent of lap completion
            for car, app in appdata.items():
                stints = app.get("Stints") or []
                if isinstance(stints, dict):
                    stints = [stints[k] for k in sorted(stints, key=lambda x: int(x))]
                for si, st in enumerate(stints):
                    if not isinstance(st, dict) or not st.get("Compound"):
                        continue
                    key = (car, si)
                    prior = stint_state.get(key)
                    total = st.get("TotalLaps")
                    start = st.get("StartLaps")
                    row = {
                        "season": season, "session_key": session_key,
                        "car_number": int(car), "stint_index": si,
                        "compound": str(st.get("Compound")),
                        "is_new": 1 if str(st.get("New")).lower() == "true" else 0,
                        "total_laps": int(total) if isinstance(total, int) else 0,
                        "tyre_age_at_start": int(start) if isinstance(start, int) else 0,
                        "start_lap_number": int(st.get("LapNumber") or 0),
                        "first_seen_sequence": prior["first_seen_sequence"] if prior else seq,
                        "first_seen_ms": prior["first_seen_ms"] if prior else ms,
                        "last_update_sequence": seq,
                    }
                    stint_state[key] = row

        elif topic == "TimingData":
            merge_delta(timing, payload.get("Lines", {}))
            # emit a lap row when a car's completed-lap count advances
            for car, line in timing.items():
                laps_done = line.get("NumberOfLaps")
                if not isinstance(laps_done, int) or laps_done <= 0:
                    continue
                if emitted.get(car) == laps_done:
                    continue
                emitted[car] = laps_done

                app = appdata.get(car, {})
                stints = app.get("Stints") or []
                if isinstance(stints, dict):
                    stints = [stints[k] for k in sorted(stints, key=lambda x: int(x))]
                stint_idx = max(len(stints) - 1, 0)
                stint = stints[stint_idx] if stints else {}

                sectors = line.get("Sectors") or []
                if isinstance(sectors, dict):
                    sectors = [sectors[k] for k in sorted(sectors, key=lambda x: int(x))]

                def sec(j: int) -> float | None:
                    if j < len(sectors) and isinstance(sectors[j], dict):
                        return _f(sectors[j].get("Value") or sectors[j].get("PreviousValue"))
                    return None

                total_stint = stint.get("TotalLaps")
                start_laps = stint.get("StartLaps") or 0
                lap_rows.append({
                    "season": season, "session_key": session_key,
                    "car_number": int(car), "lap_number": laps_done,
                    "source_sequence": seq, "event_ms": ms,
                    "lap_time_s": _f((line.get("LastLapTime") or {}).get("Value")
                                     if isinstance(line.get("LastLapTime"), dict)
                                     else line.get("LastLapTime")),
                    "sector1_s": sec(0), "sector2_s": sec(1), "sector3_s": sec(2),
                    "compound": str(stint.get("Compound") or ""),
                    "tyre_is_new": 1 if str(stint.get("New")).lower() == "true" else 0,
                    "tyre_age": int(total_stint) if isinstance(total_stint, int) else 0,
                    "tyre_age_at_start": int(start_laps) if isinstance(start_laps, int) else 0,
                    "stint_index": stint_idx,
                    "position": int(line.get("Position") or 0),
                    "grid_position": int(app.get("GridPos") or 0),
                    "pit_count": int(line.get("NumberOfPitStops") or 0),
                    "in_pit": 1 if line.get("InPit") else 0,
                    "pit_out": 1 if line.get("PitOut") else 0,
                    "retired": 1 if line.get("Retired") else 0,
                    "stopped": 1 if line.get("Stopped") else 0,
                    "gap_to_leader_s": _f(line.get("GapToLeader")),
                    "interval_ahead_s": _f((line.get("IntervalToPositionAhead") or {}).get("Value")
                                           if isinstance(line.get("IntervalToPositionAhead"), dict)
                                           else line.get("IntervalToPositionAhead")),
                    "track_regime": regime,
                    "is_green_lap": 1 if regime == 1 else 0,
                })

    def write(rows: list[dict], name: str) -> int:
        """emit=False suppresses the FILE, never the count — a diagnostic that reports zero rows for a
        non-empty state is how an insensitive hash would look like a correct one."""
        if not rows:
            return 0
        if emit:
            cols = {k: [r.get(k) for r in rows] for k in rows[0]}
            pq.write_table(pa.table(cols), session_dir / f"_{name}.parquet", compression="zstd")
        return len(rows)

    stint_rows = [stint_state[k] for k in sorted(stint_state, key=lambda k: (int(k[0]), k[1]))]

    return {
        "season": season, "session_key": session_key,
        "events": n, "consumed": consumed, "cutoff_ms": cutoff_ms,
        "skipped_keyframes": skipped_keyframes,
        # highest lap reached in the AS-OF rows. A snapshot partway through a race must not know the
        # race distance; reading this from the emitted rows rather than a file on disk is the point,
        # since emit=False leaves any pre-existing parquet untouched and stale.
        "max_lap": max((r["lap_number"] for r in lap_rows), default=0),
        "state_hash": snapshot_hash(lap_rows, stint_rows, pit_rows, regime_rows),
        "total_laps": total_laps,
        "laps": write(lap_rows, "laps"),
        "stints": write(stint_rows, "stints"),
        "pit_events": write(pit_rows, "pit_events"),
        "regime_changes": write(regime_rows, "track_status"),
        "cars": len({r["car_number"] for r in lap_rows}),
        "grid_known": len({r["car_number"] for r in lap_rows if r["grid_position"] > 0}),
        "with_compound": sum(1 for r in lap_rows if r["compound"]),
        "green_laps": sum(1 for r in lap_rows if r["is_green_lap"]),
        "zero_lap_stints": sum(1 for r in stint_rows if r["total_laps"] == 0),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    args = ap.parse_args()
    info = replay(Path(args.dir).expanduser())
    for k, v in info.items():
        print(f"  {k:<16} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
