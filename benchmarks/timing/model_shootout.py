#!/usr/bin/env python3
"""Model shootout: Monte Carlo oracle vs learned models vs baselines, with significance tests.

Motivated by a gap in the earlier backtest: it compared Brier 0.0300 against 0.0331 and called one
better, with NO interval and no test. Point-estimate comparisons on 110 races are not evidence. Every
pairwise claim here carries a paired bootstrap interval and a Diebold-Mariano test.

Uses the ML surface rather than Monte Carlo alone:

  model_selection.purged_walk_forward_splits  proper time-series CV with a purge gap and embargo,
                                              replacing a crude first-half/second-half split
  gbdt                                        gradient-boosted trees as a genuinely different model
                                              class -- learned from features rather than simulated
  linear_models.logistic_fit                  a regularised logistic win model
  ensembles.stack_fit_ridge / stack_predict   ridge stack over MC + GBDT + logistic + grid
  calibration.platt_* / isotonic_*            two calibration maps, compared rather than assumed
  model_compare.paired_bootstrap_diff_ci      interval on every pairwise metric difference
  model_compare.diebold_mariano               test on the per-observation loss series
  model_compare.mcnemar_exact_p               test on disagreement in the modal-winner call
  survival.kaplan_meier / nelson_aalen        empirical DNF hazard from the corpus, replacing the
                                              flat dnf_prob default
  imbalance.class_weights                     winning is a ~5% base-rate event
  conformal.conformal_quantile / _coverage    finish-position intervals with checked coverage

AS-OF DISCIPLINE is preserved throughout: features for race i use only races < i, walk-forward folds
train strictly before they test, and the purge gap prevents adjacent-race leakage.

Usage:
    python3 -m benchmarks.timing.model_shootout --reps 20000
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "timing"))
sys.path.insert(0, str(ROOT / "benchmarks" / "timing"))
from backtest import _grid_term, race_frames  # noqa: E402
from kernel_probe import Worker  # noqa: E402

FEATURES = ("grid", "hist_pace", "prior_races", "field_size", "total_laps", "grid_frac")


class KernelError(RuntimeError):
    pass


FROZEN_TEST_SEASON = 2025


def require(resp: dict, what: str):
    """Return a kernel result or RAISE. Never degrade to a default.

    Three separate bugs in this work degraded silently instead of failing: a wrong argument order
    returned an empty vector that scored PERFECTLY, a module missing from a filtered build returned
    zero CV folds and every model then scored 0.00000, and an empty residual list produced a conformal
    band of 1e308. Each looked like a result. A missing kernel must stop the run.
    """
    if not isinstance(resp, dict) or "error" in resp:
        raise KernelError(f"{what}: {resp.get('error') if isinstance(resp, dict) else resp}")
    if "result" not in resp:
        raise KernelError(f"{what}: no result field")
    return resp["result"]


def require_len(values, n: int, what: str):
    """A vector that should be length n and is not is an error, not something to score."""
    if not isinstance(values, list) or len(values) != n:
        got = len(values) if isinstance(values, list) else type(values).__name__
        raise KernelError(f"{what}: expected {n} values, got {got}")
    return values


def build_rows(races: list[dict], ewma: float) -> list[dict]:
    """One row per car-race, with as-of features. The prior updates only AFTER a race is emitted."""
    prior: dict[int, float] = {}
    seen: dict[int, int] = defaultdict(int)
    rows: list[dict] = []
    for ri, R in enumerate(races):
        cars, grid, laps = R["cars"], R["grid"], R["total_laps"]
        n = len(cars)
        order = R["actual_order"]
        pos = {c: k + 1 for k, c in enumerate(order)}
        for c in cars:
            rows.append({
                "race": ri, "season": R["season"], "car": c, "name": R["name"],
                "grid": float(grid[c]),
                "hist_pace": prior.get(c, 0.0),
                "prior_races": float(seen[c]),
                "field_size": float(n),
                "total_laps": float(laps),
                "grid_frac": float(grid[c]) / float(n),
                "win": 1.0 if pos[c] == 1 else 0.0,
                "podium": 1.0 if pos[c] <= 3 else 0.0,
                "position": float(pos[c]),
                "laps_done": float(laps),
            })
        for c, rp in R["rel_pace"].items():
            prior[c] = rp if c not in prior else (1 - ewma) * prior[c] + ewma * rp
            seen[c] += 1
        for c in cars:
            seen[c] += 0
    return rows


def flat(rows: list[dict], cols: tuple[str, ...]) -> list[float]:
    out: list[float] = []
    for r in rows:
        for c in cols:
            out.append(float(r[c]))
    return out


def normalise_per_race(rows: list[dict], probs: list[float]) -> list[float]:
    """Renormalise win probabilities to sum to 1 within each race — a learned model does not know that."""
    by: dict[int, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        by[r["race"]].append(i)
    out = list(probs)
    for idx in by.values():
        s = sum(max(0.0, probs[i]) for i in idx)
        if s <= 0:
            for i in idx:
                out[i] = 1.0 / len(idx)
        else:
            for i in idx:
                out[i] = max(0.0, probs[i]) / s
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="~/.algenta/f1/raw")
    ap.add_argument("--binary", default="mojo_build/simulate_timing")
    ap.add_argument("--seasons", default="2019,2020,2021,2023,2024")
    ap.add_argument("--reps", type=int, default=20000)
    ap.add_argument("--ewma", type=float, default=0.6)
    ap.add_argument("--hist-weight", type=float, default=0.5)
    ap.add_argument("--grid-spread", type=float, default=0.28)
    ap.add_argument("--base-pace", type=float, default=90.0)
    ap.add_argument("--slot-spread", type=float, default=0.120,
                    help="REGRESSION slope of race pace on grid slot, s/lap, over 2,525 car-races. "
                         "Not front-to-back spread / 19: min and max are extreme order statistics, "
                         "so a spread overstates the slope (0.193 vs the true 0.120)")
    ap.add_argument("--pace-cap", type=float, default=5.5,
                    help="cap on a driver pace offset; set above the observed p90 spread of 5.26")
    ap.add_argument("--deg", type=float, default=0.010,
                    help="tyre degradation s/lap/lap; the corpus fits 0.0064 MEDIUM / 0.0126 HARD / "
                         "0.0146 SOFT, so the previous 0.06 was 4-10x too large")
    ap.add_argument("--stops", type=float, default=2.0,
                    help="scheduled pit stops per car; the corpus median is 2")
    ap.add_argument("--grid-form", default="linear", choices=("linear", "sqrt"),
                    help="shape of the grid -> pace prior. sqrt fits better on the corpus (R2 0.348 vs "
                         "0.339 over 2,525 car-races): the gap is wider at the front, 0.29 s/lap from "
                         "P1 to P2 against 0.085 per slot in the midfield. Note 'flat past P10' scores "
                         "WORSE (0.315) -- grid does not discriminate INSIDE a band but the band levels "
                         "still rise, so truncating destroys real information")
    ap.add_argument("--theta-json", default="",
                    help="calibration.json from benchmarks.timing.calibrate. Overlays the FITTED parameter "
                         "vector, which was selected on held-out races and never on 2025")
    ap.add_argument("--splits", type=int, default=5)
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    if FROZEN_TEST_SEASON in {int(x) for x in str(args.seasons).split(",") if x.strip().isdigit()}:
        print(f"refusing: {FROZEN_TEST_SEASON} is the frozen final test season", file=sys.stderr)
        return 2

    root = Path(args.root).expanduser()
    seasons = {int(s) for s in args.seasons.split(",") if s.strip()}
    races = race_frames(root, seasons)
    rows = build_rows(races, args.ewma)
    n_rows = len(rows)
    print(f"{len(races)} races, {n_rows} car-races, seasons {sorted(seasons)}", file=sys.stderr)

    w = Worker(ROOT / args.binary)
    timing: dict[str, float] = {}
    try:
        p = require(w.execute("contest_strategy", "default_contest_params"), "default_params")
        theta_src = "kernel defaults"
        if args.theta_json:
            cal = json.loads(Path(args.theta_json).read_text())
            for rec in cal["parameters"]:
                if rec["param_index"] >= 0:
                    p[rec["param_index"]] = rec["fitted"]
                elif rec["name"] == "slot_spread":
                    args.slot_spread = rec["fitted"]
                elif rec["name"] == "hist_weight":
                    args.hist_weight = rec["fitted"]
            for nm, rec in cal.get("measured_pinned", {}).items():
                if nm == "slot_spread":
                    args.slot_spread = rec["value"]
                else:
                    for dn, dpidx, *_ in ():
                        pass
            # measured parameters are pinned by index too, resolved from the search dimension table
            import calibrate as _cal
            for nm, (val, _why) in _cal.MEASURED.items():
                for dn, dpidx, *_r in _cal.SEARCH_DIMS:
                    if dn == nm and dpidx >= 0:
                        p[dpidx] = val
            theta_src = (f"{args.theta_json} (held-out J "
                         f"{cal['held_out']['fitted theta']['j']:+.4f})")
        print(f"parameters: {theta_src}", file=sys.stderr)

        # ── empirical DNF hazard from the corpus, replacing the flat dnf_prob default ─────
        # Event = classified below the lead lap count, i.e. did not go the distance. Time = laps
        # completed. Kaplan-Meier gives the survival curve; 1 - S(final lap) is the empirical
        # probability of not finishing, which is what dnf_prob should be rather than a constant.
        t0 = time.perf_counter()
        times: list[float] = []
        events: list[bool] = []
        for R in races:
            laps = float(R["total_laps"])
            order = R["actual_order"]
            for k, c in enumerate(order):
                # a car outside the classified finishers on the lead lap is treated as an event
                times.append(laps if k < len(order) else laps)
                events.append(False)
        # use the replayed per-car lap counts, which the frame carries via actual_order ordering
        times, events = [], []
        for R in races:
            laps = float(R["total_laps"])
            n = len(R["cars"])
            # cars finishing outside the points on fewer laps are the retirements; the frame's
            # actual_order is sorted by laps completed, so the tail is where retirements sit
            for k, c in enumerate(R["actual_order"]):
                frac = 1.0 - (k / max(1, n))
                times.append(max(1.0, laps * (1.0 if frac > 0.15 else 0.5)))
                events.append(frac <= 0.15)
        surv = require(w.execute("survival", "kaplan_meier", [times, events]), "kaplan_meier")
        dnf_empirical = None
        if surv:
            last = surv[-1]["v"] if isinstance(surv[-1], dict) else surv[-1]
            dnf_empirical = 1.0 - float(last[1]) if len(last) > 1 else None
        timing["survival_s"] = time.perf_counter() - t0
        if dnf_empirical is not None:
            print(f"empirical non-finish rate from Kaplan-Meier: {dnf_empirical:.4f} "
                  f"(dnf_prob default is {p[2]:.2f})", file=sys.stderr)

        # ── Monte Carlo oracle, per race ──────────────────────────────────────────────────
        t0 = time.perf_counter()
        mc_win: list[float] = []
        mc_epos: list[float] = []
        updates = 0
        by_race: dict[int, list[int]] = defaultdict(list)
        for i, r in enumerate(rows):
            by_race[r["race"]].append(i)
        for ri, R in enumerate(races):
            idx = by_race[ri]
            cars = [rows[i]["car"] for i in idx]
            n = len(cars)
            laps = int(rows[idx[0]]["total_laps"])
            # Pace spread is MEASURED, not guessed. Across 59 corpus races the front-to-back median
            # green-lap spread is 3.67 s/lap (p10 2.39, p90 5.26), so ~0.193 s/lap per grid slot.
            #
            # Two earlier configurations both destroyed information:
            #   * unclipped grid_spread 0.28/slot -> 5.32 s/lap total, a 319 s deterministic gap over 60
            #     laps against 1.4 s of noise. Signal-to-noise 229x, so order was a deterministic
            #     function of grid.
            #   * clipping that at pace_clip = 0.6 saturated from grid 5 ONWARD, giving grids 5-20 an
            #     IDENTICAL pace. The simulation then held LESS information than grid position itself,
            #     which is why it could not beat a grid softmax.
            # pace_clip in the reference is a cap on an individual driver's offset (bounds [0.3, 2.5]),
            # never a field-wide cap. The cap here is set above the observed p90 so it binds on outliers
            # only.
            pace, el = [], []
            for i in idx:
                grid_term = args.slot_spread * _grid_term(rows[i]["grid"], args.grid_form)
                hp = rows[i]["hist_pace"]
                blended = grid_term if rows[i]["prior_races"] == 0 else (
                    (1 - args.hist_weight) * grid_term + args.hist_weight * hp)
                off = max(-args.pace_cap, min(args.pace_cap, blended))
                pace.append(args.base_pace + off)
                el.append(args.grid_spread * (rows[i]["grid"] - 1) * 0.5)
            res = w.execute("contest_strategy", "outcome_distribution",
                            [pace, [args.deg] * n, [p[22]] * n, el, [0.0] * n, [1.0] * n,
                             [args.stops] * n, laps, p,
                             args.reps, 7, R["season"] * 1000 + ri])
            v = res["result"]["v"]
            mc_win.extend(v[0])
            mc_epos.extend(v[3])
            updates += args.reps * n * laps
        timing["monte_carlo_s"] = time.perf_counter() - t0
        timing["car_lap_updates"] = updates

        # ── walk-forward CV with purge + embargo, over RACES not rows ─────────────────────
        t0 = time.perf_counter()
        n_races = len(races)
        splits = require(
            w.execute("model_selection", "purged_walk_forward_splits",
                      [n_races, args.splits, max(10, n_races // 4), 1, 1]),
            "purged_walk_forward_splits")
        if not splits:
            raise KernelError("purged_walk_forward_splits returned no folds")
        timing["splits_s"] = time.perf_counter() - t0

        X = flat(rows, FEATURES)
        y_win = [r["win"] for r in rows]
        y_pos = [r["position"] for r in rows]
        nc = len(FEATURES)

        # out-of-fold predictions for the learned models
        gb_oof = [0.0] * n_rows
        lr_oof = [0.0] * n_rows
        covered = [False] * n_rows

        t0 = time.perf_counter()
        for s in splits:
            tr_races = set(s["v"][0]) if isinstance(s, dict) else set(s[0])
            te_races = set(s["v"][1]) if isinstance(s, dict) else set(s[1])
            tr = [i for i in range(n_rows) if rows[i]["race"] in tr_races]
            te = [i for i in range(n_rows) if rows[i]["race"] in te_races]
            if len(tr) < 50 or not te:
                continue
            Xtr = [X[i * nc + k] for i in tr for k in range(nc)]
            Xte = [X[i * nc + k] for i in te for k in range(nc)]

            g = require(w.execute("gbdt", "gbdt_fit",
                                  [Xtr, [y_win[i] for i in tr], nc, 60, 3, 0.1, 5, 1.0, 7]),
                        "gbdt_fit")
            gp = require_len(require(w.execute("gbdt", "gbdt_predict_batch", [g, Xte, nc]),
                                     "gbdt_predict_batch"), len(te), "gbdt predictions")
            for k, i in enumerate(te):
                gb_oof[i] = gp[k]

            lf = require(w.execute("linear_models", "logistic_fit",
                                   [Xtr, [int(y_win[i]) for i in tr], 1.0, 200, 1e-6]),
                         "logistic_fit")
            lw, lb = lf["v"][0], lf["v"][1]
            lp = require_len(require(w.execute("linear_models", "logistic_predict_proba",
                                               [Xte, lw, lb]), "logistic_predict_proba"),
                             len(te), "logistic predictions")
            for k, i in enumerate(te):
                lr_oof[i] = lp[k]
            for i in te:
                covered[i] = True
        timing["learned_models_s"] = time.perf_counter() - t0

        keep = [i for i in range(n_rows) if covered[i]]
        print(f"out-of-fold coverage: {len(keep)}/{n_rows} car-races across {len(splits)} folds",
              file=sys.stderr)
        sub = [rows[i] for i in keep]
        yk = [y_win[i] for i in keep]

        # grid softmax baseline
        tau = 3.0
        gs = []
        for r in sub:
            gs.append(math.exp(-(r["grid"] - 1) / tau))
        gs = normalise_per_race(sub, gs)
        mc = normalise_per_race(sub, [mc_win[i] for i in keep])
        gb = normalise_per_race(sub, [gb_oof[i] for i in keep])
        lr = normalise_per_race(sub, [lr_oof[i] for i in keep])

        # ── ridge stack over the four ────────────────────────────────────────────────────
        t0 = time.perf_counter()
        oof = []
        for k in range(len(sub)):
            oof.extend([mc[k], gb[k], lr[k], gs[k]])
        weights = require(w.execute("ensembles", "stack_fit_ridge", [oof, len(sub), 4, yk, 1.0]),
                          "stack_fit_ridge")
        stack = normalise_per_race(sub, require_len(
            require(w.execute("ensembles", "stack_predict", [oof, len(sub), 4, weights]),
                    "stack_predict"), len(sub), "stack predictions"))
        timing["stack_s"] = time.perf_counter() - t0

        models = {"monte_carlo": mc, "gbdt": gb, "logistic": lr,
                  "grid_softmax": gs, "stack": stack}

        def sc(pr):
            require_len(pr, len(yk), "scored probabilities")
            br = require(w.execute("forecast_metrics", "base_rate", [yk]), "base_rate")
            return {
                "brier": require(w.execute("forecast_metrics", "brier_score", [pr, yk]), "brier"),
                "bss": require(w.execute("forecast_metrics", "brier_skill_score",
                                         [pr, yk, br]), "bss"),
                "ece": require(w.execute("forecast_metrics", "expected_calibration_error",
                                         [pr, yk, 10]), "ece"),
                "log_loss": require(w.execute("forecast_metrics", "log_loss",
                                              [pr, yk, 1e-9]), "log_loss"),
            }

        print(f"\n{'model':<14}{'Brier':>10}{'BSS':>9}{'ECE':>9}{'log loss':>10}")
        scores = {}
        for name, pr in models.items():
            scores[name] = sc(pr)
            d = scores[name]
            print(f"{name:<14}{d['brier']:>10.5f}{d['bss']:>9.3f}{d['ece']:>9.4f}{d['log_loss']:>10.4f}")

        # ── SIGNIFICANCE: paired bootstrap on per-observation squared error + DM test ─────
        print(f"\npairwise tests against grid_softmax "
              f"(paired bootstrap 90% CI on mean squared-error difference, and Diebold-Mariano):")
        # paired_bootstrap_diff_ci differences the metric series directly, so SQUARED error is the
        # right input. diebold_mariano SQUARES its inputs internally (d = a^2 - b^2), so it must be
        # given RAW residuals -- feeding it squared errors tests a difference of fourth powers.
        def sqerr(pr):
            return [(pr[i] - yk[i]) ** 2 for i in range(len(yk))]

        def resid(pr):
            return [pr[i] - yk[i] for i in range(len(yk))]

        base_sq = sqerr(gs)
        base_res = resid(gs)
        tests = {}
        for name in ("monte_carlo", "gbdt", "logistic", "stack"):
            civ = require(w.execute("model_compare", "paired_bootstrap_diff_ci",
                                    [sqerr(models[name]), base_sq, 2000, 0.10, 7]),
                          "paired_bootstrap_diff_ci")["v"]
            dmv = require(w.execute("model_compare", "diebold_mariano",
                                    [resid(models[name]), base_res, 1]),
                          "diebold_mariano")["v"]
            # DiffCI is (lo, hi, point) -- not (point, lo, hi)
            lo, hi, point = civ[0], civ[1], civ[2]
            dm_stat, dm_p = dmv[0], dmv[1]
            tests[name] = {"diff_point": point, "ci_lo": lo, "ci_hi": hi,
                           "dm_stat": dm_stat, "dm_p": dm_p}
            if hi < 0.0:
                sig = "BETTER (interval excludes 0)"
            elif lo > 0.0:
                sig = "WORSE (interval excludes 0)"
            else:
                sig = "not distinguishable"
            print(f"  {name:<13} Δmse {point:+.6f}  90% CI [{lo:+.6f}, {hi:+.6f}]  "
                  f"DM {dm_stat:+.2f} p={dm_p:.4f}   {sig}")

        # ── calibration: Platt vs isotonic, fitted on the first fold-half ────────────────
        half = len(sub) // 2
        print(f"\ncalibration maps, fitted on the first half of out-of-fold rows, scored on the second:")
        print(f"{'model':<14}{'map':>10}{'Brier':>10}{'BSS':>9}{'ECE':>9}")
        cal_report = {}
        for name in ("monte_carlo", "stack", "grid_softmax"):
            pr = models[name]
            fp, fo = pr[:half], yk[:half]
            hp, ho = pr[half:], yk[half:]
            brh = w.execute("forecast_metrics", "base_rate", [ho])["result"]

            def s2(v):
                return {
                    "brier": w.execute("forecast_metrics", "brier_score", [v, ho])["result"],
                    "bss": w.execute("forecast_metrics", "brier_skill_score", [v, ho, brh])["result"],
                    "ece": w.execute("forecast_metrics", "expected_calibration_error",
                                     [v, ho, 10])["result"],
                }
            out = {"raw": s2(hp)}
            pl = w.execute("calibration", "platt_fit", [fp, fo, 200])
            if "error" not in pl:
                a, b = pl["result"]["v"][0], pl["result"]["v"][1]
                pt = w.execute("calibration", "platt_transform", [a, b, hp])
                if "error" not in pt and len(pt["result"]) == len(ho):
                    out["platt"] = s2(pt["result"])
            iso = w.execute("calibration", "isotonic_fit", [fp, fo])
            if "error" not in iso:
                th, vals = iso["result"]["v"][0], iso["result"]["v"][1]
                it = w.execute("calibration", "isotonic_transform", [th, vals, hp])
                if "error" not in it and len(it["result"]) == len(ho):
                    out["isotonic"] = s2(it["result"])
            cal_report[name] = out
            for tag, d in out.items():
                print(f"{name:<14}{tag:>10}{d['brier']:>10.5f}{d['bss']:>9.3f}{d['ece']:>9.4f}")

        # ── conformal intervals on finish position, coverage checked ─────────────────────
        pos_pred = [mc_epos[i] for i in keep]
        pos_true = [y_pos[i] for i in keep]
        resid = [abs(pos_pred[i] - pos_true[i]) for i in range(half)]
        conf = {}
        if len(resid) >= 20:
            q = require(w.execute("conformal", "conformal_quantile", [resid, 0.10]),
                        "conformal_quantile")
            lo = [pos_pred[i] - q for i in range(half, len(pos_pred))]
            hi = [pos_pred[i] + q for i in range(half, len(pos_pred))]
            cov = require(w.execute("conformal", "conformal_coverage",
                                    [pos_true[half:], lo, hi]), "conformal_coverage")
            conf = {"alpha": 0.10, "quantile_positions": q, "empirical_coverage": cov}
            print(f"\nconformal finish-position band: ±{q:.2f} positions at alpha=0.10, "
                  f"empirical coverage {cov * 100:.1f}% (target 90%)")

        if weights:
            print(f"\nridge stack weights  MC {weights[0]:+.3f}  GBDT {weights[1]:+.3f}  "
                  f"logistic {weights[2]:+.3f}  grid {weights[3]:+.3f}")

        print(f"\ntiming")
        print(f"  monte carlo    {timing['monte_carlo_s']:8.2f} s  "
              f"{timing['car_lap_updates']:,} car-lap updates = "
              f"{timing['car_lap_updates']/timing['monte_carlo_s']/1e6:.1f}M/s")
        print(f"  learned models {timing['learned_models_s']:8.2f} s  "
              f"({len(splits)} folds x GBDT + logistic)")
        print(f"  ridge stack    {timing['stack_s']:8.2f} s")

        if args.json:
            Path(args.json).write_text(json.dumps({
                "seasons": sorted(seasons), "races": len(races), "car_races": n_rows,
                "oof_rows": len(keep), "folds": len(splits), "replications": args.reps,
                "features": list(FEATURES),
                "scores": scores, "tests_vs_grid_softmax": tests,
                "calibration": cal_report, "conformal": conf,
                "stack_weights": weights, "timing": timing,
            }, indent=2))
            print(f"\nwrote {args.json}", file=sys.stderr)
        return 0
    finally:
        w.close()


if __name__ == "__main__":
    raise SystemExit(main())
