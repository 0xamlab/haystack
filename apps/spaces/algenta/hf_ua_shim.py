"""A one-line user-agent fix for `kernels` 0.17.1 on `huggingface_hub` 1.x — applied on import.

`kernels.install_kernel` and `get_kernel` pass an empty `user_agent` string to
`huggingface_hub`, whose `_http_user_agent` then appends `"; " + ""` and returns a
header ending in `"; "`. h11 refuses a header value with trailing whitespace, so every
Hub request from `kernels` fails before it leaves the process. The fix is to strip
the trailing separator from the composed header; nothing else about the header changes.

Import this module before `kernels` — in the image bake step and in `app.py`. It is
idempotent: applying it twice leaves one wrapper in place. Without `huggingface_hub`
installed it does nothing and says so through `apply()`'s return value.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

log = logging.getLogger(__name__)

SEPARATOR = "; "
_MARK = "_algenta_ua_shim"


def clean_user_agent(text: str) -> str:
    """`"kernels/0.17.1; "` -> `"kernels/0.17.1"`: drop trailing separators and spaces."""
    return text.rstrip(SEPARATOR)


def wrap(original: Callable[..., str]) -> Callable[..., str]:
    """The patched `_http_user_agent`: the original's answer with its tail cleaned."""
    if getattr(original, _MARK, False):
        return original

    def patched(
        *,
        library_name: str | None = None,
        library_version: str | None = None,
        user_agent: dict | str | None = None,
    ) -> str:
        return clean_user_agent(
            original(
                library_name=library_name,
                library_version=library_version,
                user_agent=user_agent,
            )
        )

    setattr(patched, _MARK, True)
    setattr(patched, "__wrapped__", original)  # noqa: B010 - mirrors functools.wraps
    return patched


def apply() -> bool:
    """Install the wrapper on `huggingface_hub.utils._headers`; False when the module is absent."""
    try:
        from huggingface_hub.utils import _headers
    except ImportError:
        log.debug("huggingface_hub is not installed; the user-agent shim is idle")
        return False
    current = _headers._http_user_agent
    if getattr(current, _MARK, False):
        return True
    _headers._http_user_agent = wrap(current)
    log.debug("user-agent shim applied to huggingface_hub %s", _hub_version())
    return True


def applied() -> bool:
    try:
        from huggingface_hub.utils import _headers
    except ImportError:
        return False
    return bool(getattr(_headers._http_user_agent, _MARK, False))


def _hub_version() -> str:
    try:
        import huggingface_hub

        return str(huggingface_hub.__version__)
    except ImportError:  # pragma: no cover - guarded by the caller
        return "absent"


APPLIED = apply()
