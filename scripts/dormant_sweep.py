"""Dormant-account sweep — run DAILY from a scheduler (Fly scheduled machine / cron).

DRY-RUN by default: reports what WOULD happen (counts per stage) and touches nothing. Pass
--execute to actually send the T-30/14/7/1 warning emails (via Resend) and delete accounts that
hit the 365-day deadline (never a paid subscriber). Requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
+ RESEND_API_KEY in the environment.

    python -m scripts.dormant_sweep            # dry run (safe)
    python -m scripts.dormant_sweep --execute  # live: emails + deletions
"""

from __future__ import annotations

import argparse
import asyncio
import json


async def _main(execute: bool) -> None:
    from apps.api_server.db.session import AsyncSessionLocal
    from apps.api_server.services.dormant_accounts import run_sweep

    async with AsyncSessionLocal() as db:
        summary = await run_sweep(db, execute=execute)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dormant-account 12-month sweep.")
    parser.add_argument("--execute", action="store_true", help="send emails + delete (default: dry run)")
    args = parser.parse_args()
    asyncio.run(_main(args.execute))
