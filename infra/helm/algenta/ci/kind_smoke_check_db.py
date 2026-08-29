"""Diagnostic-only: reproduces apps/api_server/main.py's /v1/health/ready DB check with a
real traceback on failure, run via `kubectl exec` INTO the live api Pod when
helm-kind-smoke's install fails. Not part of the packaged chart (excluded by .helmignore's
`ci/` entry) and not invoked by the app itself -- see .github/workflows/ci.yml's
"Deep-dive DB connectivity from inside the api Pod" step.

Kept as a real, left-aligned .py file rather than embedded inline in the workflow YAML: an
earlier version of that step wrote this same logic as a multi-line `python -c "..."` block
directly inside a `run: |` step, which broke YAML's literal-block-scalar parsing (its
continuation lines sat at column 0, less indented than the block itself) -- the exact
failure mode a comment elsewhere in ci.yml already warns about for this same reason.
"""

from __future__ import annotations

import asyncio
import traceback


async def main() -> None:
    try:
        from sqlalchemy import text

        from apps.api_server.db.session import AsyncReadSessionLocal

        async with AsyncReadSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        print("DB CHECK: OK")
    except Exception:
        print("DB CHECK FAILED:")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
