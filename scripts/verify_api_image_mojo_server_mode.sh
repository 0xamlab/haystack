#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: scripts/verify_api_image_mojo_server_mode.sh <api-image>" >&2
  exit 64
fi

image="$1"

docker run --rm -i --entrypoint python "$image" - <<'PY'
from __future__ import annotations

import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def fail(code: str, message: str, **details: object) -> None:
    payload = {
        "error": {
            "code": code,
            "message": message,
            "details": details,
        }
    }
    print(json.dumps(payload, sort_keys=True), file=sys.stderr)
    raise SystemExit(1)


def verify_embedded_mcp_router() -> None:
    products_path = Path("/app/packages/mcp/algenta_mcp/products.py")
    if not products_path.is_file():
        fail(
            "mcp_product_registry_missing",
            "The API image does not contain the canonical embedded MCP product registry.",
            path=str(products_path),
        )
    try:
        from apps.mcp_server.server import create_fastapi_router
    except Exception as exc:
        fail(
            "mcp_router_import_failed",
            "The API image cannot import the embedded MCP FastAPI router.",
            error=str(exc),
        )
    router = create_fastapi_router()
    if router is None:
        fail(
            "mcp_router_unavailable",
            "The API image did not construct the embedded MCP FastAPI router.",
        )
    paths = sorted(str(getattr(route, "path", "")) for route in router.routes)
    if "/mcp/tools" not in paths:
        fail(
            "mcp_tools_route_missing",
            "The API image embedded MCP router does not expose /mcp/tools.",
            paths=paths,
        )


def verify_platform_contract_manifest() -> None:
    manifest_path = Path("/app/apps/docs/integration_manifest.v1.json")
    if not manifest_path.is_file():
        fail(
            "platform_contract_manifest_missing",
            "The API image does not contain the platform contract manifest required by /v1/meta/contract.",
            path=str(manifest_path),
        )
    try:
        from apps.platform_contract import load_platform_contract_manifest_model
    except Exception as exc:
        fail(
            "platform_contract_import_failed",
            "The API image cannot import the platform contract loader.",
            error=str(exc),
        )
    try:
        payload = load_platform_contract_manifest_model()
    except Exception as exc:
        fail(
            "platform_contract_manifest_invalid",
            "The API image cannot load the platform contract manifest required by /v1/meta/contract.",
            error=str(exc),
        )
    if payload.primary_data_query_contract.api.contract_endpoint != "/v1/meta/contract":
        fail(
            "platform_contract_endpoint_mismatch",
            "The platform contract manifest does not advertise the canonical contract endpoint.",
            contract_endpoint=payload.primary_data_query_contract.api.contract_endpoint,
        )


def verify_playground_sdk() -> None:
    """The keyless POST /v1/playground runs algenta.simple in-process from /app/packages/algenta.

    2026-09-22: the image carried only runtime_library_contract.json under that path, `import
    algenta` resolved to a namespace-package shell, and every documented playground call on
    api.algenta.ai returned 500 "No module named 'algenta.simple'" -- undetected by this smoke,
    which is the last gate before a Fly rollout. Import it the way the router does and run one
    real decision (pure Python, no Mojo worker) so a hollow copy fails the build, not production.
    """
    sdk_root = Path("/app/packages/algenta")
    simple_py = sdk_root / "algenta" / "simple.py"
    if not simple_py.is_file():
        fail(
            "playground_sdk_missing",
            "The API image does not contain the algenta SDK package that /v1/playground imports.",
            path=str(simple_py),
        )
    sys.path.insert(0, str(sdk_root))
    try:
        from algenta.simple import decision
    except Exception as exc:
        fail(
            "playground_sdk_import_failed",
            "The API image cannot import algenta.simple, so /v1/playground would 503.",
            error=str(exc),
        )
    result = decision(runs=100, revenue=120000.0, cost=70000.0)
    if result.action not in {"proceed", "pause", "reject"}:
        fail(
            "playground_sdk_bad_result",
            "algenta.simple.decision returned an action outside the documented set.",
            action=str(result.action),
        )


