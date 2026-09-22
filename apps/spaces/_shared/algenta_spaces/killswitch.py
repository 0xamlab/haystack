"""A kill switch the fleet can flip without a redeploy: one public `flags.json`, polled.

The flag file lives in a public Dataset repo and maps feature names to booleans,
either flat (`{"provider": true}`) or under a `flags` key. `KillSwitch` polls it
every `poll_s` seconds with `If-None-Match`, so an unchanged file costs one
304. `enabled(feature)` is what every lane asks before it spends.

Two failure modes, deliberately different:

* **Reads fail open.** If the file cannot be fetched, features that only read
  (a kernel call, a parity check, a leaderboard) keep their last known value, or
  stay on when nothing was ever fetched — a broken flag file must not take the
  demo down.
* **Spend fails closed.** Features that cost money on every call (the
  Inference-Providers lane, the GPU lane) keep their last known value through
  `max_missed` consecutive failed polls and are then switched **off** until a
  poll succeeds again. A flag file that has been unreachable for over three
  minutes is indistinguishable from an operator who cannot reach us either, so
  the expensive lanes stop.

An unknown feature is on unless the file says otherwise. `start()` polls once
synchronously before the background thread begins, so a started switch never
answers from an empty state. Stdlib only; `fetch` is injectable and the default
uses `urllib` over https.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from .runtime import utc_stamp

log = logging.getLogger(__name__)

DEFAULT_POLL_S = 60.0
DEFAULT_MAX_MISSED = 3
DEFAULT_TIMEOUT_S = 5.0
DEFAULT_SPEND: frozenset[str] = frozenset({"provider", "gpu"})
FLAGS_KEY = "flags"
NOT_MODIFIED = 304


@dataclass(frozen=True)
class FetchResult:
    status: int
    body: bytes | None
    etag: str | None


Fetch = Callable[[str, str | None], FetchResult]


def urllib_fetch(
    url: str, etag: str | None, *, timeout_s: float = DEFAULT_TIMEOUT_S
) -> FetchResult:
    """GET `url` over https with `If-None-Match`; a 304 is `FetchResult(304, None, etag)`."""
    if urlsplit(url).scheme != "https":
        raise ValueError("the flag file must be served over https")
    headers = {"Accept": "application/json", "User-Agent": "algenta-spaces-killswitch"}
    if etag:
        headers["If-None-Match"] = etag
    # S310: the scheme is checked above, so only https ever reaches urlopen.
    request = urllib.request.Request(url, headers=headers, method="GET")  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
            return FetchResult(
                response.status, response.read(), response.headers.get("ETag") or None
            )
    except urllib.error.HTTPError as exc:
        if exc.code == NOT_MODIFIED:
            return FetchResult(NOT_MODIFIED, None, exc.headers.get("ETag") or etag)
        return FetchResult(exc.code, None, None)


def parse_flags(body: bytes) -> dict[str, bool]:
    """The feature → bool mapping in `body`; raises ValueError for anything else."""
    data = json.loads(body.decode("utf-8"))
    if isinstance(data, Mapping) and isinstance(data.get(FLAGS_KEY), Mapping):
        data = data[FLAGS_KEY]
    if not isinstance(data, Mapping):
        raise ValueError("the flag file is not a JSON object")
    flags: dict[str, bool] = {}
    for name, value in data.items():
        if isinstance(value, bool):
            flags[str(name)] = value
    return flags


class KillSwitch:
    def __init__(
        self,
        url: str,
        *,
        poll_s: float = DEFAULT_POLL_S,
        fetch: Fetch = urllib_fetch,
        spend_features: Iterable[str] = DEFAULT_SPEND,
        max_missed: int = DEFAULT_MAX_MISSED,
        clock: Callable[[], float] = time.time,
    ):
        if poll_s <= 0:
            raise ValueError("poll_s must be positive")
        if max_missed < 0:
            raise ValueError("max_missed cannot be negative")
        self.url = url
        self.poll_s = float(poll_s)
        self.spend_features = frozenset(spend_features)
        self.max_missed = max_missed
        self._fetch = fetch
        self._clock = clock
        self._lock = threading.Lock()
        self._flags: dict[str, bool] = {}
        self._etag: str | None = None
        self._missed = 0
        self._polls = 0
        self._last_ok: float | None = None
        self._last_error = ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # -- polling ------------------------------------------------------------

    def refresh(self) -> bool:
        """One poll. True when the file was fetched or unchanged, False when the poll failed."""
        with self._lock:
            etag = self._etag
        try:
            result = self._fetch(self.url, etag)
            if result.status == NOT_MODIFIED:
                flags, new_etag = None, result.etag or etag
            elif 200 <= result.status < 300 and result.body is not None:
                flags, new_etag = parse_flags(result.body), result.etag
            else:
                raise ValueError(f"HTTP {result.status}")
        except Exception as exc:
            with self._lock:
                self._polls += 1
                self._missed += 1
                self._last_error = f"{type(exc).__name__}: {exc}"
                missed = self._missed
            log.warning("kill switch poll failed (%d in a row): %s", missed, exc)
            return False
        with self._lock:
            self._polls += 1
            self._missed = 0
            self._last_ok = self._clock()
            self._last_error = ""
            self._etag = new_etag
            if flags is not None:
                self._flags = flags
        return True

    def _loop(self) -> None:
        while not self._stop.wait(self.poll_s):
            self.refresh()

    def start(self) -> None:
        """Poll once now, then keep polling on a daemon thread until `stop()`."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
        self.refresh()
        thread = threading.Thread(target=self._loop, name="algenta-killswitch", daemon=True)
        with self._lock:
            self._thread = thread
        thread.start()

    def stop(self, timeout_s: float = 5.0) -> None:
        self._stop.set()
        with self._lock:
            thread = self._thread
            self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout_s)

    @property
    def running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    # -- reads --------------------------------------------------------------

    @property
    def degraded(self) -> bool:
        """True while the last poll failed."""
        with self._lock:
            return self._missed > 0

    @property
    def spend_locked(self) -> bool:
        """True once more than `max_missed` polls in a row have failed."""
        with self._lock:
            return self._missed > self.max_missed

    def enabled(self, feature: str) -> bool:
        """Whether a feature may run right now.

        Spend features (provider lane, GPU lane) are fail-closed in both directions: they stay
        OFF until the flag file has been fetched successfully at least once (a fresh container
        must not spend while the operator's kill file is unreachable) and go OFF again once more
        than `max_missed` polls in a row have failed. Every other feature defaults to ON.
        """
        with self._lock:
            if feature in self.spend_features:
                if self._last_ok is None or self._missed > self.max_missed:
                    return False
            return self._flags.get(feature, True)

    def flags(self) -> dict[str, bool]:
        with self._lock:
            return dict(self._flags)

    def snapshot(self) -> dict[str, Any]:
        """Plain data for `/health`: flags, poll counters, staleness, the spend lock."""
        with self._lock:
            last_ok = self._last_ok
            return {
                "url": self.url,
                "flags": dict(self._flags),
                "etag": self._etag,
                "polls": self._polls,
                "missed": self._missed,
                "degraded": self._missed > 0,
                "spend_locked": self._missed > self.max_missed,
                "spend_features": sorted(self.spend_features),
                "last_ok_utc": utc_stamp(_utc(last_ok)) if last_ok is not None else None,
                "last_error": self._last_error,
                "running": self._thread is not None and self._thread.is_alive(),
            }


def _utc(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, UTC)
