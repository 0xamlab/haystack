"""Shared imports + helpers for test_decision_engine_query_surface_* sub-modules.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-1/tests/test_decision_engine_query_surface.py during modularization.
"""
# ruff: noqa: F401

from __future__ import annotations

import importlib

import sys

import warnings

from copy import deepcopy

from pathlib import Path

import pytest

from apps.platform_contract import load_platform_contract_manifest

from tests._manifest_backed_integrations import (
    assert_manifest_backed_integrations,
)

ROOT = Path(__file__).resolve().parents[1]

PYTHON_SDK = ROOT / "packages" / "python-sdk"

if str(PYTHON_SDK) not in sys.path:
    sys.path.insert(0, str(PYTHON_SDK))

pytestmark = pytest.mark.anyio

decision_engine = importlib.import_module("decision_engine")

runtime_manifest_models = importlib.import_module("decision_engine.models_runtime_manifest")

AsyncDecisionEngineClient = decision_engine.AsyncDecisionEngineClient

DecisionEngineClient = decision_engine.DecisionEngineClient

DecisionEngineError = decision_engine.DecisionEngineError

QueryBatchResult = decision_engine.QueryBatchResult

NotFoundError = decision_engine.NotFoundError

PlatformContractResult = decision_engine.PlatformContractResult

QuerySqlReportResult = decision_engine.QuerySqlReportResult

QueryWithMetadataResult = decision_engine.QueryWithMetadataResult

RuntimeAdminBenchmarksResult = decision_engine.RuntimeAdminBenchmarksResult

RuntimeAdminModulesResult = decision_engine.RuntimeAdminModulesResult

RuntimeManifestResult = decision_engine.RuntimeManifestResult

RuntimeReleaseValidationResult = decision_engine.RuntimeReleaseValidationResult

RuntimeAuxiliaryChannelResult = runtime_manifest_models.RuntimeAuxiliaryChannelResult

RuntimeBenchmarkBaselineResult = runtime_manifest_models.RuntimeBenchmarkBaselineResult

RuntimeBenchmarkClassCodeResult = runtime_manifest_models.RuntimeBenchmarkClassCodeResult

RuntimeBenchmarkMetricResult = runtime_manifest_models.RuntimeBenchmarkMetricResult

RuntimeCapabilityFieldResult = runtime_manifest_models.RuntimeCapabilityFieldResult

RuntimeCapabilityRuleResult = runtime_manifest_models.RuntimeCapabilityRuleResult

RuntimeArtifactKindResult = runtime_manifest_models.RuntimeArtifactKindResult

RuntimeCompiledEngineResult = runtime_manifest_models.RuntimeCompiledEngineResult

RuntimeBenchmarkDiscoveryRuleResult = (
    runtime_manifest_models.RuntimeBenchmarkDiscoveryRuleResult
)

RuntimeNonShippingRuleResult = runtime_manifest_models.RuntimeNonShippingRuleResult

RuntimeDeploymentModeResult = runtime_manifest_models.RuntimeDeploymentModeResult

RuntimeEvaluationDimensionResult = runtime_manifest_models.RuntimeEvaluationDimensionResult

RuntimeEvaluationMethodResult = runtime_manifest_models.RuntimeEvaluationMethodResult

RuntimeExecutionStateFieldResult = runtime_manifest_models.RuntimeExecutionStateFieldResult

RuntimeExecutionValidityRuleResult = runtime_manifest_models.RuntimeExecutionValidityRuleResult

RuntimeExternalNondeterminismSourceResult = (
    runtime_manifest_models.RuntimeExternalNondeterminismSourceResult
)

RuntimeFailureCodeResult = runtime_manifest_models.RuntimeFailureCodeResult

RuntimeExecutionTransitionResult = runtime_manifest_models.RuntimeExecutionTransitionResult

RuntimeFeatureFlagChannelResult = runtime_manifest_models.RuntimeFeatureFlagChannelResult

RuntimeInvariantNameResult = runtime_manifest_models.RuntimeInvariantNameResult

RuntimeArtifactLineageStepResult = runtime_manifest_models.RuntimeArtifactLineageStepResult

RuntimeAdminEndpointResult = runtime_manifest_models.RuntimeAdminEndpointResult

RuntimeLayerResult = runtime_manifest_models.RuntimeLayerResult

RuntimeLineageNodeFieldResult = runtime_manifest_models.RuntimeLineageNodeFieldResult

RuntimeMemoryRegionResult = runtime_manifest_models.RuntimeMemoryRegionResult

RuntimeMemoryRuleResult = runtime_manifest_models.RuntimeMemoryRuleResult

RuntimeMaturityResult = runtime_manifest_models.RuntimeMaturityResult

RuntimeModuleIdResult = runtime_manifest_models.RuntimeModuleIdResult

RuntimeNondeterminismArtifactResult = runtime_manifest_models.RuntimeNondeterminismArtifactResult

RuntimeProofObligationResult = runtime_manifest_models.RuntimeProofObligationResult

RuntimePublicEndpointResult = runtime_manifest_models.RuntimePublicEndpointResult

RuntimeSignatureAlgorithmResult = runtime_manifest_models.RuntimeSignatureAlgorithmResult

RuntimeSignatureScopeResult = runtime_manifest_models.RuntimeSignatureScopeResult

RuntimeReleaseArtifactResult = runtime_manifest_models.RuntimeReleaseArtifactResult

RuntimeReleaseBlockerResult = runtime_manifest_models.RuntimeReleaseBlockerResult

RuntimeReleaseConditionResult = runtime_manifest_models.RuntimeReleaseConditionResult

RuntimeReleaseGateIdResult = runtime_manifest_models.RuntimeReleaseGateIdResult

