"""Parent-side arena client — runs duel cells in the arena interpreter.

The main app (CPython 3.14) cannot import the pinned arena incumbents
(ruptures<3.14, numba, ...), so each duel runs in the arena interpreter
(CPython 3.12 venv) via arena_runner.py. This module spawns that subprocess,
streams its PROGRESS lines to the UI, and reconstructs the typed DuelOutcome
from the result JSON. All failures are explicit: an unavailable interpreter
or a crashed runner produces an error card with the reason — never a traceback,
never a canned number.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable

from arena.harness import DuelOutcome, LaneTiming, hardware_footer

DEFAULT_ARENA_PYTHON = "/opt/arena/bin/python"
RUNNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arena_runner.py")
SPACE_DIR = os.path.dirname(os.path.abspath(__file__))


class ArenaUnavailable(RuntimeError):
    """The arena interpreter (CPython 3.12 + wheels + incumbents) is not installed."""


def arena_python() -> str:
    path = os.environ.get("ARENA_PYTHON", DEFAULT_ARENA_PYTHON)
    if not os.path.isfile(path) and not os.access(path, os.X_OK):
        raise ArenaUnavailable(
            f"arena interpreter not found at {path} — the Space image builds it at "
            "/opt/arena (CPython 3.12 + arena-wheels); locally, create a 3.12 venv and "
            "point ARENA_PYTHON at its python"
        )
    return path


def arena_status() -> str:
    """Human-readable availability of the arena interpreter (for the UI badge)."""
    try:
        path = arena_python()
    except ArenaUnavailable as exc:
        return f"unavailable: {exc}"
    return f"ready: {path}"


def reconstruct_outcome(data: dict) -> DuelOutcome:
    lanes = [LaneTiming(**lane) for lane in data.pop("lanes", [])]
    outcome = DuelOutcome(**data)
    outcome.lanes = lanes
    return outcome


def run_duel(
    duel_id: str,
    size_key: str,
    progress: Callable[[str], None] | None = None,
    timeout_s: float = 300.0,
) -> DuelOutcome:
    """Run one duel cell in the arena interpreter and return the typed outcome.

    Raises ArenaUnavailable before spawning if the interpreter is missing.
    A runner crash / timeout returns a synthetic *error* outcome (error card).
    """
    from arena.duels import DUELS_BY_ID

    duel = DUELS_BY_ID[duel_id]
    py = arena_python()
    fd, result_path = tempfile.mkstemp(prefix="arena_result_", suffix=".json")
    os.close(fd)
    os.unlink(result_path)  # the runner creates it on success only

    cmd = [py, RUNNER, "--duel", duel_id, "--size", size_key, "--result", result_path]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=SPACE_DIR,
        env=env,
    )

    lines: queue.Queue[str | None] = queue.Queue()

    def reader() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.put(line.rstrip("\n"))
        lines.put(None)

    threading.Thread(target=reader, daemon=True).start()

    deadline = time.perf_counter() + timeout_s
    result_json: dict | None = None
    error_msg: str | None = None
    saw_eof = False

    while True:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            proc.kill()
            error_msg = f"arena runner timed out after {timeout_s:.0f}s — killed"
            break
        try:
            line = lines.get(timeout=min(0.5, max(remaining, 0.05)))
        except queue.Empty:
            if proc.poll() is not None and not saw_eof:
                continue
            continue
        if line is None:
            saw_eof = True
            break
        if line.startswith("PROGRESS "):
            if progress is not None:
                progress(line[len("PROGRESS ") :])
        elif line.startswith("RESULT "):
            path = line[len("RESULT ") :].strip()
            try:
                with open(path, encoding="utf-8") as fh:
                    result_json = json.load(fh)
            except (OSError, ValueError) as exc:
                error_msg = f"runner reported a result but it could not be read: {exc}"
        elif line.startswith("ERROR "):
            error_msg = line[len("ERROR ") :]
        else:
            # Non-protocol stdout (library warnings etc.) — surface as progress.
            if progress is not None and line.strip():
                progress(line)

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    if result_json is None and error_msg is None:
        error_msg = f"arena runner exited ({proc.returncode}) without a result"

    if result_json is not None:
        try:
            return reconstruct_outcome(result_json)
        except (TypeError, KeyError) as exc:
            error_msg = f"runner outcome could not be decoded: {exc}"

    return DuelOutcome(
        duel_id=duel.duel_id,
        duel_title=duel.title,
        size_key=size_key,
        size_label=duel.size_label(size_key),
        status="error",
        held_reason=error_msg or "arena runner failed",
        hardware=hardware_footer(),
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    )
