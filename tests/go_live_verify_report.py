from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tests.go_live_verify import (
    DEFAULT_REPORT_OUTPUT,
    DEFAULT_SUMMARY_OUTPUT,
    render_go_live_verify_markdown_report,
    write_go_live_verify_markdown_report,
)


def load_go_live_verify_summary(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render the machine-readable go-live verifier summary as Markdown."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_SUMMARY_OUTPUT,
        help=f"Go-live verifier summary JSON path (default: {DEFAULT_SUMMARY_OUTPUT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "Optional file path to write the Markdown report to instead of stdout. "
            f"The canonical verifier run keeps {DEFAULT_REPORT_OUTPUT} synced automatically."
        ),
    )
    args = parser.parse_args(argv)

    summary = load_go_live_verify_summary(args.input)
    rendered = render_go_live_verify_markdown_report(summary)
    if args.output is None:
        print(rendered)
    else:
        write_go_live_verify_markdown_report(summary, output_path=args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
