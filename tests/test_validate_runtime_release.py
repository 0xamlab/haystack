from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.validate_runtime_release as validate_runtime_release_script

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_runtime_release.py"


def test_validate_runtime_release_script_reports_a_valid_release() -> None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "Codna runtime release validation:" in proc.stdout
    assert "Valid release:   True" in proc.stdout
    assert "manifest-listed: pass" in proc.stdout


def test_validate_runtime_release_script_supports_json_output() -> None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), "--format", "json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["valid_release"] is True
    assert payload["conditions"][0]["condition"] == "manifest-listed"


def test_validate_runtime_release_table_prefers_raw_deployment_mode_when_typed_mode_is_missing() -> None:
    output = validate_runtime_release_script._render_table(
        {
            "runtime_version": "2026.05.0",
            "llm_core_manifest": "llm-core-v1",
            "module_manifest_version": "runtime-manifest-v1",
            "deployment_mode": None,
            "deployment_mode_raw": "shadow_realm",
            "manifest_digest": "c" * 64,
            "valid_release": False,
            "theorem_statement": "theorem",
            "conditions": [],
            "signature": {
                "algorithm": "hmac-sha256",
                "key_id": "runtime-manifest-signing-v1",
                "digest_hex": "c" * 64,
                "signature_hex": "d" * 64,
                "scope": "control_plane_hmac_v1",
            },
        }
    )

    assert "Deployment:      shadow_realm" in output


def test_validate_runtime_release_table_rejects_invalid_signed_payload_with_field_path() -> None:
    payload = validate_runtime_release_script.build_runtime_release_validation(
        validate_runtime_release_script.get_runtime_manifest()
    ).model_dump(mode="json")
    payload["conditions"][0]["condition"] = "wormhole_condition"

    with pytest.raises(
        validate_runtime_release_script.RuntimeReleaseValidationScriptError
    ) as exc_info:
        validate_runtime_release_script._render_table(payload)

    assert exc_info.value.code == "invalid_runtime_release_validation_payload"
    assert exc_info.value.details["cause"] == "conditions.0.condition"
    assert exc_info.value.details["validation_errors"][0]["path"] == "conditions.0.condition"


def test_validate_runtime_release_table_rejects_invalid_signed_model_instance() -> None:
    payload = validate_runtime_release_script.build_runtime_release_validation(
        validate_runtime_release_script.get_runtime_manifest()
    ).model_copy(deep=True)
    payload.conditions[0].condition = "wormhole_condition"

    with pytest.raises(
        validate_runtime_release_script.RuntimeReleaseValidationScriptError
    ) as exc_info:
        validate_runtime_release_script._render_table(payload)

    assert exc_info.value.code == "invalid_runtime_release_validation_payload"
    assert exc_info.value.details["cause"] == "conditions.0.condition"
    assert exc_info.value.details["validation_errors"][0]["path"] == "conditions.0.condition"


def test_validate_runtime_release_main_fails_closed_for_invalid_internal_payload(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = validate_runtime_release_script.build_runtime_release_validation(
        validate_runtime_release_script.get_runtime_manifest()
    ).model_dump(mode="json")
    payload["conditions"][0]["condition"] = "wormhole_condition"

    monkeypatch.setattr(validate_runtime_release_script, "get_runtime_manifest", lambda: object())
    monkeypatch.setattr(
        validate_runtime_release_script,
        "build_runtime_release_validation",
        lambda _: payload,
    )

    exit_code = validate_runtime_release_script.main([])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "conditions.0.condition" in captured.err


def test_validate_runtime_release_main_fails_closed_for_invalid_internal_model_instance(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = validate_runtime_release_script.build_runtime_release_validation(
        validate_runtime_release_script.get_runtime_manifest()
    ).model_copy(deep=True)
    payload.conditions[0].condition = "wormhole_condition"

    monkeypatch.setattr(validate_runtime_release_script, "get_runtime_manifest", lambda: object())
    monkeypatch.setattr(
        validate_runtime_release_script,
        "build_runtime_release_validation",
        lambda _: payload,
    )

    exit_code = validate_runtime_release_script.main([])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "conditions.0.condition" in captured.err
