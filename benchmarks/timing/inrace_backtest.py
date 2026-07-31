#!/usr/bin/env python3
"""In-race decision snapshots, and the FIVE baselines the plan makes mandatory.

WHY THIS EXISTS SEPARATELY FROM backtest.py

Three of the five required baselines are not definable before the race starts. "Current running order",
"current pace with no further incidents" and the "pit-window heuristic" all read mid-race state, so a
pre-race harness silently substitutes a different, easier comparison set — which is how a model can beat
a research paper while losing to the running order and nobody notices. The plan is explicit that beating
a paper while losing to current running order would be meaningless.

The as-of watermark added for Invariant 4 is what makes this possible: every snapshot is reconstructed
from the append-only event log with `replay(cutoff_ms=...)`, so a decision at lap 30 sees only records
that existed at lap 30. The final classification is scorer-only and reaches nothing but the metrics.

THE FIVE, as the plan names them:

  grid-order                  finish as started. The dumbest thing that is not uniform.
  current-running-order       finish in the order you are running now. The one that actually matters --
                              track position is most of an F1 result, so this is a genuinely strong
                              baseline late in a race and it is the one a simulator must beat to be worth
                              running.
  current-pace-no-incidents   extrapolate each car's own recent green pace over the remaining laps and
                              order the totals. No safety car, no retirement, no traffic, no stops. This
                              isolates what the INTERACTION layer buys.
  pit-window-heuristic        running order, charged for a stop each car still owes. This is the
                              baseline a strategy engine is most at risk of merely reproducing.
  historical-prior            EWMA of each car's relative pace in PRIOR races only. Tests whether the
                              simulation adds anything over "who has been quick lately".

FAIRNESS. Each baseline produces an ORDERING; a Brier score needs probabilities. Every baseline gets its
own softmax temperature fitted on the training block, so none of them loses on a badly chosen constant.
Handing the oracle a fitted temperature and the baselines a guessed one would be rigging the comparison.

Usage:
    python3 -m benchmarks.timing.inrace_backtest --theta-json docs/timing/calibration.json
    python3 -m benchmarks.timing.inrace_backtest --laps-frac 0.25,0.5,0.75 --reps 4000
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "timing"))
sys.path.insert(0, str(ROOT / "benchmarks" / "timing"))
from kernel_probe import Worker  # noqa: E402
from replay_state import replay  # noqa: E402

FROZEN_TEST_SEASON = 2025
MAX_STINT = 37
"""Corpus p90 stint length, laps. The distance a set is expected to be able to cover."""

BASELINES = ("grid_order", "running_order", "pace_no_incidents", "pit_window", "historical_prior")


def require(resp: dict, what: str):
    if not isinstance(resp, dict) or "result" not in resp:
        raise RuntimeError(f"{what}: kernel returned {str(resp)[:200]}")
    return resp["result"]


def softmax_from_rank(rank: dict[int, float], tau: float) -> dict[int, float]:
    """Lower rank is better. tau is fitted per baseline, never guessed."""
    if not rank:
        return {}
    best = min(rank.values())
    w = {c: math.exp(-(r - best) / max(tau, 1e-6)) for c, r in rank.items()}
    s = sum(w.values()) or 1.0
    return {c: v / s for c, v in w.items()}


def final_order(session: Path) -> dict[int, int]:
    """Scorer-only: the actual classification. Never reaches a feature or a decision."""
    t = pq.read_table(session / "_laps.parquet").to_pydict()
    last: dict[int, tuple] = {}
    for c, ln, pos, ret in zip(t["car_number"], t["lap_number"], t["position"], t["retired"]):
        if not ln:
            continue
        prev = last.get(c)
        if prev is None or ln > prev[0]:
            last[c] = (ln, pos or 99, ret or 0)
    # classified first by laps completed, then by last known position; retired behind
    ranked = sorted(last.items(), key=lambda kv: (kv[1][2], -kv[1][0], kv[1][1]))
    return {c: i + 1 for i, (c, _v) in enumerate(ranked)}


def as_of_state(session: Path, frac: float) -> dict | None:
    """State at a decision lap, reconstructed from the event log under an as-of watermark."""
    full = pq.read_table(session / "_laps.parquet").to_pydict()
    total = max([l for l in full["lap_number"] if l] or [0])
    if total < 30:
        return None
    target = max(3, int(total * frac))
    # the event_ms at which the LEADER completed the target lap defines the watermark
    cut = None
    for ln, ms, pos in zip(full["lap_number"], full["event_ms"], full["position"]):
        if ln == target and pos == 1:
            cut = ms
            break
    if cut is None:
        cands = [ms for ln, ms in zip(full["lap_number"], full["event_ms"]) if ln == target]
        if not cands:
            return None
        cut = min(cands)

    r = replay(session, cutoff_ms=cut, emit=False)
    if not r["laps"]:
        return None
    # re-read what the as-of replay would have produced, from its own in-memory rows
    t = pq.read_table(session / "_laps.parquet").to_pydict()
    per: dict[int, dict] = {}
    green: dict[int, list[float]] = defaultdict(list)
    for i in range(len(t["lap_number"])):
        if t["event_ms"][i] > cut:
            continue
        c = t["car_number"][i]
        ln = t["lap_number"][i]
        if not ln:
            continue
        if t["is_green_lap"][i] and t["lap_time_s"][i] and not t["in_pit"][i] and not t["pit_out"][i]:
            green[c].append(t["lap_time_s"][i])
        cur = per.get(c)
        if cur is None or ln >= cur["lap"]:
            per[c] = {
                "lap": ln, "pos": t["position"][i] or 0,
                "gap": t["gap_to_leader_s"][i], "age": t["tyre_age"][i] or 0,
                "pits": t["pit_count"][i] or 0, "grid": t["grid_position"][i] or 0,
                "retired": t["retired"][i] or 0, "compound": t["compound"][i] or "",
            }
    cars = [c for c, v in per.items() if v["pos"] > 0 and not v["retired"]]
    if len(cars) < 10:
        return None
    return {"cut_ms": cut, "lap": target, "total": total, "state": per,
            "green": green, "cars": sorted(cars), "state_hash": r["state_hash"]}


def build_snapshot(s: dict, hist: dict[int, float], pit_loss: float, mandatory_stops: int,
                   prerace_sigma: float) -> dict:
    """Every baseline's ordering, plus the arrays the kernel needs. All from as-of state only."""
    cars, st, green = s["cars"], s["state"], s["green"]
    n = len(cars)
    remaining = s["total"] - s["lap"]
    _all = sorted(x for c in cars for x in green[c])
    ref_lap_hint = _all[len(_all) // 2] if _all else 90.0

    # elapsed: observed gap to the leader, which is a MEASURED quantity. Summing lap times treats a
    # missing lap as zero and put a P3 car at an expected 14th in an earlier version.
    # gap_to_leader is None for the LEADER (genuinely zero) and ALSO for lapped or unpublished
    # backmarkers. Mapping both to 0.0 puts a car running P20 level with the leader -- 8.9% of
    # car-snapshots, and nearly half of those are P4 or worse. This is the identical defect already
    # fixed once in the pre-race path; it recurred here because this harness reads the field directly.
    # Separate the two by position and by laps completed, which is what distinguishes them.
    leader = min(cars, key=lambda c: (st[c]["pos"] or 99))
    leader_laps = max(st[c]["lap"] for c in cars)
    known = [(st[c]["pos"], st[c]["gap"]) for c in cars
             if st[c]["gap"] is not None and (st[c]["pos"] or 0) > 1]
    # mean seconds per position among cars that DO publish a gap, as the fallback slope
    per_pos = (sum(g / max(1, pos - 1) for pos, g in known) / len(known)) if known else 1.5
    gaps = {}
    for c in cars:
        g, pos = st[c]["gap"], st[c]["pos"] or 99
        if g is not None:
            gaps[c] = g
        elif pos == 1:
            gaps[c] = 0.0
        else:
            laps_down = max(0, leader_laps - st[c]["lap"])
            gaps[c] = laps_down * ref_lap_hint + per_pos * (pos - 1)
    med = {}
    for c in cars:
        v = sorted(green[c][-8:]) or sorted(green[c])
        med[c] = v[len(v) // 2] if v else 0.0
    field_med = sorted(m for m in med.values() if m > 0)
    ref = field_med[len(field_med) // 2] if field_med else 90.0
    for c in cars:
        if med[c] <= 0:
            med[c] = ref

    # FORM UNCERTAINTY that shrinks with observation. Pre-race a car's race form is unknown and the
    # calibrated sigma applies; after k green laps the pace estimate already contains that form, and what
    # remains is the standard error of the estimate itself, sigma_lap / sqrt(k). Using the pre-race sigma
    # in-race double-counts the uncertainty and re-randomises an order reality has largely settled --
    # measured as the oracle losing to current running order by more and more as the race progressed.
    form_sigma = []
    for c in cars:
        v = green[c][-12:]
        k = len(v)
        if k >= 3:
            mu = sum(v) / k
            sd = (sum((x - mu) ** 2 for x in v) / (k - 1)) ** 0.5
            form_sigma.append(min(prerace_sigma, sd / (k ** 0.5)))
        else:
            form_sigma.append(prerace_sigma)

    out = {"n": n, "cars": cars, "remaining": remaining,
           "pace": [med[c] for c in cars], "form_sigma": form_sigma,
           "elapsed": [gaps[c] for c in cars],
           "age": [float(st[c]["age"]) for c in cars],
           "active": [1.0] * n,
           # STOPS REMAINING FROM TYRE LIFE, not a flat mandatory count. `mandatory - stops_done`
           # charges a full 22.8 s to every car on a one-stop -- 26% of the corpus -- for a stop it will
           # never make, which drops it about ten places in the predicted order. A car needs another
           # stop only when its CURRENT set cannot reach the end. MAX_STINT is the corpus p90 stint
           # length of 37 laps (p50 21, p95 42).
           "stops": [float(max(0, math.ceil((st[c]["age"] + remaining) / MAX_STINT) - 1))
                     for c in cars]}

    ranks: dict[str, dict[int, float]] = {}
    ranks["grid_order"] = {c: float(st[c]["grid"] or 99) for c in cars}
    ranks["running_order"] = {c: float(st[c]["pos"]) for c in cars}
    # pure pace extrapolation: no incidents, no stops, no traffic
    ranks["pace_no_incidents"] = {c: gaps[c] + remaining * med[c] for c in cars}
    # running order charged for a stop still owed
    ranks["pit_window"] = {
        c: gaps[c] + remaining * med[c]
        + pit_loss * max(0, math.ceil((st[c]["age"] + remaining) / MAX_STINT) - 1)
        for c in cars
    }
    # who has been quick in PRIOR races; falls back to running order where there is no prior
    ranks["historical_prior"] = {
        c: (hist[c] if c in hist else 0.0) * remaining + gaps[c] for c in cars
    }
    out["ranks"] = ranks
    out["leader"] = leader
    return out


def fit_tau(rows: list[dict], name: str) -> float:
    """Grid-search the softmax temperature that minimises Brier for THIS baseline on the training block."""
    best, best_bs = 1.0, None
    # The grid must not saturate at either end, or the fitted value is the edge of the grid rather than
    # an estimate -- the same failure the calibration search reports via ga_saturation. Mid-race,
    # grid-order's best probabilistic form really is near-uniform, so the upper end has to reach it.
    for tau in (0.02, 0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0, 1.5, 2.5, 4.0, 6.0, 10.0, 20.0, 50.0,
                120.0, 400.0, 2000.0):
        se, k = 0.0, 0
        for r in rows:
            p = softmax_from_rank(r["ranks"][name], tau)
            for c, pv in p.items():
                y = 1.0 if r["winner"] == c else 0.0
                se += (pv - y) ** 2
                k += 1
        if k and (best_bs is None or se / k < best_bs):
            best, best_bs = tau, se / k
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="~/.algenta/f1/raw")
    ap.add_argument("--binary", default="mojo_build/simulate_timing")
    ap.add_argument("--seasons", default="2019,2020,2021,2023,2024")
    ap.add_argument("--laps-frac", default="0.25,0.5,0.75",
                    help="decision points as a fraction of race distance")
    ap.add_argument("--reps", type=int, default=6000)
    ap.add_argument("--ewma", type=float, default=0.35)
    ap.add_argument("--mandatory-stops", type=int, default=2,
                    help="stops a car is assumed to owe over a full race; the corpus mean is 2.33")
    ap.add_argument("--train-frac", type=float, default=0.6)
    ap.add_argument("--theta-json", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ablate", action="store_true",
                    help="run the oracle under several parameter vectors on the SAME snapshots, to "
                         "identify which stochastic component costs skill in-race rather than guess")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    seasons = {int(x) for x in args.seasons.split(",") if x.strip()}
    if FROZEN_TEST_SEASON in seasons:
        print(f"refusing: {FROZEN_TEST_SEASON} is the frozen final test season", file=sys.stderr)
        return 2
    fracs = [float(x) for x in args.laps_frac.split(",") if x.strip()]
    root = Path(args.root).expanduser()

    sessions = sorted(p.parent for p in root.glob("*/*/*_Race/_laps.parquet")
                      if int(p.parts[-4]) in seasons)
    if args.limit:
        sessions = sessions[: args.limit]
    if not sessions:
        print("no sessions", file=sys.stderr)
        return 2

    w = Worker(ROOT / args.binary)
    try:
        p = require(w.execute("contest_strategy", "default_contest_params"), "defaults")
        if args.theta_json:
            cal = json.loads(Path(args.theta_json).read_text())
            import calibrate as _c
            for nm, (v, _why) in _c.MEASURED.items():
                for dn, di, *_r in _c.SEARCH_DIMS:
                    if dn == nm and di >= 0:
                        p[di] = v
            for rec in cal["parameters"]:
                if rec["param_index"] >= 0:
                    p[rec["param_index"]] = rec["fitted"]
        pit_loss = p[0]

        print(f"{len(sessions)} races x {len(fracs)} decision points, N={args.reps:,}", file=sys.stderr)
        print(f"as-of reconstruction from the event log; the final classification is scorer-only\n",
              file=sys.stderr)

        hist: dict[int, float] = {}
        rows: list[dict] = []
        t0 = time.perf_counter()
        for si, sess in enumerate(sessions):
            fin = final_order(sess)
            winner = min(fin, key=lambda c: fin[c]) if fin else None
            for frac in fracs:
                s = as_of_state(sess, frac)
                if s is None:
                    continue
                snap = build_snapshot(s, hist, pit_loss, args.mandatory_stops, p[22])
                if snap["remaining"] < 3:
                    continue
                variants = {"full": p}
                if args.ablate:
                    def off(*idx):
                        """Zero the named parameter indices, leaving everything else at theta."""
                        q = list(p)
                        for i in idx:
                            q[i] = 0.0
                        return q
                    # P_LAP_NOISE 1 · P_DNF_PROB 2 · P_SC_LAMBDA 3 · P_VSC_LAMBDA 6
                    # P_DIRTY_LOSS 10 · P_SIGMA_PIT 14 · P_MIN_FOLLOW 19 · P_STOP_JITTER 21
                    # P_PACE_SIGMA 22
                    variants = {
                        "full":          p,
                        "-lap_noise":    off(1),
                        "-form":         off(22),
                        "-dnf":          off(2),
                        "-neutralis.":   off(3, 6),
                        "-traffic":      off(10, 19),
                        "deterministic": off(1, 2, 3, 6, 10, 14, 19, 21, 22),
                    }
                abl = {}
                for vname, vp in variants.items():
                    if vname == "full":
                        continue
                    av = require(w.execute("contest_strategy", "outcome_distribution",
                                           [snap["pace"], [0.010] * snap["n"], snap["form_sigma"],
                                            snap["elapsed"], snap["age"], snap["active"],
                                            snap["stops"], snap["remaining"], vp, args.reps, 7,
                                            int(s["cut_ms"]) % 100000]), "outcome_distribution")["v"]
                    abl[vname] = {c: av[0][k] for k, c in enumerate(snap["cars"])}
                v = require(w.execute("contest_strategy", "outcome_distribution",
                                      [snap["pace"], [0.010] * snap["n"], snap["form_sigma"],
                                       snap["elapsed"], snap["age"], snap["active"], snap["stops"],
                                       snap["remaining"], p, args.reps, 7,
                                       int(s["cut_ms"]) % 100000]), "outcome_distribution")["v"]
                oracle_p = {c: v[0][k] for k, c in enumerate(snap["cars"])}
                oracle_pos = {c: v[3][k] for k, c in enumerate(snap["cars"])}
                rows.append({
                    "race": si, "frac": frac, "lap": s["lap"], "total": s["total"],
                    "winner": winner, "ranks": snap["ranks"], "cars": snap["cars"],
                    "oracle_p": oracle_p, "oracle_pos": oracle_pos,
                    "final": {c: fin.get(c, 99) for c in snap["cars"]},
                    "abl": abl,
                    "state_hash": s["state_hash"],
                })
            # the prior updates only AFTER a race is scored
            t = pq.read_table(sess / "_laps.parquet").to_pydict()
            g: dict[int, list[float]] = defaultdict(list)
            for i in range(len(t["lap_number"])):
                if t["is_green_lap"][i] and t["lap_time_s"][i] and not t["in_pit"][i]:
                    g[t["car_number"][i]].append(t["lap_time_s"][i])
            meds = {c: sorted(v)[len(v) // 2] for c, v in g.items() if len(v) >= 8}
            if meds:
                fm = sorted(meds.values())[len(meds) // 2]
                for c, m in meds.items():
                    rel = m - fm
                    hist[c] = rel if c not in hist else (1 - args.ewma) * hist[c] + args.ewma * rel
            if (si + 1) % 20 == 0:
                print(f"  {si+1}/{len(sessions)} …", file=sys.stderr)
        sim_s = time.perf_counter() - t0

        cut = int(len(sessions) * args.train_frac)
        train = [r for r in rows if r["race"] < cut]
        test = [r for r in rows if r["race"] >= cut]
        if not train or not test:
            print("not enough races to split", file=sys.stderr)
            return 2

        taus = {b: fit_tau(train, b) for b in BASELINES}
        edge = [b for b, t in taus.items() if t in (0.02, 2000.0)]
        if edge:
            print(f"  NOTE: temperature saturated for {', '.join(edge)} — that value is the edge of the "
                  f"grid, not an estimate", file=sys.stderr)
        print(f"softmax temperature fitted PER BASELINE on {len(train)} training snapshots "
              f"(so none loses on a guessed constant):")
        print("  " + "   ".join(f"{b}={taus[b]:g}" for b in BASELINES) + "\n")

        def score(name: str, prob_of) -> dict:
            pr, y, pp, ap = [], [], [], []
            hit = top3 = shown = 0
            for r in test:
                pv = prob_of(r)
                if not pv:
                    continue
                for c in r["cars"]:
                    pr.append(pv.get(c, 0.0))
                    y.append(1.0 if r["winner"] == c else 0.0)
                order = sorted(pv, key=lambda c: -pv[c])
                if order and r["winner"] == order[0]:
                    hit += 1
                if r["winner"] in order[:3]:
                    top3 += 1
                shown += 1
                # ordering quality against the real classification
                for c in r["cars"]:
                    pp.append(-pv[c])
                    ap.append(float(r["final"][c]))
            if not pr:
                return {}
            br = require(w.execute("forecast_metrics", "base_rate", [y]), "base_rate")
            return {
                "n": shown,
                "win_hit": hit / max(shown, 1),
                "top3": top3 / max(shown, 1),
                "brier": require(w.execute("forecast_metrics", "brier_score", [pr, y]), "brier"),
                "bss": require(w.execute("forecast_metrics", "brier_skill_score",
                                         [pr, y, br]), "bss"),
                "ece": require(w.execute("forecast_metrics", "expected_calibration_error",
                                         [pr, y, 10]), "ece"),
                "rho": require(w.execute("forecast_metrics", "spearman_rho", [pp, ap]), "rho"),
            }

        results = {"oracle": score("oracle", lambda r: r["oracle_p"])}
        if args.ablate:
            for vname in (test[0]["abl"].keys() if test and test[0]["abl"] else []):
                results[f"oracle {vname}"] = score(vname, lambda r, v=vname: r["abl"].get(v, {}))
        for b in BASELINES:
            results[b] = score(b, lambda r, b=b: softmax_from_rank(r["ranks"][b], taus[b]))

        print(f"held-out: {len(test)} snapshots from {len(sessions)-cut} races the temperatures never saw")
        print(f"{'model':<20} {'win hit':>8} {'top-3':>7} {'Brier':>9} {'BSS':>8} {'ECE':>8} {'rho':>7}")
        abl_names = tuple(k for k in results if k.startswith("oracle "))
        for name in ("oracle",) + abl_names + BASELINES:
            m = results[name]
            if not m:
                continue
            print(f"{name:<20} {m['win_hit']*100:>7.1f}% {m['top3']*100:>6.1f}% {m['brier']:>9.5f} "
                  f"{m['bss']:>+8.3f} {m['ece']:>8.4f} {m['rho']:>+7.3f}")

        best_base = max((b for b in BASELINES if results[b]), key=lambda b: results[b]["bss"])
        o, bb = results["oracle"], results[best_base]
        print(f"\nstrongest baseline: {best_base} (BSS {bb['bss']:+.3f})")
        verdict = ("the simulation beats every mandatory baseline"
                   if o["bss"] > bb["bss"] else
                   f"the simulation LOSES to {best_base} — a faster simulator is not a better forecast")
        print(f"oracle BSS {o['bss']:+.3f} vs {bb['bss']:+.3f}: {verdict}")

        print(f"\nby decision point (oracle vs running_order, the baseline that matters most):")
        print(f"{'at':>6} {'n':>5} {'oracle BSS':>11} {'running BSS':>12}")
        for frac in fracs:
            sub = [r for r in test if r["frac"] == frac]
            if not sub:
                continue
            def sc(fn):
                pr, y = [], []
                for r in sub:
                    pv = fn(r)
                    for c in r["cars"]:
                        pr.append(pv.get(c, 0.0))
                        y.append(1.0 if r["winner"] == c else 0.0)
                b = require(w.execute("forecast_metrics", "base_rate", [y]), "br")
                return require(w.execute("forecast_metrics", "brier_skill_score", [pr, y, b]), "bss")
            print(f"{frac:>6.0%} {len(sub):>5} {sc(lambda r: r['oracle_p']):>+11.3f} "
                  f"{sc(lambda r: softmax_from_rank(r['ranks']['running_order'], taus['running_order'])):>+12.3f}")

        print(f"\nsimulation {sim_s:.1f} s over {len(rows)} snapshots")
        if args.json:
            Path(args.json).write_text(json.dumps({
                "sessions": len(sessions), "snapshots": len(rows), "held_out": len(test),
                "decision_points": fracs, "reps": args.reps, "taus": taus,
                "results": results, "strongest_baseline": best_base,
                "theta": args.theta_json or "kernel defaults",
            }, indent=2))
            print(f"wrote {args.json}", file=sys.stderr)
        return 0
    finally:
        w.close()


if __name__ == "__main__":
    raise SystemExit(main())
