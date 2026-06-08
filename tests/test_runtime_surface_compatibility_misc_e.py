"""Tests for test_runtime_surface_compatibility: misc_e.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-4/tests/test_runtime_surface_compatibility.py during modularization.
"""
from __future__ import annotations

from tests._test_runtime_surface_compatibility_helpers import *  # noqa: F401,F403


def test_live_integration_summary_script_registry_matches_suite_names() -> None:
    registry_path = ROOT / "tests" / "integration" / "live_integration_artifacts.py"
    spec = importlib.util.spec_from_file_location("live_integration_artifacts", registry_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    artifact_names = set(module.LIVE_INTEGRATION_SUMMARY_ARTIFACTS)
    script_names = set(module.LIVE_INTEGRATION_SUMMARY_SCRIPTS)

    assert script_names == artifact_names
    assert all(
        script == "tests/integration/test_go_live_connectivity_real.py"
        for name, script in module.LIVE_INTEGRATION_SUMMARY_SCRIPTS.items()
        if name in {"go_live_connectivity_local_only", "go_live_connectivity_real"}
    )
    assert all(
        script.startswith("tests/integration/test_") and script.endswith(".py")
        for script in module.LIVE_INTEGRATION_SUMMARY_SCRIPTS.values()
    )


def test_live_summary_helper_modules_keep_fail_closed_metadata_and_parser_guards() -> None:
    integration_helper = (ROOT / "tests" / "integration" / "live_integration_artifacts.py").read_text(
        encoding="utf-8"
    )
    rollout_helper = (ROOT / "benchmarks" / "llm_rollout_live_artifacts.py").read_text(
        encoding="utf-8"
    )

    assert 'if not isinstance(payload, dict):' in integration_helper
    assert 'if not isinstance(payload, dict):' in rollout_helper
    assert 'raise ValueError(f"{path} must contain a JSON object")' in integration_helper
    assert 'raise ValueError(f"{path} must contain a JSON object")' in rollout_helper
    assert 'details must use only string keys' in integration_helper
    assert 'details must not contain tuples' in integration_helper
    assert 'extra must use only string keys' in rollout_helper
    assert 'extra must not contain tuples' in rollout_helper
    assert 'channels must be a list or tuple of channel names' in rollout_helper
    assert 'channels must be a sequence of channel names, not a single string' in rollout_helper
    assert 'must be an integer, not boolean' in integration_helper
    assert 'must be an integer, not boolean' in rollout_helper
    assert 'must be an integer' in integration_helper
    assert 'must be an integer' in rollout_helper
    assert 'generated_at must be a UTC ISO-8601 string ending with Z' in integration_helper
    assert 'generated_at must be a UTC ISO-8601 string ending with Z' in rollout_helper
    assert 'sort_keys=True' in integration_helper
    assert 'sort_keys=True' in rollout_helper
    assert '+ "\\n"' in integration_helper
    assert '+ "\\n"' in rollout_helper


def test_live_runtime_library_scripts_self_bootstrap_repo_imports() -> None:
    http_live = (ROOT / "tests" / "integration" / "test_runtime_libraries_http_live.py").read_text(
        encoding="utf-8"
    )
    python_live = (ROOT / "tests" / "integration" / "test_algenta_mojo_library_live.py").read_text(
        encoding="utf-8"
    )
    cli_mcp_live = (
        ROOT / "tests" / "integration" / "test_cli_mcp_runtime_libraries_live.py"
    ).read_text(encoding="utf-8")

    assert "python3 tests/integration/test_runtime_libraries_http_live.py" in http_live
    assert "PYTHONPATH=. python3 tests/integration/test_runtime_libraries_http_live.py" not in http_live
    assert "ROOT = Path(__file__).resolve().parents[2]" in http_live
    assert "sys.path.insert(0, str(ROOT))" in http_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in http_live
    assert '_emit(f"  ... {name}")' in http_live

    assert "python3 tests/integration/test_algenta_mojo_library_live.py" in python_live
    assert "PYTHONPATH=. python3 tests/integration/test_algenta_mojo_library_live.py" not in python_live
    assert "ROOT = Path(__file__).resolve().parents[2]" in python_live
    assert "sys.path.insert(0, path)" in python_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in python_live
    assert '_emit(f"  ... {name}")' in python_live

    assert "python3 tests/integration/test_cli_mcp_runtime_libraries_live.py" in cli_mcp_live
    assert "PYTHONPATH=. python3 tests/integration/test_cli_mcp_runtime_libraries_live.py" not in cli_mcp_live
    assert "ROOT = Path(__file__).resolve().parents[2]" in cli_mcp_live
    assert "sys.path.insert(0, str(ROOT))" in cli_mcp_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in cli_mcp_live
    assert '_emit(f"  ... {name}")' in cli_mcp_live
    assert "def _resolve_base_url() -> str:" in cli_mcp_live
    assert "def _endpoint_serves_canonical_runtime_contract(base_url: str) -> bool:" in cli_mcp_live
    assert "async def _wait_for_runtime_entitlement_ready(timeout_seconds: float = 10.0)" in cli_mcp_live
    assert "runtime daemon entitlement did not become ready" in cli_mcp_live
    assert '"apps.api_server.main:app"' in cli_mcp_live
    assert "atexit.register(_cleanup_runtime)" in cli_mcp_live


def test_typescript_sdk_package_exports_point_to_real_build_outputs() -> None:
    package_json = (ROOT / "packages" / "ts-sdk" / "package.json").read_text(encoding="utf-8")

    assert '"main": "dist/index.js"' in package_json
    assert '"module": "dist/index.js"' in package_json
    assert '"import": "./dist/index.js"' in package_json


def test_typescript_contract_helper_uses_shared_manifest_fixture() -> None:
    helper = (ROOT / "packages" / "ts-sdk" / "src" / "test_contract_helpers.ts").read_text(
        encoding="utf-8"
    )

    assert "../../../tests/manifest_backed_integrations.fixture.json" in helper
    assert "MANIFEST_BACKED_INTEGRATIONS_FIXTURE_PATH =" not in helper
    assert 'readFileSync(resolve(__dirname, "../../../tests/manifest_backed_integrations.fixture.json"), "utf8")' in (
        helper
    )
    assert "const MANIFEST_BACKED_INTEGRATIONS_EXPORT_PATTERN =" not in helper
    assert "type ManifestBackedIntegration = {" in helper
    assert "description: string;" in helper
    assert "icon: string;" in helper
    assert "capabilities: string[];" in helper
    assert "auth_scheme: string;" in helper
    assert "required_scopes: string[];" in helper
    assert "read_only_default: boolean;" in helper
    assert "admin_controls: string[];" in helper
    assert "privacy_url: string;" in helper
    assert "terms_url: string;" in helper
    assert "support_url: string;" in helper
    assert "regions: string[];" in helper
    assert "status: string;" in helper
    assert "integrations: ManifestBackedIntegration[]" in helper
    assert "): ManifestBackedIntegration[]" in helper
    assert "const MANIFEST_BACKED_INTEGRATION_FIELDS =" not in helper
    assert "function normalizeManifestBackedIntegrationsWithAccessor<T>(" not in helper
    assert "function normalizeManifestBackedIntegrations(" in helper
    assert (
        "const fields = Object.keys(MANIFEST_BACKED_INTEGRATIONS[0]) as Array<keyof ManifestBackedIntegration>;"
        in helper
    )
    assert "function isCanonicalManifestBackedIntegrations(" not in helper
    assert "function normalizeOrReuseManifestBackedIntegrations(" in helper
    assert "return integrations === MANIFEST_BACKED_INTEGRATIONS" in helper
    assert "function expectManifestBackedIntegrationsWithAccessor<T>(" not in helper
    assert "export function expectManifestBackedIntegrations(" not in helper
    assert "export function expectManifestBackedIntegrationsEqual(" in helper
    assert (
        "const normalizedLeftIntegrations = normalizeOrReuseManifestBackedIntegrations(leftIntegrations);"
        in helper
    )
    assert "rightIntegrations === leftIntegrations" in helper
    assert "? normalizedLeftIntegrations" in helper
    assert "const normalizedRightIntegrations =" in helper
    assert ": normalizeOrReuseManifestBackedIntegrations(rightIntegrations);" in helper
    assert "expect(normalizedLeftIntegrations).toEqual(normalizedRightIntegrations);" in helper
    assert "pattern: RegExp = MANIFEST_BACKED_INTEGRATIONS_EXPORT_PATTERN" not in helper
    assert "const leftMatch = leftText.match(" in helper
    assert "/(?:export const INTEGRATIONS =|exports\\.INTEGRATIONS =)\\s*(\\[[\\s\\S]*?\\]);/" in helper
    assert "export function expectManifestBackedIntegrationExportText(" not in helper
    assert "export function expectManifestBackedIntegrationExportTextsEqual(" in helper
    assert "export function parseManifestBackedIntegrationExportText(" not in helper
    assert 'expect(leftMatch?.[1], "missing exported INTEGRATIONS array").toBeDefined();' in helper
    assert "const leftIntegrations = JSON.parse(leftMatch![1]) as ManifestBackedIntegration[];" in helper
    assert "rightText === leftText" in helper
    assert "if (rightText === leftText) {" in helper
    assert "return;" in helper
    assert "const rightMatch = rightText.match(" in helper
    assert 'expect(rightMatch?.[1], "missing exported INTEGRATIONS array").toBeDefined();' in helper
    assert "const rightIntegrations = JSON.parse(rightMatch![1]) as ManifestBackedIntegration[];" in helper
    assert (
        "expectManifestBackedIntegrationsEqual(leftIntegrations, MANIFEST_BACKED_INTEGRATIONS);"
        in helper
    )
    assert "expectManifestBackedIntegrations(rightIntegrations);" not in helper
    assert "expectManifestBackedIntegrationsEqual(leftIntegrations, rightIntegrations);" in helper


def test_typescript_dist_artifact_parity_uses_shared_export_text_equality_helper() -> None:
    parity_test = (
        ROOT / "packages" / "ts-sdk" / "src" / "dist_artifact_parity.test.ts"
    ).read_text(encoding="utf-8")

    assert "expectManifestBackedIntegrationExportTextsEqual," in parity_test
    assert "expectManifestBackedIntegrationsEqual," in parity_test
    assert "expectManifestBackedIntegrationExportTextsEqual(distContractText, sourceContractText);" in (
        parity_test
    )
    assert "expectManifestBackedIntegrationsEqual(" in parity_test
    assert "distContractModule.INTEGRATIONS," in parity_test
    assert "sourceContractModule.INTEGRATIONS," in parity_test
    assert "expectManifestBackedIntegrations(distContractModule.INTEGRATIONS);" not in parity_test
    assert "expectManifestBackedIntegrations(sourceContractModule.INTEGRATIONS);" not in parity_test
    assert "parseManifestBackedIntegrationExportText" not in parity_test


def test_typescript_contract_tests_use_shared_manifest_equality_helper() -> None:
    client_test = (ROOT / "packages" / "ts-sdk" / "src" / "client.test.ts").read_text(
        encoding="utf-8"
    )
    runtime_test = (ROOT / "packages" / "ts-sdk" / "src" / "runtime.test.ts").read_text(
        encoding="utf-8"
    )
    index_test = (ROOT / "packages" / "ts-sdk" / "src" / "index.test.ts").read_text(
        encoding="utf-8"
    )

    assert "expectManifestBackedIntegrationsEqual(contract.integrations, INTEGRATIONS);" in client_test
    assert "expectManifestBackedIntegrations(contract.integrations);" not in client_test
    assert "expectManifestBackedIntegrationsEqual(contract.integrations, INTEGRATIONS);" in runtime_test
    assert "expectManifestBackedIntegrations(contract.integrations);" not in runtime_test
    assert "expectManifestBackedIntegrationsEqual(INTEGRATIONS, INTEGRATIONS);" in index_test
    assert "expectManifestBackedIntegrations(INTEGRATIONS);" not in index_test


def test_python_ts_contract_artifact_proofs_use_shared_export_text_equality_helper() -> None:
    generation_test = (ROOT / "tests" / "test_platform_contract_generation.py").read_text(
        encoding="utf-8"
    )
    distribution_test = (ROOT / "tests" / "test_package_distribution_surface.py").read_text(
        encoding="utf-8"
    )

    assert "assert_manifest_backed_integration_texts_equal," in generation_test
    assert "assert_manifest_backed_integration_texts_equal(ts_dist_contract, ts_contract)" in (
        generation_test
    )
    assert "assert_manifest_backed_integration_text," not in generation_test
    assert "parse_manifest_backed_integration_text" not in generation_test
    assert "export const INTEGRATIONS =" not in generation_test
    assert "exports.INTEGRATIONS =" not in generation_test
    assert "assert_manifest_backed_integration_texts_equal," in distribution_test
    assert "assert_manifest_backed_integration_texts_equal(contract_text, source_contract_text)" in (
        distribution_test
    )
    assert "assert_manifest_backed_integration_text," not in distribution_test
    assert "parse_manifest_backed_integration_text" not in distribution_test
    assert "export const INTEGRATIONS =" not in distribution_test
    assert "exports.INTEGRATIONS =" not in distribution_test


def test_manifest_helper_test_files_pin_strict_vs_parity_semantics() -> None:
    python_helper_tests = (ROOT / "tests" / "test_platform_contract.py").read_text(
        encoding="utf-8"
    )
    typescript_helper_tests = (
        ROOT / "packages" / "ts-sdk" / "src" / "test_contract_helpers.test.ts"
    ).read_text(encoding="utf-8")

    assert "test_assert_manifest_backed_integrations_equal_accepts_matching_drifted_payloads" in (
        python_helper_tests
    )
    assert "test_contract_integrations_match_manifest_fails_closed_for_empty_sequences" in (
        python_helper_tests
    )
    assert "test_contract_integrations_match_manifest_fails_closed_for_malformed_input" in (
        python_helper_tests
    )
    assert "test_contract_integrations_match_manifest_accepts_attribute_backed_fixture_payload" in (
        python_helper_tests
    )
    assert "test_contract_integrations_match_manifest_fails_closed_for_drifted_payload" in (
        python_helper_tests
    )
    assert "test_normalize_manifest_backed_integrations_supports_attribute_backed_sequences" in (
        python_helper_tests
    )
    assert "test_normalize_manifest_backed_integrations_rejects_empty_sequences" in (
        python_helper_tests
    )
    assert "test_assert_manifest_backed_integrations_rejects_drifted_payload" in (
        python_helper_tests
    )
    assert "test_assert_manifest_backed_integrations_equal_rejects_drifted_payloads" in (
        python_helper_tests
    )
    assert "test_manifest_export_text_helper_rejects_missing_integration_export" in (
        python_helper_tests
    )
    assert "test_manifest_export_text_helper_rejects_missing_left_hand_integration_export" in (
        python_helper_tests
    )
    assert "test_manifest_export_text_helper_accepts_matching_esm_and_commonjs_exports" in (
        python_helper_tests
    )
    assert "test_manifest_export_text_helper_accepts_identical_export_texts" in (
        python_helper_tests
    )
    assert "test_manifest_export_text_helper_rejects_identical_drifted_export_texts" in (
        python_helper_tests
    )
    assert "test_manifest_export_text_helper_rejects_mismatched_integration_payloads" in (
        python_helper_tests
    )
    assert "test_manifest_export_text_helper_rejects_matching_drifted_payloads" in (
        python_helper_tests
    )
    assert "assert contract_integrations_match_manifest([object()]) is False" in python_helper_tests
    assert "assert contract_integrations_match_manifest([]) is False" in python_helper_tests
    assert "assert contract_integrations_match_manifest(integrations) is True" in python_helper_tests
    assert "assert contract_integrations_match_manifest(drifted_integrations) is False" in (
        python_helper_tests
    )
    assert (
        "with pytest.raises(AssertionError, match=\"expected manifest-backed integrations\"):\n"
        "        manifest_helpers.normalize_manifest_backed_integrations([])"
        in python_helper_tests
    )
    assert "assert manifest_helpers.normalize_manifest_backed_integrations(integrations) == (" in (
        python_helper_tests
    )
    assert "with pytest.raises(AssertionError):\n        assert_manifest_backed_integrations(drifted_integrations)" in (
        python_helper_tests
    )
    assert (
        "manifest_helpers.assert_manifest_backed_integrations_equal(\n"
        "        left_drifted_integrations,\n"
        "        right_drifted_integrations,\n"
        "    )"
        in python_helper_tests
    )
    assert (
        "manifest_helpers.assert_manifest_backed_integrations_equal(\n"
        "            list(MANIFEST_BACKED_INTEGRATIONS),\n"
        "            drifted_integrations,\n"
        "        )"
        in python_helper_tests
    )
    assert "with pytest.raises(AssertionError):\n        assert_manifest_backed_integration_texts_equal(" in (
        python_helper_tests
    )
    assert (
        "with pytest.raises(AssertionError, match=\"missing exported INTEGRATIONS array\"):\n"
        "        assert_manifest_backed_integration_texts_equal(\n"
        "            f\"export const INTEGRATIONS = {payload};\",\n"
        "            \"export const CONTRACT_VERSION = '2026.05.0';\",\n"
        "        )"
        in python_helper_tests
    )
    assert (
        "with pytest.raises(AssertionError, match=\"missing exported INTEGRATIONS array\"):\n"
        "        assert_manifest_backed_integration_texts_equal(\n"
            "            \"export const CONTRACT_VERSION = '2026.05.0';\",\n"
            "            f\"exports.INTEGRATIONS = {payload};\",\n"
        "        )"
        in python_helper_tests
    )
    assert "assert_manifest_backed_integration_texts_equal(esm_text, cjs_text)" in python_helper_tests
    assert "assert_manifest_backed_integration_texts_equal(text, text)" in python_helper_tests
    assert "with pytest.raises(AssertionError):\n        assert_manifest_backed_integration_texts_equal(text, text)" in (
        python_helper_tests
    )
    assert "f\"exports.INTEGRATIONS = {right_payload};\"" in python_helper_tests
    assert "fails closed when a copied integration payload drifts from the manifest" in (
        typescript_helper_tests
    )
    assert "normalizes copied manifest-backed integrations before comparing" in (
        typescript_helper_tests
    )
    assert "accepts matching drifted integration payloads in the two-sided parity helper" in (
        typescript_helper_tests
    )
    assert (
        "rejects matching drifted integration export payloads because the left-hand export must stay canonical"
        in typescript_helper_tests
    )
    assert "fails closed when the left-hand integration payload is empty" in typescript_helper_tests
    assert "fails closed when the right-hand integration payload is empty" in (
        typescript_helper_tests
    )
    assert "fails closed when an integration export is missing" in typescript_helper_tests
    assert "fails closed when the left-hand integration export is missing" in (
        typescript_helper_tests
    )
    assert "accepts matching ESM and CommonJS integration exports" in typescript_helper_tests
    assert "accepts identical integration export texts" in typescript_helper_tests
    assert (
        "rejects identical drifted integration export texts because the left-hand export must stay canonical"
        in typescript_helper_tests
    )
    assert "fails closed when an integration export payload drifts from the manifest" in (
        typescript_helper_tests
    )
    assert "expectManifestBackedIntegrationsEqual(cloneManifestBackedIntegrations(), INTEGRATIONS);" in (
        typescript_helper_tests
    )
    assert "expectManifestBackedIntegrationExportTextsEqual(" in typescript_helper_tests
    assert "`export const INTEGRATIONS = ${payload};`" in typescript_helper_tests
    assert "`exports.INTEGRATIONS = ${payload};`" in typescript_helper_tests
    assert "expectManifestBackedIntegrationExportTextsEqual(text, text);" in typescript_helper_tests
    assert "expect(() => expectManifestBackedIntegrationExportTextsEqual(text, text)).toThrowError();" in (
        typescript_helper_tests
    )
    assert "expectManifestBackedIntegrationsEqual(leftDriftedIntegrations, rightDriftedIntegrations);" in (
        typescript_helper_tests
    )
    assert "expect(() =>\n      expectManifestBackedIntegrationsEqual(mismatchedIntegrations, INTEGRATIONS)," in (
        typescript_helper_tests
    )
    assert "expect(() => expectManifestBackedIntegrationsEqual([], INTEGRATIONS)).toThrowError();" in (
        typescript_helper_tests
    )
    assert "expect(() => expectManifestBackedIntegrationsEqual(INTEGRATIONS, [])).toThrowError();" in (
        typescript_helper_tests
    )
    assert "expect(() =>\n      expectManifestBackedIntegrationExportTextsEqual(" in (
        typescript_helper_tests
    )
    assert ").toThrowError(\"missing exported INTEGRATIONS array\");" in typescript_helper_tests
    assert "expectManifestBackedIntegrationExportTextsEqual(" in typescript_helper_tests
    assert "`exports.INTEGRATIONS = ${JSON.stringify(mismatchedIntegrations)};`" in (
        typescript_helper_tests
    )


def test_outward_facing_contract_proofs_use_shared_normalized_manifest_fixture() -> None:
    meta_contract_api = (ROOT / "tests" / "test_meta_contract_api.py").read_text(
        encoding="utf-8"
    )
    mcp_data_tools = (ROOT / "tests" / "test_mcp_data_tools.py").read_text(encoding="utf-8")
    runtime_startup = (ROOT / "tests" / "test_runtime_startup_smoke.py").read_text(
        encoding="utf-8"
    )
    # tests/test_cli_data.py was split into 9 per-command-family sub-files.
    # Concat all of them so textual surface checks cover the same content.
    cli_data = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((ROOT / "tests").glob("test_cli_data_*.py"))
    )
    mcp_meta_tools = (ROOT / "tests" / "test_mcp_meta_tools.py").read_text(encoding="utf-8")
    query_surface = (ROOT / "tests" / "test_decision_engine_query_surface.py").read_text(
        encoding="utf-8"
    )
    algenta_runtime = (ROOT / "tests" / "test_algenta_runtime.py").read_text(encoding="utf-8")
    platform_contract = (ROOT / "tests" / "test_platform_contract.py").read_text(
        encoding="utf-8"
    )
    decision_engine_client_wrapper = (
        ROOT / "tests" / "test_decision_engine_client_wrapper.py"
    ).read_text(encoding="utf-8")
    decision_engine_lazy_exports = (
        ROOT / "tests" / "test_decision_engine_lazy_exports.py"
    ).read_text(encoding="utf-8")
    algenta_lazy_exports = (ROOT / "tests" / "test_algenta_lazy_exports.py").read_text(
        encoding="utf-8"
    )
    distribution_artifact = (
        ROOT / "tests" / "test_distribution_artifact_privacy_runtime.py"
    ).read_text(encoding="utf-8")
    platform_contract_generation = (
        ROOT / "tests" / "test_platform_contract_generation.py"
    ).read_text(encoding="utf-8")

    assert "assert_manifest_backed_integrations," in meta_contract_api
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," not in meta_contract_api
    assert "assert_manifest_backed_integrations_equal(" not in meta_contract_api
    assert "assert_manifest_backed_integrations," in mcp_data_tools
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," not in mcp_data_tools
    assert "assert_manifest_backed_integrations_equal(" not in mcp_data_tools
    assert "assert_manifest_backed_integrations," in runtime_startup
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," not in runtime_startup
    assert "assert_manifest_backed_integrations_equal(" not in runtime_startup
    assert "assert_manifest_backed_integrations," in cli_data
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," not in cli_data
    assert "assert_manifest_backed_integrations_equal(" not in cli_data
    assert "assert_manifest_backed_integrations," in mcp_meta_tools
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," not in mcp_meta_tools
    assert "assert_manifest_backed_integrations_equal(" not in mcp_meta_tools
    assert "assert_manifest_backed_integrations," in query_surface
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," not in query_surface
    assert "assert_manifest_backed_integrations_equal(" not in query_surface
    assert "assert_manifest_backed_integrations," in algenta_runtime
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," not in algenta_runtime
    assert "assert_manifest_backed_integrations_equal(" not in algenta_runtime
    assert "assert_manifest_backed_integrations," in decision_engine_client_wrapper
    assert "assert_manifest_backed_integrations_equal," not in decision_engine_client_wrapper
    assert "assert_manifest_backed_integrations," in distribution_artifact
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," not in distribution_artifact
    assert "assert_manifest_backed_integrations," in platform_contract_generation
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," not in platform_contract_generation
    assert "assert_manifest_backed_integrations_equal(" not in platform_contract_generation
    assert "normalize_manifest_backed_integrations," not in meta_contract_api
    assert "normalize_manifest_backed_integrations," not in mcp_data_tools
    assert "normalize_manifest_backed_integrations," not in runtime_startup
    assert "normalize_manifest_backed_integrations," not in cli_data
    assert "normalize_manifest_backed_integrations," not in mcp_meta_tools
    assert "normalize_manifest_backed_integrations," not in query_surface
    assert "normalize_manifest_backed_integrations," not in algenta_runtime
    assert "normalize_manifest_backed_integrations," not in decision_engine_lazy_exports
    assert "normalize_manifest_backed_integrations," not in algenta_lazy_exports
    assert 'sys.modules["decision_engine._contract"].INTEGRATIONS' in decision_engine_lazy_exports
    assert 'sys.modules["algenta._contract"].INTEGRATIONS' in algenta_lazy_exports
    assert "_normalized_decision_engine_contract_integrations" not in decision_engine_lazy_exports
    assert "_normalized_algenta_contract_integrations" not in algenta_lazy_exports
    assert "assert_manifest_backed_integrations_equal(" in decision_engine_lazy_exports
    assert "assert_manifest_backed_integrations_equal(" in algenta_lazy_exports
    assert "NORMALIZED_ARTIFACT_CONTRACT_INTEGRATIONS =" not in distribution_artifact
    assert "normalize_manifest_backed_integrations," not in distribution_artifact
    assert "_normalized_module_integrations" not in distribution_artifact
    assert "assert_manifest_backed_integrations_equal(" in distribution_artifact
    assert "NORMALIZED_MANIFEST_INTEGRATIONS =" not in meta_contract_api
    assert "assert_manifest_backed_integrations_equal," not in platform_contract
    assert "normalize_manifest_backed_integrations," not in platform_contract
    assert "NORMALIZED_PLATFORM_CONTRACT_INTEGRATIONS =" not in mcp_data_tools
    assert "NORMALIZED_EXPECTED_CONTRACT_INTEGRATIONS =" not in runtime_startup
    assert "NORMALIZED_PLATFORM_CONTRACT_INTEGRATIONS =" not in cli_data
    assert "NORMALIZED_PLATFORM_CONTRACT_INTEGRATIONS =" not in mcp_meta_tools
    assert "NORMALIZED_PLATFORM_CONTRACT_INTEGRATIONS =" not in query_surface
    assert "NORMALIZED_PLATFORM_CONTRACT_INTEGRATIONS =" not in algenta_runtime
    assert "normalized_contract_integrations =" not in platform_contract_generation
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," not in decision_engine_client_wrapper


