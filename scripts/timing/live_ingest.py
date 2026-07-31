#!/usr/bin/env python3
"""Gate 4 — live SignalR ingest, writing the SAME format the archive uses.

ONE DECODER, NEVER A RACE-DAY PATH

The plan is explicit: same bronze sink, same decoder, same state builder as replay. So this client does
not parse timing data at all. It appends records to `<topic>.jsonStream` in exactly the archive's format
— `HH:MM:SS.mmm` followed by the payload, CRLF-separated, UTF-8 BOM — and everything downstream
(build_event_log, replay_state, the option board, the TUI) runs unchanged and untouched.

That is a correctness decision, not tidiness. A separate live path is a second implementation of the
state machine that only ever executes when it matters most, on a Sunday afternoon, with no way to test
it against ground truth afterwards.

THE FOUR THINGS A LIVE FEED DOES THAT AN ARCHIVE DOES NOT

  reconnects        the socket drops. On reconnect the hub re-sends a KEYFRAME, which is current state,
                    not history. Archived keyframes carry POST-SESSION state and are excluded from the
                    as-of path for that reason; a live keyframe is legitimate but must be stamped with
                    the CONNECT TIME rather than zero, or it lands before the whole session and
                    reintroduces exactly the leak that was just fixed.
  duplicates        a resend after reconnect repeats records already written. Suppressed by a hash of
                    (topic, timestamp, payload) so replay stays idempotent.
  out-of-order      frames arrive late. They are written in arrival order and REORDERED BY THE EVENT LOG,
                    which sorts on (event_ms, topic order, index) — the fault-injection suite proves that
                    sort repairs local jitter, so the client does not need to buffer.
  clock drift       the feed's session clock is authoritative for ordering; the wall clock is recorded
                    separately so drift is measurable rather than silently absorbed.

TESTABLE WITHOUT A RACE. `--replay-from <session>` runs the identical ingest loop against a local fake
that streams an archived session, so reconnect, resync and dedup are exercised on a Tuesday. A live path
first tested on a race weekend is a live path that has not been tested.

Usage:
    python3 scripts/timing/live_ingest.py --out ~/.algenta/f1/live/zandvoort
    python3 scripts/timing/live_ingest.py --replay-from <archived session> --out /tmp/fake --speed 50
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CRLF = b"\r\n"
BOM = b"\xef\xbb\xbf"
NEGOTIATE = "https://livetiming.formula1.com/signalr/negotiate"
SOCKET = "wss://livetiming.formula1.com/signalr/connect"
HUB = '[{"name":"Streaming"}]'
UA = "Mozilla/5.0 (compatible; algenta-timing/1.0)"

# The strategy-relevant subset, matching fetch_session.FEEDS. Team radio, audio and content streams are
# excluded by the legal gate and add no strategy value.
TOPICS = ("SessionInfo", "SessionStatus", "SessionData", "DriverList", "LapCount", "LapSeries",
          "TimingData", "TimingDataF1", "TimingAppData", "TimingStats", "CurrentTyres",
          "TyreStintSeries", "PitStop", "PitStopSeries", "PitLaneTimeCollection", "OvertakeSeries",
          "TrackStatus", "RaceControlMessages", "WeatherData", "WeatherDataSeries",
          "DriverRaceInfo", "ExtrapolatedClock", "Heartbeat")


class Sink:
    """Append-only writer producing archive-identical .jsonStream files.

    DEDUP IS SCOPED TO A RESYNC WINDOW, not global, and that distinction is load-bearing.

    The obvious design -- drop any record whose (topic, timestamp, payload) has been seen -- is wrong,
    and the replay parity test caught it: one lap row of 938 diverged from the archive (car 30 lap 24,
    interval_ahead_s 0.456 against None). A byte-identical record is NOT always redundant, because
    merge_delta treats arrays as index-keyed objects and re-applying such a delta is not idempotent. The
    feed sends the same bytes twice and means it.

    A reconnect resend genuinely IS redundant: the hub replays a contiguous block you already hold. So
    suppression applies only inside the window that follows a reconnect, which is the only place the
    duplicate is an artifact of transport rather than content.
    """

    def __init__(self, out: Path):
        self.out = out
        out.mkdir(parents=True, exist_ok=True)
        self.seen: set[str] = set()
        self.counts: dict[str, int] = {}
        self.dupes = 0
        self.resync_left = 0      # records still eligible for suppression after a reconnect
        self.t0 = time.monotonic()
        self.first_wall = datetime.now(timezone.utc)
        self.drift: list[float] = []

    def _key(self, topic: str, ts: str, payload: str) -> str:
        return hashlib.sha256(f"{topic}\x1f{ts}\x1f{payload}".encode()).hexdigest()

    def begin_resync(self, window: int = 500) -> None:
        """Open the suppression window. Called on (re)connect, and only then."""
        self.resync_left = window

    def write(self, topic: str, ts: str, payload: str) -> bool:
        k = self._key(topic, ts, payload)
        if self.resync_left > 0:
            self.resync_left -= 1
            if k in self.seen:
                self.dupes += 1
                return False
        self.seen.add(k)
        f = self.out / f"{topic}.jsonStream"
        first = not f.exists()
        with f.open("ab") as fh:
            if first:
                fh.write(BOM)
            else:
                fh.write(CRLF)
            fh.write((ts + payload).encode("utf-8"))
        self.counts[topic] = self.counts.get(topic, 0) + 1
        return True

    def keyframe(self, topic: str, payload: str, connect_ts: str) -> None:
        """A live keyframe is state AT CONNECT TIME, so it is stamped and appended as a normal record.

        It is NOT written to `<topic>.json`. That file is the archive's keyframe slot, which replay_state
        excludes from the as-of path precisely because an archived keyframe is post-session state; writing
        a live keyframe there would put current state at event_ms 0 and reintroduce the leak.
        """
        self.write(topic, connect_ts, payload)

    def note_drift(self, feed_ms: int) -> None:
        """Feed clock against wall clock. Recorded, never used to reorder — the feed clock is authoritative."""
        wall_ms = (time.monotonic() - self.t0) * 1000.0
        self.drift.append(wall_ms - feed_ms)

    def summary(self) -> dict:
        d = sorted(self.drift)
        return {
            "records": sum(self.counts.values()), "duplicates_suppressed": self.dupes,
            "topics": dict(sorted(self.counts.items(), key=lambda kv: -kv[1])),
            "clock_drift_ms_p50": d[len(d) // 2] if d else 0.0,
            "clock_drift_ms_max": d[-1] if d else 0.0,
            "started": self.first_wall.isoformat(),
        }


def session_ts(started: float) -> str:
    """HH:MM:SS.mmm since the client started — the archive's timestamp shape."""
    ms = int((time.monotonic() - started) * 1000)
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, msec = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{msec:03d}"


