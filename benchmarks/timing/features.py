#!/usr/bin/env python3
"""As-of feature engineering for the pre-race pace prior.

WHY THE FEATURES ARE SELECTED BY THE SIMULATION

The Murphy decomposition localises the remaining error precisely: reliability is ~0.0005 and resolution
is ~0.019, so the model is honest about its uncertainty and short on DISCRIMINATION. Discrimination in a
pre-race forecast comes from the pace prior, not from the simulator — a better simulator propagating a
blunt prior cannot separate cars that the prior does not separate.

So these features exist to sharpen that prior, and their weights are searched by the GA against the
SIMULATION's held-out objective rather than fitted to pace RMSE. Those are different targets and they
disagree: fitting a prior to minimise pace error optimises a proxy, while what the board is scored on is
a win probability after the prior has been pushed through traffic, tyre life, neutralisations and
retirement. A feature that lowers pace RMSE can still cost skill once propagated, and only the
simulation can say so.

EVERY FEATURE IS AS-OF. Walk-forward strictly: a race's features are built from races that finished
BEFORE it, and never from its own result. The one same-weekend source is practice, which genuinely
precedes the race. Invariant 4 applies to feature construction exactly as it applies to replay.

Features, and what each is meant to add:

  grid_centred   starting slot, zero-meaned per race. Centring matters: an uncentred slot term carries a
                 systematic offset against a field-median-relative target and scored R^2 -0.712 against
                 +0.408 centred, which is a property of the encoding rather than of grid.
  hist_pace      EWMA of the car's own relative race pace. The single strongest history signal.
  mate_pace      the team-mate's EWMA. Shared machinery, so it carries car performance separately from
                 driver performance, and it covers a driver with little history of their own.
  team_pace      constructor-level EWMA across both cars.
  circuit_pace   the car's EWMA at THIS circuit only. Teams have circuit-type strengths that a global
                 average washes out.
  form_trend     fast EWMA minus slow EWMA: is the car improving or falling back? Level and trend are
                 different quantities and a single EWMA carries only the level.
  prior_races    how much history exists, so the search can discount a thin estimate rather than trust
                 it equally.
  practice_pace  long-run pace from this weekend's practice sessions. This is what a team's own race
                 engineers use to estimate race pace, and it is the only feature here observed on the
                 actual car, on the actual circuit, in the actual conditions.

MEASURED OUTCOME, recorded because the negative result is the useful part. Practice long-run pace
correlates only 0.137 with race pace against 0.657 for a centred grid slot and 0.611 for constructor
history. Six extraction variants were tried -- fastest versus longest stint, FP2 only versus all sessions,
with and without per-session normalisation -- and every one lands between 0.069 and 0.138.

The reason is structural rather than fixable by better extraction: a long run's pace is dominated by FUEL
LOAD, which the team chooses and public timing never publishes. Teams can use their own practice data for
this precisely because they know the fuel; we do not, and the signal is swamped. This is the second
same-weekend hypothesis to fail after qualifying gap (0.099 against grid's 0.339), and both failed for the
same reason -- the observable is contaminated by a choice we cannot see.

The weight stays in the search rather than being dropped. If it is worthless the GA drives it toward zero
and ga_diversity reports it UNIDENTIFIED, which is the discipline doing its job; hand-removing a feature
on a proxy correlation would pre-empt the objective that is supposed to decide.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq

FROZEN_TEST_SEASON = 2025

# A practice stint long enough to be a race-pace read rather than a qualifying simulation or an out-lap.
LONG_RUN_MIN_LAPS = 5

FEATURES = ("grid_centred", "hist_pace", "mate_pace", "team_pace", "circuit_pace",
            "form_trend", "prior_races", "practice_pace")


def _read_drivers(session: Path) -> dict[int, str]:
    dl = session / "DriverList.json"
    if not dl.exists():
        return {}
    raw = dl.read_bytes()
    raw = raw[3:] if raw[:3] == b"\xef\xbb\xbf" else raw
    try:
        d = json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return {}
    return {int(k): str(v.get("TeamName") or "?") for k, v in d.items() if k.isdigit()}


def _green_median(session: Path) -> dict[int, float]:
    """Median green-flag lap per car, excluding in/out laps. The pace read for a session."""
    lp = session / "_laps.parquet"
    if not lp.exists():
        return {}
    t = pq.read_table(lp).to_pydict()
    per: dict[int, list[float]] = defaultdict(list)
    for i in range(len(t["lap_number"])):
        if (t["is_green_lap"][i] and t["lap_time_s"][i]
                and not t["in_pit"][i] and not t["pit_out"][i]):
            per[t["car_number"][i]].append(t["lap_time_s"][i])
    return {c: statistics.median(v) for c, v in per.items() if len(v) >= 8}


def practice_long_run(event_dir: Path) -> dict[int, float]:
    """Long-run pace per car from this weekend's practice, relative to the field.

    A practice session mixes qualifying simulations, aero rakes, out-laps and race runs. The race read is
    the LONG stint: consecutive green laps on one set. Taking a session median instead would be dominated
    by low-fuel qualifying simulations, which rank cars differently from race pace — the thing being
    predicted.
    """
    runs: dict[int, list[float]] = defaultdict(list)
    for prac in sorted(event_dir.glob("*_Practice*")):
        lp = prac / "_laps.parquet"
        if not lp.exists():
            continue
        t = pq.read_table(lp).to_pydict()
        seq: dict[int, list[tuple[int, float, int]]] = defaultdict(list)
        for i in range(len(t["lap_number"])):
            ln = t["lap_number"][i]
            if not ln or not t["lap_time_s"][i] or not t["is_green_lap"][i]:
                continue
            if t["in_pit"][i] or t["pit_out"][i]:
                continue
            seq[t["car_number"][i]].append((ln, t["lap_time_s"][i], t["stint_index"][i] or 0))
        for car, rows in seq.items():
            rows.sort()
            by_stint: dict[int, list[float]] = defaultdict(list)
            for _ln, lt, si in rows:
                by_stint[si].append(lt)
            for laps in by_stint.values():
                if len(laps) >= LONG_RUN_MIN_LAPS:
                    # trim the fastest and slowest: a long run still contains a push lap and a lift
                    laps = sorted(laps)[1:-1] or laps
                    runs[car].append(statistics.median(laps))
    if len(runs) < 6:
        return {}
    best = {c: min(v) for c, v in runs.items()}
    ref = statistics.median(best.values())
    return {c: v - ref for c, v in best.items()}


def build(root: Path, seasons: set[int], ewma_fast: float = 0.5,
          ewma_slow: float = 0.15) -> list[dict]:
    """One row per car-race with as-of features and the scorer-only outcome.

    Walk-forward: every feature is updated only AFTER a race has been emitted, so a race can never see
    its own result. The prior state carried between races is the entire memory.
    """
    if FROZEN_TEST_SEASON in seasons:
        raise ValueError(f"{FROZEN_TEST_SEASON} is the frozen final test season")

    races = sorted(p.parent for p in root.glob("*/*/*_Race/_laps.parquet")
                   if int(p.parts[-4]) in seasons)

    fast: dict[int, float] = {}
    slow: dict[int, float] = {}
    seen: dict[int, int] = defaultdict(int)
    team_of: dict[int, str] = {}
    team_hist: dict[str, float] = {}
    circuit_hist: dict[tuple[int, str], float] = {}

    out: list[dict] = []
    race_index = 0
    for session in races:
        event = session.parent
        circuit = event.name.split("_", 1)[-1]
        season = int(session.parts[-3])  # .../raw/<year>/<event>/<session>
        med = _green_median(session)
        if len(med) < 12:
            continue
        drivers = _read_drivers(session)
        prac = practice_long_run(event)

        t = pq.read_table(session / "_laps.parquet").to_pydict()
        grid: dict[int, int] = {}
        finish: dict[int, tuple] = {}
        for i in range(len(t["lap_number"])):
            c, ln = t["car_number"][i], t["lap_number"][i]
            if not ln:
                continue
            if t["grid_position"][i] and c not in grid:
                grid[c] = t["grid_position"][i]
            cur = finish.get(c)
            if cur is None or ln > cur[0]:
                finish[c] = (ln, t["position"][i] or 99, t["retired"][i] or 0)
        if not grid:
            continue
        ranked = sorted(finish.items(), key=lambda kv: (kv[1][2], -kv[1][0], kv[1][1]))
        final = {c: i + 1 for i, (c, _v) in enumerate(ranked)}

        cars = [c for c in med if c in grid]
        n = len(cars)
        if n < 12:
            continue
        mid = (n + 1) / 2.0
        # team-mates as of this race
        mates: dict[int, list[int]] = defaultdict(list)
        for c in cars:
            tm = drivers.get(c, "?")
            if tm != "?":
                mates[tm].append(c)

        for c in cars:
            tm = drivers.get(c, "?")
            mate_vals = [fast[k] for k in mates.get(tm, ()) if k != c and k in fast]
            out.append({
                "race": race_index, "season": season, "circuit": circuit, "car": c,
                "grid_centred": 0.120 * (grid[c] - mid),
                "hist_pace": fast.get(c, 0.0),
                "mate_pace": statistics.mean(mate_vals) if mate_vals else fast.get(c, 0.0),
                "team_pace": team_hist.get(tm, fast.get(c, 0.0)),
                "circuit_pace": circuit_hist.get((c, circuit), fast.get(c, 0.0)),
                "form_trend": fast.get(c, 0.0) - slow.get(c, 0.0),
                "prior_races": float(min(seen[c], 40)) / 40.0,
                "practice_pace": prac.get(c, 0.0),
                "has_practice": 1.0 if c in prac else 0.0,
                # scorer-only
                "grid": float(grid[c]), "position": float(final.get(c, 99)),
                "win": 1.0 if final.get(c) == 1 else 0.0,
                "rel_pace": med[c] - statistics.median(med.values()),
            })

        race_index += 1

        # ── update the carried state AFTER emitting, never before ──────────────
        field_med = statistics.median(med.values())
        per_team: dict[str, list[float]] = defaultdict(list)
        for c in cars:
            rel = med[c] - field_med
            fast[c] = rel if c not in fast else (1 - ewma_fast) * fast[c] + ewma_fast * rel
            slow[c] = rel if c not in slow else (1 - ewma_slow) * slow[c] + ewma_slow * rel
            seen[c] += 1
            team_of[c] = drivers.get(c, "?")
            key = (c, circuit)
            circuit_hist[key] = rel if key not in circuit_hist else 0.5 * circuit_hist[key] + 0.5 * rel
            if drivers.get(c, "?") != "?":
                per_team[drivers[c]].append(rel)
        for tm, vals in per_team.items():
            v = statistics.mean(vals)
            team_hist[tm] = v if tm not in team_hist else 0.6 * team_hist[tm] + 0.4 * v
    return out


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="~/.algenta/f1/raw")
    ap.add_argument("--seasons", default="2019,2020,2021,2023,2024")
    args = ap.parse_args()
    rows = build(Path(args.root).expanduser(),
                 {int(x) for x in args.seasons.split(",") if x.strip()})
    print(f"{len(rows)} car-races, {len({(r['season'], r['circuit']) for r in rows})} races")
    have = sum(1 for r in rows if r["has_practice"])
    print(f"practice long-run pace available for {have} ({100*have/max(1,len(rows)):.0f}%)")

    # univariate out-of-sample correlation with the outcome each feature is meant to predict
    print(f"\n{'feature':<16} {'corr vs rel_pace':>17} {'corr vs finish':>15}")
    for f in FEATURES:
        xs = [r[f] for r in rows]
        if len(set(xs)) < 3:
            print(f"{f:<16} {'(constant)':>17}")
            continue
        for target, label in (("rel_pace", None), ("position", None)):
            pass
        def corr(a, b):
            n = len(a); ma = sum(a) / n; mb = sum(b) / n
            va = sum((x - ma) ** 2 for x in a); vb = sum((y - mb) ** 2 for y in b)
            if va <= 0 or vb <= 0:
                return 0.0
            return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb)
        print(f"{f:<16} {corr(xs, [r['rel_pace'] for r in rows]):>17.3f} "
              f"{corr(xs, [r['position'] for r in rows]):>15.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
