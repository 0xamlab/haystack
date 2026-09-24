"""The GPU stage's live throughput, as one tile the Try and LLM tabs share.

The governed-agent Space (the GPU stage) publishes its last measured decode
throughput at ``/api/status``. This module fetches that JSON on a timer, parses
it strictly and renders one tile: the number with its unit, when and where it
was measured, and a link to the live agent. When the endpoint does not answer,
or answers with something that is not a measurement, the tile is the
unavailable card with an error code — never a remembered number without its
stamp.

Status contract (what the GPU stage serves; every field checked here)::

    {"tok_per_s": 41.7, "measured_utc": "2026-09-22 14:02 UTC", "hardware": "NVIDIA L4 · sm_89",
     "model": "Qwen3-1.7B", "lane": "algenta-cuda", "ttft_ms": 212.0, "online": true}

``online: false`` with a ``tok_per_s`` means the lane is held right now and the
number is the last measurement; the tile then says so. Stdlib only; the fetch
is injectable and the default uses ``urllib`` over https.

The tile exists only where the stage is configured: ``configured(env)`` is true
when ``ALGENTA_GPU_STATUS_URL`` names an https endpoint (``status_url(env)``
returns it), and a tab renders no tile otherwise — nothing is polled and no
"unavailable" is shown for a stage that was never wired up. When configured and
not answering, the tile is the quiet neutral one: the code in a neutral chip,
the fetch stamp, no red.
"""

from __future__ import annotations

import html
import json
import logging
import math
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from algenta_spaces import cards, shell
from algenta_spaces.css import rule, stylesheet
from algenta_spaces.runtime import utc_stamp

log = logging.getLogger(__name__)

GOVERNED_AGENT_HOST = "thyn-ai-algenta-governed-agent.hf.space"
STATUS_PATH = "/api/status"
#: The GPU stage's endpoint as published; a Space opts in by naming it in `STATUS_URL_ENV`.
STATUS_URL = f"https://{GOVERNED_AGENT_HOST}{STATUS_PATH}"
STATUS_URL_ENV = "ALGENTA_GPU_STATUS_URL"
OPEN_URL = shell.GOVERNED_AGENT_URL
POLL_S = 60.0
TIMEOUT_S = 5.0
MAX_BODY_BYTES = 64 * 1024

TITLE = "GPU stage"
OPEN_TEXT = "Open the live agent"
OFFLINE_TEXT = "GPU stage offline"
LAST_MEASURED_TEXT = "last measured"
CODE_UNREACHABLE = "gpu_status_unreachable"
CODE_MALFORMED = "gpu_status_malformed"
CODE_NOT_FETCHED = "gpu_status_not_fetched"
HINT_UNREACHABLE = "The GPU stage did not answer, so no throughput is shown."
HINT_MALFORMED = "The GPU stage answered without a measurement, so no throughput is shown."
HINT_NOT_FETCHED = "The GPU stage has not been asked yet."
HINTS: Mapping[str, str] = {
    CODE_UNREACHABLE: HINT_UNREACHABLE,
    CODE_MALFORMED: HINT_MALFORMED,
    CODE_NOT_FETCHED: HINT_NOT_FETCHED,
}

_REQUIRED_TEXT = ("measured_utc", "hardware", "model")


@dataclass(frozen=True)
class GpuStatus:
    tok_per_s: float
    measured_utc: str
    hardware: str
    model: str
    lane: str = ""
    ttft_ms: float | None = None
    online: bool = True


Fetch = Callable[[str, float], bytes]


def urllib_fetch(url: str, timeout_s: float = TIMEOUT_S) -> bytes:
    """GET `url` over https; raises OSError/ValueError on any failure."""
    if urlsplit(url).scheme != "https":
        raise ValueError("the status endpoint must be served over https")
    request = urllib.request.Request(  # noqa: S310 - scheme checked above
        url, headers={"Accept": "application/json", "User-Agent": "algenta-spaces-gpu-status"}
    )
    with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
        if response.status != 200:
            raise urllib.error.HTTPError(url, response.status, "not ok", response.headers, None)
        return response.read(MAX_BODY_BYTES + 1)