RuntimeReplayabilityResult = runtime_manifest_models.RuntimeReplayabilityResult

RuntimeRiskLevelResult = runtime_manifest_models.RuntimeRiskLevelResult

RuntimeSchedulerInvariantResult = runtime_manifest_models.RuntimeSchedulerInvariantResult

RuntimeSchedulerMaximizeObjectiveResult = (
    runtime_manifest_models.RuntimeSchedulerMaximizeObjectiveResult
)

RuntimeSchedulerMinimizeObjectiveResult = (
    runtime_manifest_models.RuntimeSchedulerMinimizeObjectiveResult
)

RuntimeSchedulerPolicyResult = runtime_manifest_models.RuntimeSchedulerPolicyResult

RuntimeSideEffectClassResult = runtime_manifest_models.RuntimeSideEffectClassResult

RuntimeSLOBudgetAppliesToResult = runtime_manifest_models.RuntimeSLOBudgetAppliesToResult

RuntimeSLOBudgetNameResult = runtime_manifest_models.RuntimeSLOBudgetNameResult

RuntimeSupportedChannelResult = runtime_manifest_models.RuntimeSupportedChannelResult

RuntimeFeatureFlagEndpointResult = runtime_manifest_models.RuntimeFeatureFlagEndpointResult

RuntimeThreatClassResult = runtime_manifest_models.RuntimeThreatClassResult

RuntimeThreatControlResult = runtime_manifest_models.RuntimeThreatControlResult

RuntimeThreatRuleResult = runtime_manifest_models.RuntimeThreatRuleResult

def _platform_contract_payload() -> dict[str, object]:
    return deepcopy(load_platform_contract_manifest())

def _query_result_payload(**overrides):
    return {
        "query_id": "query_1",
        "result": {"rows": []},
        "result_type": "table",
        "confidence": 0.98,
        "plan": ["resolve metric", "execute query"],
        "resolved_column": "revenue",
        "resolved_role": "metric",
        "resolved_source": "orders",
        "row_count": 1,
        "candidates": [],
        "source_scores": {"orders": 0.98},
        "ambiguous": False,
        "exact_spec": True,
        "explanation": ["used exact spec"],
        "latency_ms": 12.5,
        "decision_path": "exact_spec",
        "plan_hash": "plan_1",
        "validated": True,
        "deterministic_scope": "exact",
        "confidence_source": "schema_truth",
        "request_id": "req_query",
        **overrides,
    }



__all__ = [
    "annotations",
    "importlib",
    "sys",
    "warnings",
    "deepcopy",
    "Path",
    "pytest",
    "load_platform_contract_manifest",
    "assert_manifest_backed_integrations",
    "ROOT",
    "PYTHON_SDK",
    "pytestmark",
    "decision_engine",
    "runtime_manifest_models",
    "AsyncDecisionEngineClient",
    "DecisionEngineClient",
    "DecisionEngineError",
    "QueryBatchResult",
    "NotFoundError",
    "PlatformContractResult",
    "QuerySqlReportResult",
    "QueryWithMetadataResult",
    "RuntimeAdminBenchmarksResult",
    "RuntimeAdminModulesResult",
    "RuntimeManifestResult",
    "RuntimeReleaseValidationResult",
    "RuntimeAuxiliaryChannelResult",
    "RuntimeBenchmarkBaselineResult",
    "RuntimeBenchmarkClassCodeResult",
    "RuntimeBenchmarkMetricResult",
    "RuntimeCapabilityFieldResult",
    "RuntimeCapabilityRuleResult",
    "RuntimeArtifactKindResult",
    "RuntimeCompiledEngineResult",
    "RuntimeBenchmarkDiscoveryRuleResult",
    "RuntimeNonShippingRuleResult",
    "RuntimeDeploymentModeResult",
    "RuntimeEvaluationDimensionResult",
    "RuntimeEvaluationMethodResult",
    "RuntimeExecutionStateFieldResult",
    "RuntimeExecutionValidityRuleResult",
    "RuntimeExternalNondeterminismSourceResult",
    "RuntimeFailureCodeResult",
    "RuntimeExecutionTransitionResult",
    "RuntimeFeatureFlagChannelResult",
    "RuntimeInvariantNameResult",
    "RuntimeArtifactLineageStepResult",
    "RuntimeAdminEndpointResult",
    "RuntimeLayerResult",
    "RuntimeLineageNodeFieldResult",
    "RuntimeMemoryRegionResult",
    "RuntimeMemoryRuleResult",
    "RuntimeMaturityResult",
    "RuntimeModuleIdResult",
    "RuntimeNondeterminismArtifactResult",
    "RuntimeProofObligationResult",
    "RuntimePublicEndpointResult",
    "RuntimeSignatureAlgorithmResult",
    "RuntimeSignatureScopeResult",
    "RuntimeReleaseArtifactResult",
    "RuntimeReleaseBlockerResult",
    "RuntimeReleaseConditionResult",
    "RuntimeReleaseGateIdResult",
    "RuntimeReplayabilityResult",
    "RuntimeRiskLevelResult",
    "RuntimeSchedulerInvariantResult",
    "RuntimeSchedulerMaximizeObjectiveResult",
    "RuntimeSchedulerMinimizeObjectiveResult",
    "RuntimeSchedulerPolicyResult",
    "RuntimeSideEffectClassResult",
    "RuntimeSLOBudgetAppliesToResult",
    "RuntimeSLOBudgetNameResult",
    "RuntimeSupportedChannelResult",
    "RuntimeFeatureFlagEndpointResult",
    "RuntimeThreatClassResult",
    "RuntimeThreatControlResult",
    "RuntimeThreatRuleResult",
    "_platform_contract_payload",
    "_query_result_payload",
]
