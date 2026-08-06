"""Turn the locally-archived professional car-racing timing corpus into a
per-car-per-race survival table: laps completed, a retirement event, and two
directly-observed covariates (starting grid position, prior-races experience).

Source: `~/.algenta/f1/raw`, decoded per-session `_laps.parquet` files spanning every
locally-fetched season (2019-2026 as of this writing, populated by a separate,
already-shipped ingest pipeline -- see `scripts/timing/fetch_corpus.py`). This script
only reads that corpus; it fetches and decodes nothing.

A car's last recorded row in a race session carries `lap_number` -- how many laps it
completed. That is duration. Event vs censoring needs a decision rule, and the
per-lap `retired` flag this corpus carries is NOT usable for it: checked directly, it is
1 exactly once across every session in the corpus, against a known ground truth of
multiple retirements in a single sampled session (see the sibling project's
`docs/timing/DATA_SOURCES.md`, which independently confirms 3 retirements in one probed
race via two other data sources). That field is not populated by this decoder path.

Retirement is instead read off the standard motor-racing classification rule: a car that
completes fewer than 90% of the laps the race winner completed did not finish; a car
within 90% is classified as a finisher even if lapped. This is a real, external,
citable rule (not invented for this benchmark), and it reproduces the known-good example
above exactly (three cars well under 90% of that race's winner-lap-count, correctly
flagged; every classified finisher, including lapped ones, correctly not flagged).

Usage: python3 build_motorsport_survival.py [root] [out_csv]
  (default root: ~/.algenta/f1/raw, default out: motorsport_survival.csv)
"""
import glob
import os
import sys

import pandas as pd
import pyarrow.parquet as pq


def main() -> None:
    root = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/.algenta/f1/raw")
    out_csv = sys.argv[2] if len(sys.argv) > 2 else "motorsport_survival.csv"

    sessions = sorted(glob.glob(os.path.join(root, "*", "*", "*_Race", "_laps.parquet")))
    print(f"{len(sessions)} race sessions found under {root}", file=sys.stderr)

    prior_races: dict[int, int] = {}
    rows = []
    n_sessions_used = 0

    for path in sessions:
        t = pq.read_table(path).to_pydict()
        n = len(t["lap_number"])
        if n == 0:
            continue
        finish: dict[int, int] = {}
        grid: dict[int, int] = {}
        for i in range(n):
            c, ln = t["car_number"][i], t["lap_number"][i]
            if not ln:
                continue
            if t["grid_position"][i] and c not in grid:
                grid[c] = t["grid_position"][i]
            if c not in finish or ln > finish[c]:
                finish[c] = ln
        if len(finish) < 10:
            continue

        winner_laps = max(finish.values())
        threshold = 0.90 * winner_laps
        n_sessions_used += 1
        for c, laps in finish.items():
            rows.append({
                "laps_completed": laps,
                "retired": 1 if laps < threshold else 0,
                "grid_position": grid.get(c),
                "prior_races": prior_races.get(c, 0),
            })
        for c in finish:
            prior_races[c] = prior_races.get(c, 0) + 1

    df = pd.DataFrame(rows)
    n_events = int(df["retired"].sum())
    print(
        f"sessions used: {n_sessions_used}  car-races: {len(df)}  "
        f"retirements(events): {n_events}  censored: {len(df) - n_events}  "
        f"event_rate: {df['retired'].mean():.4f}",
        file=sys.stderr,
    )
    complete = df.dropna(subset=["grid_position"])
    print(
        f"car-races with grid position present: {len(complete)} ({len(complete) / len(df):.1%})",
        file=sys.stderr,
    )

    df.to_csv(out_csv, index=False)
    print(f"wrote {out_csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
