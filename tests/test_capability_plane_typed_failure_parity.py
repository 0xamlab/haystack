from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_capability_plane_runtime_typed_failures_stay_aligned_across_python_and_typescript() -> None:
    python_runtime = (
        ROOT / "packages" / "algenta-core" / "algenta" / "runtime_capability_plane.py"
    ).read_text(encoding="utf-8")
    # runtime.ts is now a barrel re-exporting per-domain sub-modules; concat
    # the barrel + every _runtime_*.ts so textual surface checks cover the
    # same source content as before the modularization.
    ts_src_dir = ROOT / "packages" / "ts-sdk" / "src"
    typescript_runtime = (ts_src_dir / "runtime.ts").read_text(
        encoding="utf-8"
    ) + "\n".join(
        p.read_text(encoding="utf-8") for p in sorted(ts_src_dir.glob("_runtime_*.ts"))
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
