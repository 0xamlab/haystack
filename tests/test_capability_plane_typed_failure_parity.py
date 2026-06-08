from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_capability_plane_runtime_typed_failures_stay_aligned_across_python_and_typescript() -> None:
    python_runtime = (
        ROOT / "packages" / "algenta-core" / "algenta" / "runtime_capability_plane.py"
    ).read_text(encoding="utf-8")
    typescript_runtime = (ROOT / "packages" / "ts-sdk" / "src" / "runtime.ts").read_text(
        encoding="utf-8"
    )
    python_tests = (ROOT / "tests" / "test_algenta_runtime_capability_plane.py").read_text(
        encoding="utf-8"
    )
    typescript_tests = (
        ROOT / "packages" / "ts-sdk" / "src" / "capability_plane.test.ts"
    ).read_text(encoding="utf-8")

    expected_codes = (
        "capability_execution_owner_unsupported",
        "capability_adapter_missing",
    )

    for code in expected_codes:
        assert code in python_runtime
        assert code in typescript_runtime
        assert code in python_tests
        assert code in typescript_tests

    assert "client_managed_capability_requires_adapter" not in typescript_runtime
    assert "client_managed_capability_requires_adapter" not in typescript_tests