def status_url(env: Mapping[str, str] | None = None) -> str:
    """The configured https status endpoint, or an empty string when the stage is not wired up."""
    env = {} if env is None else env
    url = str(env.get(STATUS_URL_ENV, "") or "").strip()
    if not url:
        return ""
    parts = urlsplit(url)
    return url if parts.scheme == "https" and parts.netloc else ""


def configured(env: Mapping[str, str] | None = None) -> bool:
    """True only when `STATUS_URL_ENV` names an https endpoint; without it the tabs draw no tile."""
    return bool(status_url(env))


def _finite_positive(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("tok_per_s is not a number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError("tok_per_s is not a positive finite number")
    return number


def parse_status(body: bytes) -> GpuStatus:
    """The status JSON → `GpuStatus`; ValueError names the first field that is not a measurement."""
    if len(body) > MAX_BODY_BYTES:
        raise ValueError("status body is too large")
    data = json.loads(body.decode("utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("status is not a JSON object")
    tok_per_s = _finite_positive(data.get("tok_per_s"))
    texts: dict[str, str] = {}
    for key in _REQUIRED_TEXT:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} is missing")
        texts[key] = value.strip()
    ttft = data.get("ttft_ms")
    ttft_ms = None if ttft is None else _finite_positive(ttft)
    online = data.get("online", True)
    if not isinstance(online, bool):
        raise ValueError("online is not a boolean")
    lane = data.get("lane", "")
    return GpuStatus(
        tok_per_s=tok_per_s,
        measured_utc=texts["measured_utc"],
        hardware=texts["hardware"],
        model=texts["model"],
        lane=str(lane).strip() if isinstance(lane, str) else "",
        ttft_ms=ttft_ms,
        online=online,
    )


@dataclass(frozen=True)
class Snapshot:
    """What the tile renders: the last good status, or the code that explains its absence."""

    status: GpuStatus | None
    error_code: str
    fetched_utc: str

    @property
    def ok(self) -> bool:
        return self.status is not None


class GpuStatusPoller:
    """Fetch the status every `poll_s` seconds on a daemon thread; `latest()` never blocks long."""

    def __init__(
        self,
        url: str = STATUS_URL,
        *,
        poll_s: float = POLL_S,
        fetch: Fetch = urllib_fetch,
        timeout_s: float = TIMEOUT_S,
        clock: Callable[[], float] = time.time,
    ):
        if poll_s <= 0:
            raise ValueError("poll_s must be positive")
        self.url = url
        self.poll_s = float(poll_s)
        self.timeout_s = float(timeout_s)
        self._fetch = fetch
        self._clock = clock
        self._lock = threading.Lock()
        self._snapshot = Snapshot(None, CODE_NOT_FETCHED, "")
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def refresh(self) -> Snapshot:
        """One fetch; a failure replaces the snapshot with its code (no stale number survives)."""
        stamp = utc_stamp(datetime.fromtimestamp(self._clock(), UTC))
        try:
            body = self._fetch(self.url, self.timeout_s)
        except Exception as exc:  # noqa: BLE001 - every transport failure is one code
            log.warning("gpu status fetch failed: %s: %s", type(exc).__name__, exc)
            snapshot = Snapshot(None, CODE_UNREACHABLE, stamp)
        else:
            try:
                snapshot = Snapshot(parse_status(body), "", stamp)
            except (ValueError, UnicodeDecodeError) as exc:
                log.warning("gpu status malformed: %s", exc)
                snapshot = Snapshot(None, CODE_MALFORMED, stamp)
        with self._lock:
            self._snapshot = snapshot
        return snapshot

    def latest(self) -> Snapshot:
        with self._lock:
            return self._snapshot

    def _loop(self) -> None:
        while not self._stop.wait(self.poll_s):
            self.refresh()

    def start(self) -> None:
        """Fetch once now, then keep fetching on a daemon thread until `stop()`."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
        self.refresh()
        thread = threading.Thread(target=self._loop, name="algenta-gpu-status", daemon=True)
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


_SHARED: GpuStatusPoller | None = None
_SHARED_LOCK = threading.Lock()


def shared_poller(url: str = STATUS_URL) -> GpuStatusPoller:
    """The one poller both tabs read; created (not started) on first use."""
    global _SHARED
    with _SHARED_LOCK:
        if _SHARED is None or _SHARED.url != url:
            _SHARED = GpuStatusPoller(url)
        return _SHARED


def _esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def _chip(text: str) -> str:
    return f'<span class="alg-chip alg-chip-neutral">{_esc(text)}</span>'


def quiet_code_chip(code: str) -> str:
    """The fleet's unavailable chip in its quiet form (`cards.code_chip`): neutral colour, the
    normalised code, and the `data-kind="unavailable">unavailable · <code>` the verifier reads
    — a documented state, not a failure, so nothing turns red."""
    return cards.code_chip(code)


def fmt_tok_s(value: float) -> str:
    return f"{value:,.1f} tok/s"


def _quiet_tile(label: str, code: str, meta: str) -> str:
    """`cards.tile` in its `unavailable` state: an em dash where the number would be, the quiet
    code chip and the provenance in the meta line."""
    return cards.tile(label, "", meta, "unavailable", code=code)


def render_tile(snapshot: Snapshot, *, open_url: str = OPEN_URL) -> str:
    """The GPU stage as one `cards.tile` — the same geometry in every state — plus the link.

    Online: the throughput as the value, the machine, model and `measured <UTC>` as the meta
    line. Held (`online: false`): the last measurement, labelled offline, state `warn`. Not
    answering: the quiet tile — an em dash where the number would be, the code in a neutral
    chip and the fetch stamp in the meta line; hairline border, never red. The endpoint's
    address is configuration, not copy, so it is not printed here.
    """
    status = snapshot.status
    stamp = f" · asked {snapshot.fetched_utc}" if snapshot.fetched_utc else ""
    if status is None:
        code = snapshot.error_code or CODE_NOT_FETCHED
        hint = HINTS.get(code, HINT_NOT_FETCHED)
        tile = _quiet_tile(TITLE, code, f"{OFFLINE_TEXT} — {hint}{stamp}")
    else:
        where = " · ".join(part for part in (status.hardware, status.model, status.lane) if part)
        extra = f" · first token {cards.fmt_ms(status.ttft_ms)}" if status.ttft_ms else ""
        if status.online:
            meta = f"decode throughput · measured {status.measured_utc} · {where}{extra}"
            state = "ok"
        else:
            meta = f"{OFFLINE_TEXT} · {LAST_MEASURED_TEXT} {status.measured_utc} · {where}{extra}"
            state = "warn"
        tile = cards.tile(TITLE, fmt_tok_s(status.tok_per_s), meta=meta, state=state)
    link = f'<a class="alg-gpu-open" href="{_esc(open_url)}" rel="noopener">{OPEN_TEXT}</a>'
    kind = "ok" if status else "unavailable"
    return f'<div class="alg-gpu-tile" data-kind="{kind}">{tile}{link}</div>'


# alg-gpu-* classes only; css.rule() repeats each class four times. The tile is the shared
# `alg-stat` (cards.CARD_CSS); the open link is a 44 px pill: the mono line (20 px) plus
# 2 x 12 px padding, all on the 8-pt scale.
GPU_CSS = stylesheet(
    rule(
        "alg-gpu-tile", "display: flex; flex-direction: column; gap: 8px; align-items: flex-start;"
    ),
    rule("alg-gpu-tile", "align-self: stretch;", suffix=" .alg-stat"),
    rule(
        "alg-gpu-open",
        "display: inline-block; font-family: var(--alg-font); font-size: var(--alg-mono-size);"
        " line-height: var(--alg-mono-line); color: var(--alg-text); text-decoration: none;"
        " border: 1px solid var(--alg-hairline); border-radius: var(--alg-radius-pill);"
        " padding: 12px 16px;",
    ),
    rule("alg-gpu-open", "border-color: var(--alg-text-2);", suffix=":hover"),
    rule(
        "alg-gpu-open",
        "outline: 2px solid var(--alg-accent-to); outline-offset: 2px;"
        " border-radius: var(--alg-radius-pill);",
        suffix=":focus-visible",
    ),
)
