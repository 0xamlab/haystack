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


def test_generated_contract_is_current_and_sanitized() -> None:
    proc = subprocess.run(
        [sys.executable, "scripts/generate_algenta_runtime_contract.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout

    contract_path = ALGENTA_PACKAGE / "algenta" / "runtime_library_contract.json"
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    encoded = contract_path.read_text(encoding="utf-8").lower()
    assert payload["module_count"] == 472
    assert payload["function_count"] == 4757
    assert len(runtime_modules()) == 472
    assert "runtime_library_dispatch_generated" not in {
        module["name"] for module in payload["modules"]
    }
    assert set(payload) == {"schema_version", "module_count", "function_count", "modules"}
    for module in payload["modules"]:
        assert set(module) == {"name", "engine", "functions", "structs"}
        for function in module["functions"]:
            assert set(function) == {"name", "params", "return_type"}
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