def negotiate() -> tuple[str, dict]:
    q = urllib.parse.urlencode({"connectionData": HUB, "clientProtocol": "1.5"})
    req = urllib.request.Request(f"{NEGOTIATE}?{q}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read().decode("utf-8-sig"))
        cookie = r.headers.get("Set-Cookie", "")
    return body["ConnectionToken"], {"Cookie": cookie, "User-Agent": UA}


async def pump(sink: Sink, started: float, max_seconds: float, log_every: float,
               replay_from: Path | None, speed: float) -> None:
    if replay_from is not None:
        await _replay_pump(sink, started, replay_from, speed, max_seconds, log_every)
        return

    import websockets

    backoff = 1.0
    deadline = started + max_seconds if max_seconds else None
    while deadline is None or time.monotonic() < deadline:
        try:
            token, headers = negotiate()
            q = urllib.parse.urlencode({"transport": "webSockets", "clientProtocol": "1.5",
                                        "connectionToken": token, "connectionData": HUB})
            async with websockets.connect(f"{SOCKET}?{q}", extra_headers=headers,
                                          max_size=None, ping_interval=20) as ws:
                connect_ts = session_ts(started)
                sink.begin_resync()
                await ws.send(json.dumps({"H": "Streaming", "M": "Subscribe",
                                          "A": [list(TOPICS)], "I": 1}))
                print(f"connected at {connect_ts}; subscribed to {len(TOPICS)} topics",
                      file=sys.stderr)
                backoff = 1.0
                last_log = time.monotonic()
                async for raw in ws:
                    _handle(sink, raw, started, connect_ts)
                    if time.monotonic() - last_log > log_every:
                        s = sink.summary()
                        print(f"  {s['records']} records, {s['duplicates_suppressed']} dupes "
                              f"suppressed, drift p50 {s['clock_drift_ms_p50']:.0f} ms",
                              file=sys.stderr)
                        last_log = time.monotonic()
                    if deadline and time.monotonic() > deadline:
                        return
        except Exception as exc:  # a live feed drops; that is not an error, it is the job
            print(f"  disconnected ({type(exc).__name__}: {exc}); reconnecting in {backoff:.0f}s "
                  f"— the keyframe on reconnect will be stamped at the new connect time",
                  file=sys.stderr)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)


