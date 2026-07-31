#!/usr/bin/env python3
"""The append-only decision outbox, and its tamper-evidence chain.

WHY A RECORD OF WHAT WE PREDICTED IS NOT THE SAME AS EVIDENCE

Anyone can produce a file after a race saying what they would have predicted. What makes a prospective
claim worth anything to a sceptical reader is that the prediction was fixed BEFORE the outcome was
knowable and demonstrably has not moved since. So:

  every decision is one canonically-serialised row, hashed
  each row's hash includes the PREVIOUS row's hash, forming a chain
  the chain head is published EXTERNALLY before the outcome is known
  recomputing the chain from the stored rows must reproduce that head

An administrator with write access can still rewrite the file. What they cannot do is make the rewritten
file hash to a head that was already published, and that asymmetry is the whole point. Queryability comes
later from ClickHouse; the digest is what makes the record evidence.

THE OUTBOX IS ALSO AN ARCHITECTURAL BOUNDARY. The plan requires the decision runtime to hold no
ClickHouse route, credentials or client at all -- not by convention but structurally, because ClickHouse
stores corrected and final data and a decision path able to query it reintroduces look-ahead through the
storage layer. The runtime appends here; a separate shipper tails this file. This module therefore
imports nothing that could reach a database, and the boundary guard asserts that.

Each row records what a sceptic would need: what the engine knew (watermarks and state hash), which model
and commit produced it (config hash, theta source, rng_version), what it said (option probabilities,
paired deltas, simultaneous CIs, verdict), and when it was written.

Usage:
    python3 scripts/timing/decision_outbox.py --verify <outbox.jsonl>
    python3 scripts/timing/decision_outbox.py --head <outbox.jsonl>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

GENESIS = "0" * 64
OPTION_NAMES = ("STAY", "BOX_NOW", "BOX_PLUS_1", "BOX_PLUS_2")


def canonical(row: dict) -> bytes:
    """Deterministic serialisation. Sorted keys, no whitespace, the hash field excluded.

    A canonical form is required or the chain verifies only against the exact writer that produced it:
    dict ordering, float repr and separator choices would all otherwise change the hash without changing
    the content.
    """
    body = {k: v for k, v in row.items() if k not in ("row_hash",)}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()


def row_hash(row: dict, prev: str) -> str:
    h = hashlib.sha256()
    h.update(prev.encode())
    h.update(b"\x1e")
    h.update(canonical(row))
    return h.hexdigest()


class Outbox:
    """Append-only writer. One line per decision, fsynced, chained to its predecessor."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.prev = GENESIS
        self.count = 0
        if path.exists():
            for line in path.read_text().splitlines():
                if line.strip():
                    self.prev = json.loads(line)["row_hash"]
                    self.count += 1

    def append(self, *, session_key: str, decision_event_time: str, event_watermark: int,
               ingest_watermark: int, state_hash: str, config_hash: str, source_commit: str,
               corpus_version: str, rng_version: str, master_seed: int, theta_source: str,
               objective_version: str, target_car: int, target_rival: int, laps_remaining: int,
               replications: int, latency_ms: float, p_ahead: list, delta: list,
               ci_lo: list, ci_hi: list, recommended: int, verdict: int,
               crn_variance_ratio: float) -> str:
        """Write one decision. Returns the new chain head.

        decision_id is DETERMINISTIC over the inputs that identify the decision, so the same board
        computed twice yields the same id -- which is what lets a duplicate be detected rather than
        silently double-counted.
        """
        decision_id = hashlib.sha256(
            f"{session_key}\x1f{event_watermark}\x1f{ingest_watermark}\x1f{target_car}"
            f"\x1f{target_rival}\x1f{objective_version}\x1f{config_hash}\x1f{rng_version}".encode()
        ).hexdigest()
        row = {
            "decision_id": decision_id,
            "seq": self.count + 1,
            "prev_hash": self.prev,
            "written_at": datetime.now(timezone.utc).isoformat(),
            "session_key": session_key,
            "decision_event_time": decision_event_time,
            "event_time_watermark": event_watermark,
            "ingest_sequence_watermark": ingest_watermark,
            "state_hash": state_hash,
            "config_hash": config_hash,
            "source_commit": source_commit,
            "corpus_version": corpus_version,
            "rng_version": rng_version,
            "master_seed_commitment": hashlib.sha256(str(master_seed).encode()).hexdigest()[:32],
            "theta_source": theta_source,
            "objective_version": objective_version,
            "target_car": target_car,
            "target_rival": target_rival,
            "laps_remaining": laps_remaining,
            "replication_count": replications,
            "simulation_latency_ms": round(latency_ms, 3),
            "options": list(OPTION_NAMES),
            "p_ahead": [round(x, 6) for x in p_ahead],
            "delta_vs_stay": [round(x, 6) for x in delta],
            "ci_lo": [round(x, 6) for x in ci_lo],
            "ci_hi": [round(x, 6) for x in ci_hi],
            "crn_variance_ratio": round(crn_variance_ratio, 6),
            "recommended": OPTION_NAMES[recommended] if 0 <= recommended < 4 else str(recommended),
            "verdict": {0: "STAY", 1: "RECOMMENDED", 2: "INCONCLUSIVE"}.get(verdict, str(verdict)),
        }
        row["row_hash"] = row_hash(row, self.prev)
        # append + fsync: a decision that was computed but lost on a crash is worse than none, because
        # the gap in the sequence is indistinguishable from a decision never made
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self.prev = row["row_hash"]
        self.count += 1
        return self.prev


