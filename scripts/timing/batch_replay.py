#!/usr/bin/env python3
"""Build event logs and derived state for every ingested session.

Runs build_event_log then replay_state over the corpus, in parallel across sessions. Each session is
independent, so a failure isolates to that session rather than aborting the corpus.

Resume: a session with an up-to-date _laps.parquet is skipped unless --force.

Usage:
    python3 scripts/timing/batch_replay.py --session-types Race
    python3 scripts/timing/batch_replay.py --workers 6 --force
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

_lock = threading.Lock()


def process(session_dir_s: str, force: bool) -> dict:
    from build_event_log import build as build_log
    from replay_state import replay

    d = Path(session_dir_s)
    try:
        laps = d / "_laps.parquet"
        log = d / "_event_log.parquet"
        if not force and laps.exists() and log.exists():
            return {"dir": session_dir_s, "skipped": True}
        info = build_log(d)
        st = replay(d)
        return {
            "dir": session_dir_s, "session_key": info["session_key"], "season": info["season"],
            "events": info["events"], "digest": info["logical_digest"],
            "laps": st["laps"], "stints": st["stints"], "pits": st["pit_events"],
            "cars": st["cars"], "total_laps": st["total_laps"],
        }
    except Exception as exc:
        return {"dir": session_dir_s, "error": f"{type(exc).__name__}: {exc}",
                "trace": traceback.format_exc()[-400:]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="~/.algenta/f1/raw")
    ap.add_argument("--session-types", default="Race")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    root = Path(args.root).expanduser()
    want = {t.strip() for t in args.session_types.split(",") if t.strip()}

    sessions = []
    for m in sorted(root.rglob("_ingest_manifest.json")):
        try:
            man = json.loads(m.read_text())
        except Exception:
            continue
        if man.get("session_type") not in want or not man.get("complete"):
            continue
        sessions.append(str(m.parent))
    if args.limit:
        sessions = sessions[: args.limit]

    print(f"{len(sessions)} sessions ({', '.join(sorted(want))})", file=sys.stderr)
    done = skipped = failed = 0
    t0 = time.time()
    manifest: list[dict] = []

    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(process, s, args.force): s for s in sessions}
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            if r.get("skipped"):
                skipped += 1
                continue
            if r.get("error"):
                failed += 1
                print(f"  [{i}/{len(sessions)}] FAIL {Path(r['dir']).name}: {r['error']}",
                      file=sys.stderr)
                continue
            done += 1
            manifest.append(r)
            name = "/".join(Path(r["dir"]).parts[-2:])
            print(f"  [{i}/{len(sessions)}] {r['season']} key={r['session_key']:<6} "
                  f"{r['events']:>7,} events  {r['laps']:>5} laps  {r['stints']:>3} stints  "
                  f"{r['pits']:>3} pits  {r['cars']:>2} cars   {name}", file=sys.stderr)

    out = root / "_corpus_manifest.json"
    out.write_text(json.dumps({
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session_types": sorted(want),
        "sessions": sorted(manifest, key=lambda r: (r["season"], r["session_key"])),
    }, indent=2))
    print(f"\n{done} built, {skipped} skipped, {failed} failed in {(time.time()-t0)/60:.1f} min",
          file=sys.stderr)
    print(f"manifest -> {out}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
