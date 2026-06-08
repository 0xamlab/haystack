"""Tests for test_runtime_surface_compatibility: misc_d.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-4/tests/test_runtime_surface_compatibility.py during modularization.
"""
from __future__ import annotations

from tests._test_runtime_surface_compatibility_helpers import *  # noqa: F401,F403


def test_remaining_live_integration_scripts_write_summary_artifacts() -> None:
    auth_security_live = (
        ROOT / "tests" / "integration" / "test_auth_security.py"
    ).read_text(encoding="utf-8")
    api_live = (ROOT / "tests" / "integration" / "test_api_live.py").read_text(
        encoding="utf-8"
    )
    billing_team_live = (
        ROOT / "tests" / "integration" / "test_billing_team.py"
    ).read_text(encoding="utf-8")
    connectors_live = (ROOT / "tests" / "integration" / "test_connectors.py").read_text(
        encoding="utf-8"
    )
    middleware_live = (ROOT / "tests" / "integration" / "test_middleware.py").read_text(
        encoding="utf-8"
    )
    mojo_pool_live = (ROOT / "tests" / "integration" / "test_mojo_pool.py").read_text(
        encoding="utf-8"
    )
    mojo_engines_realdata_live = (
        ROOT / "tests" / "integration" / "test_mojo_engines_realdata.py"
    ).read_text(encoding="utf-8")
    templates_live = (ROOT / "tests" / "integration" / "test_templates.py").read_text(
        encoding="utf-8"
    )
    all_engines_live = (ROOT / "tests" / "integration" / "test_all_engines.py").read_text(
        encoding="utf-8"
    )
    benchmarks_live = (ROOT / "tests" / "integration" / "test_benchmarks.py").read_text(
        encoding="utf-8"
    )
    e2e_complete_live = (ROOT / "tests" / "integration" / "test_e2e_complete.py").read_text(
        encoding="utf-8"
    )
    database_live = (ROOT / "tests" / "integration" / "test_database.py").read_text(
        encoding="utf-8"
    )
    jobs_live = (ROOT / "tests" / "integration" / "test_jobs.py").read_text(
        encoding="utf-8"
    )
    mcp_runtime_live = (
        ROOT / "tests" / "integration" / "test_mcp_runtime_live.py"
    ).read_text(encoding="utf-8")
    algenta_client_live = (
        ROOT / "tests" / "integration" / "test_algenta_client_live.py"
    ).read_text(encoding="utf-8")
    algenta_runtime_live = (
        ROOT / "tests" / "integration" / "test_algenta_runtime_live.py"
    ).read_text(encoding="utf-8")
    python_sdk_live = (ROOT / "tests" / "integration" / "test_python_sdk.py").read_text(
        encoding="utf-8"
    )
    typescript_sdk_live = (
        ROOT / "tests" / "integration" / "test_typescript_sdk_client_live.py"
    ).read_text(encoding="utf-8")
    typescript_runtime_live = (
        ROOT / "tests" / "integration" / "test_typescript_runtime_live.py"
    ).read_text(encoding="utf-8")
    local_runtime_real = (
        ROOT / "tests" / "integration" / "test_local_runtime_real.py"
    ).read_text(encoding="utf-8")
    cli_live = (ROOT / "tests" / "integration" / "test_cli.py").read_text(encoding="utf-8")
    services_live = (ROOT / "tests" / "integration" / "test_services.py").read_text(
        encoding="utf-8"
    )

    assert "python3 tests/integration/test_auth_security.py" in auth_security_live
    assert "PYTHONPATH=. python3 tests/integration/test_auth_security.py" not in auth_security_live
    assert "PROJECT_ROOT = os.path.normpath" in auth_security_live
    assert 'SUITE_NAME = "auth_security_integration"' in auth_security_live
    assert "write_live_integration_summary(" in auth_security_live
    assert "Summary artifact:" in auth_security_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in auth_security_live
    assert '_emit(f"  ... {name}")' in auth_security_live

    assert "python tests/integration/test_api_live.py" in api_live
    assert "PYTHONPATH=. python tests/integration/test_api_live.py" not in api_live
    assert "_PROJECT_ROOT = os.path.abspath" in api_live
    assert 'SUITE_NAME = "api_live_integration"' in api_live
    assert "write_live_integration_summary(" in api_live
    assert "Summary artifact:" in api_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in api_live
    assert '_emit(f"  ... {name}")' in api_live

    assert "python3 tests/integration/test_billing_team.py" in billing_team_live
    assert "PYTHONPATH=. python3 tests/integration/test_billing_team.py" not in billing_team_live
    assert '_ROOT = Path(__file__).resolve().parents[2]' in billing_team_live
    assert 'SUITE_NAME = "billing_team_integration"' in billing_team_live
    assert "write_live_integration_summary(" in billing_team_live
    assert "Summary artifact:" in billing_team_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in billing_team_live
    assert '_emit(f"  ... {name}")' in billing_team_live

    assert "python3 tests/integration/test_connectors.py" in connectors_live
    assert "PYTHONPATH=. python3 tests/integration/test_connectors.py" not in connectors_live
    assert "PROJECT_ROOT = os.path.normpath" in connectors_live
    assert 'SUITE_NAME = "connectors_integration"' in connectors_live
    assert "write_live_integration_summary(" in connectors_live
    assert "Summary artifact:" in connectors_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in connectors_live
    assert '_emit(f"  ... {name}")' in connectors_live

    assert "python tests/integration/test_middleware.py" in middleware_live
    assert "PYTHONPATH=. python tests/integration/test_middleware.py" not in middleware_live
    assert "_PROJECT_ROOT = os.path.abspath" in middleware_live
    assert 'SUITE_NAME = "middleware_integration"' in middleware_live
    assert "write_live_integration_summary(" in middleware_live
    assert "Summary artifact:" in middleware_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in middleware_live
    assert '_emit(f"  ... {name}")' in middleware_live

    assert "python tests/integration/test_mojo_pool.py" in mojo_pool_live
    assert "PYTHONPATH=. python tests/integration/test_mojo_pool.py" not in mojo_pool_live
    assert "Path(__file__).parents[2]" in mojo_pool_live
    assert 'SUITE_NAME = "mojo_pool_integration"' in mojo_pool_live
    assert "write_live_integration_summary(" in mojo_pool_live
    assert "Summary artifact:" in mojo_pool_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in mojo_pool_live
    assert '_emit(f"  ... {name}")' in mojo_pool_live

    assert "python3 tests/integration/test_mojo_engines_realdata.py" in mojo_engines_realdata_live
    assert (
        "PYTHONPATH=. python3 tests/integration/test_mojo_engines_realdata.py"
        not in mojo_engines_realdata_live
    )
    assert "_PROJECT_ROOT = Path(__file__).resolve().parents[2]" in mojo_engines_realdata_live
    assert 'SUITE_NAME = "mojo_engines_realdata_integration"' in mojo_engines_realdata_live
    assert "write_live_integration_summary(" in mojo_engines_realdata_live
    assert "Summary artifact:" in mojo_engines_realdata_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in mojo_engines_realdata_live
    assert '_emit(f"  ... {name}")' in mojo_engines_realdata_live

    assert "python tests/integration/test_templates.py" in templates_live
    assert "PYTHONPATH=. python tests/integration/test_templates.py" not in templates_live
    assert "_PROJECT_ROOT = os.path.abspath" in templates_live
    assert 'SUITE_NAME = "templates_integration"' in templates_live
    assert "write_live_integration_summary(" in templates_live
    assert "Summary artifact:" in templates_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in templates_live
    assert '_emit(f"  ... {name}")' in templates_live

    assert "python tests/integration/test_all_engines.py" in all_engines_live
    assert "PYTHONPATH=. python tests/integration/test_all_engines.py" not in all_engines_live
    assert "PROJECT_ROOT = os.path.normpath" in all_engines_live
    assert 'SUITE_NAME = "all_engines_integration"' in all_engines_live
    assert "write_live_integration_summary(" in all_engines_live
    assert "Summary artifact:" in all_engines_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in all_engines_live
    assert '_emit(f"  ... {name}")' in all_engines_live

    assert "python tests/integration/test_benchmarks.py" in benchmarks_live
    assert "PYTHONPATH=. python tests/integration/test_benchmarks.py" not in benchmarks_live
    assert "PROJECT_ROOT = os.path.normpath" in benchmarks_live
    assert 'SUITE_NAME = "benchmarks_integration"' in benchmarks_live
    assert "write_live_integration_summary(" in benchmarks_live
    assert "Summary artifact:" in benchmarks_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in benchmarks_live
    assert '_emit(f"  ... {name}")' in benchmarks_live

    assert "python tests/integration/test_e2e_complete.py" in e2e_complete_live
    assert "PYTHONPATH=. python tests/integration/test_e2e_complete.py" not in e2e_complete_live
    assert "_PROJECT_ROOT = os.path.normpath" in e2e_complete_live
    assert 'SUITE_NAME = "e2e_complete_integration"' in e2e_complete_live
    assert "write_live_integration_summary(" in e2e_complete_live
    assert "Summary artifact:" in e2e_complete_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in e2e_complete_live
    assert '_emit(f"  ... {name}")' in e2e_complete_live

    assert "python tests/integration/test_database.py" in database_live
    assert "PYTHONPATH=. python tests/integration/test_database.py" not in database_live
    assert "\nROOT = Path(__file__).resolve().parents[2]\n" not in database_live
    assert "PROJECT_ROOT = Path(__file__).resolve().parents[2]" in database_live
    assert "sys.path.insert(0, str(PROJECT_ROOT))" in database_live
    assert 'SUITE_NAME = "database_integration"' in database_live
    assert "write_live_integration_summary(" in database_live
    assert "Summary artifact:" in database_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in database_live
    assert '_emit(f"  ... {name}")' in database_live

    assert "python tests/integration/test_jobs.py" in jobs_live
    assert "PYTHONPATH=. python tests/integration/test_jobs.py" not in jobs_live
    assert 'SUITE_NAME = "jobs_integration"' in jobs_live
    assert "write_live_integration_summary(" in jobs_live
    assert "Summary artifact:" in jobs_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in jobs_live
    assert '_emit(f"  ... {name}")' in jobs_live

    assert "python3 tests/integration/test_mcp_runtime_live.py" in mcp_runtime_live
    assert "PYTHONPATH=. python3 tests/integration/test_mcp_runtime_live.py" not in mcp_runtime_live
    assert 'SUITE_NAME = "mcp_runtime_live"' in mcp_runtime_live
    assert "write_live_integration_summary(" in mcp_runtime_live
    assert "Summary artifact:" in mcp_runtime_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in mcp_runtime_live
    assert '_emit(f"  ... {name}")' in mcp_runtime_live
    assert "_missing_live_api_key_reason()" in mcp_runtime_live
    assert 'results.append((SKIP, name, str(exc)))' in mcp_runtime_live

    assert "python3 tests/integration/test_algenta_client_live.py" in algenta_client_live
    assert "PYTHONPATH=. python3 tests/integration/test_algenta_client_live.py" not in algenta_client_live
    assert "ROOT = Path(__file__).resolve().parents[2]" in algenta_client_live
    assert "sys.path.insert(0, path)" in algenta_client_live
    assert 'SUITE_NAME = "algenta_client_live"' in algenta_client_live
    assert "write_live_integration_summary(" in algenta_client_live
    assert "Summary artifact:" in algenta_client_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in algenta_client_live
    assert '_emit(f"  ... {name}")' in algenta_client_live
    assert '_emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")' in (
        algenta_client_live
    )
    assert "resolve_local_live_base_url" not in algenta_client_live

    assert "python3 tests/integration/test_algenta_runtime_live.py" in algenta_runtime_live
    assert (
        "PYTHONPATH=. python3 tests/integration/test_algenta_runtime_live.py"
        not in algenta_runtime_live
    )
    assert 'SUITE_NAME = "algenta_runtime_live"' in algenta_runtime_live
    assert "write_live_integration_summary(" in algenta_runtime_live
    assert "Summary artifact:" in algenta_runtime_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in algenta_runtime_live
    assert '_emit(f"  ... {name}")' in algenta_runtime_live
    assert '_emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")' in (
        algenta_runtime_live
    )
    assert "resolve_local_live_base_url" not in algenta_runtime_live

    assert "python3 tests/integration/test_python_sdk.py" in python_sdk_live
    assert "PYTHONPATH=. python3 tests/integration/test_python_sdk.py" not in python_sdk_live
    assert "ROOT = Path(__file__).resolve().parents[2]" in python_sdk_live
    assert "sys.path.insert(0, path)" in python_sdk_live
    assert 'SUITE_NAME = "python_sdk_integration"' in python_sdk_live
    assert "PlatformContractResponse.model_validate(contract)" in python_sdk_live
    assert "from tests._manifest_backed_integrations import (" in python_sdk_live
    assert "contract_integrations_match_manifest" in python_sdk_live
    assert 'if not contract_integrations_match_manifest(contract["integrations"]):' in (
        python_sdk_live
    )
    assert "RuntimeAdminBenchmarksResponse.model_validate(" in python_sdk_live
    assert '("/v1/me", "get")' in python_sdk_live
    assert '("/v1/me", "patch")' in python_sdk_live
    assert '("/v1/billing/info", "get")' in python_sdk_live
    assert '("/v1/distributions", "get")' in python_sdk_live
    assert '("/v1/templates", "get")' in python_sdk_live
    assert '("/v1/webhooks/test", "post")' in python_sdk_live
    assert '("/v1/execution/policy/snapshots", "get")' in python_sdk_live
    assert '("/v1/connectors", "get")' in python_sdk_live
    assert '("/v1/connectors", "post")' in python_sdk_live
    assert '("/v1/connectors/test", "post")' in python_sdk_live
    assert '("/v1/connectors/browse", "post")' in python_sdk_live
    assert '("/v1/connectors/{connector_id}", "get")' in python_sdk_live
    assert '("/v1/connectors/{connector_id}", "patch")' in python_sdk_live
    assert '("/v1/connectors/{connector_id}/test", "post")' in python_sdk_live
    assert '("/v1/connectors/{connector_id}/browse", "get")' in python_sdk_live
    assert '("/v1/connectors/{connector_id}", "delete")' in python_sdk_live
    assert '("/v1/data/connect", "post")' in python_sdk_live
    assert '("/v1/data", "get")' in python_sdk_live
    assert '("/v1/data/{dataset_id}", "get")' in python_sdk_live
    assert '("/v1/data/{dataset_id}/summary", "get")' in python_sdk_live
    assert '("/v1/data/{dataset_id}/refresh", "post")' in python_sdk_live
    assert '("/v1/data/{dataset_id}", "delete")' in python_sdk_live
    assert '("/v1/team/invite", "post")' in python_sdk_live
    assert '("/v1/api-keys", "post")' in python_sdk_live
    assert '("/v1/credits/refresh", "post")' in python_sdk_live
    assert "Sync client account/API-key surface" in python_sdk_live
    assert "preview_test_connector(" in python_sdk_live
    assert "preview_browse_connector(" in python_sdk_live
    assert "Sync client saved connector + dataset lifecycle" in python_sdk_live
    assert "Sync client team/credits/metering/audit/execution-policy helpers" in python_sdk_live
    assert "Sync client deployment create/delete lifecycle" in python_sdk_live
    assert "_assert_model_catalog_provider_metadata(models)" in python_sdk_live
    assert "resolved_chat_routing_targets" in python_sdk_live
    assert "routing_fallback_on" in python_sdk_live
    assert "routing_max_attempts" in python_sdk_live
    assert "timeout_seconds" in python_sdk_live
    assert "provider_auth_configured" in python_sdk_live
    assert "chat_provider_auth_configured" in python_sdk_live
    assert "embedding_provider_auth_configured" in python_sdk_live
    assert "_assert_empty_provider_trace(response, output_items=True)" in python_sdk_live
    assert "_assert_empty_provider_trace(embedded)" in python_sdk_live
    assert "AsyncClient account/API-key surface" in python_sdk_live
    assert "AsyncClient saved connector + dataset lifecycle" in python_sdk_live
    assert "AsyncClient team/credits/metering/audit/execution-policy helpers" in python_sdk_live
    assert "AsyncClient deployment create/delete lifecycle" in python_sdk_live
    assert "await client.chat_completions(" in python_sdk_live
    assert "await client.responses(" in python_sdk_live
    assert "write_live_integration_summary(" in python_sdk_live
    assert "Summary artifact:" in python_sdk_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in python_sdk_live
    assert '_emit(f"  ... {name}")' in python_sdk_live
    assert "resolve_local_live_base_url" not in python_sdk_live

    assert (
        "python3 tests/integration/test_typescript_sdk_client_live.py" in typescript_sdk_live
    )
    assert (
        "PYTHONPATH=. python3 tests/integration/test_typescript_sdk_client_live.py"
        not in typescript_sdk_live
    )
    assert "ROOT = Path(__file__).resolve().parents[2]" in typescript_sdk_live
    assert "node" in typescript_sdk_live
    assert 'SUITE_NAME = "typescript_sdk_client_live"' in typescript_sdk_live
    assert "PlatformContractResponse.model_validate(contract)" in typescript_sdk_live
    assert "from tests._manifest_backed_integrations import (" in typescript_sdk_live
    assert "contract_integrations_match_manifest" in typescript_sdk_live
    assert 'if not contract_integrations_match_manifest(contract["integrations"]):' in (
        typescript_sdk_live
    )
    assert "RuntimeAdminBenchmarksResponse.model_validate(" in typescript_sdk_live
    assert "write_live_integration_summary(" in typescript_sdk_live
    assert "Summary artifact:" in typescript_sdk_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in typescript_sdk_live
    assert '_emit(f"  ... {name}")' in typescript_sdk_live
    assert '_emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")' in (
        typescript_sdk_live
    )
    assert "resolve_local_live_base_url" not in typescript_sdk_live
    assert "test_client_decision_runtime_surface" in typescript_sdk_live
    assert "test_client_account_surface" in typescript_sdk_live
    assert "test_client_dataset_surface" in typescript_sdk_live
    assert "test_client_control_plane_surface" in typescript_sdk_live
    assert "test_client_deployment_lifecycle_surface" in typescript_sdk_live
    assert 'case \'decision\':' in typescript_sdk_live
    assert "case 'account':" in typescript_sdk_live
    assert "case 'datasets':" in typescript_sdk_live
    assert "case 'control_plane':" in typescript_sdk_live
    assert "case 'deployment_lifecycle':" in typescript_sdk_live
    assert '("/v1/me", "get")' in typescript_sdk_live
    assert '("/v1/me", "patch")' in typescript_sdk_live
    assert '("/v1/connectors", "get")' in typescript_sdk_live
    assert '("/v1/connectors", "post")' in typescript_sdk_live
    assert '("/v1/connectors/test", "post")' in typescript_sdk_live
    assert '("/v1/connectors/browse", "post")' in typescript_sdk_live
    assert '("/v1/connectors/{connector_id}", "get")' in typescript_sdk_live
    assert '("/v1/connectors/{connector_id}", "patch")' in typescript_sdk_live
    assert '("/v1/connectors/{connector_id}/test", "post")' in typescript_sdk_live
    assert '("/v1/connectors/{connector_id}/browse", "get")' in typescript_sdk_live
    assert '("/v1/connectors/{connector_id}", "delete")' in typescript_sdk_live
    assert '("/v1/data/connect", "post")' in typescript_sdk_live
    assert '("/v1/data", "get")' in typescript_sdk_live
    assert '("/v1/data/{dataset_id}", "get")' in typescript_sdk_live
    assert '("/v1/data/{dataset_id}/summary", "get")' in typescript_sdk_live
    assert '("/v1/data/{dataset_id}/refresh", "post")' in typescript_sdk_live
    assert '("/v1/data/{dataset_id}", "delete")' in typescript_sdk_live
    assert '("/v1/billing/info", "get")' in typescript_sdk_live
    assert "previewTestConnector" in typescript_sdk_live
    assert "previewBrowseConnector" in typescript_sdk_live
    assert '("/v1/distributions", "get")' in typescript_sdk_live
    assert '("/v1/templates", "get")' in typescript_sdk_live
    assert '("/v1/webhooks/test", "post")' in typescript_sdk_live
    assert '("/v1/credits/refresh", "post")' in typescript_sdk_live
    assert '("/v1/execution/policy/snapshots", "get")' in typescript_sdk_live
    assert '("/v1/team", "get")' in typescript_sdk_live
    assert '("/v1/team/invite", "post")' in typescript_sdk_live
    assert '"resolved_chat_routing_targets"' in typescript_sdk_live
    assert '"routing_fallback_on"' in typescript_sdk_live
    assert '"routing_max_attempts"' in typescript_sdk_live
    assert '"timeout_seconds"' in typescript_sdk_live
    assert '"provider_auth_env_vars"' in typescript_sdk_live
    assert '"provider_auth_configured"' in typescript_sdk_live
    assert '"chat_provider_auth_configured"' in typescript_sdk_live
    assert '"embedding_provider_auth_configured"' in typescript_sdk_live
    assert '"provider_attempts"' in typescript_sdk_live

    assert "test_client_control_plane_surface" in algenta_client_live
    assert "test_client_saved_connector_surface" in algenta_client_live
    assert "test_client_dataset_surface" in algenta_client_live
    assert "test_client_deployment_lifecycle_surface" in algenta_client_live
    assert (
        "from tests._manifest_backed_integrations import (\n"
        "    contract_integrations_match_manifest,\n"
        ")"
    ) in algenta_client_live
    assert 'if not contract_integrations_match_manifest(contract["integrations"]):' in (
        algenta_client_live
    )
    assert "assert contract_integrations_match_manifest(contract.integrations)" in (
        algenta_client_live
    )
    assert "get_billing_info" in algenta_client_live
    assert '("/v1/connectors", "get")' in algenta_client_live
    assert '("/v1/connectors", "post")' in algenta_client_live
    assert '("/v1/connectors/test", "post")' in algenta_client_live
    assert '("/v1/connectors/browse", "post")' in algenta_client_live
    assert '("/v1/connectors/{connector_id}", "get")' in algenta_client_live
    assert '("/v1/connectors/{connector_id}", "patch")' in algenta_client_live
    assert '("/v1/connectors/{connector_id}/test", "post")' in algenta_client_live
    assert '("/v1/connectors/{connector_id}/browse", "get")' in algenta_client_live
    assert '("/v1/connectors/{connector_id}", "delete")' in algenta_client_live
    assert '("/v1/data/connect", "post")' in algenta_client_live
    assert '("/v1/data", "get")' in algenta_client_live
    assert '("/v1/data/{dataset_id}", "get")' in algenta_client_live
    assert '("/v1/data/{dataset_id}/summary", "get")' in algenta_client_live
    assert "preview_test_connector(" in algenta_client_live
    assert "preview_browse_connector(" in algenta_client_live
    assert '("/v1/data/{dataset_id}/refresh", "post")' in algenta_client_live
    assert '("/v1/data/{dataset_id}", "delete")' in algenta_client_live
    assert '("/v1/distributions", "get")' in algenta_client_live
    assert '("/v1/templates", "get")' in algenta_client_live
    assert '("/v1/webhooks/test", "post")' in algenta_client_live
    assert '("/v1/credits/refresh", "post")' in algenta_client_live
    assert '("/v1/execution/policy/snapshots", "get")' in algenta_client_live
    assert '("/v1/team", "get")' in algenta_client_live
    assert '("/v1/me", "patch")' in algenta_client_live
    assert '("/v1/team/invite", "post")' in algenta_client_live
    assert "_assert_model_catalog_provider_metadata(models)" in algenta_client_live
    assert "resolved_chat_routing_targets" in algenta_client_live
    assert "routing_fallback_on" in algenta_client_live
    assert "routing_max_attempts" in algenta_client_live
    assert "timeout_seconds" in algenta_client_live
    assert "provider_auth_configured" in algenta_client_live
    assert "chat_provider_auth_configured" in algenta_client_live
    assert "embedding_provider_auth_configured" in algenta_client_live
    assert "_assert_empty_provider_trace(response, output_items=True)" in algenta_client_live

    assert "run_api_runtime_control_plane_surface" in algenta_runtime_live
    assert "run_api_runtime_dataset_surface" in algenta_runtime_live
    assert "run_api_runtime_deployment_lifecycle_surface" in algenta_runtime_live
    assert "PlatformContractResponse.model_validate(contract)" in algenta_runtime_live
    assert "from tests._manifest_backed_integrations import (" in algenta_runtime_live
    assert "contract_integrations_match_manifest" in algenta_runtime_live
    assert 'if not contract_integrations_match_manifest(contract["integrations"]):' in (
        algenta_runtime_live
    )
    assert "RuntimeAdminBenchmarksResponse.model_validate(" in algenta_runtime_live
    assert '("/v1/meta/contract", "get")' in algenta_runtime_live
    assert '("/v1/admin/runtime/benchmarks", "get")' in algenta_runtime_live
    assert '("/v1/models", "get")' in algenta_runtime_live
    assert '("/v1/connectors", "get")' in algenta_runtime_live
    assert '("/v1/connectors", "post")' in algenta_runtime_live
    assert '("/v1/connectors/test", "post")' in algenta_runtime_live
    assert '("/v1/connectors/browse", "post")' in algenta_runtime_live
    assert '("/v1/connectors/{connector_id}", "get")' in algenta_runtime_live
    assert '("/v1/connectors/{connector_id}", "patch")' in algenta_runtime_live
    assert '("/v1/connectors/{connector_id}/test", "post")' in algenta_runtime_live
    assert '("/v1/connectors/{connector_id}/browse", "get")' in algenta_runtime_live
    assert '("/v1/connectors/{connector_id}", "delete")' in algenta_runtime_live
    assert '("/v1/data/connect", "post")' in algenta_runtime_live
    assert '("/v1/data", "get")' in algenta_runtime_live
    assert '("/v1/data/{dataset_id}", "get")' in algenta_runtime_live
    assert '("/v1/data/{dataset_id}/summary", "get")' in algenta_runtime_live
    assert '("/v1/data/{dataset_id}/refresh", "post")' in algenta_runtime_live
    assert '("/v1/data/{dataset_id}", "delete")' in algenta_runtime_live
    assert '("/v1/distributions", "get")' in algenta_runtime_live
    assert '("/v1/templates", "get")' in algenta_runtime_live
    assert '("/v1/webhooks/test", "post")' in algenta_runtime_live
    assert "_assert_model_catalog_provider_metadata(models)" in algenta_runtime_live
    assert "resolved_chat_routing_targets" in algenta_runtime_live
    assert "routing_fallback_on" in algenta_runtime_live
    assert "routing_max_attempts" in algenta_runtime_live
    assert "timeout_seconds" in algenta_runtime_live
    assert "provider_auth_configured" in algenta_runtime_live
    assert "chat_provider_auth_configured" in algenta_runtime_live
    assert "embedding_provider_auth_configured" in algenta_runtime_live
    assert "_assert_empty_provider_trace(response, output_items=True)" in algenta_runtime_live
    assert '("/v1/credits/refresh", "post")' in algenta_runtime_live
    assert '("/v1/execution/policy/snapshots", "get")' in algenta_runtime_live
    assert '("/v1/me", "patch")' in algenta_runtime_live
    assert "get_billing_info" in algenta_runtime_live
    assert "preview_tested_connector = runtime.test_connector(" in algenta_runtime_live
    assert "preview_browsed_connector = runtime.browse_connector(" in algenta_runtime_live
    assert "API Runtime connectors + dataset lifecycle surface" in algenta_runtime_live
    assert '("/v1/team", "get")' in algenta_runtime_live
    assert '("/v1/team/invite", "post")' in algenta_runtime_live
    assert "from tests._manifest_backed_integrations import (" in typescript_runtime_live
    assert "contract_integrations_match_manifest" in typescript_runtime_live
    assert 'if not contract_integrations_match_manifest(contract["integrations"]):' in (
        typescript_runtime_live
    )
    assert "resolve_local_live_base_url" not in typescript_runtime_live
    assert 'case "datasets":' in typescript_runtime_live
    assert "run_typescript_runtime_dataset_surface" in typescript_runtime_live
    assert '("/v1/connectors", "get")' in typescript_runtime_live
    assert '("/v1/connectors", "post")' in typescript_runtime_live
    assert '("/v1/connectors/test", "post")' in typescript_runtime_live
    assert '("/v1/connectors/browse", "post")' in typescript_runtime_live
    assert '("/v1/connectors/{connector_id}", "get")' in typescript_runtime_live
    assert '("/v1/connectors/{connector_id}", "patch")' in typescript_runtime_live
    assert '("/v1/connectors/{connector_id}/test", "post")' in typescript_runtime_live
    assert '("/v1/connectors/{connector_id}/browse", "get")' in typescript_runtime_live
    assert '("/v1/connectors/{connector_id}", "delete")' in typescript_runtime_live
    assert '("/v1/data/connect", "post")' in typescript_runtime_live
    assert '("/v1/data", "get")' in typescript_runtime_live
    assert '("/v1/data/{dataset_id}", "get")' in typescript_runtime_live
    assert '("/v1/data/{dataset_id}/summary", "get")' in typescript_runtime_live
    assert '("/v1/data/{dataset_id}/refresh", "post")' in typescript_runtime_live
    assert '("/v1/data/{dataset_id}", "delete")' in typescript_runtime_live
    assert "TypeScript Runtime(mode='api') connectors + dataset lifecycle helpers" in (
        typescript_runtime_live
    )
    assert "previewTestedConnector = await runtime.testConnector({" in typescript_runtime_live
    assert "previewBrowsedConnector = await runtime.browseConnector({" in typescript_runtime_live
    assert '"routing_fallback_on"' in typescript_runtime_live
    assert '"routing_max_attempts"' in typescript_runtime_live
    assert '"timeout_seconds"' in typescript_runtime_live
    assert '"provider_attempts"' in typescript_runtime_live
    assert '("/v1/usage", "get")' in typescript_sdk_live
    assert '("/v1/limits", "get")' in typescript_sdk_live
    assert '("/v1/api-keys", "post")' in typescript_sdk_live
    assert '("/v1/recommend", "post")' in typescript_sdk_live
    assert '("/v1/score", "post")' in typescript_sdk_live
    assert '("/v1/batch", "post")' in typescript_sdk_live
    assert '("/v1/compare", "post")' in typescript_sdk_live

    assert 'SUITE_NAME = "local_runtime_real"' in local_runtime_real
    assert "write_live_integration_summary(" in local_runtime_real
    assert "Summary artifact:" in local_runtime_real
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in local_runtime_real
    assert '_emit(f"  ... {name}")' in local_runtime_real

    assert "python3 tests/integration/test_cli.py" in cli_live
    assert "PYTHONPATH=. python3 tests/integration/test_cli.py" not in cli_live
    assert 'SUITE_NAME = "cli_integration"' in cli_live
    assert "write_live_integration_summary(" in cli_live
    assert "Summary artifact:" in cli_live
    assert '_emit(f"  ... {name}")' in cli_live
    assert "PlatformContractResponse.model_validate(contract)" in cli_live
    assert "from tests._manifest_backed_integrations import (" in cli_live
    assert "contract_integrations_match_manifest" in cli_live
    assert 'if not contract_integrations_match_manifest(contract["integrations"]):' in (
        cli_live
    )
    assert "resolve_local_live_base_url" not in cli_live
    assert "test_cli_team_surface" in cli_live
    assert "test_cli_webhook_test_surface" in cli_live
    assert "test_cli_audit_logs_surface" in cli_live
    assert "test_cli_execution_policy_surface" in cli_live
    assert "test_cli_data_surface" in cli_live
    assert "test_cli_connector_surface" in cli_live
    assert "test_cli_credit_refresh_surface" in cli_live
    assert '("/v1/connectors", "post")' in cli_live
    assert '("/v1/connectors/test", "post")' in cli_live
    assert '("/v1/connectors/browse", "post")' in cli_live
    assert '("/v1/connectors/{connector_id}", "get")' in cli_live
    assert '("/v1/connectors/{connector_id}", "patch")' in cli_live
    assert '("/v1/connectors/{connector_id}/test", "post")' in cli_live
    assert '("/v1/connectors/{connector_id}/browse", "get")' in cli_live
    assert '("/v1/connectors/{connector_id}", "delete")' in cli_live
    assert '("/v1/data/connect", "post")' in cli_live
    assert '("/v1/data", "get")' in cli_live
    assert '("/v1/data/{dataset_id}/refresh", "post")' in cli_live
    assert '("/v1/data/{dataset_id}/summary", "get")' in cli_live
    assert '("/v1/data/{dataset_id}", "get")' in cli_live
    assert '("/v1/data/{dataset_id}", "delete")' in cli_live
    assert 'run_cli("connectors", "preview-test"' in cli_live
    assert 'run_cli("connectors", "preview-browse"' in cli_live
    assert '("/v1/execution/policy/snapshots", "get")' in cli_live
    assert '("/v1/credits/refresh", "post")' in cli_live
    assert "billing" in cli_live
    assert '("/v1/team", "get")' in cli_live
    assert '("/v1/me", "patch")' in cli_live
    assert '("/v1/distributions", "get")' in cli_live
    assert '("/v1/templates", "get")' in cli_live
    assert '("/v1/team/invite", "post")' in cli_live
    assert '("/v1/billing/info", "get")' in cli_live
    assert '("/v1/webhooks/test", "post")' in cli_live
    assert '("/v1/audit-logs", "get")' in cli_live
    assert '("/v1/audit-logs/artifacts", "get")' in cli_live
    assert '("/v1/agent/runs", "get")' in cli_live
    assert '("/v1/agent/runs/{run_id}/checkpoints", "get")' in cli_live
    assert '("/v1/agent/runs/checkpoints", "get")' in cli_live
    assert '("/v1/agent/runs/{run_id}/mission-events", "get")' in cli_live
    assert '("/v1/agent/runs/mission-events", "get")' in cli_live
    assert '("/v1/agent/runs/{run_id}/telemetry", "get")' in cli_live
    assert '("/v1/agent/runs/telemetry", "get")' in cli_live
    assert '("/v1/execution/policy", "patch")' in cli_live
    assert "test_cli_deployment_surface" in cli_live
    assert '("/v1/deployments/regions", "get")' in cli_live
    assert '("/v1/deployments/{deployment_id}/cost", "get")' in cli_live
    assert 'response_events[-1]["response"]["provider_attempts"] == []' in cli_live
    assert 'chat_data["provider_attempts"] == []' in cli_live
    assert 'tokenizer["chat_required_provider_headers"] == []' in cli_live
    assert 'tokenizer["embedding_required_provider_headers"] == []' in cli_live
    assert 'tokenizer["chat_provider_auth_env_vars"] == []' in cli_live
    assert 'tokenizer["embedding_provider_auth_env_vars"] == []' in cli_live
    assert 'tokenizer["chat_provider_auth_configured"] is False' in cli_live
    assert 'tokenizer["embedding_provider_auth_configured"] is False' in cli_live

    assert "python3 tests/integration/test_services.py" in services_live
    assert "PYTHONPATH=. python tests/integration/test_services.py" not in services_live
    assert "ROOT = Path(__file__).resolve().parents[2]" in services_live
    assert "sys.path.insert(0, str(ROOT))" in services_live
    assert 'SUITE_NAME = "services_integration"' in services_live
    assert "write_live_integration_summary(" in services_live
    assert "Summary artifact:" in services_live
    assert '_emit(f"  ... {name}")' in services_live