def recv_frame(sock: socket.socket, *, timeout_s: float) -> dict[str, object]:
    sock.settimeout(timeout_s)
    header = sock.recv(4)
    if len(header) != 4:
        fail("mojo_frame_header_missing", "Mojo worker returned an incomplete frame header.")
    length = struct.unpack(">I", header)[0]
    chunks: list[bytes] = []
    remaining = length
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            fail("mojo_frame_body_missing", "Mojo worker closed before sending a complete frame.")
        chunks.append(chunk)
        remaining -= len(chunk)
    try:
        payload = json.loads(b"".join(chunks).decode("utf-8"))
    except json.JSONDecodeError as exc:
        fail("mojo_frame_invalid_json", "Mojo worker returned invalid JSON.", error=str(exc))
    if not isinstance(payload, dict):
        fail("mojo_frame_invalid_shape", "Mojo worker returned a non-object JSON payload.")
    return payload


def send_frame(sock: socket.socket, payload: dict[str, object]) -> None:
    data = json.dumps(payload, sort_keys=True).encode("utf-8")
    sock.sendall(struct.pack(">I", len(data)) + data)


def main() -> None:
    verify_platform_contract_manifest()
    verify_embedded_mcp_router()
    verify_playground_sdk()

    binary = Path(os.environ.get("MOJO_BINARY_PATH", "/app/mojo_build/simulate"))
    if not binary.is_file():
        fail("mojo_binary_missing", "The API image does not contain the bundled Mojo worker.", binary=str(binary))
    if not os.access(binary, os.X_OK):
        fail("mojo_binary_not_executable", "The bundled Mojo worker is not executable.", binary=str(binary))

    socket_path = Path(tempfile.gettempdir()) / f"algenta-api-image-mojo-{os.getpid()}.sock"
    try:
        socket_path.unlink(missing_ok=True)
    except OSError:
        pass

    proc = subprocess.Popen(
        [str(binary), "--server", str(socket_path)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
    )
    try:
        deadline = time.monotonic() + 15.0
        while not socket_path.exists():
            if proc.poll() is not None:
                stdout, stderr = proc.communicate(timeout=1)
                fail(
                    "mojo_server_exited_early",
                    "The bundled Mojo worker exited before creating its server socket.",
                    returncode=proc.returncode,
                    stdout=stdout.decode(errors="replace")[-2000:],
                    stderr=stderr.decode(errors="replace")[-2000:],
                )
            if time.monotonic() > deadline:
                fail(
                    "mojo_server_socket_timeout",
                    "The bundled Mojo worker did not create its server socket within 15s.",
                    binary=str(binary),
                )
            time.sleep(0.05)

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(str(socket_path))
            ready = recv_frame(sock, timeout_s=5.0)
            if ready.get("status") != "ready":
                fail("mojo_server_bad_handshake", "The bundled Mojo worker sent an invalid handshake.", ready=ready)

            send_frame(
                sock,
                {
                    "engine_type": "monte_carlo",
                    "runs": 100,
                    "seed": 1,
                    "variables": [
                        {
                            "name": "x",
                            "distribution": "fixed",
                            "params": {"value": 100.0},
                        }
                    ],
                    "objective_function": "x",
                    "correlations": [],
                    "scoring": {"expected_value": 1.0, "downside_risk": 0.0},
                },
            )
            result = recv_frame(sock, timeout_s=10.0)

        if "error" in result:
            fail("mojo_server_returned_error", "The bundled Mojo worker returned an engine error.", result=result)
        mean = float(dict(result.get("summary") or {}).get("mean", 0.0))
        if abs(mean - 100.0) > 1e-9:
            fail(
                "mojo_server_wrong_result",
                "The bundled Mojo worker server mode returned an incorrect deterministic result.",
                mean=mean,
                expected=100.0,
            )
        print(json.dumps({"status": "pass", "binary": str(binary), "mean": mean}, sort_keys=True))
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        try:
            socket_path.unlink(missing_ok=True)
        except OSError:
            pass


main()
PY
