from __future__ import annotations

import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_PACKAGE = ROOT / "packages" / "algenta"
if str(ALGENTA_PACKAGE) not in sys.path:
    sys.path.insert(0, str(ALGENTA_PACKAGE))

from algenta.native import worker  # noqa: E402
from algenta.runtime_library_contract import (  # noqa: E402
    RuntimeLibraryContractError,
    find_runtime_function,
    runtime_modules,
)
from algenta.runtime_library_transport import (  # noqa: E402
    build_worker_request,
    parse_worker_response,
)

CONTRACT_PATH = ALGENTA_PACKAGE / "algenta" / "runtime_library_contract.json"

# Regression floors for the shipped kernel surface. The surface may only grow.
# These are floors, not fixtures: adding a kernel must not require editing a
# test. Exact agreement with the source tree is proven separately by
# `scripts/generate_algenta_runtime_contract.py --check`, and internal
# consistency is derived from the payload itself. Raise these deliberately after
# `make inventory-refresh`; never lower them.
MODULE_COUNT_FLOOR = 495
FUNCTION_COUNT_FLOOR = 4873


def _contract_payload() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_generated_contract_is_current() -> None:
    """The committed contract must match a fresh generation from mojo/engine.

    Fails when a kernel was added without running `make inventory-refresh` — in
    which case that kernel is invisible to the local SDK (`find_runtime_function`
    raises `module_not_registered`) even though it compiles and its tests pass.
    """
    proc = subprocess.run(
        [sys.executable, "scripts/generate_algenta_runtime_contract.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, (
        (proc.stderr or proc.stdout) + "\n\nRun: make inventory-refresh"
    )


def test_contract_counts_are_self_consistent_and_meet_floors() -> None:
    payload = _contract_payload()

    # Derived from the payload — never needs bumping.
    assert payload["module_count"] == len(payload["modules"])
    assert payload["function_count"] == sum(
        len(module["functions"]) for module in payload["modules"]
    )
    assert len(runtime_modules()) == payload["module_count"]

    # Regression floors — the surface must not shrink.
    assert payload["module_count"] >= MODULE_COUNT_FLOOR
    assert payload["function_count"] >= FUNCTION_COUNT_FLOOR


def test_generated_contract_is_sanitized() -> None:
    contract_path = CONTRACT_PATH
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    encoded = contract_path.read_text(encoding="utf-8").lower()
    assert "runtime_library_dispatch_generated" not in {
        module["name"] for module in payload["modules"]
    }
    # runtime_bundle is the OPTIONAL managed-runtime footer (version + per-platform
    # URLs + sha256s + public key) stamped at bundle-cut time by
    # scripts/generate_algenta_runtime_contract.py --bundle-metadata; the surface
    # gate (--check) ignores it, so it may be absent or present.
    assert set(payload) <= {
        "schema_version",
        "module_count",
        "function_count",
        "modules",
        "runtime_bundle",
    }
    assert {"schema_version", "module_count", "function_count", "modules"} <= set(payload)
    if "runtime_bundle" in payload:
        footer = payload["runtime_bundle"]
        assert isinstance(footer.get("version"), str) and footer["version"]
        platforms = footer.get("platforms")
        assert isinstance(platforms, dict) and platforms
        for platform, pin in platforms.items():
            assert isinstance(platform, str) and platform
            assert isinstance(pin.get("url"), str) and pin["url"].startswith("https://")
            assert isinstance(pin.get("sha256"), str) and len(pin["sha256"]) == 64
    for module in payload["modules"]:
        assert set(module) == {"name", "engine", "functions", "structs"}
        for function in module["functions"]:
            # `count_relations` is OPTIONAL and present only on functions carrying a declared
            # `@capability` block (#429). It is part of the shipped contract on purpose — an SDK
            # needs the count/list relation to reject an aborting call before it reaches the worker
            # — so this test asserts the closed set of keys a function MAY have, not a fixed one.
            assert set(function) <= {"name", "params", "return_type", "count_relations"}
            assert {"name", "params", "return_type"} <= set(function)
            for param in function["params"]:
                assert set(param) == {"name", "type", "has_default", "is_mut"}
        for struct in module["structs"]:
            assert set(struct) == {"name", "fields"}
            for field in struct["fields"]:
                assert set(field) == {"name", "type"}
    for forbidden in ("/users/", "decision-engine", "codna"):
        assert forbidden not in encoded


def test_contract_rejects_unknown_module_and_function() -> None:
    with pytest.raises(RuntimeLibraryContractError) as module_error:
        find_runtime_function("internal.missing", "run")
    assert module_error.value.code == "module_not_registered"

    module = runtime_modules()[0]
    with pytest.raises(RuntimeLibraryContractError) as function_error:
        find_runtime_function(module.import_path, "__missing_function__")
    assert function_error.value.code == "function_not_registered"


def test_transport_validates_arguments_and_response() -> None:
    module, function = find_runtime_function("vector_kernels.dot", "dot64_f32")
    _, _, request = build_worker_request(
        module.import_path,
        function.name,
        {"a": [1, 2, 6], "b": [3, 2, 1]},
    )
    assert request == {
        "type": "library_execute",
        "engine_type": "library_execute",
        "module": "vector_kernels.dot",
        "function": "dot64_f32",
        "args": [[1.0, 2.0, 6.0], [3.0, 2.0, 1.0]],
    }
    assert parse_worker_response(module, function, {"result": 13.0}) == 13.0

    with pytest.raises(RuntimeLibraryContractError) as invalid:
        build_worker_request(module.import_path, function.name, {"a": [True], "b": [1]})
    assert invalid.value.code == "invalid_arguments"


def test_frame_reader_rejects_non_object_payload() -> None:
    client, server = socket.socketpair()
    try:
        raw = b"[]"
        client.sendall(len(raw).to_bytes(4, "big") + raw)
        with pytest.raises(worker.NativeWorkerUnavailable, match="non-object"):
            worker._recv_frame(server)
    finally:
        client.close()
        server.close()


def test_transport_decodes_struct_results_to_public_fields() -> None:
    module, function = find_runtime_function("vector_kernels.table", "build_query")
    rank_request = next(struct for struct in module.structs if struct.name == "RankRequest")

    def encoded_struct(struct_name: str, values: list[object]) -> dict[str, object]:
        return {"__algenta_struct": struct_name, "v": values}

    values: list[object] = []
    for field in rank_request.fields:
        if field.typ == "Int" or field.typ.startswith("UInt"):
            values.append(1)
        elif field.typ in {"Float32", "Float64"}:
            values.append(1.0)
        elif field.typ == "_Vec64":
            nested = next(struct for struct in module.structs if struct.name == "_Vec64")
            nested_values = [
                ([] if item.typ.startswith("List[") else 0.0) for item in nested.fields
            ]
            values.append(encoded_struct("_Vec64", nested_values))
        else:
            raise AssertionError(f"unexpected RankRequest field type: {field.typ}")

    decoded = parse_worker_response(
        module,
        function,
        {"result": encoded_struct("RankRequest", values)},
    )

    assert set(decoded) == {field.name for field in rank_request.fields}
    assert "__algenta_struct" not in decoded
