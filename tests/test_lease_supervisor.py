from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEASE_SUPERVISOR_SCRIPT = ROOT / "scripts" / "lease_supervisor.py"


def test_lease_supervisor_stops_child_when_lease_is_removed(tmp_path: Path) -> None:
    lease_path = tmp_path / "service.lease"
    lease_token = "token-123"
    lease_path.write_text(lease_token, encoding="utf-8")
    log_path = tmp_path / "service.log"
    ready_path = tmp_path / "ready.txt"
    child_pid_path = tmp_path / "child.pid"

    supervisor = subprocess.Popen(
        [
            sys.executable,
            str(LEASE_SUPERVISOR_SCRIPT),
            "--cwd",
            str(ROOT),
            "--stdout-log",
            str(log_path),
            "--lease-file",
            str(lease_path),
            "--lease-token",
            lease_token,
            "--",
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                f"Path({str(child_pid_path)!r}).write_text(str(__import__('os').getpid()), encoding='utf-8'); "
                f"Path({str(ready_path)!r}).write_text('ready', encoding='utf-8'); "
                "import time; time.sleep(30)"
            ),
        ],
        cwd=ROOT,
    )

    try:
        for _ in range(30):
            if ready_path.exists() and child_pid_path.exists():
                break
            time.sleep(0.1)
        assert ready_path.read_text(encoding="utf-8") == "ready"
        child_pid = int(child_pid_path.read_text(encoding="utf-8"))
        os.kill(child_pid, 0)

        lease_path.unlink()
        supervisor.wait(timeout=10)

        for _ in range(30):
            try:
                os.kill(child_pid, 0)
            except OSError:
                break
            time.sleep(0.1)
        else:
            os.kill(child_pid, signal.SIGKILL)
            raise AssertionError(f"child {child_pid} remained alive after lease removal")
    finally:
        if supervisor.poll() is None:
            supervisor.terminate()
            supervisor.wait(timeout=5)


def test_lease_supervisor_rejects_mismatched_initial_lease(tmp_path: Path) -> None:
    lease_path = tmp_path / "service.lease"
    lease_path.write_text("wrong-token", encoding="utf-8")
    log_path = tmp_path / "service.log"

    result = subprocess.run(
        [
            sys.executable,
            str(LEASE_SUPERVISOR_SCRIPT),
            "--cwd",
            str(ROOT),
            "--stdout-log",
            str(log_path),
            "--lease-file",
            str(lease_path),
            "--lease-token",
            "expected-token",
            "--",
            sys.executable,
            "-c",
            "print('never')",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "lease file does not contain the expected token" in result.stderr


def test_lease_supervisor_stops_child_when_lease_token_changes(tmp_path: Path) -> None:
    lease_path = tmp_path / "service.lease"
    lease_token = "token-123"
    lease_path.write_text(lease_token, encoding="utf-8")
    log_path = tmp_path / "service.log"
    ready_path = tmp_path / "ready.txt"
    child_pid_path = tmp_path / "child.pid"

    supervisor = subprocess.Popen(
        [
            sys.executable,
            str(LEASE_SUPERVISOR_SCRIPT),
            "--cwd",
            str(ROOT),
            "--stdout-log",
            str(log_path),
            "--lease-file",
            str(lease_path),
            "--lease-token",
            lease_token,
            "--",
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                f"Path({str(child_pid_path)!r}).write_text(str(__import__('os').getpid()), encoding='utf-8'); "
                f"Path({str(ready_path)!r}).write_text('ready', encoding='utf-8'); "
                "import time; time.sleep(30)"
            ),
        ],
        cwd=ROOT,
    )

    try:
        for _ in range(30):
            if ready_path.exists() and child_pid_path.exists():
                break
            time.sleep(0.1)
        assert ready_path.read_text(encoding="utf-8") == "ready"
        child_pid = int(child_pid_path.read_text(encoding="utf-8"))
        os.kill(child_pid, 0)

        lease_path.write_text("replacement-token", encoding="utf-8")
        supervisor.wait(timeout=10)

        for _ in range(30):
            try:
                os.kill(child_pid, 0)
            except OSError:
                break
            time.sleep(0.1)
        else:
            os.kill(child_pid, signal.SIGKILL)
            raise AssertionError(f"child {child_pid} remained alive after lease token change")
    finally:
        if supervisor.poll() is None:
            supervisor.terminate()
            supervisor.wait(timeout=5)
