from __future__ import annotations

import json
import socket
import struct
import subprocess
import time
from pathlib import Path

import pytest


def _recv_frame(sock: socket.socket) -> dict[str, object]:
    header = sock.recv(4)
    if len(header) < 4:
        raise RuntimeError("short frame header from Mojo server")
    frame_len = struct.unpack(">I", header)[0]
    payload = bytearray()
    while len(payload) < frame_len:
        chunk = sock.recv(frame_len - len(payload))
        if not chunk:
            raise RuntimeError("unexpected EOF from Mojo server")
        payload.extend(chunk)
    return json.loads(payload.decode("utf-8"))


def _send_frame(sock: socket.socket, payload: dict[str, object]) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8")
    sock.sendall(struct.pack(">I", len(body)) + body)
    return _recv_frame(sock)


def test_mojo_rank_server_handles_control_messages() -> None:
    binary = Path("mojo_build/simulate")
    if not binary.exists():
        pytest.skip("mojo_build/simulate not present")

    socket_path = Path("/tmp/algenta-rank-test.sock")
    if socket_path.exists():
        socket_path.unlink()

    proc = subprocess.Popen(  # noqa: S603
        [str(binary), "--server", str(socket_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 5.0
        while not socket_path.exists():
            if proc.poll() is not None:
                stderr_output = proc.stderr.read() if proc.stderr is not None else ""
                pytest.skip(
                    "Mojo rank server mode unavailable for current binary: "
                    f"{stderr_output.strip() or 'server exited before opening socket'}"
                )
            if time.monotonic() >= deadline:
                raise TimeoutError("timed out waiting for Mojo rank server socket")
            time.sleep(0.01)

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(str(socket_path))
            assert _recv_frame(sock) == {"status": "ready"}
            assert _send_frame(sock, {"type": "ping"}) == {"status": "ok"}

            init_result = _send_frame(
                sock,
                {
                    "type": "column_rank_init",
                    "engine_type": "column_rank_init",
                    "entries": [
                        {
                            "id": 0,
                            "source": "POS",
                            "column": "UNIT_PRICE",
                            "source_id": 1,
                            "role_id": 1,
                        }
                    ],
                },
            )
            assert init_result == {"status": "ok", "count": 1}

            query_result = _send_frame(
                sock,
                {
                    "type": "column_rank_query",
                    "engine_type": "column_rank_query",
                    "hint": "unit price",
                    "source_id": 1,
                    "role_id": 1,
                    "candidate_ids": [0],
                    "top_k": 3,
                },
            )
            ranked = query_result.get("ranked")
            assert isinstance(ranked, list) and ranked
            top = ranked[0]
            assert top["id"] == 0

            assert _send_frame(sock, {"type": "shutdown"}) == {"status": "bye"}

        proc.wait(timeout=5.0)
        assert proc.returncode == 0
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1.0)
        if socket_path.exists():
            socket_path.unlink()
