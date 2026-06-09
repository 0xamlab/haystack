from __future__ import annotations

import runpy
from pathlib import Path

import pytest


# Integration scripts that intentionally remain standalone (run via
# `python tests/integration/<file>.py`) and therefore skip on pytest import.
#
# The previously-listed scripts below were converted to first-class pytest
# modules (collected + run by pytest directly) and no longer skip on import,
# so they have been removed from this list:
#   test_redis, test_all_engines, test_benchmarks, test_cli, test_database,
#   test_e2e_complete, test_jobs, test_middleware, test_mojo_engines_realdata,
#   test_mojo_pool, test_mcp_server, test_openapi, test_python_sdk,
#   test_typescript_sdk_client_live, test_typescript_runtime_live,
#   test_runtime_libraries_http_live, test_algenta_client_live,
#   test_algenta_runtime_live, test_services, test_auth_security, test_load,
#   test_connectors, test_exports, test_go_live_connectivity_real,
#   test_csv_pipeline, test_mcp_100_questions.
SCRIPT_GUARDS = [
    ("test_api_live.py", "Standalone integration script"),
    ("test_mcp_runtime_live.py", "Standalone integration script"),
    ("test_algenta_mojo_library_live.py", "Standalone integration script"),
    ("test_cli_mcp_runtime_libraries_live.py", "Standalone integration script"),
    ("test_local_runtime_real.py", "Standalone integration script"),
    ("test_templates.py", "Standalone integration script"),
]


@pytest.mark.parametrize(("filename", "message"), SCRIPT_GUARDS)
def test_script_skips_on_import_under_pytest(filename: str, message: str) -> None:
    script_path = Path(__file__).resolve().parents[1] / "tests" / "integration" / filename

    with pytest.raises(pytest.skip.Exception, match=message):
        runpy.run_path(str(script_path), run_name=f"tests.integration.{script_path.stem}")
