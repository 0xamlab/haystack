"""
Runtime model manifest — public facade.

The implementation is split into _runtime_manifest_*.py submodules
for maintainability (each <1000 lines). This file re-exports the
complete public API so existing imports continue to work unchanged.
"""
from __future__ import annotations


from algenta._runtime_manifest_enums import *  # noqa: F401, F403
from algenta._runtime_manifest_coercion import *  # noqa: F401, F403
from algenta._runtime_manifest_references import *  # noqa: F401, F403
from algenta._runtime_manifest_modules import *  # noqa: F401, F403
from algenta._runtime_manifest_topology import *  # noqa: F401, F403
from algenta._runtime_manifest_operations import *  # noqa: F401, F403
from algenta._runtime_manifest_release import *  # noqa: F401, F403
from algenta._runtime_manifest_admin_outputs import *  # noqa: F401, F403
from algenta._runtime_manifest_release_outputs import *  # noqa: F401, F403

# Explicit re-export of the one public helper that starts with a lowercase letter.
from algenta._runtime_manifest_coercion import coerce_payload_mapping  # noqa: F401

__all__ = [
    'RuntimeMaturity',
    'RuntimeSideEffectClass',
    'RuntimeRiskLevel',
    'RuntimeReplayability',
    'RuntimeSupportedChannel',
    'RuntimeAuxiliaryChannel',
    'RuntimeFeatureFlagChannel',
    'RuntimeDeploymentMode',
    'RuntimeLayer',
    'RuntimeModuleId',
    'RuntimeCompiledEngine',
    'RuntimeKernelPromotionStatus',
    'RuntimeBenchmarkDiscoveryRule',
    'RuntimeNonShippingRule',
    'RuntimePublicEndpoint',
    'RuntimeAdminEndpoint',
    'RuntimeFeatureFlagEndpoint',
    'RuntimeExecutionTransition',
    'RuntimeReleaseCondition',
    'RuntimeFailureCode',
    'RuntimeBenchmarkClassCode',
    'RuntimeSchedulerPolicy',
    'RuntimeSchedulerMinimizeObjective',
    'RuntimeSchedulerMaximizeObjective',
    'RuntimeSchedulerInvariant',
    'RuntimeReleaseGateId',
    'RuntimeInvariantName',
    'RuntimeExecutionStateField',
    'RuntimeExecutionValidityRule',
    'RuntimeLineageNodeField',
    'RuntimeExternalNondeterminismSource',
    'RuntimeNondeterminismArtifact',
    'RuntimeArtifactLineageStep',
    'RuntimeCapabilityField',
    'RuntimeCapabilityRule',
    'RuntimeSLOBudgetName',
    'RuntimeSLOBudgetAppliesTo',
    'RuntimeMemoryRegion',
    'RuntimeMemoryRule',
    'RuntimeProofObligation',
    'RuntimeBenchmarkMetric',
    'RuntimeBenchmarkBaseline',
    'RuntimeEvaluationMethod',
    'RuntimeReleaseBlocker',
    'RuntimeEvaluationDimension',
    'RuntimeThreatClass',
    'RuntimeThreatControl',
    'RuntimeThreatRule',
    'RuntimeReleaseArtifact',
    'RuntimeArtifactKind',
    'RuntimeSignatureAlgorithm',
    'RuntimeSignatureScope',
    'RuntimeArtifactReference',
    'RuntimeManifestSignature',
    'RuntimeSnapshotReference',
    'RuntimeKernelPromotionCriteria',
    'RuntimeModuleManifestEntry',
    'RuntimeDeploymentModes',
    'RuntimeShippingContractSummary',
    'RuntimeBenchmarkDiscoverySourceModuleEntry',
    'RuntimeBenchmarkDiscoveryLane',
    'RuntimeAdvertisedCapabilities',
    'RuntimeNamedRule',
    'RuntimeExecutionModel',
    'RuntimeExternalNondeterminismPolicy',
    'RuntimeArtifactLineageSchema',
    'RuntimeCapabilityEnums',
    'RuntimeCapabilityAlgebraSchema',
    'RuntimeLayerProofMatrixEntry',
    'RuntimeBenchmarkClassEntry',
    'RuntimeBenchmarkFramework',
    'RuntimeSLOBudget',
    'RuntimeSchedulerModel',
    'RuntimeMemoryModel',
    'RuntimeEvaluationScience',
    'RuntimeThreatModel',
    'RuntimeTypedFailure',
    'RuntimeFormalReleaseTheorem',
    'RuntimeReleaseArtifactBundle',
    'RuntimeReleaseGate',
    'RuntimeImmediateImplementationPR',
    'RuntimeAdminModuleSummary',
    'RuntimeAdminEvaluationSummary',
    'RuntimeAdminModulesOutput',
    'RuntimeBenchmarkModuleEntry',
    'RuntimeAdminBenchmarksOutput',
    'ReleaseConditionEvaluation',
    'RuntimeReleaseValidationOutput',
    'RuntimeManifestOutput',
    'coerce_payload_mapping',
]
