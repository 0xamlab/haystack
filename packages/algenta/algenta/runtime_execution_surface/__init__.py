"""runtime_execution_surface — public facade.

The implementation is split into _<name>.py submodules of this package
for maintainability (each well under 1000 lines). This __init__.py
re-exports the complete public API so existing
`from algenta.runtime_execution_surface import X` imports continue
to work unchanged.
"""
from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from functools import cache
from importlib import import_module
from typing import TYPE_CHECKING, Any

from algenta.runtime_errors import RuntimeConfigurationError, RuntimeValidationError
from algenta.runtime_model_common import coerce_payload_mapping

if TYPE_CHECKING:
    from types import ModuleType


@cache
def _runtime_api_exact_module() -> ModuleType:
    return import_module("algenta.runtime_api_exact")


@cache
def _runtime_api_payloads_module() -> ModuleType:
    return import_module("algenta.runtime_api_payloads")


@cache
def _runtime_intent_module() -> ModuleType:
    return import_module("algenta.runtime_intent")


@cache
def _runtime_local_limits_module() -> ModuleType:
    return import_module("algenta.runtime_local_limits")


@cache
def _runtime_local_query_module() -> ModuleType:
    return import_module("algenta.runtime_local_query")


@cache
def _runtime_local_resolve_module() -> ModuleType:
    return import_module("algenta.runtime_local_resolve")


@cache
def _runtime_model_query_output_module() -> ModuleType:
    return import_module("algenta.runtime_model_query_output")


@cache
def _runtime_model_query_metadata_module() -> ModuleType:
    return import_module("algenta.runtime_model_query_metadata")


@cache
def _runtime_model_resolve_output_module() -> ModuleType:
    return import_module("algenta.runtime_model_resolve_output")


@cache
def _runtime_model_verify_output_module() -> ModuleType:
    return import_module("algenta.runtime_model_verify_output")


@cache
def _runtime_model_decision_plan_module() -> ModuleType:
    return import_module("algenta.runtime_model_decision_plan")


@cache
def _runtime_model_decision_envelope_module() -> ModuleType:
    return import_module("algenta.runtime_model_decision_envelope")


@cache
def _runtime_model_decision_memory_module() -> ModuleType:
    return import_module("algenta.runtime_model_decision_memory")


@cache
def _runtime_model_repository_intelligence_module() -> ModuleType:
    return import_module("algenta.runtime_model_repository_intelligence")


@cache
def _runtime_model_products_module() -> ModuleType:
    return import_module("algenta.runtime_model_products")


@cache
def _runtime_model_llm_module() -> ModuleType:
    return import_module("algenta.runtime_model_llm")


@cache
def _runtime_model_agent_runs_module() -> ModuleType:
    return import_module("algenta.runtime_model_agent_runs")


@cache
def _runtime_model_account_module() -> ModuleType:
    return import_module("algenta.runtime_model_account")


@cache
def _runtime_model_deployments_module() -> ModuleType:
    return import_module("algenta.runtime_model_deployments")


@cache
def _runtime_model_control_plane_module() -> ModuleType:
    return import_module("algenta.runtime_model_control_plane")


from algenta.runtime_execution_surface._api_client_local import *  # noqa: E402, F401, F403
from algenta.runtime_execution_surface._api_client_local import (  # noqa: E402, F401
    _run_sync,
)
from algenta.runtime_execution_surface._validation import *  # noqa: E402, F401, F403
from algenta.runtime_execution_surface._validation import (  # noqa: E402, F401
    _validate_contract_payload,
    _build_runtime_validation_error_details,
    _validate_runtime_proof_payload,
    _validate_runtime_api_payload,
    _validate_runtime_api_mapping_payload,
    _validate_runtime_api_structured_mapping_payload,
    _validate_runtime_api_mapping_list_payload,
    _validate_runtime_api_stream,
    _validate_runtime_api_payload_list,
    _request_runtime_contract_payload,
)
from algenta.runtime_execution_surface._query_jobs_triggers import *  # noqa: E402, F401, F403
from algenta.runtime_execution_surface._decision_repo_product_deploy import *  # noqa: E402, F401, F403
from algenta.runtime_execution_surface._account_team_billing import *  # noqa: E402, F401, F403
from algenta.runtime_execution_surface._llm_runtime import *  # noqa: E402, F401, F403
from algenta.runtime_execution_surface._agent_runs import *  # noqa: E402, F401, F403

__all__ = [
    "cancel_job_runtime_request",
    "create_api_key_runtime_request",
    "coerce_api_query_payload",
    "coerce_api_resolve_payload",
    "coerce_plan",
    "extract_columns_local_request",
    "extract_columns_runtime_request",
    "contract_runtime_request",
    "consume_local_credit",
    "ensure_local_execution_entitlement",
    "forget_api_registration",
    "get_job_result_runtime_request",
    "get_job_runtime_request",
    "ingest_metering_events_runtime_request",
    "invite_team_member_runtime_request",
    "limits_runtime_request",
    "list_api_keys_runtime_request",
    "list_devices_runtime_request",
    "list_jobs_runtime_request",
    "me_runtime_request",
    "query_batch_runtime_request",
    "query_local_request",
    "query_sql_report_runtime_request",
    "query_runtime_request",
    "remove_team_member_runtime_request",
    "revoke_device_runtime_request",
    "revoke_api_key_runtime_request",
    "remember_api_registration",
    "resolve_local_request",
    "resolve_runtime_request",
    "runtime_api_client",
    "runtime_benchmarks_runtime_request",
    "runtime_manifest_runtime_request",
    "runtime_modules_runtime_request",
    "runtime_release_validation_runtime_request",
    "stream_agent_run_events_runtime_request",
    "stream_chat_completions_runtime_request",
    "stream_responses_runtime_request",
    "submit_job_runtime_request",
    "test_webhook_delivery_runtime_request",
    "try_exact_api_resolve",
    "usage_runtime_request",
    "update_team_member_role_runtime_request",
    "verify_local_request",
    "verify_runtime_request",
    "poll_job_runtime_request",
]