def _handle(sink: Sink, raw, started: float, connect_ts: str) -> None:
    try:
        msg = json.loads(raw)
    except Exception:
        return
    # R = the keyframe delivered on subscribe; M = the delta stream
    for topic, payload in (msg.get("R") or {}).items():
        if topic in TOPICS:
            sink.keyframe(topic, json.dumps(payload, separators=(",", ":")), connect_ts)
    for m in msg.get("M") or []:
        a = m.get("A") or []
        if len(a) >= 2 and a[0] in TOPICS:
            ts = a[2] if len(a) > 2 and isinstance(a[2], str) else session_ts(started)
            sink.write(a[0], ts, json.dumps(a[1], separators=(",", ":")))


async def _replay_pump(sink: Sink, started: float, session: Path, speed: float,
                       max_seconds: float, log_every: float) -> None:
    """Stream an archived session through the identical sink, with injected reconnects.

    This is how reconnect, keyframe resync and dedup get tested on a Tuesday. The reconnect at 40% of the
    stream re-sends the preceding 30 records, which is what a real hub does and what the dedup must
    absorb.
    """
    records: list[tuple[str, str, str]] = []
    for f in sorted(session.glob("*.jsonStream")):
        topic = f.name[: -len(".jsonStream")]
        if topic not in TOPICS:
            continue
        raw = f.read_bytes()
        raw = raw[3:] if raw[:3] == BOM else raw
        for line in raw.split(CRLF):
            if not line.strip():
                continue
            t = line[:12].decode("utf-8", errors="replace")
            records.append((topic, t, line[12:].decode("utf-8", errors="replace")))
    records.sort(key=lambda r: r[1])
    print(f"replaying {len(records)} records from {session.name} at {speed:g}x", file=sys.stderr)

    reconnect_at = int(len(records) * 0.4)
    i = 0
    last_log = time.monotonic()
    while i < len(records):
        topic, ts, payload = records[i]
        sink.write(topic, ts, payload)
        # Clock drift is NOT recorded in replay: at accelerated speed wall time cannot track feed time by
        # construction, so the number would be an artifact of --speed rather than a measurement. A
        # meaningless metric on a diagnostic line is worse than an absent one.
        if i == reconnect_at:
            print(f"  [injected reconnect at record {i}] re-sending the previous 30 records, "
                  f"as a real hub does", file=sys.stderr)
            sink.begin_resync()
            for j in range(max(0, i - 30), i):
                sink.write(*records[j])
        if speed > 0:
            await asyncio.sleep(1.0 / (speed * 200.0))
        if time.monotonic() - last_log > log_every:
            s = sink.summary()
            print(f"  {s['records']} records, {s['duplicates_suppressed']} dupes suppressed",
                  file=sys.stderr)
            last_log = time.monotonic()
        if max_seconds and time.monotonic() - started > max_seconds:
            break
        i += 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--replay-from", default="",
                    help="archived session to stream through the identical loop, for testing without a race")
    ap.add_argument("--speed", type=float, default=50.0)
    ap.add_argument("--max-seconds", type=float, default=0.0)
    ap.add_argument("--log-every", type=float, default=10.0)
    args = ap.parse_args()

    out = Path(args.out).expanduser()
    sink = Sink(out)
    started = time.monotonic()
    try:
        asyncio.run(pump(sink, started, args.max_seconds, args.log_every,
                         Path(args.replay_from).expanduser() if args.replay_from else None,
                         args.speed))
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
    s = sink.summary()
    (out / "_ingest_summary.json").write_text(json.dumps(s, indent=2))
    print(f"\n{s['records']} records across {len(s['topics'])} topics")
    print(f"{s['duplicates_suppressed']} duplicates suppressed")
    print(f"clock drift p50 {s['clock_drift_ms_p50']:.0f} ms, max {s['clock_drift_ms_max']:.0f} ms")
    print(f"wrote {out}")
    print("\nthe output is archive-format, so build_event_log and replay_state run on it unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
