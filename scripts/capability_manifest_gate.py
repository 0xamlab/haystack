#!/usr/bin/env python3
"""Gate: declared capability blocks ratchet forward, never backward.

Four checks, in the order a failure is most likely to be a real defect:

1. **Any declaration issue anywhere fails.** A block that does not parse, names a function
   that is not there, or names a count that is not an `Int` is a hard failure even in a
   grandfathered module. A broken declaration reads to the runtime guard as "nothing
   declared", which is the silent-skip failure this whole mechanism exists to remove.

2. **A module the baseline does not grandfather must be classified.** It needs a
   `@capability-module` block plus a `counts:` decision on every function that takes both a
   `List` and an `Int`. So a module added after this landed fails the build until someone
   decides -- which is the point: "someone must decide" instead of "it silently ships
   undeclared".

3. **The grandfather list only ever SHRINKS.** `--update-baseline` cannot add to it, so a
   new module can never be grandfathered by re-baselining, and a module that has been
   declared leaves the list permanently. Coverage floor = modules − grandfathered, and it
   rises by construction. `declared_modules` records the names behind that floor so a
   removed declaration is named rather than inferred from a count.

4. **The undeclared (List, Int) census is a ceiling.** It may fall, never rise, so an old
   module cannot gain a NEW undeclared count pair.

Deleting a module is not a regression: checks 3 and 4 are evaluated only over modules that
still exist, which is why the baseline stores names and not just totals.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.runtime.mojo_inventory import (  # noqa: E402
    DEFAULT_ENGINE_DIR,
    RuntimeCapabilityManifest,
    build_capability_manifest,
)

BASELINE_PATH = ROOT / "scripts" / "capability_manifest_baseline.json"
BASELINE_SCHEMA_VERSION = 2
BOOTSTRAP = "__bootstrap__"


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _load_baseline(path: Path) -> dict[str, object]:
    if not path.exists():
        # Bootstrap: no recorded history, so `--update-baseline` records what is there
        # today. A gate RUN with no baseline still demands a block from every module.
        return {
            "schema_version": BASELINE_SCHEMA_VERSION,
            "grandfathered_modules": [],
            "declared_modules": [],
            "undeclared_count_pair_ceiling": None,
            BOOTSTRAP: True,
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"{path}: baseline must be a JSON object")
    if payload.get("schema_version") != BASELINE_SCHEMA_VERSION:
        raise SystemExit(
            f"{path}: baseline schema_version {payload.get('schema_version')!r} != "
            f"{BASELINE_SCHEMA_VERSION}"
        )
    return payload


def _write_baseline(
    path: Path,
    manifest: RuntimeCapabilityManifest,
    previous: dict[str, object],
) -> int:
    present = {module.import_path for module in manifest.modules}
    declared_now = {module.import_path for module in manifest.modules if module.is_fully_declared}
    previous_declared = set(previous.get("declared_modules") or ())  # type: ignore[arg-type]
    previous_grandfathered = set(previous.get("grandfathered_modules") or ())  # type: ignore[arg-type]
    previous_ceiling = previous.get("undeclared_count_pair_ceiling")

    regressed = sorted((previous_declared & present) - declared_now)
    if regressed:
        print(
            "❌ refusing to record a regression: these modules were declared and still exist "
            f"but no longer are — {', '.join(regressed)}"
        )
        return 1

    ceiling = manifest.undeclared_count_pair_function_count
    if previous_ceiling is not None and ceiling > int(previous_ceiling):
        print(
            f"❌ refusing to raise the undeclared-count-pair ceiling {previous_ceiling} -> "
            f"{ceiling}. A new undeclared (List, Int) function was added; declare its counts."
        )
        return 1

    if previous.get(BOOTSTRAP):
        # First run: everything that exists predates the manifest.
        grandfathered = present - declared_now
    else:
        # Shrink-only. A module never enters this list again, so re-baselining cannot
        # grandfather something new, and leaving it is irreversible.
        grandfathered = (previous_grandfathered & present) - declared_now

    payload = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "_comment": (
            "Grandfathered modules predate the declared capability manifest and are exempt from "
            "carrying a block; the list only ever shrinks, so coverage only rises. A module NOT "
            "listed here must carry a @capability-module block plus a `counts:` decision on every "
            "(List, Int) function. Grammar: apps/runtime/mojo_capability_manifest.py."
        ),
        "declared_module_floor": len(declared_now),
        "declared_modules": sorted(declared_now),
        "grandfathered_modules": sorted(grandfathered),
        "undeclared_count_pair_ceiling": ceiling,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"wrote {_display(path)}: {len(declared_now)} declared module(s) "
        f"(was {len(previous_declared)}), {len(grandfathered)} grandfathered "
        f"(was {len(previous_grandfathered) if not previous.get(BOOTSTRAP) else len(present)}), "
        f"undeclared count pairs {previous_ceiling} -> {ceiling}."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-root", type=Path, default=DEFAULT_ENGINE_DIR)
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print the summary as JSON only.")
    args = parser.parse_args(argv)

    manifest = build_capability_manifest(args.engine_root, strict=False)
    baseline = _load_baseline(args.baseline)

    if args.update_baseline:
        if manifest.issues:
            print(f"❌ {len(manifest.issues)} declaration issue(s) — fix them before baselining:")
            for issue in manifest.issues:
                print(f"    {issue.render()}")
            return 1
        return _write_baseline(args.baseline, manifest, baseline)

    grandfathered = set(baseline.get("grandfathered_modules") or ())  # type: ignore[arg-type]
    must_stay_declared = set(baseline.get("declared_modules") or ())  # type: ignore[arg-type]
    ceiling = int(baseline.get("undeclared_count_pair_ceiling") or 0)

    failures = [f"declaration issue: {issue.render()}" for issue in manifest.issues]

    declared_now: set[str] = set()
    for module in manifest.modules:
        if module.is_fully_declared:
            declared_now.add(module.import_path)
        if module.import_path in grandfathered:
            continue
        reason = (
            "was declared and must stay declared"
            if module.import_path in must_stay_declared
            else "is not grandfathered, so it must be classified"
        )
        if module.module is None:
            failures.append(
                f"{module.import_path} {reason}, but has no @capability-module block "
                f"({_display(module.path)})"
            )
        missing = module.undeclared_count_pair_functions
        if missing:
            failures.append(
                f"{module.import_path} {reason}: {len(missing)} function(s) take a (List, Int) "
                f"pair with no declared `counts:` — {', '.join(missing)}"
            )

    undeclared_pairs = manifest.undeclared_count_pair_function_count
    if undeclared_pairs > ceiling:
        failures.append(
            f"undeclared (List, Int) functions rose above the ceiling: {undeclared_pairs} > "
            f"{ceiling}. Declare `counts:` for the new one(s)."
        )

    summary = {
        "modules": len(manifest.modules),
        "grandfathered_modules": len(grandfathered),
        "declared_modules": len(declared_now),
        "declared_module_floor": len(must_stay_declared),
        "count_pair_functions": sum(len(m.count_pair_functions) for m in manifest.modules),
        "undeclared_count_pair_functions": undeclared_pairs,
        "undeclared_count_pair_ceiling": ceiling,
        "declaration_issues": len(manifest.issues),
        "failures": failures,
    }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"capability manifest: {len(declared_now)} of {len(manifest.modules)} modules fully "
            f"declared ({len(grandfathered)} grandfathered, floor {len(must_stay_declared)}); "
            f"{summary['count_pair_functions']} functions take a (List, Int) pair, "
            f"{undeclared_pairs} still undeclared (ceiling {ceiling})."
        )
        if failures:
            print(f"\n❌ capability manifest gate: {len(failures)} failure(s):")
            for failure in failures:
                print(f"    {failure}")
            print(
                "\nDeclare the missing block(s) — the grammar is in "
                "apps/runtime/mojo_capability_manifest.py — then re-run. `--update-baseline` "
                "records new coverage but never a regression, and never grandfathers a new module."
            )
    if failures:
        return 1
    if not args.json:
        print("✅ capability manifest gate: no new undeclared kernels.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
