#!/usr/bin/env python3
"""Gate 3C — freeze and preregister, so the final test can only be run once.

WHAT A FREEZE IS FOR

Everything up to here was selection: parameters chosen on held-out races, features chosen by the search,
bounds widened when they saturated. All of that is legitimate, and all of it is why the development
numbers cannot be reported as accuracy. A frozen artifact is the line where selection stops. After it,
exactly one number is produced, on a season that has never been read, and it is reported whatever it says.

The freeze is only worth anything if it is CHECKABLE, so this records the things that would let a later
reader — or a later version of us — detect that the line was crossed:

  source_commit            the tree that produced it, and whether that tree was dirty
  corpus_digest            a hash over every input file's path, size and mtime, so a repaired session
                           after the freeze is detectable rather than silent
  theta + search_bounds    the fitted vector AND the box it was fitted in. ga_init/ga_step map every
                           draw through the bounds, so a bound is part of the result; publishing a value
                           without its box makes the value unreproducible, which happened once already
  metric_definitions       spelled out, because "Brier" is ambiguous across the literature and the
                           reference paper's 0.0745 is not the same quantity as ours
  epsilon / margin         the preregistered decision thresholds
  rng_version              the randomness contract
  claim_licence            which rung of the ladder each planned result may support, written BEFORE the
                           result exists so it cannot be chosen to fit the outcome

RUNNING THE FINAL TEST IS DELIBERATELY AWKWARD. `--run-final` refuses unless a frozen artifact exists,
refuses if the tree has moved since the freeze, and refuses if a result file is already present. That
last one is the important one: the failure mode is not running the test twice by accident, it is running
it, disliking the number, changing something and running it again.

Usage:
    python3 -m benchmarks.timing.freeze --freeze
    python3 -m benchmarks.timing.freeze --verify
    python3 -m benchmarks.timing.freeze --run-final        # once. ever.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "timing"))
sys.path.insert(0, str(ROOT / "benchmarks" / "timing"))

FROZEN_TEST_SEASON = 2025
DEV_SEASONS = (2019, 2020, 2021, 2023, 2024)
DOCS = ROOT / "docs" / "timing"


def artifact_paths(name: str) -> tuple[Path, Path]:
    """Each preregistered test gets its OWN artifact and result pair.

    A second test must not be able to overwrite the first: the whole value of the 2025 record is that it
    was written before its number was known and has not moved since. Naming them separately also makes
    the disclosure unavoidable -- 2026 is genuinely unseen, 2025 has been read once, and a reader can see
    which is which without being told.
    """
    suffix = "" if name == "final" else f"_{name.upper()}"
    return (DOCS / f"PREREGISTRATION{suffix}.json", DOCS / f"FINAL_TEST{suffix or '_2025'}.json")


ARTIFACT = DOCS / "PREREGISTRATION.json"
RESULT = DOCS / "FINAL_TEST_2025.json"


def commit_ok(frozen: str) -> tuple[bool, str]:
    """HEAD may differ from the frozen commit ONLY by the preregistration artifact itself.

    Recording the commit at freeze time and then committing the artifact necessarily advances HEAD, so a
    strict equality check fails on the very first legitimate step and would block the final test for a
    reason that has nothing to do with the science. The honest check is: the frozen commit is an ancestor
    of HEAD, and the only file that changed between them is the artifact.
    """
    head = _git("rev-parse", "HEAD")
    if head == frozen:
        return True, "identical"
    if _git("merge-base", "--is-ancestor", frozen, head) != "" or \
            subprocess.run(["git", "merge-base", "--is-ancestor", frozen, head],
                           cwd=str(ROOT), capture_output=True).returncode != 0:
        return False, f"the frozen commit {frozen[:12]} is not an ancestor of HEAD {head[:12]}"
    changed = [x for x in _git("diff", "--name-only", frozen, head).splitlines() if x.strip()]
    # any preregistration artifact, since each named test commits its own
    extra = [c for c in changed
             if not (c.startswith("docs/timing/PREREGISTRATION") and c.endswith(".json"))]
    if extra:
        return False, ("files changed since the freeze: " + ", ".join(extra[:6])
                       + (f" (+{len(extra)-6} more)" if len(extra) > 6 else ""))
    return True, "only the preregistration artifact was committed"


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                              text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def corpus_digest(root: Path, seasons) -> dict:
    """A hash over the input inventory, not the bytes.

    Hashing every byte of a 7.6 GB corpus on each verify would make the check something people skip, and
    a check people skip is not a check. Path, size and mtime catch a session repaired or re-replayed
    after the freeze, which is the failure this exists to detect.
    """
    h = hashlib.sha256()
    n = 0
    for season in sorted(seasons):
        for p in sorted((root / str(season)).rglob("_laps.parquet")):
            st = p.stat()
            h.update(f"{p.relative_to(root)}\x1f{st.st_size}\x1f{int(st.st_mtime)}\x1e".encode())
            n += 1
    return {"files": n, "digest": h.hexdigest()}


METRIC_DEFINITIONS = {
    "brier": "mean over CAR-RACES of (p_win - is_winner)^2. Binary per car, NOT a summed multiclass "
             "Brier. The reference paper's 0.0745 sits above the p(1-p)=0.0484 a constant base-rate "
             "forecast scores under this definition, so it is a different quantity and the two are not "
             "comparable.",
    "bss": "1 - brier / brier(constant base-rate forecast). The primary number, because a rare event "
           "flatters raw Brier.",
    "ece": "bin-weighted mean |forecast - observed| over 10 equal-width bins, sharing one binning "
           "function with the reliability diagram so the two cannot disagree.",
    "winner_hit": "fraction of races whose argmax p_win equals the classified winner.",
    "top3": "fraction of races where the classified winner is in the top 3 by p_win.",
    "podium_recall": "fraction of the actual top 3 appearing in the predicted top 3.",
    "spearman": "rank correlation of expected finishing position against classification, average ranks "
                "with tie handling.",
    "murphy": "BS = reliability - resolution + uncertainty over the same 10 bins.",
}

CLAIM_LICENCE = {
    "rung_1_replay_fidelity": "SUPPORTED: 22/22 stint parity, DNF matches Jolpica, fault injection and "
                              "the Invariant-4 leakage tests pass.",
    "rung_2_same_model_speed": "SUPPORTED: 28.1x over optimised NumPy at |p_win| divergence 0.0123, "
                               "below the Monte Carlo sampling floor. Withheld automatically if the "
                               "arms diverge.",
    "rung_3_outcome_calibration": "PENDING this final test. Reportable only from the 2025 result, and "
                                  "only against the metric definitions above.",
    "rung_4_option_contrast": "PARTIAL: paired simultaneous CIs and the abstention rule are "
                              "implemented and tested; stability across N is published in the ladder.",
    "rung_5_decision_quality": "NOT SUPPORTED and not claimed. The six-row evidence table is not built. "
                               "We may claim option contrasts; we may not claim better pit decisions.",
    "rung_6_exploratory_2026": "NOT SUPPORTED. Demonstration only.",
}


def build_artifact(theta_path: Path, root: Path) -> dict:
    import calibrate as cal

    theta = json.loads(theta_path.read_text())
    dirty = bool(_git("status", "--porcelain"))
    return {
        "preregistered_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": _git("rev-parse", "HEAD"),
        "tree_dirty_at_freeze": dirty,
        "development_seasons": list(DEV_SEASONS),
        "frozen_test_season": FROZEN_TEST_SEASON,
        "corpus": corpus_digest(root, DEV_SEASONS + (FROZEN_TEST_SEASON,)),
        "rng_version": "philox4x64-10/v1",
        "objective_version": "ahead-of-target-rival/v1",
        "search_objective": theta.get("objective"),
        "theta": {p["name"]: p["fitted"] for p in theta["parameters"]},
        "theta_identifiability": {p["name"]: p["identifiability"] for p in theta["parameters"]},
        "search_bounds": theta.get("search_bounds"),
        "measured_pinned": theta.get("measured_pinned"),
        "ga_settings": theta.get("ga_settings"),
        "held_out_development": theta.get("held_out"),
        "epsilon_pp": 2.0,
        "margin_pp": 1.0,
        "metric_definitions": METRIC_DEFINITIONS,
        "claim_licence": CLAIM_LICENCE,
        "final_test_protocol": {
            "command": "python3 -m benchmarks.timing.freeze --run-final",
            "runs_permitted": 1,
            "seasons": [FROZEN_TEST_SEASON],
            "no_configuration_change_after_reading": True,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="~/.algenta/f1/raw")
    ap.add_argument("--theta", default="docs/timing/calibration.json")
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--run-final", action="store_true")
    ap.add_argument("--reps", type=int, default=20000)
    ap.add_argument("--i-understand-this-runs-once", action="store_true")
    ap.add_argument("--test-name", default="final",
                    help="names an independent preregistration/result pair, so a later test cannot "
                         "overwrite an earlier one")
    ap.add_argument("--test-seasons", default=str(FROZEN_TEST_SEASON))
    ap.add_argument("--session-types", default="Race",
                    help="pinned from the second preregistration onward. The first test silently "
                         "included sprints, which run ~19 laps against ~57")
    args = ap.parse_args()
    global ARTIFACT, RESULT
    ARTIFACT, RESULT = artifact_paths(args.test_name)
    test_seasons = [int(x) for x in args.test_seasons.split(",") if x.strip().isdigit()]
    root = Path(args.root).expanduser()

    if args.freeze:
        if ARTIFACT.exists():
            print(f"refusing: {ARTIFACT.name} already exists. A re-freeze after seeing any 2025 number "
                  f"is the exact failure this gate prevents. Delete it deliberately if the freeze "
                  f"genuinely predates any final-test run.", file=sys.stderr)
            return 2
        art = build_artifact(ROOT / args.theta, root)
        art["test_name"] = args.test_name
        art["frozen_test_season"] = test_seasons
        art["session_types"] = sorted({t.strip() for t in args.session_types.split(",") if t.strip()})
        art["final_test_protocol"]["seasons"] = test_seasons
        art["final_test_protocol"]["session_types"] = art["session_types"]
        art["prior_tests_already_read"] = sorted(
            q.name for q in DOCS.glob("FINAL_TEST*.json") if q.exists())
        ARTIFACT.write_text(json.dumps(art, indent=2))
        print(f"frozen at {art['source_commit'][:12]}"
              f"{' (TREE DIRTY)' if art['tree_dirty_at_freeze'] else ''}")
        print(f"  corpus {art['corpus']['files']} files, digest {art['corpus']['digest'][:16]}")
        print(f"  theta  {len(art['theta'])} parameters, {len(art['measured_pinned'] or {})} pinned")
        print(f"  wrote {ARTIFACT}")
        if art["tree_dirty_at_freeze"]:
            print("\n  WARNING: the tree was dirty, so source_commit does not fully describe what ran.")
        return 0

    if not ARTIFACT.exists():
        print(f"no preregistration at {ARTIFACT}. Run --freeze first.", file=sys.stderr)
        return 2
    art = json.loads(ARTIFACT.read_text())

    if args.verify:
        now = corpus_digest(root, DEV_SEASONS + (FROZEN_TEST_SEASON,))
        commit = _git("rev-parse", "HEAD")
        cok, why = commit_ok(art["source_commit"])
        ok = cok
        print(f"preregistered {art['preregistered_at']}")
        print(f"  commit  frozen {art['source_commit'][:12]}  now {commit[:12]}"
              f"   {'OK — ' + why if cok else 'MOVED — ' + why}")
        same = now["digest"] == art["corpus"]["digest"]
        print(f"  corpus  {art['corpus']['files']} -> {now['files']} files   "
              f"{'MATCH' if same else 'CHANGED'}")
        if not same:
            ok = False
            print("    a corpus change after the freeze means the frozen scorecard no longer describes "
                  "the data it was frozen against")
        print(f"  final test {'ALREADY RUN — ' + RESULT.name if RESULT.exists() else 'not yet run'}")
        return 0 if ok else 1

    if args.run_final:
        if RESULT.exists():
            print(f"refusing: {RESULT.name} exists. The final test runs ONCE. The failure mode is not "
                  f"running it twice by accident — it is running it, disliking the number, changing "
                  f"something and running it again.", file=sys.stderr)
            return 2
        if not args.i_understand_this_runs_once:
            print("refusing: pass --i-understand-this-runs-once. After this, no configuration may "
                  "change on the basis of what it says.", file=sys.stderr)
            return 2
        cok, why = commit_ok(art["source_commit"])
        if not cok:
            print(f"refusing: {why}. Check out the frozen commit or re-freeze deliberately.",
                  file=sys.stderr)
            return 2
        if _git("status", "--porcelain"):
            print("refusing: the working tree is dirty, so what runs is not what was frozen.",
                  file=sys.stderr)
            return 2
        print("running the frozen final test on 2025 — once")
        print("this is the number, whatever it says.\n")
        cmd = [sys.executable, "-m", "benchmarks.timing.backtest",
               "--seasons", ",".join(str(x) for x in art.get("frozen_test_season", test_seasons)),
               "--session-types", ",".join(art.get("session_types", ["Race"])),
               "--reps", str(args.reps), "--pace-prior", "history", "--theta-json", args.theta]
        print("  " + " ".join(cmd) + "\n")
        env = dict(os.environ)
        env["ALGENTA_FINAL_TEST"] = "1"   # the single sanctioned path past backtest.py's season guard
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, env=env)
        sys.stdout.write(r.stdout)
        sys.stderr.write(r.stderr)
        RESULT.write_text(json.dumps({
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "preregistration_commit": art["source_commit"],
            "test_name": art.get("test_name"), "seasons": art.get("frozen_test_season"),
            "session_types": art.get("session_types"),
            "prior_tests_already_read": art.get("prior_tests_already_read"),
            "reps": args.reps,
            "returncode": r.returncode, "stdout": r.stdout, "stderr": r.stderr[-4000:],
        }, indent=2))
        print(f"\nrecorded to {RESULT}")
        return r.returncode

    print("nothing to do: pass --freeze, --verify or --run-final", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
