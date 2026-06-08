from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.plan_alignment import collect_plan_alignment_snapshot

OUTPUT_PATH = ROOT / "build" / "plan_alignment_matrix.json"


def main() -> None:
    snapshot = collect_plan_alignment_snapshot()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(snapshot.to_dict(), indent=2, sort_keys=True) + "\n")

    route_counts = {"implemented": 0, "partial": 0, "missing": 0}
    for route in snapshot.public_llm_routes:
        route_counts[route.status] += 1

    tranche_counts = {"implemented": 0, "partial": 0, "missing": 0}
    for tranche in snapshot.immediate_pr_sequence:
        tranche_counts[tranche.status] += 1

    print(f"Plan alignment artifact: {OUTPUT_PATH}")
    print(
        "LLM public routes — "
        f"implemented: {route_counts['implemented']}, "
        f"partial: {route_counts['partial']}, "
        f"missing: {route_counts['missing']}"
    )
    print(
        "Immediate PR tranches — "
        f"implemented: {tranche_counts['implemented']}, "
        f"partial: {tranche_counts['partial']}, "
        f"missing: {tranche_counts['missing']}"
    )


if __name__ == "__main__":
    main()