def verify(path: Path) -> tuple[bool, str, list[str]]:
    """Recompute the chain from the stored rows. Returns (ok, RECOMPUTED head, problems).

    The head is recomputed FORWARD from the content, never read from the last row. Following each row's
    stored hash would make the head whatever the final row claims -- a value an attacker edits along with
    everything else -- so an edit in the middle would be flagged locally while the head still matched the
    one published beforehand. Recomputing forward means a single altered byte anywhere propagates to the
    head, which is the property the external publication actually relies on.
    """
    problems: list[str] = []
    prev = GENESIS
    head = GENESIS
    seen: set[str] = set()
    n = 0
    for i, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        n += 1
        try:
            row = json.loads(line)
        except Exception as exc:
            problems.append(f"line {i}: unparseable ({exc})")
            continue
        if row.get("prev_hash") != prev:
            problems.append(f"line {i}: prev_hash does not match the preceding row — a row was "
                            f"inserted, removed or reordered")
        want = row_hash(row, prev)
        if row.get("row_hash") != want:
            problems.append(f"line {i}: row_hash does not match its content — the row was edited "
                            f"after it was written")
        if row.get("seq") != n:
            problems.append(f"line {i}: seq {row.get('seq')} against position {n}")
        if row.get("decision_id") in seen:
            problems.append(f"line {i}: duplicate decision_id — the same board was written twice")
        seen.add(row.get("decision_id"))
        prev = want          # the RECOMPUTED hash, so an edit propagates to the head
        head = prev
    return (not problems), head, problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("outbox")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--head", action="store_true")
    args = ap.parse_args()
    path = Path(args.outbox).expanduser()
    if not path.exists():
        print(f"no outbox at {path}", file=sys.stderr)
        return 2
    ok, head, problems = verify(path)
    if args.head:
        print(head)
        return 0 if ok else 1
    n = sum(1 for line in path.read_text().splitlines() if line.strip())
    print(f"{n} decisions in {path.name}")
    print(f"chain head {head}")
    if ok:
        print("chain intact — every row hashes to its content and to its predecessor")
        print("\nPublish this head externally BEFORE the outcome is known. A record that could have been")
        print("written afterwards is not evidence, however honest it happens to be.")
    else:
        print(f"\nCHAIN BROKEN — {len(problems)} problem(s):")
        for p in problems[:20]:
            print(f"  {p}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
