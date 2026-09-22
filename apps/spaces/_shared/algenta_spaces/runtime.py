"""Small runtime facts shared by several modules: UTC stamps, pinned versions, sha stamps.

Kept separate so `shell`, `bench` and `facts` can all use them without importing
each other.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

_SHA_RE = re.compile(r"^[0-9a-f]{7,64}$")
STAMP_DEFAULT = "dev"


def utc_stamp(now: datetime | None = None) -> str:
    """`2026-09-22 14:02 UTC` for the given instant (default: now)."""
    moment = datetime.now(UTC) if now is None else now.astimezone(UTC)
    return moment.strftime("%Y-%m-%d %H:%M UTC")


def pinned_versions(dist_names: Iterable[str]) -> dict[str, str | None]:
    """Installed version per distribution name, `None` when it is not installed."""
    out: dict[str, str | None] = {}
    for name in dist_names:
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = None
    return out


def is_sha(text: str) -> bool:
    """True for a lowercase hex git object id of 7 to 64 characters."""
    return bool(_SHA_RE.match(text))


def read_stamp(path: Path | str, default: str = STAMP_DEFAULT) -> str:
    """The sha written in a stamp file, or `default` when absent or malformed."""
    try:
        text = Path(path).read_text(encoding="utf-8").strip().lower()
    except OSError:
        return default
    return text if is_sha(text) else default
