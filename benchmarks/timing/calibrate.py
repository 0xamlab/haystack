#!/usr/bin/env python3
"""Gate 3A/3B — calibrate the simulation parameters against the corpus, then select on held-out races.

WHAT THIS IS FOR

The simulation has 23 parameters. A handful were fitted from observation (pit loss and its tail from
3,260 pit-lane times), a handful are reference defaults, and the five interaction parameters plus the
per-car form sigma are the ones the corpus has to speak to. Guessing them is how the earlier
configuration ended up 41x short on pace uncertainty while looking superficially reasonable.

WHAT MAKES THE RESULT REPORTABLE

  * SELECTION IS ON HELD-OUT RACES. The search optimises on a training block and the reported score
    comes from a later, unseen block. 2025 is the frozen final test and is not read here at all.
  * COMMON RANDOM NUMBERS ACROSS CANDIDATES. Every candidate simulates the same random world (one
    master seed), so two thetas are compared on paired outcomes. Without this the search would chase
    Monte Carlo noise: at 600 replications the sampling error on a win probability is around 2pp, which
    is larger than the differences between good candidates.
  * THE SEARCH IS A KERNEL. Simulation (`outcome_distribution`), scoring (`forecast_metrics`) and the
    evolutionary operators (`evolutionary_search`) all execute in Mojo. Python moves arrays between them.
  * IDENTIFIABILITY IS REPORTED, NOT ASSUMED. `ga_diversity` gives the surviving spread per dimension
    and `ga_saturation` shows which bounds the search pressed against. A parameter whose spread never
    collapses is one the objective cannot resolve, and printing a precise value for it would overstate
    what the data supports.

The objective follows the plan: J = rho_Spearman - 2*Brier - ECE, all three from the metrics kernel.
Churn is reported alongside as a structural diagnostic -- the corpus measures a mean 2.68 positions of
displacement between the opening lap and the finish, and a model that misses that is wrong in a way no
single probability score exposes.

Usage:
    python3 -m benchmarks.timing.calibrate                      # default search
    python3 -m benchmarks.timing.calibrate --pop 24 --gens 20 --reps 800
    python3 -m benchmarks.timing.calibrate --json docs/timing/calibration.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "timing"))
sys.path.insert(0, str(ROOT / "benchmarks" / "timing"))
from features import FEATURES, build as build_features  # noqa: E402
from kernel_probe import Worker  # noqa: E402
from model_shootout import require  # noqa: E402

FROZEN_TEST_SEASON = 2025

# WHAT THE SEARCH IS AND IS NOT ALLOWED TO CHOOSE
#
# A first run over all 18 dimensions drove sc_lambda to 0.000 against its lower bound: the objective
# wanted safety cars ABOLISHED. lap_noise saturated high and cliff_age went to its ceiling at the same
# time. That is one coherent preference, not three quirks -- for a PRE-RACE win probability, real-world
# structured variance is noise, so a Brier/ECE objective buys calibration by deleting it. The fitted
# vector scored better on held-out races while describing a world with no safety cars in it.
#
# Shipping that to the decision board would be worthless: pit timing is largely ABOUT neutralisations.
# This is the dual-path hazard the plan names -- "a calibration objective rewards whatever correlates
# with finishing order" -- so parameters the corpus measures DIRECTLY and cleanly are fixed at their
# measured values, and only the ones public data cannot pin down are searched.
#
# MEASURED (fixed): event rates and durations from 131 races, and the grid-pace regression slope. These
# are observations, not preferences, and the objective does not get a vote on them.
# CONFOUNDED (searched): pace_sigma is contaminated by reverse causation -- a car stuck in traffic
# records slow "race pace" BECAUSE it finished badly -- and the cliff is selection-confounded because
# long stints are disproportionately hard-tyre stints on low-degradation tracks.
# UNOBSERVABLE (searched): nothing in public timing pins down dirty-air loss, following distance,
# bunching, or the pass model's coefficients.
MEASURED: dict[str, tuple[float, str]] = {
    "sc_lambda":   (0.0191, "1.09 SC events per race over ~57 laps, 131 races"),
    "vsc_lambda":  (0.0082, "0.47 VSC events per race over ~57 laps"),
    "sc_dur_max":  (5.0,    "mean SC duration 3.17 laps; uniform 1..5 has mean 3.0"),
    "vsc_dur_max": (2.0,    "mean VSC duration 1.28 laps; uniform 1..2 has mean 1.5"),
    # The search drove this to its LOWER bound -- it wants no retirements at all, the same
    # variance-deletion preference that tried to abolish safety cars. Retirement rate is directly
    # measurable, so the objective gets no vote on it either.
    "dnf_prob":    (0.00273, "0.165 of cars retire over a mean 61-lap race, as a per-lap hazard"),
}

# (name, params[] index or a driver-side sentinel, low, high)
SEARCH_DIMS: tuple[tuple[str, int, float, float], ...] = (
    ("pace_sigma",   22, 0.00, 1.20),
    ("ot_bias",      17, -4.00, 0.00),
    ("ot_kpace",     18, 0.00, 2.00),
    ("dirty_loss",   10, 0.00, 0.80),
    ("min_follow",   19, 0.00, 2.50),
    ("sc_bunch",     20, 0.20, 3.00),
    ("lap_noise",     1, 0.05, 0.60),
    ("dnf_prob",      2, 0.00, 0.010),
    ("sc_lambda",     3, 0.00, 0.06),
    ("vsc_lambda",    6, 0.00, 0.03),
    ("stop_jitter",  21, 0.00, 0.30),
    # Durations are measured (SC 3.17 laps, VSC 1.28) but the uniform 1..max shape is an assumption,
    # so the max stays in the search rather than being asserted.
    ("sc_dur_max",   23, 1.00, 10.00),
    ("vsc_dur_max",  24, 1.00, 5.00),
    ("ot_kage",       25, 0.00, 0.20),
    # The cliff is what makes a pit stop worth taking at all, so its knee and slope are the two
    # dimensions the held-out score depends on most.
    ("cliff_age",     26, 5.00, 70.00),
    ("cliff_slope",   27, 0.00, 0.30),
) + tuple(
    # FEATURE WEIGHTS, selected by the SIMULATION rather than fitted to pace RMSE. Those are different
    # targets: minimising pace error optimises a proxy, while the board is scored on a win probability
    # after the prior has been pushed through traffic, tyre life, neutralisations and retirement. A
    # feature can lower pace RMSE and still cost skill once propagated, and only the simulation can say
    # so. The range admits NEGATIVE weights, because a feature may be useful as a suppressor of another.
    # THE BOX IS PART OF THE MODEL, and wider is not better. These bounds saturated, so they were
    # widened to [-2.00, 3.00] with pace_sigma to 2.20 and a larger budget (48 x 55). The result was
    # WORSE on held-out races -- Brier 0.03449 against 0.03034, BSS +0.303 against +0.387 -- with four
    # weights pinned to the new bounds and pace_sigma driven to 0.000, i.e. all per-car form uncertainty
    # deleted. Given a sharper prior and more freedom the search builds a near-deterministic
    # configuration that fits the training block and does not transfer.
    #
    # So saturation is not automatically evidence that a bound is wrong: here the bound was doing useful
    # regularisation, and the narrower box is retained deliberately. Choosing between the two on held-out
    # score is Gate 3B selection, done before the final test is opened, and it is recorded rather than
    # quietly applied.
    (f"w_{name}", -100 - k, -0.60, 1.60) for k, name in enumerate(FEATURES)
)


def _git_commit() -> str:
    """The commit the fitted theta was produced at. A theta without one cannot be re-derived."""
    import subprocess
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT), capture_output=True,
                              text=True, timeout=10).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def pace_prior(rows: list[dict], idx: list[int], weights: dict, base_pace: float,
               cap: float) -> tuple[list[float], list[float]]:
    """Weighted sum of the engineered features, in s/lap relative to the field.

    Every feature is already expressed in s/lap relative to the field median (prior_races is a 0-1
    confidence scalar), so a weight near 1 is the natural scale and the sum is directly a pace offset.
    A car with no practice read contributes 0 from that term rather than a guessed value, so the weight
    is never asked to compensate for missingness.
    """
    pace, el = [], []
    for i in idx:
        r = rows[i]
        off = 0.0
        for name in FEATURES:
            w = weights.get(name, 0.0)
            if w:
                off += w * r.get(name, 0.0)
        pace.append(base_pace + max(-cap, min(cap, off)))
        # track position at the flag is the GRID, independent of the pace prior
        el.append(0.28 * (r["grid"] - 1) * 0.5)
    return pace, el


def evaluate(w: Worker, theta: list[float], base: list[float], races: list[dict],
             rows: list[dict], by_race: dict, race_ids: list[int],
             reps: int, seed: int, deg: float, stops: float,
             base_pace: float, cap: float,
             free: tuple = SEARCH_DIMS) -> dict:
    """Simulate every race in the block under one theta and score it with the metrics kernel."""
    params = list(base)
    weights: dict[str, float] = {}
    # pin every measured parameter first, so a searched dimension can never overwrite an observation
    for name, (value, _why) in MEASURED.items():
        for dn, dpidx, _l, _h in SEARCH_DIMS:
            if dn == name and dpidx >= 0:
                params[dpidx] = value
    for k, (name, pidx, _lo, _hi) in enumerate(free):
        if pidx >= 0:
            params[pidx] = theta[k]
        elif pidx <= -100:
            weights[FEATURES[-100 - pidx]] = theta[k]

    p_win, y_win, pred_pos, act_pos, churn = [], [], [], [], []
    for ri in race_ids:
        idx = by_race[ri]
        n = len(idx)
        if n < 4:
            continue
        R = races[ri] if ri < len(races) else {"season": 0, "total_laps": 57}
        pace, el = pace_prior(rows, idx, weights, base_pace, cap)
        laps = int(R["total_laps"])
        v = require(w.execute("contest_strategy", "outcome_distribution",
                              [pace, [deg] * n, [params[22]] * n, el, [0.0] * n, [1.0] * n,
                               [stops] * n, laps, params, reps, seed,
                               R["season"] * 1000 + ri]), "outcome_distribution")["v"]
        pw, ep, disp = v[0], v[3], v[6]
        s = sum(pw) or 1.0
        for k, i in enumerate(idx):
            p_win.append(pw[k] / s)
            y_win.append(rows[i]["win"])
            pred_pos.append(ep[k])
            act_pos.append(rows[i]["position"])
        churn.append(disp)

    if not p_win:
        return {"j": -9e9, "brier": 0.0, "ece": 0.0, "rho": 0.0, "churn": 0.0}
    br = require(w.execute("forecast_metrics", "base_rate", [y_win]), "base_rate")
    brier = require(w.execute("forecast_metrics", "brier_score", [p_win, y_win]), "brier")
    ece = require(w.execute("forecast_metrics", "expected_calibration_error",
                            [p_win, y_win, 10]), "ece")
    bss = require(w.execute("forecast_metrics", "brier_skill_score", [p_win, y_win, br]), "bss")
    rho = require(w.execute("forecast_metrics", "spearman_rho", [pred_pos, act_pos]), "spearman")
    return {"j": rho - 2.0 * brier - ece, "brier": brier, "ece": ece, "rho": rho, "bss": bss,
            "churn": sum(churn) / len(churn), "n": len(p_win)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="~/.algenta/f1/raw")
    ap.add_argument("--binary", default="mojo_build/simulate_timing")
    ap.add_argument("--seasons", default="2019,2020,2021,2023,2024",
                    help="Gate 3A development seasons. 2025 is the frozen final test and is absent "
                         "by construction, not by a filter that could be edited away")
    ap.add_argument("--pop", type=int, default=24)
    ap.add_argument("--gens", type=int, default=18)
    ap.add_argument("--reps", type=int, default=600, help="replications per race DURING the search")
    ap.add_argument("--final-reps", type=int, default=6000, help="replications for the held-out score")
    ap.add_argument("--train-frac", type=float, default=0.65)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--ewma", type=float, default=0.35)
    ap.add_argument("--base-pace", type=float, default=90.0)
    ap.add_argument("--pace-cap", type=float, default=5.5)
    ap.add_argument("--deg", type=float, default=0.010)
    ap.add_argument("--stops", type=float, default=2.0)
    ap.add_argument("--tournament", type=int, default=3)
    ap.add_argument("--cx-rate", type=float, default=0.5)
    ap.add_argument("--mut-rate", type=float, default=0.30)
    ap.add_argument("--mut-scale", type=float, default=0.15)
    ap.add_argument("--elite", type=int, default=3)
    ap.add_argument("--search-measured", action="store_true",
                    help="also search the directly-measured parameters. Reproduces the run that drove "
                         "sc_lambda to zero; useful as a demonstration, not as a shipping config")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    binary = ROOT / args.binary
    if not binary.exists():
        print(f"binary not found: {binary}", file=sys.stderr)
        return 2

    seasons = {int(x) for x in args.seasons.split(",") if x.strip()}
    if FROZEN_TEST_SEASON in seasons:
        print(f"refusing to calibrate on {FROZEN_TEST_SEASON}: it is the frozen final test season",
              file=sys.stderr)
        return 2
    rows = build_features(Path(args.root).expanduser(), seasons)
    if not rows:
        print("no feature rows built", file=sys.stderr)
        return 2
    by_race: dict[int, list[int]] = {}
    for i, r in enumerate(rows):
        by_race.setdefault(r["race"], []).append(i)
    races = [{"season": rows[v[0]]["season"], "name": rows[v[0]]["circuit"],
              "total_laps": 57} for _k, v in sorted(by_race.items())]
    ids = sorted(by_race)
    cut = int(len(ids) * args.train_frac)
    train, val = ids[:cut], ids[cut:]

    free = tuple(d for d in SEARCH_DIMS if d[0] not in MEASURED or args.search_measured)
    lo = [d[2] for d in free]
    hi = [d[3] for d in free]
    n_dim = len(free)

    w = Worker(binary)
    try:
        base = require(w.execute("contest_strategy", "default_contest_params"), "defaults")
        ver = require(w.execute("evolutionary_search", "search_version"), "search_version")
        st = require(w.execute("evolutionary_search", "search_selftest"), "search_selftest")
        print(f"search {ver}   selftest {st:.4f} (peak at 3.0)   rng "
              f"{require(w.execute('counter_rng', 'rng_version'), 'rng')}")
        print(f"corpus: {len(races)} races, {len(rows)} car-races. {FROZEN_TEST_SEASON} withheld "
              f"as the frozen final test and not read here.")
        print(f"train {len(train)} races (seasons "
              f"{sorted({races[i]['season'] for i in train})}) -> "
              f"select on {len(val)} LATER races (seasons {sorted({races[i]['season'] for i in val})})")
        print(f"search: pop {args.pop} x {args.gens} generations x {len(train)} races x "
              f"{args.reps} reps over {n_dim} FREE dimensions")
        if not args.search_measured:
            print(f"  {len(MEASURED)} measured parameters PINNED (the objective gets no vote):")
            for nm, (v, why) in MEASURED.items():
                print(f"    {nm:<12} = {v:<8} {why}")
        print()

        def score(theta, ids_, reps):
            return evaluate(w, theta, base, races, rows, by_race, ids_, reps, args.seed,
                            args.deg, args.stops, args.base_pace, args.pace_cap, free)

        # The incumbent is the SHIPPED configuration, so the search starts from what is deployed and
        # elitism carries it until something genuinely beats it. Before the feature layer the prior was
        # 0.5*grid + 0.5*history, which is exactly w_grid_centred = w_hist_pace = 0.5 with the rest off.
        SHIPPED_WEIGHTS = {"w_grid_centred": 0.5, "w_hist_pace": 0.5}
        incumbent = []
        for name, pidx, l, h in free:
            if pidx >= 0:
                incumbent.append(base[pidx])
            else:
                incumbent.append(SHIPPED_WEIGHTS.get(name, 0.0))

        t0 = time.perf_counter()
        pop = w.execute("evolutionary_search", "ga_init", [lo, hi, args.pop, args.seed])["result"]
        if isinstance(pop, dict):
            pop = pop["v"]
        # plant the incumbent so the search cannot silently lose to the shipped defaults
        for j in range(n_dim):
            pop[j] = incumbent[j]

        trace = []
        best_theta, best_j = None, -9e9
        for g in range(args.gens):
            fit = []
            for i in range(args.pop):
                th = pop[i * n_dim:(i + 1) * n_dim]
                fit.append(score(th, train, args.reps)["j"])
            b = w.execute("evolutionary_search", "ga_best", [pop, fit, n_dim])["result"]
            if isinstance(b, dict):
                b = b["v"]
            if b[-1] > best_j:
                best_j, best_theta = b[-1], b[:n_dim]
            div = w.execute("evolutionary_search", "ga_diversity", [pop, n_dim])["result"]
            if isinstance(div, dict):
                div = div["v"]
            trace.append({"gen": g, "best_j": b[-1], "mean_j": sum(fit) / len(fit),
                          "mean_diversity": sum(div) / len(div)})
            print(f"  gen {g:>2}  best J {b[-1]:+.4f}   mean J {sum(fit)/len(fit):+.4f}   "
                  f"spread {sum(d/(hi[k]-lo[k]) for k, d in enumerate(div))/n_dim:.3f}   "
                  f"{time.perf_counter()-t0:>6.1f}s")
            if g < args.gens - 1:
                pop = w.execute("evolutionary_search", "ga_step",
                                [pop, fit, lo, hi, args.tournament, args.cx_rate,
                                 args.mut_rate, args.mut_scale, args.elite, args.seed, g])["result"]
                if isinstance(pop, dict):
                    pop = pop["v"]
        search_s = time.perf_counter() - t0

        div = w.execute("evolutionary_search", "ga_diversity", [pop, n_dim])["result"]
        sat = w.execute("evolutionary_search", "ga_saturation", [pop, lo, hi])["result"]
        div = div["v"] if isinstance(div, dict) else div
        sat = sat["v"] if isinstance(sat, dict) else sat

        print(f"\nfitted parameters, with the diagnostics that say how much to trust each one")
        print(f"{'parameter':<14} {'default':>9} {'fitted':>9} {'bounds':>16} "
              f"{'spread':>8} {'bound':>7}  identifiability")
        report = []
        for k, (name, pidx, l, h) in enumerate(free):
            rel = div[k] / (h - l)
            # a dimension whose population still spans most of its box is one the objective cannot see
            tag = "resolved" if rel < 0.12 else ("weak" if rel < 0.28 else "UNIDENTIFIED")
            bd = "" if abs(sat[k]) < 0.35 else ("at hi" if sat[k] > 0 else "at lo")
            print(f"{name:<14} {incumbent[k]:>9.3f} {best_theta[k]:>9.3f} "
                  f"[{l:>6.2f},{h:>6.2f}] {div[k]:>8.3f} {bd:>7}  {tag}")
            report.append({"name": name, "param_index": pidx, "default": incumbent[k],
                           "fitted": best_theta[k], "lo": l, "hi": h, "spread": div[k],
                           "relative_spread": rel, "saturation": sat[k], "identifiability": tag})

        print(f"\nheld-out selection at {args.final_reps} replications "
              f"({len(val)} races never used by the search)")
        rows_out = []
        for label, th in (("shipped defaults", incumbent), ("fitted theta", best_theta)):
            m = score(th, val, args.final_reps)
            rows_out.append((label, m))
            print(f"  {label:<18} J {m['j']:+.4f}   Brier {m['brier']:.5f}   BSS {m['bss']:+.3f}   "
                  f"ECE {m['ece']:.4f}   rho {m['rho']:+.3f}   churn {m['churn']:.2f}")
        d_j = rows_out[1][1]["j"] - rows_out[0][1]["j"]
        print(f"\n  churn target from the corpus: 2.68 positions")
        print(f"  held-out J change {d_j:+.4f} — "
              + ("the fitted theta generalises" if d_j > 0
                 else "the fitted theta does NOT generalise; the defaults stand"))
        print(f"\nsearch cost {search_s:.1f}s for "
              f"{args.pop * args.gens * len(train)} race simulations")

        if args.json:
            Path(args.json).write_text(json.dumps({
                # PROVENANCE. calibrate.py's min_follow bound was widened 1.00 -> 2.50 in the same
                # commit that published the previous artifact, so a re-run at HEAD reproduced none of the
                # fitted values: ga_init/ga_step map every draw through the per-dimension bounds, so the
                # bounds ARE part of the result. Recording them, the commit and the corpus digest is what
                # makes a published theta re-derivable rather than merely reported.
                "source_commit": _git_commit(),
                "search_bounds": {d[0]: [d[2], d[3]] for d in SEARCH_DIMS},
                "corpus_seasons": sorted(seasons),
                "corpus_races": len(races),
                "ga_settings": {"pop": args.pop, "gens": args.gens, "tournament": args.tournament,
                                "cx_rate": args.cx_rate, "mut_rate": args.mut_rate,
                                "mut_scale": args.mut_scale, "elite": args.elite},
                "search_version": ver, "objective": "spearman - 2*brier - ece",
                "frozen_test_season_withheld": FROZEN_TEST_SEASON,
                "train_races": len(train), "val_races": len(val),
                "pop": args.pop, "generations": args.gens, "search_reps": args.reps,
                "final_reps": args.final_reps, "master_seed": args.seed,
                "parameters": report,
                "measured_pinned": {k: {"value": v, "source": w2} for k, (v, w2) in MEASURED.items()},
                "searched_measured_too": args.search_measured,
                "trace": trace,
                "held_out": {label: m for label, m in rows_out},
                "corpus_churn_target": 2.68, "search_seconds": search_s,
            }, indent=2))
            print(f"wrote {args.json}", file=sys.stderr)
        return 0
    finally:
        w.close()


if __name__ == "__main__":
    raise SystemExit(main())
