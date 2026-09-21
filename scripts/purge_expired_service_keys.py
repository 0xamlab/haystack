"""Purge expired short-lived SERVICE keys from ``api_keys`` -- DRY-RUN by default.

    python -m scripts.purge_expired_service_keys                      # count only (safe)
    python -m scripts.purge_expired_service_keys --execute            # delete, 5,000 per statement
    python -m scripts.purge_expired_service_keys --retention-days 14 --batch-size 1000 --execute

Only rows with ``is_service = true`` whose ``expires_at`` is older than ``now - retention`` (and
that own no device registration) are candidates -- the full safety contract and the reason this
exists are in ``apps/api_server/services/api_key_retention.py``. Human keys, keys without an
expiry and unexpired keys are never touched.

Prints exactly one JSON line on success, e.g.
``{"batch_size": 5000, "batches": 0, "candidates": 20447, "cutoff": "...", "deleted": 0,
"execute": false, "purge_expired_service_keys": "ok"}``; any failure raises and exits non-zero
without it, which is what the scheduled runner (``.github/workflows/db-maintenance.yml``) keys
on. Runs inside the deployed codna-api image, where DATABASE_URL is the app's own Fly secret.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import timedelta
from typing import Any

from apps.api_server.services.api_key_retention import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_RETENTION_DAYS,
    RETENTION_DAYS_ENV,
)


def _non_negative_int(raw: str) -> int:
    value = int(raw)
    if value < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {raw}")
    return value


def _positive_int(raw: str) -> int:
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1, got {raw}")
    return value


def _non_negative_float(raw: str) -> float:
    value = float(raw)
    if value < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {raw}")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Purge expired short-lived service keys from api_keys (dry-run by default)."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="actually delete (default: dry run, count only)",
    )
    parser.add_argument(
        "--retention-days",
        type=_non_negative_int,
        default=None,
        help=(
            "delete only keys expired for longer than this many days "
            f"(default: ${RETENTION_DAYS_ENV} or {DEFAULT_RETENTION_DAYS})"
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=_positive_int,
        default=DEFAULT_BATCH_SIZE,
        help=f"rows per DELETE statement (default {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--pause-s",
        type=_non_negative_float,
        default=0.2,
        help="seconds to sleep between batches so the API keeps its share (default 0.2)",
    )
    return parser


async def run(args: argparse.Namespace) -> dict[str, Any]:
    from apps.api_server.db.session import AsyncSessionLocal, engine
    from apps.api_server.services.api_key_retention import purge_expired_service_keys

    retention = None if args.retention_days is None else timedelta(days=args.retention_days)
    try:
        async with AsyncSessionLocal() as db:
            report = await purge_expired_service_keys(
                db,
                execute=args.execute,
                retention=retention,
                batch_size=args.batch_size,
                pause_s=args.pause_s,
            )
    finally:
        await engine.dispose()
    return {"purge_expired_service_keys": "ok", **report.as_dict()}


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    print(json.dumps(asyncio.run(run(args)), sort_keys=True))


if __name__ == "__main__":
    main()
