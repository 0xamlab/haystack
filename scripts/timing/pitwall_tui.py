#!/usr/bin/env python3
"""Pit-wall TUI: replay a race and show the live option board.

The artifact. Replays a session lap by lap from the append-only event log's derived records, and at each
lap rebuilds every car's state AS OF that lap only, fits pace in Mojo, and calls the CRN option board.

Every number on screen is produced by a Mojo kernel over the socket. Python selects laps, marks
exclusion flags from observed state, and renders.

As-of discipline: at lap L the board sees only laps <= L. Nothing reads the final classification. That
is what makes the replay an honest rehearsal of live operation rather than a retrospective animation.

Plain ANSI, no curses and no extra dependency, so it runs anywhere the SDK does.

Usage:
    python3 scripts/timing/pitwall_tui.py --dir <session> --focal 1 --speed 30
    python3 scripts/timing/pitwall_tui.py --dir <session> --focal 1 --from-lap 30 --to-lap 45 --speed 0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).parent))
from kernel_probe import Worker  # noqa: E402

LAP_GREEN, LAP_OUT, LAP_IN, LAP_NEUTRALISED, LAP_DIRTY_AIR = 0, 1, 2, 4, 8
OPT_NAMES = ("STAY", "BOX NOW", "BOX +1", "BOX +2")
REGIME = {1: ("GREEN", "\033[32m"), 2: ("YELLOW", "\033[33m"),
          4: ("SAFETY CAR", "\033[91m"), 6: ("VSC", "\033[95m"), 7: ("VSC ENDING", "\033[95m")}

CLR, BOLD, DIM, RST = "\033[2J\033[H", "\033[1m", "\033[2m", "\033[0m"
CYAN, GREY, RED, GRN, YEL = "\033[36m", "\033[90m", "\033[31m", "\033[32m", "\033[33m"


def load(session_dir: Path) -> dict:
    laps = pq.read_table(session_dir / "_laps.parquet").to_pydict()
    rows = [dict(zip(laps.keys(), v)) for v in zip(*laps.values())]
    by_car: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        by_car[r["car_number"]].append(r)
    for v in by_car.values():
        v.sort(key=lambda r: r["lap_number"])

    regimes = []
    ts_path = session_dir / "_track_status.parquet"
    if ts_path.exists():
        t = pq.read_table(ts_path).to_pydict()
        regimes = [dict(zip(t.keys(), v)) for v in zip(*t.values())]

    info = {}
    si = session_dir / "SessionInfo.json"
    if si.exists():
        raw = si.read_bytes()
        info = json.loads((raw[3:] if raw[:3] == b"\xef\xbb\xbf" else raw).decode())

    drivers = {}
    dl = session_dir / "DriverList.json"
    if dl.exists():
        raw = dl.read_bytes()
        d = json.loads((raw[3:] if raw[:3] == b"\xef\xbb\xbf" else raw).decode())
        drivers = {int(k): v.get("Tla", k) for k, v in d.items() if k.isdigit()}

    total = max((r["lap_number"] for r in rows), default=0)
    return {"by_car": by_car, "regimes": regimes, "info": info, "drivers": drivers, "total": total}


ABSENT_LAPS = 3
"""Laps a car may fall behind the leader before it is presumed retired rather than merely lagging."""


def select_rival(states: dict, running: list, fi: int | None, locked: int | None,
                 names: dict) -> tuple[int | None, str | None, dict | None]:
    """The frozen utility's target-rival rule, as a named function so it can be tested.

    The utility is "P(focal finishes ahead of the NAMED target rival)". Re-selecting the nearest car
    ahead every lap silently changes the question being answered, so P(ahead) jumps between laps for a
    reason no operator can see -- which reads as a model failure rather than as a different rival.

    So the target is STICKY, and the spec's two substitution conditions are the only things that move it:

      the target RETIRES     fall back to the next classified car ahead as of the snapshot where
                             retirement became observable
      the target is no longer AHEAD   the utility is defined against a car in front; once the focal car
                             has passed it, holding the target would be answering a question about a car
                             behind

    Both are LOGGED. A substitution performed quietly is indistinguishable from the model changing its
    mind, and the plan requires it be recorded.
    """
    nearest = running[fi - 1]["car"] if fi is not None and fi > 0 else None
    if locked is None:
        return nearest, None, None

    st = states.get(locked)
    if st is None or st.get("retired"):
        return nearest, (f"target {names.get(locked, locked)} retired -> "
                         f"{names.get(nearest, nearest)}"), {"reason": "target retired", "to": nearest}

    if nearest is not None and nearest != locked:
        pos_locked = next((k for k, s_ in enumerate(running) if s_["car"] == locked), None)
        if fi is not None and (pos_locked is None or pos_locked > fi):
            return nearest, (f"passed {names.get(locked, locked)} -> now racing "
                             f"{names.get(nearest, nearest)}"), {"reason": "target no longer ahead",
                                                                 "to": nearest}
    return locked, None, None


def provenance(states: dict[int, dict], lap: int, total: int) -> dict:
    """Freshness and data-quality flags — the plan requires the TUI degrade VISIBLY, never silently.

    A pit wall that shows a confident board over a feed that stopped two laps ago is worse than one that
    shows nothing, because the number looks identical either way. Everything here is derived from the
    as-of rows the board was actually computed from, so it cannot disagree with them.
    """
    # laps_done is the field state_as_of actually emits. An earlier version read a "lap" key that does
    # not exist, so every car reported a lag equal to the lap number and the whole field showed STALE --
    # a warning that always fires is worse than none, because it trains the reader to ignore it.
    leader = max((s_.get("laps_done") or 0) for s_ in states.values()) if states else lap
    ages, missing_pace, missing_compound, stale, absent = [], 0, 0, 0, 0
    for c, s_ in states.items():
        if s_.get("retired"):
            continue
        ln = s_.get("laps_done") or 0
        behind = max(0, leader - ln)
        # THREE distinct conditions, kept apart because they call for different responses:
        #   a car a lap or two down          -> normal racing
        #   a car absent for many laps       -> PRESUMED RETIRED. The retired flag under-detects: a car
        #                                      that simply stops appearing is never marked, and one such
        #                                      car sat 35 laps behind while still counted as running.
        #   a genuine feed gap               -> what this line exists to surface, and it would be lost
        #                                      in the noise if the two above were counted as staleness
        if behind > ABSENT_LAPS:
            absent += 1
            continue
        ages.append(behind)
        if behind > 1:
            stale += 1
        if not s_.get("pace"):
            missing_pace += 1
        if not s_.get("compound"):
            missing_compound += 1
    return {
        "presumed_retired": absent,
        "max_lap_lag": max(ages) if ages else 0,
        "median_lap_lag": sorted(ages)[len(ages) // 2] if ages else 0,
        "stale_cars": stale,
        "missing_pace": missing_pace,
        "missing_compound": missing_compound,
        "cars": len(ages),
    }


def state_as_of(by_car: dict[int, list[dict]], lap: int) -> dict[int, dict]:
    """Per-car state using ONLY laps <= lap. No look-ahead."""
    # median green lap, used to price a lap of deficit for lapped cars
    med_lap = 90.0
    greens = sorted(r["lap_time_s"] for recs in by_car.values() for r in recs
                    if r["lap_number"] <= lap and r["lap_time_s"] and r["track_regime"] == 1)
    if greens:
        med_lap = greens[len(greens) // 2]
    leader_laps = max((r["lap_number"] for recs in by_car.values() for r in recs
                       if r["lap_number"] <= lap), default=lap)

    out: dict[int, dict] = {}
    for car, recs in by_car.items():
        seen = [r for r in recs if r["lap_number"] <= lap]
        if not seen:
            continue
        cur = seen[-1]
        # Relative race time comes from the OBSERVED gap to the leader, not from summing lap times.
        # Summing treats a missing lap_time as zero, so any car with feed gaps looks impossibly fast --
        # which put a P3 car at an expected finish of 14th.
        #
        # But GapToLeader is EMPTY in two distinct cases, and conflating them put the actual race leader
        # at P12: the leader has no gap to itself, and a lapped car reports "+1 LAP" rather than seconds.
        # Distinguish them by observed position and lap count.
        gap = cur["gap_to_leader_s"]
        laps_down = max(0, leader_laps - cur["lap_number"])
        if gap is not None:
            elapsed = float(gap)
        elif cur["position"] == 1:
            elapsed = 0.0
        else:
            elapsed = laps_down * med_lap + float(cur["position"])
        stint = cur["stint_index"]
        stint_laps = [r for r in seen if r["stint_index"] == stint]
        out[car] = {
            "car": car, "position": cur["position"], "elapsed": float(elapsed),
            "compound": cur["compound"], "age": cur["tyre_age"], "stint": stint,
            "laps_done": cur["lap_number"], "pit_count": cur["pit_count"],
            "retired": cur["retired"], "interval": cur["interval_ahead_s"],
            "regime": cur["track_regime"], "stint_laps": stint_laps,
            "recent_green": [r for r in seen[-12:]
                             if r["track_regime"] == 1 and not r["in_pit"] and r["lap_time_s"]],
        }
    return out


def fit_pace(w: Worker, st: dict, fallback_pace: float, min_laps: int = 4) -> tuple[float, float]:
    """Fit (pace, degradation) in Mojo from this stint's laps.

    A freshly-pitted car has too few laps to fit, and that is exactly the car whose decision matters
    most. So the fallback is the car's own recent green-lap pace where available, then the field median
    passed in -- never a hardcoded constant, which previously put a leading car at 90.0 s/lap and made
    the board saturate.
    """
    recs = st["stint_laps"]
    times, ages, flags = [], [], []
    first = recs[0]["lap_number"] if recs else 0
    for r in recs:
        if r["lap_time_s"] is None:
            continue
        f = LAP_GREEN
        if st["stint"] > 0 and r["lap_number"] == first:
            f |= LAP_OUT
        if r["in_pit"]:
            f |= LAP_IN
        if r["track_regime"] != 1:
            f |= LAP_NEUTRALISED
        iv = r["interval_ahead_s"]
        if iv is not None and 0.0 < iv <= 1.2:
            f |= LAP_DIRTY_AIR
        times.append(float(r["lap_time_s"]))
        ages.append(float(r["tyre_age"]))
        flags.append(f)

    usable = [t for t, f in zip(times, flags) if f & (LAP_OUT | LAP_IN | LAP_NEUTRALISED) == 0]
    if len(usable) < min_laps:
        # too few green laps in this stint to fit: prefer the car's own best recent green lap,
        # otherwise the field median. Never a constant.
        prior = [r["lap_time_s"] for r in st.get("recent_green", []) if r["lap_time_s"]]
        if prior:
            return min(prior), 0.03
        return (min(usable) if usable else fallback_pace), 0.03

    res = w.execute("degradation_state", "pace_kalman_run",
                    [times, ages, flags, usable[0], 0.0, 4.0, 0.02, 0.18, 0.0005])
    if "error" in res:
        return usable[0], 0.03
    v = res["result"]["v"]
    return v[0], v[1]


def render_provenance(prov: dict) -> list[str]:
    """One line, and it turns yellow before it turns silent."""
    out = []
    warn = (prov["stale_cars"] or prov["missing_pace"] or prov["missing_compound"])
    col = YEL if warn else GREY
    bits = [f"{prov['cars']} cars running",
            f"laps behind leader: median {prov['median_lap_lag']} / max {prov['max_lap_lag']}"]
    if prov["stale_cars"]:
        bits.append(f"{BOLD}{prov['stale_cars']} LAGGING{RST}{col}")
    if prov["presumed_retired"]:
        bits.append(f"{prov['presumed_retired']} presumed retired "
                    f"(absent >{ABSENT_LAPS} laps, not flagged)")
    if prov["missing_pace"]:
        bits.append(f"{prov['missing_pace']} no pace estimate")
    if prov["missing_compound"]:
        bits.append(f"{prov['missing_compound']} compound unknown")
    out.append(f"{col}DATA   " + "   ".join(bits) + RST)
    return out


def render(sess: dict, lap: int, states: dict, board: dict | None, focal: int, rival: int | None,
           latency_ms: float, params: dict, speed: str, prov: dict, contract: dict,
           swap_note: str | None = None, swaps: int = 0) -> None:
    d = sess["drivers"]
    meeting = sess["info"].get("Meeting", {}).get("Name", "?")
    year = str(sess["info"].get("StartDate", ""))[:4]
    reg_code = states.get(focal, {}).get("regime", 1)
    reg_name, reg_col = REGIME.get(reg_code, (f"CODE {reg_code}", YEL))

    out = [CLR]
    out.append(f"{BOLD}{CYAN}ALGENTA PITWALL{RST}  {meeting} {year}   "
               f"lap {BOLD}{lap}{RST}/{sess['total']}   {reg_col}{BOLD}{reg_name}{RST}   "
               f"{GREY}replay {speed}{RST}")
    out.append(f"{GREY}{'─' * 96}{RST}")
    out.extend(render_provenance(prov))
    out.append(f"{GREY}{'─' * 96}{RST}")

    running = sorted([s for s in states.values() if not s["retired"]],
                     key=lambda s: (-s["laps_done"], s["elapsed"]))
    out.append(f"{BOLD}{'P':>2} {'CAR':>4} {'DRV':<4} {'CMP':<7} {'AGE':>4} {'STOPS':>6} "
               f"{'GAP':>8}  {'PACE':>7} {'DEG':>7}{RST}")
    for i, s in enumerate(running[:12], 1):
        mark = f"{BOLD}{CYAN}>{RST}" if s["car"] == focal else (f"{YEL}r{RST}" if s["car"] == rival else " ")
        gap = "" if i == 1 else (f"+{s['interval']:.3f}" if s["interval"] is not None else "—")
        pace = s.get("pace")
        deg = s.get("deg")
        pv = f"{pace:.3f}" if pace else "—"
        dv = f"{deg:+.4f}" if deg is not None else "—"
        out.append(f"{mark}{i:>2} {s['car']:>4} {d.get(s['car'], '?'):<4} {str(s['compound'])[:7]:<7} "
                   f"{s['age']:>4} {s['pit_count']:>6} {gap:>8}  {pv:>7} {dv:>7}")
    retired = [s for s in states.values() if s["retired"]]
    if retired:
        out.append(f"{GREY}retired: " + ", ".join(f"{d.get(s['car'], s['car'])}" for s in retired) + RST)

    out.append("")
    out.append(f"{GREY}{'─' * 96}{RST}")
    if board is None:
        out.append(f"{DIM}board not evaluated at this lap{RST}")
    else:
        rn = d.get(rival, rival)
        if swap_note:
            # the probability is about to move for a reason that is NOT the model changing its mind
            out.append(f"  {BOLD}{YEL}TARGET RIVAL CHANGED{RST}  {swap_note}   "
                       f"{GREY}P(ahead) is now answering a different question{RST}")
        out.append(f"{BOLD}OPTION BOARD{RST}  focal {BOLD}{d.get(focal, focal)}{RST} "
                   f"vs target rival {BOLD}{rn}{RST}"
                   f"{'' if not swaps else f'  {GREY}(substitution #' + str(swaps) + f'){RST}'}   "
                   f"{GREY}P(finish ahead of {rn}){RST}")
        out.append(f"{BOLD}{'OPTION':<9} {'P(ahead)':>9} {'Δ vs stay':>10} "
                   f"{'90% simultaneous CI':>24} {'E[pos]':>7}{RST}")
        rec = board["recommended"]
        for o in range(4):
            pa = board["p_ahead"][o]
            dl = board["delta"][o]
            lo, hi = board["ci_lo"][o], board["ci_hi"][o]
            ep = board["exp_pos"][o]
            col = f"{BOLD}{GRN}" if o == rec and board["verdict"] == 1 else ""
            ci = "—" if o == 0 else f"[{lo * 100:+6.2f}, {hi * 100:+6.2f}] pp"
            out.append(f"{col}{OPT_NAMES[o]:<9} {pa * 100:>8.2f}% {dl * 100:>9.2f}pp "
                       f"{ci:>24} {ep:>7.2f}{RST}")

        if board["verdict"] == 1:
            if rec == 0:
                out.append(f"\n  {BOLD}{GRN}RECOMMEND: STAY OUT{RST}")
            else:
                out.append(f"\n  {BOLD}{GRN}RECOMMEND: {OPT_NAMES[rec]}{RST}")
        else:
            out.append(f"\n  {BOLD}{YEL}DECISION: INCONCLUSIVE{RST}  "
                       f"{GREY}interval straddles the ε={params['eps'] * 100:.1f}pp practical bar{RST}")

        out.append("")
        # CONVERGENCE: the widest simultaneous interval, and what it would take to halve it. A board is
        # only actionable if the interval is narrow relative to the edge it claims, and a bare N tells
        # the reader nothing about that.
        widest = max((board["ci_hi"][o] - board["ci_lo"][o]) for o in range(1, 4)) * 100.0
        need = int(board["n"] * 4) if widest > 0 else board["n"]
        out.append(f"{GREY}N={board['n']:,}  CRN variance ratio {board['crn']:.3f} "
                   f"({1 / board['crn']:.1f}× reduction vs independent)  "
                   f"widest CI {widest:.2f}pp  (halving it needs N≈{need:,})  "
                   f"board latency {latency_ms:.1f} ms{RST}")
        # PIT-LOSS COMPONENTS, not a single total: the in-lap and out-lap deltas and the right-tailed
        # service time are priced separately, and the plan requires the board show them that way so a
        # reader can see WHY a stop costs what it costs.
        out.append(f"{GREY}pit loss {params['pit_loss']:.1f}s stationary+lane  "
                   f"+{params['delta_in']:.2f}s in-lap  +{params['delta_out']:.2f}s out-lap  "
                   f"Exp tail σ={params['sigma_pit']:.2f}s  "
                   f"→ {params['pit_loss'] + params['delta_in'] + params['delta_out']:.1f}s expected "
                   f"under green{RST}")
        # TYRE INVENTORY: the plan forbids recommending a compound whose availability is unknown. The
        # four options here are all TIMING of a stop on an unspecified set, so no compound is being
        # proposed -- stated explicitly rather than left for the reader to assume.
        out.append(f"{GREY}tyre inventory: {BOLD}not observable{RST}{GREY} from public timing. The board "
                   f"varies stop TIMING only and proposes no compound.{RST}")
    out.append(f"{GREY}{'─' * 96}{RST}")
    out.append(f"{DIM}CALIBRATED: pace, degradation, pit timing from public timing data. "
               f"Uncertainty shown is simulation sampling CI only — not parameter or model-form error.{RST}")
    out.append(f"{DIM}Rivals stop when their tyres reach the cliff (no covering response). "
               f"Independent analytics demo, not team-authorized.{RST}")
    # CONTRACT IDENTIFIERS. Without these a screenshot is not reproducible evidence -- you cannot tell
    # which model, which random contract or which parameter vector produced the number on screen.
    out.append(f"{DIM}engine {contract['engine']}  rng {contract['rng']}  "
               f"config {contract['config_hash'][:16]}  θ {contract['theta_source']}  "
               f"corpus {contract['corpus']}{RST}")
    sys.stdout.write("\n".join(out) + "\n")
    sys.stdout.flush()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--binary", default="mojo_build/simulate_timing")
    ap.add_argument("--focal", type=int, required=True)
    ap.add_argument("--reps", type=int, default=4000)
    ap.add_argument("--boot", type=int, default=300)
    ap.add_argument("--speed", type=float, default=30.0, help="replay multiplier; 0 = as fast as possible")
    ap.add_argument("--from-lap", type=int, default=2)
    ap.add_argument("--to-lap", type=int, default=0)
    ap.add_argument("--every", type=int, default=1)
    ap.add_argument("--outbox", default="",
                    help="append every board to an append-only, hash-chained decision outbox. This is "
                         "what makes a shadow run EVIDENCE: publish the chain head externally before the "
                         "outcome is known, and a record written afterwards cannot hash to it")
    ap.add_argument("--theta-json", default="",
                    help="calibration.json — the theta selected on held-out races. Named on screen so a "
                         "board can be traced to the parameter vector that produced it")
    args = ap.parse_args()

    sess = load(Path(args.dir).expanduser())
    last = args.to_lap or sess["total"]
    w = Worker(Path(args.binary))
    try:
        p = w.execute("contest_strategy", "default_contest_params")["result"]
        theta_source = "kernel defaults"
        if args.theta_json:
            cal = json.loads(Path(args.theta_json).read_text())
            sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "benchmarks" / "timing"))
            import calibrate as _c
            for nm, (v, _why) in _c.MEASURED.items():
                for dn, di, *_r in _c.SEARCH_DIMS:
                    if dn == nm and di >= 0:
                        p[di] = v
            for rec in cal["parameters"]:
                if rec["param_index"] >= 0:
                    p[rec["param_index"]] = rec["fitted"]
            theta_source = Path(args.theta_json).name
        # named by index rather than magic numbers, so a params[] change cannot silently mislabel a
        # displayed quantity
        params = {"pit_loss": p[0], "eps": p[15], "delta_out": p[12], "delta_in": p[13],
                  "sigma_pit": p[14]}
        # The config hash is what makes a screenshot reproducible evidence: it covers the whole parameter
        # vector plus the contracts, so two boards that look alike but were not computed alike differ here.
        contract = {
            "engine": w.execute("contest_strategy", "contest_strategy_version")["result"],
            "rng": w.execute("counter_rng", "rng_version")["result"],
            "theta_source": theta_source,
            "corpus": Path(args.dir).expanduser().name,
            "config_hash": hashlib.sha256(
                json.dumps({"theta": p, "reps": args.reps, "boot": args.boot,
                            "rng": w.execute("counter_rng", "rng_version")["result"]},
                           sort_keys=True).encode()).hexdigest(),
        }
        speed_label = "max" if args.speed == 0 else f"{args.speed:.0f}×"
        rival_locked = None
        rival_swaps: list[dict] = []
        d_names = sess["drivers"]
        outbox = None
        if args.outbox:
            from decision_outbox import Outbox
            outbox = Outbox(Path(args.outbox).expanduser())
            print(f"decision outbox: {args.outbox} ({outbox.count} existing rows)", file=sys.stderr)

        for lap in range(args.from_lap, last + 1, args.every):
            states = state_as_of(sess["by_car"], lap)
            if args.focal not in states:
                continue
            # field median green lap as the last-resort pace fallback
            all_green = sorted(r["lap_time_s"] for st_ in states.values()
                               for r in st_.get("recent_green", []) if r["lap_time_s"])
            med = all_green[len(all_green) // 2] if all_green else 90.0
            for s in states.values():
                if not s["retired"]:
                    s["pace"], s["deg"] = fit_pace(w, s, med)

            running = sorted([s for s in states.values() if not s["retired"]],
                             key=lambda s: (-s["laps_done"], s["elapsed"]))
            idx = {s["car"]: i for i, s in enumerate(running)}
            fi = idx.get(args.focal)
            rival_locked, swap_note, swap = select_rival(
                states, running, fi, rival_locked, sess["drivers"])
            if swap:
                rival_swaps.append({"lap": lap, **swap})
            rival = rival_locked

            board = None
            latency = 0.0
            laps_left = sess["total"] - lap
            if rival is not None and laps_left >= 2:
                pace = [s["pace"] for s in running]
                deg = [s["deg"] for s in running]
                el = [s["elapsed"] for s in running]
                age = [float(s["age"]) for s in running]
                act = [1.0] * len(running)
                t0 = time.perf_counter()
                res = w.execute("contest_strategy", "option_board",
                                [pace, deg, el, age, act, fi, idx[rival], laps_left,
                                 p, args.reps, args.boot, 42, lap])
                latency = (time.perf_counter() - t0) * 1000.0
                if "error" not in res:
                    v = res["result"]["v"]
                    board = {"p_ahead": v[0], "delta": v[1], "ci_lo": v[2], "ci_hi": v[3],
                             "exp_pos": v[4], "p_win": v[5], "p_podium": v[6],
                             "recommended": v[7], "verdict": v[8], "n": v[9], "crn": v[10]}

            if outbox is not None and board is not None and rival is not None:
                outbox.append(
                    session_key=str(sess["info"].get("Key") or "0"),
                    decision_event_time=f"lap {lap}",
                    event_watermark=lap, ingest_watermark=lap,
                    state_hash=hashlib.sha256(
                        json.dumps({str(c): [s_["laps_done"], s_["pit_count"], s_["age"]]
                                    for c, s_ in sorted(states.items())},
                                   sort_keys=True).encode()).hexdigest(),
                    config_hash=contract["config_hash"], source_commit=contract["engine"],
                    corpus_version=contract["corpus"], rng_version=contract["rng"],
                    master_seed=42, theta_source=contract["theta_source"],
                    objective_version="ahead-of-target-rival/v1",
                    target_car=args.focal, target_rival=rival,
                    laps_remaining=sess["total"] - lap, replications=board["n"],
                    latency_ms=latency, p_ahead=board["p_ahead"], delta=board["delta"],
                    ci_lo=board["ci_lo"], ci_hi=board["ci_hi"],
                    recommended=board["recommended"], verdict=board["verdict"],
                    crn_variance_ratio=board["crn"])
            prov = provenance(states, lap, sess["total"])
            render(sess, lap, states, board, args.focal, rival, latency, params, speed_label,
                   prov, contract, swap_note, len(rival_swaps))
            if args.speed > 0:
                time.sleep(max(0.0, 90.0 / args.speed))
        return 0
    finally:
        w.close()


if __name__ == "__main__":
    raise SystemExit(main())
