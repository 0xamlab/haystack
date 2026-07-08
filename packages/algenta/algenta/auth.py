"""Read cached credentials from `algenta login` (env override → ~/.algenta/…). No engine/native import."""
from __future__ import annotations

import os

from algenta import paths


def _read_file(path: str) -> str | None:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip() or None
    return None


def read_api_key() -> str | None:
    """The Algenta API key: $ALGENTA_API_KEY, else the cached key from `algenta login`."""
    return (os.environ.get("ALGENTA_API_KEY") or "").strip() or _read_file(paths.api_key_path())


def read_token() -> str | None:
    """The control-plane auth token: $ALGENTA_TOKEN, else the cached login token, else the API key."""
    return (os.environ.get("ALGENTA_TOKEN") or "").strip() or _read_file(paths.token_path()) or read_api_key()


def is_logged_in() -> bool:
    return bool(read_api_key())