def test_platform_contract_proof_pins_canonical_manifest_fixture_and_fail_closed_guard() -> None:
    platform_contract = (ROOT / "tests" / "test_platform_contract.py").read_text(
        encoding="utf-8"
    )

    assert "MANIFEST_BACKED_INTEGRATIONS," in platform_contract
    assert 'assert manifest["integrations"] == list(MANIFEST_BACKED_INTEGRATIONS)' in (
        platform_contract
    )
    assert "assert_manifest_backed_integrations(manifest[\"integrations\"])" in platform_contract
    assert "contract_integrations_match_manifest," in platform_contract
    assert "assert contract_integrations_match_manifest([object()]) is False" in platform_contract


def test_python_manifest_helper_exports_normalized_fixture_constant() -> None:
    helper = (ROOT / "tests" / "_manifest_backed_integrations.py").read_text(encoding="utf-8")

    assert "manifest_backed_integrations.fixture.json" in helper
    assert "MANIFEST_BACKED_INTEGRATIONS_FIXTURE_PATH =" not in helper
    assert "MANIFEST_BACKED_INTEGRATIONS = tuple(" in helper
    assert 'Path(__file__)' in helper
    assert '.resolve()' in helper
    assert '.with_name("manifest_backed_integrations.fixture.json")' in helper
    assert "MANIFEST_BACKED_INTEGRATION_FIELDS =" not in helper
    assert "MANIFEST_BACKED_INTEGRATION_NAMES =" not in helper
    assert "MANIFEST_BACKED_READ_ONLY_INTEGRATIONS =" not in helper
    assert "MANIFEST_BACKED_INTEGRATIONS_EXPORT_PATTERN =" not in helper
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS = normalize_manifest_backed_integrations(" in (
        helper
    )
    assert "def assert_manifest_backed_integrations(integrations: Sequence[Any]) -> None:" in (
        helper
    )
    assert "def _get_integration_field(" not in helper
    assert "def _is_canonical_manifest_integration_sequence(" not in helper
    assert "def _normalize_or_reuse_manifest_backed_integrations(" in helper
    assert "integrations is MANIFEST_BACKED_INTEGRATIONS" in helper
    assert "or integrations is NORMALIZED_MANIFEST_BACKED_INTEGRATIONS" in helper
    assert "return NORMALIZED_MANIFEST_BACKED_INTEGRATIONS" in helper
    assert helper.count("if not integrations:") == 1
    assert "assert_manifest_backed_integrations_equal(" in (
        helper
    )
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," in helper
    assert "def assert_manifest_backed_integration_texts_equal(" in helper
    assert "def parse_manifest_backed_integration_text(" not in helper
    assert 'left_match = re.search(' in helper
    assert 'raise AssertionError("missing exported INTEGRATIONS array")' in helper
    assert "left_integrations = json.loads(left_match.group(1))" in helper
    assert "if right_text == left_text:" in helper
    assert "return" in helper
    assert 'right_match = re.search(' in helper
    assert "right_integrations = json.loads(right_match.group(1))" in helper
    assert "assert_manifest_backed_integrations(left_integrations)" in helper
    assert "assert_manifest_backed_integrations(right_integrations)" not in helper
    assert "_normalize_or_reuse_manifest_backed_integrations(integrations)" in helper
    assert "if expected_integrations is integrations:" in helper
    assert "normalized_expected_integrations = normalized_integrations" in helper
    assert "_normalize_or_reuse_manifest_backed_integrations(" in helper
    assert "fields = tuple(MANIFEST_BACKED_INTEGRATIONS[0].keys())" in helper
    assert "integration[field] if isinstance(integration, Mapping) else getattr(integration, field)" in (
        helper
    )
    assert "assert_manifest_backed_integrations_equal(left_integrations, right_integrations)" in (
        helper
    )
    assert "assert normalized_integrations == normalized_expected_integrations" in helper
    assert "def contract_integrations_match_manifest(integrations: Sequence[Any]) -> bool:" in (
        helper
    )
    assert "_normalize_or_reuse_manifest_backed_integrations(integrations)" in helper
    assert "== NORMALIZED_MANIFEST_BACKED_INTEGRATIONS" in helper
    assert "assert_manifest_backed_integrations(integrations)" not in helper
    assert "except (AssertionError, AttributeError, IndexError, KeyError, TypeError):" in helper
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS" in helper


