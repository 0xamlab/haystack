from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch a detached child process and print its PID."
    )
    parser.add_argument("--cwd", required=True, help="Working directory for the child process.")
    parser.add_argument(
        "--stdout-log",
        required=True,
        help="File path that receives merged stdout/stderr for the child process.",
    )
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Additional environment variable overrides for the child process.",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv[1:])
    if not args.command:
        parser.error("a child command is required after '--'")
    if args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("a child command is required after '--'")
    return args


def build_env(overrides: list[str]) -> dict[str, str]:
    env = os.environ.copy()
    for entry in overrides:
        if "=" not in entry:
            raise ValueError(f"invalid env override {entry!r}; expected KEY=VALUE")
        key, value = entry.split("=", 1)
        if not key or any(ch.isspace() for ch in key):
            raise ValueError(f"invalid env override key {key!r}")
        env[key] = value
    return env


def main(argv: list[str]) -> int:
    try:
        args = parse_args(argv)
        log_path = Path(args.stdout_log)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        env = build_env(args.env)
        with log_path.open("ab") as log_file:
            process = subprocess.Popen(
                args.command,
                cwd=args.cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(process.pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
