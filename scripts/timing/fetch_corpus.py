#!/usr/bin/env python3
"""Bulk-fetch the historical F1 live-timing corpus into the immutable ingest root.

Transport only — writes raw bytes verbatim plus a per-session content-addressed manifest. No parsing,
no derivation. Decoding is a Mojo kernel.

Corpus shape, established by probing (docs/timing/DATA_COVERAGE_AUDIT.md):
  * root Index.json lists ONLY the current year, so years are enumerated explicitly
  * 2022 is not served at all (year index HTTP-errors) -- excluded
  * 2018 is partial: early rounds error, late rounds carry 28 feeds -- excluded by default
  * PitStop / OvertakeSeries exist only from 2025

Politeness and safety:
  * modest concurrency, capped; this is someone else's CDN
  * exponential backoff on transient failures, 404 treated as "feed absent" not an error
  * resume: a session whose manifest records complete=true is skipped entirely
  * ArchiveStatus must read Complete, else the session is recorded incomplete and NOT marked done --
    ingesting a live/partial archive would silently truncate a corpus entry

Usage:
    python3 scripts/timing/fetch_corpus.py --plan                 # enumerate + size, no download
    python3 scripts/timing/fetch_corpus.py --session-types Race   # races only
    python3 scripts/timing/fetch_corpus.py --workers 4
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = "https://livetiming.formula1.com/static"
UA = "algenta-timing-ingest/0.1 (+research)"

# Years with a served, usable archive. 2022 is absent upstream; 2018 is partial.
DEFAULT_YEARS = (2019, 2020, 2021, 2023, 2024, 2025, 2026)

FEEDS = (
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

_print_lock = threading.Lock()


def _log(msg: str) -> None:
    with _print_lock:
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()


def _encode_url(url: str) -> str:
    """Percent-encode non-ASCII path characters.

    Session paths contain accented venue names -- 'São Paulo', 'México City', 'Emilia-Romagna' --
    and urllib raises UnicodeEncodeError ('ascii' codec can't encode '\\xe3') on a raw non-ASCII URL.
    `%` is in the safe set so an already-encoded URL is not double-encoded on retry.
    """
    return urllib.parse.quote(url, safe=":/?&=%#")


def _get(url: str, *, timeout: float = 180.0, retries: int = 4) -> bytes | None:
    """Fetch bytes. None means 404 (absent), exception means give up."""
    last: Exception | None = None
    url = _encode_url(url)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            last = exc
        except Exception as exc:  # URLError, timeout, incomplete read
            last = exc
        time.sleep(min(2.0 * (attempt + 1), 8.0))
    raise RuntimeError(f"{url}: {last}")


def _get_json(url: str) -> dict | None:
    raw = _get(url)
    if raw is None:
        return None
    return json.loads(raw.decode("utf-8-sig"))


def enumerate_sessions(years: tuple[int, ...], wanted_types: set[str]) -> list[dict]:
    out: list[dict] = []
    for year in years:
        try:
            index = _get_json(f"{BASE}/{year}/Index.json")
        except Exception as exc:
            _log(f"  [{year}] year index unavailable: {exc}")
            continue
        if not index:
            _log(f"  [{year}] year index absent")
            continue
        meetings = index.get("Meetings", [])
        n = 0
        for meeting in meetings:
            for session in meeting.get("Sessions", []):
                path = session.get("Path")
                stype = session.get("Type")
                if not path or stype not in wanted_types:
                    continue
                out.append({
                    "year": year,
                    "meeting": meeting.get("Name"),
                    "session_key": session.get("Key"),
                    "session_type": stype,
                    "session_name": session.get("Name"),
                    "start": session.get("StartDate"),
                    "path": path.strip("/"),
                })
                n += 1
        _log(f"  [{year}] {len(meetings)} meetings, {n} sessions selected")
    return out


def session_is_done(out_dir: Path) -> bool:
    m = out_dir / "_ingest_manifest.json"
    if not m.exists():
        return False
    try:
        return bool(json.loads(m.read_text()).get("complete"))
    except Exception:
        return False


# CarData.z and Position.z are the bulk of a session and contribute nothing to a stint-level long-run
# pace estimate, which is the only reason practice is being fetched at all.
HEAVY_FEEDS = ("CarData.z", "Position.z")


def fetch_one(session: dict, root: Path, light: bool = False) -> dict:
    path = session["path"]
    out_dir = root / path
    if session_is_done(out_dir):
        return {**session, "skipped": True, "bytes": 0, "artifacts": 0}

    out_dir.mkdir(parents=True, exist_ok=True)
    index = _get_json(f"{BASE}/{path}/Index.json")
    if not index:
        return {**session, "error": "no Index.json", "bytes": 0, "artifacts": 0}
    available = set(index.get("Feeds", {}))

    artifacts: list[dict] = []

    def store(local: str, payload: bytes) -> None:
        (out_dir / local).write_bytes(payload)
        artifacts.append({
            "artifact": local,
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        })

    store("Index.json", json.dumps(index).encode())

    archive_complete = False
    for feed in FEEDS:
        if feed not in available or (light and feed in HEAVY_FEEDS):
            continue
        for suffix in (".json", ".jsonStream"):
            try:
                payload = _get(f"{BASE}/{path}/{feed}{suffix}")
            except Exception as exc:
                return {**session, "error": f"{feed}{suffix}: {exc}",
                        "bytes": sum(a["bytes"] for a in artifacts), "artifacts": len(artifacts)}
            if payload is None:
                continue
            store(f"{feed}{suffix}", payload)
            if feed == "ArchiveStatus" and suffix == ".json":
                try:
                    body = json.loads(payload.decode("utf-8-sig"))
                    archive_complete = body.get("Status") == "Complete"
                except Exception:
                    archive_complete = False

    total = sum(a["bytes"] for a in artifacts)
    manifest = {
        **{k: session[k] for k in ("year", "meeting", "session_key", "session_type", "session_name", "start")},
        "session_path": path,
        "source_base": BASE,
        "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "archive_status_complete": archive_complete,
        # Only a session whose upstream archive reads Complete is marked done; anything else is
        # re-fetched next run rather than silently frozen as a truncated corpus entry.
        "complete": archive_complete,
        "artifact_count": len(artifacts),
        "total_bytes": total,
        "artifacts": sorted(artifacts, key=lambda a: a["artifact"]),
    }
    (out_dir / "_ingest_manifest.json").write_text(json.dumps(manifest, indent=2))
    return {**session, "bytes": total, "artifacts": len(artifacts), "complete": archive_complete}


def plan(sessions: list[dict]) -> None:
    """Size the corpus by HEADing one representative session per (year, type)."""
    _log("\nsizing a representative session per (year, session_type) …")
    seen: dict[tuple, int] = {}
    for s in sessions:
        key = (s["year"], s["session_type"])
        if key in seen:
            continue
        total = 0
        index = _get_json(f"{BASE}/{s['path']}/Index.json") or {}
        for feed in FEEDS:
            if feed not in index.get("Feeds", {}):
                continue
            for suffix in (".json", ".jsonStream"):
                try:
                    req = urllib.request.Request(
                        f"{BASE}/{s['path']}/{feed}{suffix}", headers={"User-Agent": UA}, method="HEAD"
                    )
                    with urllib.request.urlopen(req, timeout=30) as r:
                        total += int(r.headers.get("Content-Length") or 0)
                except Exception:
                    pass
        seen[key] = total
        _log(f"  {s['year']} {s['session_type']:<11} ~{total / 1e6:6.1f} MB  ({s['meeting']})")

    counts: dict[tuple, int] = {}
    for s in sessions:
        counts[(s["year"], s["session_type"])] = counts.get((s["year"], s["session_type"]), 0) + 1
    est = sum(counts[k] * seen.get(k, 0) for k in counts)
    _log(f"\n  sessions: {len(sessions)}")
    _log(f"  estimated total: {est / 1e9:.2f} GB")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="~/.algenta/f1/raw")
    ap.add_argument("--years", default=",".join(str(y) for y in DEFAULT_YEARS))
    ap.add_argument("--session-types", default="Race,Qualifying,Practice")
    ap.add_argument("--light", action="store_true",
                    help="timing feeds only, skipping CarData.z/Position.z. Practice is fetched for "
                         "long-run pace, and the per-sample channels contribute nothing to that")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    root = Path(args.root).expanduser()
    years = tuple(int(y) for y in args.years.split(",") if y.strip())
    types = {t.strip() for t in args.session_types.split(",") if t.strip()}

    _log(f"enumerating years {years} for types {sorted(types)}")
    sessions = enumerate_sessions(years, types)
    if args.limit:
        sessions = sessions[: args.limit]

    if args.plan:
        plan(sessions)
        return 0

    todo = [s for s in sessions if not session_is_done(root / s["path"])]
    _log(f"\n{len(sessions)} sessions, {len(sessions) - len(todo)} already complete, {len(todo)} to fetch")

    done = failed = skipped = 0
    total_bytes = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch_one, s, root, args.light): s for s in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            s = futures[fut]
            try:
                r = fut.result()
            except Exception as exc:
                failed += 1
                _log(f"  [{i}/{len(todo)}] FAIL {s['path']}: {exc}")
                continue
            if r.get("skipped"):
                skipped += 1
                continue
            if r.get("error"):
                failed += 1
                _log(f"  [{i}/{len(todo)}] ERR  {s['path']}: {r['error']}")
                continue
            done += 1
            total_bytes += r["bytes"]
            flag = "" if r.get("complete") else "  (archive INCOMPLETE — will refetch)"
            _log(
                f"  [{i}/{len(todo)}] {s['year']} {s['session_type']:<11} "
                f"{r['artifacts']:>2} artifacts {r['bytes'] / 1e6:7.1f} MB  {s['meeting']}{flag}"
            )

    dt = time.time() - t0
    _log(
        f"\ndone: {done} fetched, {skipped} skipped, {failed} failed, "
        f"{total_bytes / 1e9:.2f} GB in {dt / 60:.1f} min"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