def test_root_test_graph_includes_formal_runtime_foundation_proof_bundle() -> None:
    package_json = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    scripts = package_json["scripts"]

    assert scripts["test:js"] == (
        "pnpm --dir packages/ts-sdk test -- --run "
        "src/libraries.test.ts src/runtime_daemon_client.test.ts src/index.test.ts "
        "&& pnpm --dir apps/gateway test "
        "&& pnpm --dir apps/gateway exec tsx --test ../../examples/shared/privacyProfile.test.ts"
    )
    assert scripts["test"] == "pnpm test:js && pnpm test:formal-runtime-foundation"
    assert scripts["validate:formal-runtime-foundation"] == (
        "./scripts/run_repo_python.sh scripts/validate_runtime_release.py --format table"
    )
    assert (ROOT / "scripts" / "run_repo_python.sh").exists()
    assert "tests/test_platform_contract.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_platform_contract_schema_surface.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_runtime_manifest.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_runtime_admin_api.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_runtime_release_validation.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_validate_runtime_release.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_runtime_manifest_model_validation.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_runtime_schema_surface.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_runtime_startup_smoke.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_decision_engine_query_surface.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_decision_engine_lazy_exports.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_algenta_lazy_exports.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_algenta_runtime.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_algenta_runtime_llm_and_agent_surface.py" in scripts[
        "test:formal-runtime-foundation"
    ]
    assert "tests/test_algenta_client_plan_surface.py" in scripts[
        "test:formal-runtime-foundation"
    ]
    # test_cli_data.py was split into 9 per-command-family sub-files; the
    # foundation script now lists each one explicitly. Assert all are present.
    for suffix in (
        "test_cli_data_account.py",
        "test_cli_data_agent_runs.py",
        "test_cli_data_capabilities.py",
        "test_cli_data_connectors.py",
        "test_cli_data_data.py",
        "test_cli_data_decision.py",
        "test_cli_data_jobs.py",
        "test_cli_data_llm.py",
        "test_cli_data_runtime.py",
    ):
        assert f"tests/{suffix}" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_mcp_meta_tools.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_mcp_llm_agent_tools.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_mcp_router.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_js_workspace_surface.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_package_distribution_surface.py" in scripts["test:formal-runtime-foundation"]
    for suffix in (
        "test_runtime_surface_compatibility_all_standalone.py",
        "test_runtime_surface_compatibility_go_live.py",
        "test_runtime_surface_compatibility_misc_a.py",
        "test_runtime_surface_compatibility_misc_b.py",
        "test_runtime_surface_compatibility_misc_c.py",
        "test_runtime_surface_compatibility_misc_d.py",
        "test_runtime_surface_compatibility_misc_e.py",
    ):
        assert f"tests/{suffix}" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_benchmark_inventory_surface.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_scorecard_suite_summaries.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_csv_pipeline_summary.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_benchmark_scorecard_sync.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_go_live_scorecard.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_live_integration_artifacts.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_llm_rollout_live_artifacts.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_llm_rollout_scorecard.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_plan_alignment_matrix.py" in scripts["test:formal-runtime-foundation"]
    assert scripts["test:formal-runtime-foundation"].startswith(
        "./scripts/run_repo_python.sh tests/integration/test_csv_pipeline.py && "
        "./scripts/run_repo_python.sh benchmarks/scorecard_suite_summaries.py && "
        'if [ "${DE_SKIP_GO_LIVE_VERIFY:-0}" != "1" ]; then ./scripts/run_repo_python.sh tests/go_live_verify.py; fi && '
        "./scripts/run_repo_python.sh benchmarks/llm_rollout_proof_bundle.py --skip-live && "
        "./scripts/run_repo_python.sh -m pytest -q "
    )
    assert 'DE_SKIP_GO_LIVE_VERIFY:-0' in scripts["test:formal-runtime-foundation"]
    assert (
        "&& ./scripts/run_repo_python.sh tests/integration/test_runtime_libraries_http_live.py"
        in scripts["test:formal-runtime-foundation"]
    )
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_cli.py" in scripts["test:formal-runtime-foundation"]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_algenta_client_live.py" in scripts[
        "test:formal-runtime-foundation"
    ]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_typescript_sdk_client_live.py" in scripts[
        "test:formal-runtime-foundation"
    ]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_typescript_runtime_live.py" in scripts[
        "test:formal-runtime-foundation"
    ]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_python_sdk.py" in scripts["test:formal-runtime-foundation"]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_algenta_runtime_live.py" in scripts[
        "test:formal-runtime-foundation"
    ]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_mcp_server.py" in scripts["test:formal-runtime-foundation"]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_openapi.py" in scripts["test:formal-runtime-foundation"]
    assert (
        scripts["check"]
        == "pnpm lint && pnpm test && pnpm validate:formal-runtime-foundation && pnpm build"
    )


