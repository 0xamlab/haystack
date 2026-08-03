"""Regression test for the `llm_e2e.py` structured-formulation parser.

Guards two things:
  - a constraint/objective term with coefficient EXACTLY 0.0 that names an
    undeclared variable is a mathematical no-op and must be dropped, not treated
    as a hard parse failure (a real gpt-5-mini formulation for instance
    `m_tsptw_e_00` hit exactly this: a `{"var": "x_1_1", "coeff": 0}` term inside
    constraint `cust1_incoming`, where `x_1_1` was never declared);
  - a term with a NONZERO coefficient referencing an undeclared variable must
    still hard-fail exactly as before -- the fix narrows the rejection, it does
    not loosen correctness checking for anything that actually matters to the
    solve.

The fixture at tests/fixtures/optmodel_llm_e2e_m_tsptw_e_00.json is the exact,
unmodified raw LLM output object from the real end-to-end run this repo already
measured and reported (2026-08-02, gpt-5-mini; see
benchmarks/optmodel_plane/README.md). Before the fix, parsing it raised
"constraint cust1_incoming: references undeclared variable 'x_1_1'" and the
instance was scored `malformed`. This test only asserts that parsing now
succeeds -- the parsed instance likely still fails the actual solve as
infeasible for a separate, unrelated reason (a big-M sign error in the LLM's own
time-propagation constraints), which is not this test's concern.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

# llm_e2e.py unconditionally imports its sibling harness.py, which imports
# scipy.optimize for its independent HiGHS referee re-solve -- a real runtime
# dependency of the (real-spend, owner-gated) LLM e2e benchmark script itself,
# not of the core app, so it is not part of this repo's default test
# environment. Skip rather than error where it's absent, same convention as
# tests/test_agent_run_service.py (pyarrow) and tests/test_mcp_router.py (mcp).
pytest.importorskip("scipy")

REPO_ROOT = Path(__file__).resolve().parents[1]
LLM_E2E_PATH = REPO_ROOT / "benchmarks" / "optmodel_plane" / "llm_e2e.py"
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "optmodel_llm_e2e_m_tsptw_e_00.json"


def _load_llm_e2e_module() -> ModuleType:
    """Load benchmarks/optmodel_plane/llm_e2e.py as an isolated module.

    The module isn't part of an importable package (no __init__.py in
    benchmarks/optmodel_plane/), but it manages its own sys.path insertion for
    its sibling imports (`harness`, `llm_e2e_render`), so loading it by file
    path works the same as running it as a script.
    """
    spec = importlib.util.spec_from_file_location("optmodel_llm_e2e_under_test", LLM_E2E_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec: the module's own @dataclass decorator (SampleResult)
    # looks itself up via sys.modules[cls.__module__] during class creation.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


llm_e2e = _load_llm_e2e_module()


def _minimal_original(inst_id: str = "stub") -> dict:
    """The subset of an original mirror-instance dict llm_formulation_to_instance
    reads through untouched; solve-relevant fields are stubbed since these tests
    only exercise parsing, never the solver."""
    return {
        "id": inst_id,
        "family": "stub_family",
        "subcategory": "stub_subcategory",
        "difficulty": "easy",
        "description": "stub",
        "max_nodes": 1000,
        "ground_truth": {"objective": 0.0},
        "paper_floor": 0.0,
    }


def test_zero_coeff_term_on_undeclared_variable_is_dropped() -> None:
    formulation = {
        "maximize": False,
        "variables": [{"name": "x", "kind": "continuous", "lower": 0.0, "upper": None}],
        "objective": {"terms": [{"var": "x", "coeff": 1.0}], "constant": 0.0},
        "constraints": [
            {
                "name": "c0",
                "terms": [
                    {"var": "x", "coeff": 1.0},
                    {"var": "undeclared_var", "coeff": 0.0},
                ],
                "sense": "<=",
                "rhs": 5.0,
            }
        ],
    }

    instance = llm_e2e.llm_formulation_to_instance(_minimal_original(), formulation)

    assert instance["constraints"][0]["coeffs"] == {"x": 1.0}


def test_nonzero_coeff_term_on_undeclared_variable_still_hard_fails() -> None:
    """The narrowing must not loosen correctness checking for anything that
    actually matters to the solve: a genuinely undeclared, nonzero-coefficient
    reference is still a hard parse failure, byte-for-byte the same message."""
    formulation = {
        "maximize": False,
        "variables": [{"name": "x", "kind": "continuous", "lower": 0.0, "upper": None}],
        "objective": {"terms": [{"var": "x", "coeff": 1.0}], "constant": 0.0},
        "constraints": [
            {
                "name": "c0",
                "terms": [
                    {"var": "x", "coeff": 1.0},
                    {"var": "undeclared_var", "coeff": 0.001},
                ],
                "sense": "<=",
                "rhs": 5.0,
            }
        ],
    }

    with pytest.raises(ValueError, match=r"references undeclared variable 'undeclared_var'"):
        llm_e2e.llm_formulation_to_instance(_minimal_original(), formulation)


def test_m_tsptw_e_00_real_llm_output_parses_after_fix() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    formulation = fixture["llm_formulation"]

    # Sanity-check the fixture still contains the exact triggering term, so this
    # test keeps testing what it claims to test even if the fixture file is ever
    # hand-edited.
    var_names = {v["name"] for v in formulation["variables"]}
    assert "x_1_1" not in var_names
    cust1_incoming = next(
        c for c in formulation["constraints"] if c["name"] == "cust1_incoming"
    )
    zero_term = next(t for t in cust1_incoming["terms"] if t["var"] == "x_1_1")
    assert float(zero_term["coeff"]) == 0.0

    original = _minimal_original(fixture["id"])
    original["family"] = fixture["family"]
    original["subcategory"] = fixture["subcategory"]
    original["difficulty"] = fixture["difficulty"]

    instance = llm_e2e.llm_formulation_to_instance(original, formulation)

    assert instance["id"] == "m_tsptw_e_00"
    parsed_constraint = next(
        c for c in instance["constraints"] if c["name"] == "cust1_incoming"
    )
    assert "x_1_1" not in parsed_constraint["coeffs"]
