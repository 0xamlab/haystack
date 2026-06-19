"""
Import a customer-agnostic capability-plane bundle into the Algenta control plane.

The input payload must conform to the canonical capability-plane import schema exposed by
`apps.api_server.services.capability_plane_importer`. The command accepts a JSON file or
reads the payload from stdin when `--file` is omitted.
"""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.api_server.db.session import AsyncSessionLocal
from apps.api_server.services.capability_plane_importer import (
    CapabilityPlaneImportSummary,
    import_capability_plane_bundle,
    load_capability_plane_import_bundle,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import a capability-plane bundle into the Algenta control plane.",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Path to a JSON capability-plane import bundle. Reads stdin when omitted.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and summarize the import without persisting changes.",
    )
    parser.add_argument(
        "--format",
        choices=("env", "json"),
        default="env",
        help="Output format for the import summary.",
    )
    return parser


def _read_payload_text(payload_path: Path | None, *, stdin_text: str | None = None) -> str:
    if payload_path is not None:
        return payload_path.read_text(encoding="utf-8")
    text = sys.stdin.read() if stdin_text is None else stdin_text
    if not text.strip():
        raise ValueError("Capability-plane import payload is empty.")
    return text


def _parse_payload_text(payload_text: str) -> dict[str, object]:
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Capability-plane import payload is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Capability-plane import payload must be a JSON object.")
    return payload


def _render_summary(summary: CapabilityPlaneImportSummary, *, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True)
    lines = [
        "ALGENTA_CAPABILITY_IMPORT_READY=1",
        f"CAPABILITY_IMPORT_DRY_RUN={'1' if summary.dry_run else '0'}",
        f"CAPABILITY_IMPORT_PROVIDERS_UPSERTED={summary.providers_upserted}",
        f"CAPABILITY_IMPORT_PROFILES_UPSERTED={summary.profiles_upserted}",
        f"CAPABILITY_IMPORT_BINDINGS_UPSERTED={summary.bindings_upserted}",
        f"CAPABILITY_IMPORT_SNAPSHOTS_INSERTED={summary.snapshots_inserted}",
        f"CAPABILITY_IMPORT_ROUTING_OUTCOMES_INSERTED={summary.routing_outcomes_inserted}",
    ]
    return "\n".join(lines)


async def _import_payload(
    payload: dict[str, object],
    *,
    dry_run: bool,
) -> CapabilityPlaneImportSummary:
    bundle = load_capability_plane_import_bundle(payload)
    async with AsyncSessionLocal() as session:
        return await import_capability_plane_bundle(session, bundle, dry_run=dry_run)


async def _main_async(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    payload_text = _read_payload_text(args.file)
    payload = _parse_payload_text(payload_text)
    summary = await _import_payload(payload, dry_run=args.dry_run)
    print(_render_summary(summary, output_format=args.format))
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_main_async(argv))


if __name__ == "__main__":
    raise SystemExit(main())
