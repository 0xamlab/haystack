from __future__ import annotations

import runpy
from pathlib import Path

import pytest


SCRIPT_GUARDS = [
    ("test_redis.py", "Standalone Redis integration script"),
    ("test_all_engines.py", "Standalone integration script"),
    ("test_api_live.py", "Standalone integration script"),
    ("test_benchmarks.py", "Standalone integration script"),
    ("test_cli.py", "Standalone integration script"),
    ("test_database.py", "Standalone integration script"),
    ("test_e2e_complete.py", "Standalone integration script"),
    ("test_jobs.py", "Standalone integration script"),
    ("test_middleware.py", "Standalone integration script"),
    ("test_mcp_runtime_live.py", "Standalone integration script"),
    ("test_mojo_engines_realdata.py", "Standalone integration script"),
    ("test_mojo_pool.py", "Standalone integration script"),
    ("test_mcp_server.py", "Standalone integration script"),
    ("test_openapi.py", "Standalone integration script"),
    ("test_python_sdk.py", "Standalone integration script"),
    ("test_typescript_sdk_client_live.py", "Standalone integration script"),
    ("test_runtime_libraries_http_live.py", "Standalone integration script"),
    ("test_algenta_mojo_library_live.py", "Standalone integration script"),
    ("test_algenta_client_live.py", "Standalone integration script"),
    ("test_algenta_runtime_live.py", "Standalone integration script"),
    ("test_cli_mcp_runtime_libraries_live.py", "Standalone integration script"),
    ("test_local_runtime_real.py", "Standalone integration script"),
    ("test_services.py", "Standalone integration script"),
    ("test_templates.py", "Standalone integration script"),
]


@pytest.mark.parametrize(("filename", "message"), SCRIPT_GUARDS)
def test_script_skips_on_import_under_pytest(filename: str, message: str) -> None:
    script_path = Path(__file__).resolve().parents[1] / "tests" / "integration" / filename

    with pytest.raises(pytest.skip.Exception, match=message):
        runpy.run_path(str(script_path), run_name=f"tests.integration.{script_path.stem}")
