"""Tests for test_algenta_runtime: misc.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-3/tests/test_algenta_runtime.py during modularization.
"""
from __future__ import annotations

from tests._test_algenta_runtime_helpers import *  # noqa: F401,F403


def test_runtime_query_rejects_schema_revision_mismatch() -> None:
    runtime = Runtime()
    runtime.connect(_sample_rows(), name="orders")
    plan = runtime.resolve({"source_name": "orders", "metric": "revenue"})
    assert plan.resolved_plan is not None
    tampered_plan = plan.resolved_plan.to_dict()
    tampered_plan["schema_revision"] = "stale"

    with pytest.raises(RuntimeValidationError, match="schema_revision"):
        runtime.query(tampered_plan)


def test_runtime_validation_error_exposes_field_errors_from_direct_details() -> None:
    exc = RuntimeValidationError(
        "invalid_runtime_contract_payload",
        "invalid signed payload",
        {
            "cause": "proof_matrix.0.status",
            "validation_errors": [
                {
                    "path": "proof_matrix.0.status",
                    "message": "Input should be a valid enum value",
                    "type": "enum",
                }
            ],
        },
    )

    assert exc.validation_errors == [
        {
            "path": "proof_matrix.0.status",
            "message": "Input should be a valid enum value",
            "type": "enum",
        }
    ]
    assert exc.field_errors == exc.validation_errors


def test_runtime_manifest_output_accepts_direct_producer_model_payload() -> None:
    from apps.runtime_manifest import get_runtime_manifest

    manifest = RuntimeManifestOutput.from_api(get_runtime_manifest())

    assert manifest.maturity[RuntimeModuleId.bpe_tokenizer] is RuntimeMaturity.channel_covered
    assert manifest.to_dict()["maturity"]["bpe_tokenizer"] == "channel_covered"


def test_runtime_admin_modules_output_accepts_direct_producer_model_payload() -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    modules = RuntimeAdminModulesOutput.from_api(get_runtime_admin_modules())

    assert modules.summary.maturity_counts[RuntimeMaturity.channel_covered] == 22
    assert modules.summary.layer_counts[RuntimeLayer.mojo_llm_runtime_core] == 22
    assert modules.to_dict()["summary"]["maturity_counts"]["channel_covered"] == 22
    assert modules.to_dict()["summary"]["layer_counts"]["mojo_llm_runtime_core"] == 22


def test_runtime_release_validation_output_accepts_direct_producer_model_payload() -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    validation = RuntimeReleaseValidationOutput.from_api(get_runtime_release_validation())

    assert validation.conditions[0].condition is RuntimeReleaseCondition.manifest_listed
    assert validation.to_dict()["conditions"][0]["condition"] == "manifest-listed"


