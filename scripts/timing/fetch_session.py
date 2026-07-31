#!/usr/bin/env python3
"""Fetch one F1 live-timing session's raw feeds into the immutable ingest root.

Transport only. This writes raw bytes verbatim plus a content-addressed sidecar
manifest; it never parses or derives anything. Decoding is a Mojo kernel.

Uses urllib from the stdlib rather than httpx: the ``raw_egress`` guard forbids
constructing httpx clients under ``apps/``, and a corpus-pull tool has no business
carrying the service egress surface. The live SignalR path is a separate,
egress-guarded service module.

Usage:
    python3 scripts/timing/fetch_session.py \
        --session 2026/2026-07-26_Hungarian_Grand_Prix/2026-07-26_Race \
        --root ~/.algenta/f1/raw
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://livetiming.formula1.com/static"

# The strategy-relevant subset of the 33 available feeds. TeamRadio, AudioStreams
# and ContentStreams are excluded (legal + storage surface, no strategy value);
# ChampionshipPrediction is excluded because it is a third-party model output, not
# an observation, and ingesting it risks contaminating our own probabilities.
FEEDS = (
    "SessionInfo",
    "SessionStatus",
    "SessionData",
    "DriverList",
    "LapCount",
    "LapSeries",
    "TimingData",
    "TimingDataF1",
    "TimingAppData",
    "TimingStats",
    "CurrentTyres",
    "TyreStintSeries",
    "PitStop",
    "PitStopSeries",
    "PitLaneTimeCollection",
    "OvertakeSeries",
    "TrackStatus",
    "RaceControlMessages",
    "WeatherData",
    "WeatherDataSeries",
    "DriverRaceInfo",
    "ExtrapolatedClock",
    "Heartbeat",
    "CarData.z",
    "Position.z",
)

UA = "algenta-timing-ingest/0.1 (+research)"


def _get(url: str, *, timeout: float = 120.0, retries: int = 3) -> bytes | None:
    """Fetch a URL, returning None on a 404 (feed absent for this session)."""
    last: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            last = exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last}")


# Practice sessions are fetched for LONG-RUN PACE only, so the heavy per-sample channels are not worth
# their bytes: CarData.z and Position.z are the bulk of a session and contribute nothing to a stint-level
# pace estimate. Restricting to the timing feeds turns a ~3.7 GB fetch into a fraction of that.
LIGHT_FEEDS = ("SessionInfo", "SessionStatus", "SessionData", "DriverList", "LapCount", "LapSeries",
               "TimingData", "TimingDataF1", "TimingAppData", "TimingStats", "CurrentTyres",
               "TyreStintSeries", "TrackStatus", "RaceControlMessages", "WeatherData",
               "ExtrapolatedClock", "Heartbeat", "ArchiveStatus")


def fetch_session(session_path: str, root: Path, feeds: tuple = ()) -> dict[str, object]:
    session_path = session_path.strip("/")
    out_dir = root / session_path
    out_dir.mkdir(parents=True, exist_ok=True)

    artifacts: list[dict[str, object]] = []

    index = _get(f"{BASE}/{session_path}/Index.json")
    if index is None:
        raise RuntimeError(f"no Index.json at {session_path}")
    available = set(json.loads(index.decode("utf-8-sig")).get("Feeds", {}))

    targets: list[tuple[str, str]] = [("Index.json", "Index.json")]
    for feed in (feeds or FEEDS):
        if feed not in available:
            print(f"  [skip] {feed}: not offered for this session", file=sys.stderr)
            continue
        targets.append((f"{feed}.json", f"{feed}.json"))
        targets.append((f"{feed}.jsonStream", f"{feed}.jsonStream"))

    for remote, local in targets:
        payload = _get(f"{BASE}/{session_path}/{remote}")
        if payload is None:
            continue
        (out_dir / local).write_bytes(payload)
        artifacts.append(
            {
                "artifact": local,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "has_bom": payload[:3] == b"\xef\xbb\xbf",
            }
        )
        print(f"  {local:34} {len(payload):>10,} B", file=sys.stderr)

    manifest = {
        "session_path": session_path,
        "source_base": BASE,
        "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "artifact_count": len(artifacts),
        "total_bytes": sum(int(a["bytes"]) for a in artifacts),
        "artifacts": sorted(artifacts, key=lambda a: str(a["artifact"])),
    }
    manifest["manifest_sha256"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()
    ).hexdigest()
    (out_dir / "_ingest_manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True, help="e.g. 2026/2026-07-26_Hungarian_Grand_Prix/2026-07-26_Race")
    ap.add_argument("--root", default="~/.algenta/f1/raw")
    args = ap.parse_args()

    root = Path(args.root).expanduser()
    m = fetch_session(args.session, root)
    print(
        f"\n{m['artifact_count']} artifacts, {int(m['total_bytes']):,} bytes "
        f"→ {root / str(m['session_path'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
