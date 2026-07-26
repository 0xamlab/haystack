"""Dev-only license stub — the ONLY place the HS256 dev secret lives.

This module is intentionally isolated so the PRODUCTION build can physically strip it from the
wheel (see ``scripts/strip_dev_stub.py`` / the ``production-wheel`` make target). When it is
absent, ``apps.runtime.license`` degrades to RS256-only automatically (the HS256 dev-stub path
becomes unreachable) — defense-in-depth on top of the runtime ``ALGENTA_LICENSE_RS256_ONLY``
guard, so a shipped artifact does not even CONTAIN the forgeable secret.

Never import this from production code paths without a guarded ``try/except ImportError``.
"""
from __future__ import annotations

# Self-signed local dev secret (HS256). NEVER used for cloud/production validation. Present only in
# dev/test builds; stripped from the production wheel.
DEV_SECRET = "algenta-dev-local-v1-not-for-production"  # noqa: S105
