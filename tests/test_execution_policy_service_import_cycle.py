from __future__ import annotations

import importlib
import os
import sys


def test_execution_policy_service_and_runtime_manifest_import_without_cycle(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / ".algenta-runtime"))

    for module_name in (
        "apps.runtime_manifest",
        "apps.api_server.services.runtime_internal_contracts",
        "apps.api_server.services.execution_policy_service",
    ):
        sys.modules.pop(module_name, None)

    service = importlib.import_module("apps.api_server.services.execution_policy_service")
    manifest = importlib.import_module("apps.runtime_manifest")

    policy = service.get_policy("org_import_cycle_test")
    assert policy.snapshot_id
    assert manifest.RuntimeReleaseValidationResponse is not None
    assert os.path.exists(os.environ["ALGENTA_RUNTIME_DIR"])
