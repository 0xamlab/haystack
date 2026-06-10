from __future__ import annotations

from typing import Any

from benchmarks.repository_intelligence_real_repo_probe_seed_plan_phase_a_1_support import (
    apply_seed_plan_phase_a_1 as _apply_seed_plan_phase_a_1_support,
)
from benchmarks.repository_intelligence_real_repo_probe_seed_plan_phase_a_2_support import (
    apply_seed_plan_phase_a_2 as _apply_seed_plan_phase_a_2_support,
)


def apply_seed_plan_phase_a(state: Any) -> None:
    _apply_seed_plan_phase_a_1_support(state)
    _apply_seed_plan_phase_a_2_support(state)
