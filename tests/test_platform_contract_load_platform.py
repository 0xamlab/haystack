"""Tests for test_platform_contract: load_platform.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-4/tests/test_platform_contract.py during modularization.
"""
from __future__ import annotations

from tests._test_platform_contract_helpers import *  # noqa: F401,F403


def test_load_platform_contract_manifest_model_validates_full_primary_contract_shape() -> None:
    platform_contract.clear_platform_contract_caches()
    manifest = platform_contract.load_platform_contract_manifest_model()
    assert (
        manifest.primary_data_query_contract.runtime_sdk.typescript.libraries_entrypoint
        == "libraries"
    )
    assert manifest.primary_data_query_contract.cli.runtime_execute_command.startswith(
        "de runtime execute"
    )


def test_load_platform_contract_manifest_model_rejects_non_object_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "integration_manifest.invalid.json"
    manifest_path.write_text(json.dumps(["not-an-object"]))
    monkeypatch.setattr(platform_contract, "MANIFEST_PATH", manifest_path)
    platform_contract.clear_platform_contract_caches()

    with pytest.raises(
        platform_contract.PlatformContractManifestError,
        match="JSON object",
    ) as exc:
        platform_contract.load_platform_contract_manifest_model()
    assert exc.value.code == "invalid_platform_contract_manifest"


def test_load_platform_contract_manifest_model_rejects_invalid_nested_contract_shape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    manifest["primary_data_query_contract"]["runtime_sdk"]["typescript"].pop("runtime_class")
    manifest_path = tmp_path / "integration_manifest.invalid.json"
    manifest_path.write_text(json.dumps(manifest))
    monkeypatch.setattr(platform_contract, "MANIFEST_PATH", manifest_path)
    platform_contract.clear_platform_contract_caches()

    with pytest.raises(
        platform_contract.PlatformContractManifestError,
        match="canonical Codna contract schema",
    ) as exc:
        platform_contract.load_platform_contract_manifest_model()
    assert exc.value.code == "invalid_platform_contract_manifest"


