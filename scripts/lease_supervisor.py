from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a child process while a lease file matches the expected token."
    )
    parser.add_argument("--cwd", required=True, help="Working directory for the child process.")
    parser.add_argument(
        "--stdout-log",
        required=True,
        help="File path that receives merged stdout/stderr for the child process.",
    )
    parser.add_argument("--lease-file", required=True, help="Lease file that controls liveness.")
    parser.add_argument("--lease-token", required=True, help="Expected lease token content.")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv[1:])
    if not args.command:
        parser.error("a child command is required after '--'")
    if args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("a child command is required after '--'")
    return args


def lease_matches(path: Path, expected_token: str) -> bool:
    try:
        return path.read_text(encoding="utf-8").strip() == expected_token
    except FileNotFoundError:
        return False


def terminate_child(process: subprocess.Popen[bytes], *, timeout_seconds: float = 5.0) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return
        time.sleep(0.1)
    process.kill()
    process.wait(timeout=5)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    lease_path = Path(args.lease_file)
    if not lease_matches(lease_path, args.lease_token):
        print("lease file does not contain the expected token", file=sys.stderr)
        return 2

    stop_requested = False

    def _request_stop(_signum: int, _frame: object) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    log_path = Path(args.stdout_log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log_file:
        child = subprocess.Popen(
            args.command,
            cwd=args.cwd,
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        try:
            while child.poll() is None:
                if stop_requested or not lease_matches(lease_path, args.lease_token):
                    terminate_child(child)
                    break
                time.sleep(0.25)
        finally:
            if child.poll() is None:
                terminate_child(child)

    return child.returncode or 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