def test_repository_intelligence_live_scripts_cover_public_surfaces() -> None:
    repository_fixture = (
        ROOT / "tests" / "integration" / "live_repository_fixture.py"
    ).read_text(encoding="utf-8")
    python_sdk_live = (ROOT / "tests" / "integration" / "test_python_sdk.py").read_text(
        encoding="utf-8"
    )
    algenta_client_live = (
        ROOT / "tests" / "integration" / "test_algenta_client_live.py"
    ).read_text(encoding="utf-8")
    algenta_runtime_live = (
        ROOT / "tests" / "integration" / "test_algenta_runtime_live.py"
    ).read_text(encoding="utf-8")
    cli_live = (ROOT / "tests" / "integration" / "test_cli.py").read_text(encoding="utf-8")
    mcp_server_live = (
        ROOT / "tests" / "integration" / "test_mcp_server.py"
    ).read_text(encoding="utf-8")
    typescript_sdk_live = (
        ROOT / "tests" / "integration" / "test_typescript_sdk_client_live.py"
    ).read_text(encoding="utf-8")
    typescript_runtime_live = (
        ROOT / "tests" / "integration" / "test_typescript_runtime_live.py"
    ).read_text(encoding="utf-8")

    assert "class LiveRepositoryFixture:" in repository_fixture
    assert "def local_repository_live_support_reason(base_url: str) -> str | None:" in (
        repository_fixture
    )
    assert "connector_type\": \"local_repo\"" in repository_fixture
    assert "decision_plan_id" in repository_fixture
    assert "mode\": \"patch_only\"" in repository_fixture
    assert "def apply_local_branch_request(" in repository_fixture
    assert "mode\": \"local_branch\"" in repository_fixture
    assert "\"write_permission\": True" in repository_fixture
    assert "def assert_local_branch_applied(" in repository_fixture

    assert "test_sync_repository_surface" in python_sdk_live
    assert "test_async_repository_surface" in python_sdk_live
    assert 'check("Sync client repository intelligence surface → typed live results"' in (
        python_sdk_live
    )
    assert 'check("AsyncClient repository intelligence surface → typed live results"' in (
        python_sdk_live
    )
    assert '("/v1/repositories/{repository_id}/decision-plans", "post")' in python_sdk_live
    assert "local_repository_live_support_reason(BASE_URL)" in python_sdk_live
    assert "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL" in python_sdk_live
    assert 'repository_analysis.planner_model_id == "repository.deterministic_local_v1"' in (
        python_sdk_live
    )
    assert 'repository_analysis.planner_execution_mode == "deterministic_local"' in (
        python_sdk_live
    )
    assert "repository_analysis.planner_provider_backend is None" in python_sdk_live

    assert "test_client_repository_surface" in algenta_client_live
    assert 'check("AlgentaClient repository intelligence surface"' in algenta_client_live
    assert '("/v1/repositories/{repository_id}/decision-plans", "post")' in algenta_client_live
    assert "local_repository_live_support_reason(BASE_URL)" in algenta_client_live
    assert "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL" in algenta_client_live
    assert '_value(repository_analysis, "planner_model_id") == "repository.deterministic_local_v1"' in (
        algenta_client_live
    )
    assert '_value(repository_analysis, "planner_execution_mode") == "deterministic_local"' in (
        algenta_client_live
    )
    assert '_value(repository_analysis, "planner_provider_backend") is None' in (
        algenta_client_live
    )

    assert "run_api_runtime_repository_surface" in algenta_runtime_live
    assert 'check("API Runtime repository intelligence surface"' in algenta_runtime_live
    assert '("/v1/repositories/{repository_id}/decision-plans", "post")' in algenta_runtime_live
    assert "local_repository_live_support_reason(BASE_URL)" in algenta_runtime_live
    assert "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL" in algenta_runtime_live
    assert 'planner_model_id == "repository.deterministic_local_v1"' in algenta_runtime_live
    assert 'planner_execution_mode == "deterministic_local"' in algenta_runtime_live
    assert "planner_provider_backend is None" in algenta_runtime_live

    assert "test_cli_repository_surface" in cli_live
    assert (
        '"CLI repository intelligence surface → snapshot/triage/graph/plan/simulate/apply"'
        in cli_live
    )
    assert '"decision-plan"' in cli_live
    assert '("/v1/repositories/{repository_id}/decision-plans", "post")' in cli_live
    assert "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL" in cli_live
    assert 'repository_analysis["planner_model_id"] == "repository.deterministic_local_v1"' in (
        cli_live
    )
    assert 'repository_analysis["planner_execution_mode"] == "deterministic_local"' in cli_live
    assert 'repository_analysis["planner_provider_backend"] is None' in cli_live

    assert "test_tool_repository_intelligence_lifecycle" in mcp_server_live
    assert '"create_repository_snapshot"' in mcp_server_live
    assert '"apply_repository"' in mcp_server_live
    assert "local_repository_live_support_reason(BASE_URL)" in mcp_server_live
    assert "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL" in mcp_server_live
    assert 'repository_analysis["planner_model_id"] == "repository.deterministic_local_v1"' in (
        mcp_server_live
    )
    assert 'repository_analysis["planner_execution_mode"] == "deterministic_local"' in (
        mcp_server_live
    )
    assert 'repository_analysis["planner_provider_backend"] is None' in mcp_server_live

    assert "test_client_repository_surface" in typescript_sdk_live
    assert 'check("TypeScript SDK client repository intelligence surface"' in typescript_sdk_live
    assert "case 'repositories':" in typescript_sdk_live
    assert '("/v1/repositories/{repository_id}/decision-plans", "post")' in (
        typescript_sdk_live
    )
    assert '"DE_LOCAL_REPOSITORY_PATH": repository_path or ""' in typescript_sdk_live
    assert "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL" in typescript_sdk_live
    assert 'repository_analysis["planner_model_id"] == "repository.deterministic_local_v1"' in (
        typescript_sdk_live
    )
    assert 'repository_analysis["planner_execution_mode"] == "deterministic_local"' in (
        typescript_sdk_live
    )
    assert 'repository_analysis["planner_provider_backend"] is None' in typescript_sdk_live

    assert "run_typescript_runtime_repository_surface" in typescript_runtime_live
    assert (
        'check(\n            "TypeScript Runtime(mode=\'api\') repository intelligence helpers",'
        in typescript_runtime_live
    )
    assert 'case "repositories":' in typescript_runtime_live
    assert '("/v1/repositories/{repository_id}/decision-plans", "post")' in (
        typescript_runtime_live
    )
    assert '"DE_LOCAL_REPOSITORY_PATH": repository_path or ""' in typescript_runtime_live
    assert "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL" in typescript_runtime_live
    assert 'repository_analysis["planner_model_id"] == "repository.deterministic_local_v1"' in (
        typescript_runtime_live
    )
    assert 'repository_analysis["planner_execution_mode"] == "deterministic_local"' in (
        typescript_runtime_live
    )
    assert 'repository_analysis["planner_provider_backend"] is None' in (
        typescript_runtime_live
    )


def test_live_integration_artifact_paths_follow_suite_name_summary_suffix() -> None:
    registry_path = ROOT / "tests" / "integration" / "live_integration_artifacts.py"
    spec = importlib.util.spec_from_file_location("live_integration_artifacts", registry_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    artifact_paths = module.LIVE_INTEGRATION_SUMMARY_ARTIFACTS

    assert {
        name: path.name for name, path in artifact_paths.items()
    } == {name: f"{name}_summary.json" for name in artifact_paths}


