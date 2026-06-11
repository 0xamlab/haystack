from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_FALLBACK = 'os.environ.get(\n            "JWT_SECRET",\n            "change-me-in-production-use-256-bit-random-value",\n        )'


def test_local_runtime_integration_scripts_preserve_configured_jwt_secret() -> None:
    targets = (
        ROOT / "tests" / "integration" / "test_local_runtime_real.py",
        ROOT / "tests" / "integration" / "test_algenta_mojo_library_live.py",
        ROOT / "tests" / "integration" / "test_cli_mcp_runtime_libraries_live.py",
        ROOT / "tests" / "integration" / "test_typescript_runtime_live.py",
    )

    violations: list[str] = []
    for path in targets:
        text = path.read_text(encoding="utf-8")
        if _FALLBACK not in text:
            violations.append(path.name)

    assert not violations, (
        "Local-runtime integration scripts must preserve an existing JWT_SECRET "
        f"before falling back to the default seed: {violations}"
    )


def test_cli_mcp_runtime_live_script_invokes_the_modular_cli_entrypoint() -> None:
    text = (
        ROOT / "tests" / "integration" / "test_cli_mcp_runtime_libraries_live.py"
    ).read_text(encoding="utf-8")

    assert 'CLI = [sys.executable, "-m", "apps.cli.main"]' in text
    assert 'apps" / "cli" / "main.py"' not in text
