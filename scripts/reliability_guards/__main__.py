"""CLI: ``python3 -m scripts.reliability_guards [--guard NAME ...] [--update-baseline]``."""

from __future__ import annotations

import argparse

from . import GUARDS, run_guards, update_baseline


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="reliability_guards", description=__doc__)
    ap.add_argument("--guard", action="append", choices=list(GUARDS), help="Run only these guard(s).")
    ap.add_argument(
        "--update-baseline",
        action="store_true",
        help="Record current violations as the baseline (review the diff before committing).",
    )
    args = ap.parse_args(argv)

    if args.update_baseline:
        total = update_baseline()
        print(f"wrote baseline ({total} known violations).")
        return 0

    result = run_guards(guards=args.guard)
    failed = False
    for name, r in result.items():
        if r["new"]:
            failed = True
            print(f"\n❌ {name}: {len(r['new'])} NEW violation(s) — not allowed (fix wave: {GUARDS[name].fix_wave}):")
            for k in r["new"]:
                print(f"    {k}")
        if r["known"]:
            print(f"⚠️  {name}: {len(r['known'])} known/baselined violation(s) — debt for wave {GUARDS[name].fix_wave}.")
    if failed:
        print(
            "\nNew reliability-guard violations detected. Route through the approved "
            "wrapper/boundary, or — if intentional and tracked — run "
            "`python3 -m scripts.reliability_guards --update-baseline` and justify it in review."
        )
        return 1
    print("\n✅ reliability guards: no new violations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
