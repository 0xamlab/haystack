#!/usr/bin/env python3
"""Pre-race oracle backtest across the corpus, scored in Mojo, with timing.

AS-OF DISCIPLINE. The oracle sees ONLY the starting grid. No lap times, no stint history, no final
classification -- nothing that was unknown before the lights went out. That is what makes this a
forecast rather than a retrodiction, and it is why the numbers are modest: the simulation has to earn
its skill over grid order alone.

Every probability comes from outcome_distribution in Mojo; every score from forecast_metrics in Mojo. Python
selects races, derives grid-based pace priors, and prints.

Baselines are mandatory. Beating a research paper while losing to "the pole-sitter wins" would be
meaningless, so the same metrics are computed for:
  * grid-order      -- pole wins with certainty
  * grid-softmax    -- win probability decaying with grid slot
  * uniform         -- 1/N for every car

Usage:
    python3 -m benchmarks.timing.backtest --reps 20000
    python3 -m benchmarks.timing.backtest --seasons 2019,2020,2021,2023,2024 --json bt.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "timing"))
from kernel_probe import Worker  # noqa: E402


FROZEN_TEST_SEASON = 2025


def _grid_term(grid: float, form: str) -> float:
    """Grid slot mapped to a pace offset, in units the slot_spread scales.

    sqrt is measured as the better shape: the front of the grid is spread more than the midfield, so a
    linear slope over-separates P14 from P20 and under-separates P1 from P2. Normalised so that a
    20-car field spans the same range as the linear form, keeping slot_spread comparable across forms.
    """
    import math as _m
    if form == "sqrt":
        return (_m.sqrt(grid) - 1.0) * 19.0 / (_m.sqrt(20.0) - 1.0)
    return grid - 1.0


def race_frames(root: Path, seasons: set[int], kinds: set[str] | None = None) -> list[dict]:
    """Grid + actual classification + observed relative pace per race, from the replayed state.

    relative_pace is a car's median GREEN lap minus the field median for that race. Normalising to the
    field removes circuit and era level, leaving a comparable car/team pace offset in s/lap. It is used
    only to build a prior for LATER races -- never for the race it came from.
    """
    out = []
    for p in sorted(root.rglob("_laps.parquet")):
        # session type comes from the directory name; qualifying and practice are already excluded by
        # the grid-position test below, but sprints are NOT and had been silently included
        if kinds is not None and p.parts[-2].split("_", 1)[-1] not in kinds:
            continue
        t = pq.read_table(p).to_pydict()
        rows = [dict(zip(t.keys(), v)) for v in zip(*t.values())]
        if not rows:
            continue
        season = rows[0]["season"]
        if seasons and season not in seasons:
            continue
        # grid from the first lap each car appears on (observed pre-race)
        grid: dict[int, int] = {}
        last: dict[int, dict] = {}
        for r in rows:
            c = r["car_number"]
            if c not in grid and r["grid_position"]:
                grid[c] = r["grid_position"]
            if c not in last or r["lap_number"] > last[c]["lap_number"]:
                last[c] = r
        cars = sorted(c for c in grid if grid[c] > 0)
        if len(cars) < 10:
            continue
        total_laps = max(r["lap_number"] for r in rows)
        # observed relative pace, for use as a prior in SUBSEQUENT races only
        per_car: dict[int, list[float]] = defaultdict(list)
        for r in rows:
            if r["lap_time_s"] and r["track_regime"] == 1 and not r["in_pit"] and not r["pit_out"]:
                per_car[r["car_number"]].append(r["lap_time_s"])
        med_car = {c: sorted(v)[len(v) // 2] for c, v in per_car.items() if len(v) >= 5}
        field = sorted(med_car.values())
        field_med = field[len(field) // 2] if field else None
        rel_pace = ({c: m - field_med for c, m in med_car.items()} if field_med else {})
        # actual finishing order: laps completed desc, then final position
        def key(c: int) -> tuple:
            r = last[c]
            return (-r["lap_number"], r["position"] if r["position"] else 99)
        actual = sorted(cars, key=key)
        out.append({
            "path": str(p.parent), "season": season,
            "name": p.parent.parent.name, "total_laps": total_laps,
            "cars": cars, "grid": {c: grid[c] for c in cars},
            "actual_order": actual,
            "start": rows[0].get("event_ms", 0),
            "rel_pace": rel_pace,
        })
    # chronological, so a prior can only ever see earlier races
    out.sort(key=lambda R: (R["season"], R["name"]))
    return out


def score(w: Worker, probs: list[float], outcomes: list[float], bins: int = 10) -> dict:
    # Guard the silent-perfect-score path: an empty or mismatched probability vector used to produce
    # Brier 0.0 and BSS 1.0 rather than an error.
    if not probs or len(probs) != len(outcomes):
        raise ValueError(f"score(): {len(probs)} probs against {len(outcomes)} outcomes")
    br = w.execute("forecast_metrics", "base_rate", [outcomes])["result"]
    return {
        "brier": w.execute("forecast_metrics", "brier_score", [probs, outcomes])["result"],
        "bss": w.execute("forecast_metrics", "brier_skill_score", [probs, outcomes, br])["result"],
        "ece": w.execute("forecast_metrics", "expected_calibration_error",
                         [probs, outcomes, bins])["result"],
        "log_loss": w.execute("forecast_metrics", "log_loss", [probs, outcomes, 1e-9])["result"],
        "base_rate": br,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="~/.algenta/f1/raw")
    ap.add_argument("--binary", default="mojo_build/simulate_timing")
    ap.add_argument("--reps", type=int, default=20000)
    ap.add_argument("--seasons", default="2019,2020,2021,2023,2024",
                    help="development split; 2025 is the frozen final test, 2026 prospective")
    ap.add_argument("--grid-spread", type=float, default=0.28)
    ap.add_argument("--base-pace", type=float, default=90.0)
    ap.add_argument("--slot-spread", type=float, default=0.120)
    ap.add_argument("--grid-form", default="linear", choices=("linear", "sqrt"),
                    help="shape of the grid -> pace prior. sqrt fits better on the corpus (R2 0.348 vs "
                         "0.339 over 2,525 car-races): the gap is wider at the front, 0.29 s/lap from "
                         "P1 to P2 against 0.085 per slot in the midfield. Note 'flat past P10' scores "
                         "WORSE (0.315) -- grid does not discriminate INSIDE a band but the band levels "
                         "still rise, so truncating destroys real information")
    ap.add_argument("--theta-ensemble", type=int, default=0,
                    help="average the oracle over K parameter vectors drawn around the fitted theta, "
                         "each dimension perturbed by the SPREAD the search itself left behind. The "
                         "frozen tests showed resolution holding while reliability degraded tenfold -- "
                         "the model is sharp and overconfident -- and the plan already notes the "
                         "intervals cover sampling error only, not parameter uncertainty. This "
                         "propagates the uncertainty the search measured instead of discarding it: an "
                         "UNIDENTIFIED dimension widens the prediction, a resolved one barely moves it")
    ap.add_argument("--ensemble-scale", type=float, default=1.0,
                    help="multiplier on the recorded spread; 1.0 uses the search's own estimate")
    ap.add_argument("--session-types", default="Race,Sprint",
                    help="which session types count as a scoreable race. The 2025 frozen test consumed "
                         "24 grands prix AND 6 sprints because the preregistration pinned only the "
                         "season -- sprints run ~19 laps against ~57 and usually take no stop, so the "
                         "two-stop, tyre-cliff configuration does not fit them. Pinned explicitly from "
                         "the second preregistration onward")
    ap.add_argument("--theta-json", default="",
                    help="calibration.json from benchmarks.timing.calibrate — the theta selected on "
                         "held-out races, never on the frozen test season")
    ap.add_argument("--pace-cap", type=float, default=5.5)
    ap.add_argument("--stops", type=float, default=2.0,
                    help="scheduled pit stops per car; the corpus median is 2")
    ap.add_argument("--deg", type=float, default=0.010,
                    help="tyre degradation s/lap/lap; the corpus fits 0.0064 MEDIUM / 0.0126 HARD / "
                         "0.0146 SOFT, so the previous 0.06 was 4-10x too large")
    ap.add_argument("--pace-prior", default="grid", choices=("grid", "history"),
                    help="grid = grid position only; history = EWMA of a car's PRIOR races' relative pace")
    ap.add_argument("--ewma", type=float, default=0.6, help="weight on the most recent prior race")
    ap.add_argument("--hist-weight", type=float, default=0.3,
                    help="weight on the historical prior vs the grid term (0 = grid only)")
    ap.add_argument("--calibrate", action="store_true",
                    help="fit Platt scaling on the FIRST half of races, apply to the second, score the second")
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    if FROZEN_TEST_SEASON in {int(x) for x in str(args.seasons).split(",") if x.strip().isdigit()}:
        # ONE sanctioned path: benchmarks/timing/freeze.py --run-final sets this, having already checked a
        # preregistration exists, the tree matches it, and no result file is present. A bare
        # `--seasons 2025` still refuses, which is the accident this guard is for.
        if os.environ.get("ALGENTA_FINAL_TEST") != "1":
            print(f"refusing: {FROZEN_TEST_SEASON} is the frozen final test season. The only sanctioned "
                  f"path is `python3 -m benchmarks.timing.freeze --run-final`, which checks the "
                  f"preregistration first.", file=sys.stderr)
            return 2
        print(f"running the FROZEN {FROZEN_TEST_SEASON} test under the preregistration", file=sys.stderr)

    root = Path(args.root).expanduser()
    seasons = {int(s) for s in args.seasons.split(",") if s.strip()}
    races = race_frames(root, seasons,
                        {t.strip() for t in args.session_types.split(",") if t.strip()})
    print(f"{len(races)} races, seasons {sorted(seasons)}, N={args.reps:,}", file=sys.stderr)

    theta_members: list = []
    w = Worker(ROOT / args.binary)
    try:
        p = w.execute("contest_strategy", "default_contest_params")["result"]
        if args.theta_json:
            import json as _json
            _cal = _json.loads(Path(args.theta_json).read_text())
            sys.path.insert(0, str(ROOT / "benchmarks" / "timing"))
            import calibrate as _c
            for _nm, (_v, _w) in _c.MEASURED.items():
                for _dn, _di, *_r in _c.SEARCH_DIMS:
                    if _dn == _nm and _di >= 0:
                        p[_di] = _v
            for _rec in _cal["parameters"]:
                if _rec["param_index"] >= 0:
                    p[_rec["param_index"]] = _rec["fitted"]
                elif _rec["name"] == "slot_spread":
                    args.slot_spread = _rec["fitted"]
                elif _rec["name"] == "hist_weight":
                    args.hist_weight = _rec["fitted"]
            print(f"theta: {args.theta_json}", file=sys.stderr)
        if args.theta_ensemble > 1:
            import hashlib as _h
            _members = []
            for _k in range(args.theta_ensemble):
                _q = list(p)
                for _rec in _cal["parameters"]:
                    _i = _rec["param_index"]
                    if _i < 0 or _rec["spread"] <= 0:
                        continue
                    # deterministic per (dimension, member): the ensemble must be reproducible, and a
                    # non-replayable ensemble is not evidence any more than a non-replayable theta is
                    _seed = int(_h.sha256(f"{_rec['name']}|{_k}".encode()).hexdigest()[:12], 16)
                    _u1 = ((_seed % 1000003) + 1) / 1000004.0
                    _u2 = ((_seed // 1000003) % 1000003 + 1) / 1000004.0
                    _z = math.sqrt(-2.0 * math.log(_u1)) * math.cos(2.0 * math.pi * _u2)
                    _v = _rec["fitted"] + args.ensemble_scale * _rec["spread"] * _z
                    _q[_i] = max(_rec["lo"], min(_rec["hi"], _v))
                _members.append(_q)
            theta_members = _members
            print(f"theta ensemble: {len(theta_members)} members, each dimension perturbed by its own "
                  f"recorded spread x {args.ensemble_scale:g}", file=sys.stderr)
        acc: dict[str, dict[str, list]] = {
            m: {"win_p": [], "win_o": [], "pod_p": [], "pod_o": [], "pts_p": [], "pts_o": []}
            for m in ("oracle", "grid", "grid_softmax", "uniform")
        }
        hits = {m: {"winner": 0, "top3": 0, "podium_recall": 0.0} for m in acc}
        rho_pairs: list[tuple[list, list]] = []
        sim_s = 0.0
        total_updates = 0
        # as-of pace prior, carried forward. Updated only AFTER a race is scored.
        prior: dict[int, float] = {}
        n_with_prior = 0

        for i, R in enumerate(races, 1):
            cars = R["cars"]
            n = len(cars)
            grid = R["grid"]
            laps = R["total_laps"]
            order = R["actual_order"]
            actual_pos = {c: k + 1 for k, c in enumerate(order)}

            # pace prior
            PACE_CAP = 5.5
            if args.pace_prior == "history":
                # BLEND, not replace. An earlier version substituted the historical prior for grid and
                # degraded everything -- win hit 51.8% -> 43.6%, BSS 0.080 -> -0.046. Grid encodes the
                # car's form at THIS circuit hours earlier; a multi-race EWMA averages over circuits
                # where relative performance genuinely differs. Grid is the primary signal and history
                # can only be a correction to it.
                pace = []
                for c in cars:
                    g = args.slot_spread * _grid_term(grid[c], args.grid_form)
                    b = g if c not in prior else (
                        (1.0 - args.hist_weight) * g + args.hist_weight * prior[c])
                    if c in prior:
                        n_with_prior += 1
                    off = max(-PACE_CAP, min(PACE_CAP, b))
                    pace.append(args.base_pace + off)
            else:
                pace = [args.base_pace
                        + max(-PACE_CAP, min(PACE_CAP,
                                             args.slot_spread * _grid_term(grid[c], args.grid_form)))
                        for c in cars]
            deg = [args.deg] * n
            el = [args.grid_spread * (grid[c] - 1) * 0.5 for c in cars]
            age = [0.0] * n
            act = [1.0] * n

            t0 = time.perf_counter()
            if theta_members:
                # Average p_win ACROSS members. Splitting the replication budget keeps the compute
                # identical to a single-theta run, so the comparison is like for like: any gain comes
                # from propagating parameter uncertainty, not from spending more simulation.
                per = max(200, args.reps // len(theta_members))
                acc_win = [0.0] * n
                acc_pod_l = [0.0] * n
                acc_pts_l = [0.0] * n
                acc_pos = [0.0] * n
                for _m, _q in enumerate(theta_members):
                    _r = w.execute("contest_strategy", "outcome_distribution",
                                   [pace, deg, [_q[22]] * n, el, age, act, [args.stops] * n, laps, _q,
                                    per, 7, R["season"] * 1000 + i + 100000 * _m])
                    if "error" in _r:
                        continue
                    _v = _r["result"]["v"]
                    for _c in range(n):
                        acc_win[_c] += _v[0][_c] / len(theta_members)
                        acc_pod_l[_c] += _v[1][_c] / len(theta_members)
                        acc_pts_l[_c] += _v[2][_c] / len(theta_members)
                        acc_pos[_c] += _v[3][_c] / len(theta_members)
                # mirror the full OracleBoard shape: p_win, p_podium, p_points, e_pos, modal winner,
                # n_reps, mean_displacement. Returning a short list made the caller index past the end.
                acc_pod, acc_pts = acc_pod_l, acc_pts_l
                modal = max(range(n), key=lambda c: acc_win[c]) if n else 0
                res = {"result": {"v": [acc_win, acc_pod, acc_pts, acc_pos, modal,
                                        per * len(theta_members), 0.0]}}
                total_updates += per * len(theta_members) * n * laps
            else:
                res = w.execute("contest_strategy", "outcome_distribution",
                                [pace, deg, [p[22]] * n, el, age, act, [args.stops] * n, laps, p,
                                 args.reps, 7, R["season"] * 1000 + i])
                total_updates += args.reps * n * laps
            sim_s += time.perf_counter() - t0
            if "error" in res:
                print(f"  race {i} error: {res['error']}", file=sys.stderr)
                continue
            v = res["result"]["v"]
            o_win, o_pod, o_pts, o_epos, modal = v[0], v[1], v[2], v[3], v[4]

            # baselines
            g_win = [1.0 if grid[c] == 1 else 0.0 for c in cars]
            tau = 3.0
            raw = [math.exp(-(grid[c] - 1) / tau) for c in cars]
            z = sum(raw)
            s_win = [x / z for x in raw]
            u_win = [1.0 / n] * n

            win_o = [1.0 if actual_pos[c] == 1 else 0.0 for c in cars]
            pod_o = [1.0 if actual_pos[c] <= 3 else 0.0 for c in cars]
            pts_o = [1.0 if actual_pos[c] <= 10 else 0.0 for c in cars]

            for name, wp in (("oracle", o_win), ("grid", g_win),
                             ("grid_softmax", s_win), ("uniform", u_win)):
                a = acc[name]
                a["win_p"] += wp
                a["win_o"] += win_o
                # podium/points probabilities only exist for the oracle; baselines reuse the win shape
                a["pod_p"] += (o_pod if name == "oracle" else [min(1.0, x * 3) for x in wp])
                a["pod_o"] += pod_o
                a["pts_p"] += (o_pts if name == "oracle" else [min(1.0, x * 10) for x in wp])
                a["pts_o"] += pts_o

                ranked = sorted(range(n), key=lambda k: -wp[k])
                if cars[ranked[0]] == order[0]:
                    hits[name]["winner"] += 1
                if order[0] in [cars[k] for k in ranked[:3]]:
                    hits[name]["top3"] += 1
                pred_pod = {cars[k] for k in ranked[:3]}
                hits[name]["podium_recall"] += len(pred_pod & set(order[:3])) / 3.0

            rho_pairs.append(([float(o_epos[k]) for k in range(n)],
                              [float(actual_pos[cars[k]]) for k in range(n)]))

            # update the prior AFTER scoring -- this is the as-of boundary
            for c, rp in R["rel_pace"].items():
                prior[c] = rp if c not in prior else (1 - args.ewma) * prior[c] + args.ewma * rp

            if i % 20 == 0:
                print(f"  {i}/{len(races)} …", file=sys.stderr)

        # ── Platt calibration, fitted on the first half and applied to the second ──────────
        # The oracle out-ranks grid_softmax but is worse CALIBRATED -- better ordering, over-spread
        # probabilities. That is the dual-path situation the reference paper describes, and the remedy
        # is a monotone recalibration rather than a model change. Fitted on races 1..h and applied to
        # h+1..n so the calibration map never sees the data it is scored on.
        calib_report = {}
        if args.calibrate:
            half = len(acc["oracle"]["win_p"]) // 2
            for name in ("oracle", "grid_softmax"):
                a = acc[name]
                fit_p, fit_o = a["win_p"][:half], a["win_o"][:half]
                hold_p, hold_o = a["win_p"][half:], a["win_o"][half:]
                pl = w.execute("calibration", "platt_fit", [fit_p, fit_o, 200])
                if "error" in pl:
                    calib_report[name] = {"error": pl["error"]}
                    continue
                pa, pb = pl["result"]["v"][0], pl["result"]["v"][1]
                # platt_transform signature is (a, b, scores) -- NOT (scores, a, b)
                cal = w.execute("calibration", "platt_transform", [pa, pb, hold_p])
                cal_p = cal["result"] if "error" not in cal else hold_p
                calib_report[name] = {
                    "platt_a": pa, "platt_b": pb,
                    "raw": score(w, hold_p, hold_o),
                    "calibrated": score(w, cal_p, hold_o),
                }

        # Spearman per race, averaged
        rhos = [w.execute("forecast_metrics", "spearman_rho", [a, b])["result"]
                for a, b in rho_pairs]
        mean_rho = sum(rhos) / len(rhos) if rhos else 0.0

        nr = len(races)
        if args.pace_prior == "history":
            print(f"pace prior: history (EWMA {args.ewma}), "
                  f"{n_with_prior} car-races had a prior", file=sys.stderr)
        print(f"\n{'model':<14}{'win hit':>9}{'top-3':>8}{'pod rec':>9}"
              f"{'win Brier':>11}{'win BSS':>9}{'win ECE':>9}{'log loss':>10}")
        results = {}
        for name in ("oracle", "grid_softmax", "grid", "uniform"):
            a = acc[name]
            sw = score(w, a["win_p"], a["win_o"])
            results[name] = {
                "winner_hit_pct": 100.0 * hits[name]["winner"] / nr,
                "top3_pct": 100.0 * hits[name]["top3"] / nr,
                "podium_recall_pct": 100.0 * hits[name]["podium_recall"] / nr,
                "win": sw,
                "podium": score(w, a["pod_p"], a["pod_o"]),
                "points": score(w, a["pts_p"], a["pts_o"]),
            }
            r = results[name]
            print(f"{name:<14}{r['winner_hit_pct']:>8.1f}%{r['top3_pct']:>7.1f}%"
                  f"{r['podium_recall_pct']:>8.1f}%{sw['brier']:>11.5f}{sw['bss']:>9.3f}"
                  f"{sw['ece']:>9.4f}{sw['log_loss']:>10.4f}")

        m = w.execute("forecast_metrics", "murphy_decomposition",
                      [acc["oracle"]["win_p"], acc["oracle"]["win_o"], 10])["result"]["v"]
        print(f"\noracle Murphy (win): BS {m[0]:.5f} = REL {m[1]:.5f} - RES {m[2]:.5f} "
              f"+ UNC {m[3]:.5f}   base rate {m[5]:.4f}")
        print(f"oracle mean Spearman rho vs final classification: {mean_rho:.3f}")

        if calib_report:
            print(f"\nPlatt recalibration — fitted on the first half of races, scored on the second:")
            print(f"{'model':<14}{'':>4}{'Brier':>10}{'BSS':>9}{'ECE':>9}{'log loss':>10}")
            for name, cr in calib_report.items():
                if "error" in cr:
                    print(f"{name:<14}  {cr['error']}")
                    continue
                for tag in ("raw", "calibrated"):
                    d = cr[tag]
                    print(f"{name:<14}{tag[:4]:>4}{d['brier']:>10.5f}{d['bss']:>9.3f}"
                          f"{d['ece']:>9.4f}{d['log_loss']:>10.4f}")

        print(f"\nsimulation: {sim_s:.1f} s for {total_updates:,} car-lap updates "
              f"= {total_updates/sim_s/1e6:.1f}M updates/s")
        print(f"  {nr} races x N={args.reps:,} replications, {sim_s/nr*1000:.0f} ms per race")

        if args.json:
            Path(args.json).write_text(json.dumps({
                "seasons": sorted(seasons), "races": nr, "replications": args.reps,
                "pace_prior": args.pace_prior, "ewma": args.ewma,
                "hist_weight": args.hist_weight,
                "results": results, "oracle_mean_spearman": mean_rho,
                "oracle_murphy_win": {"brier": m[0], "reliability": m[1],
                                      "resolution": m[2], "uncertainty": m[3], "base_rate": m[5]},
                "timing": {"simulation_seconds": sim_s, "car_lap_updates": total_updates,
                           "updates_per_s": total_updates / sim_s},
            }, indent=2))
            print(f"\nwrote {args.json}", file=sys.stderr)
        return 0
    finally:
        w.close()


if __name__ == "__main__":
    raise SystemExit(main())
