from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DETACH_PROCESS_SCRIPT = ROOT / "scripts" / "detach_process.py"


def test_detach_process_launches_child_in_new_session(tmp_path: Path) -> None:
    log_path = tmp_path / "child.log"
    ready_path = tmp_path / "ready.txt"

    result = subprocess.run(
        [
            sys.executable,
            str(DETACH_PROCESS_SCRIPT),
            "--cwd",
            str(ROOT),
            "--stdout-log",
            str(log_path),
            "--",
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                f"Path({str(ready_path)!r}).write_text('ready', encoding='utf-8'); "
                "import time; time.sleep(30)"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    pid = int(result.stdout.strip())

    for _ in range(20):
        if ready_path.exists():
            break
        time.sleep(0.1)
    assert ready_path.read_text(encoding="utf-8") == "ready"
    os.kill(pid, 0)

    os.kill(pid, signal.SIGTERM)
    for _ in range(20):
        try:
            os.kill(pid, 0)
        except OSError:
            break
        time.sleep(0.1)
    else:
        os.kill(pid, signal.SIGKILL)
        raise AssertionError(f"detached child {pid} did not terminate after SIGTERM")


def test_detach_process_rejects_invalid_env_override(tmp_path: Path) -> None:
    log_path = tmp_path / "child.log"

    result = subprocess.run(
        [
            sys.executable,
            str(DETACH_PROCESS_SCRIPT),
            "--cwd",
            str(ROOT),
            "--stdout-log",
            str(log_path),
            "--env",
            "NOT VALID",
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
    assert "invalid env override" in result.stderr
