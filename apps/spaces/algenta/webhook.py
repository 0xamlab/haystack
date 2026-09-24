"""The engine's webhook, received by this Space — the last hop of a governed execution.

``execute_decision`` makes the hosted engine POST the decision to a webhook URL
and waits for the answer before it returns the receipt (``delivered`` when this
Space answered 2xx, ``failed`` otherwise). The flagship passes its own public
address plus a per-boot nonce (``https://<SPACE_HOST>/hook/<nonce>``), mounts
the route beside Gradio and shows the engine's POST body next to the receipt —
end to end, nothing staged.

**The engine's decision webhook carries no signature.** ``apps/api_server/routers/
decisions.py`` sends the payload as a plain JSON POST (the HMAC header belongs to
the job webhooks of ``webhook_service.py``, a different route), so nothing on the
wire proves who sent it. What this receiver verifies instead, all of it before a
POST is recorded:

* **the nonce** — the path segment, compared in constant time, never published:
  ``/health`` and the receipt card name the route's prefix and the host, the
  nonce is known to this process and the engine alone;
* **the session** — ``decision_id`` names a decision this process logged in this
  boot (``Hook.expect`` is armed by the handler right after ``log_decision`` and
  disarmed by ``Hook.settle`` when ``execute_decision`` returns), and no POST has
  been accepted for it since it was armed;
* **the integrity block** — ``policy_snapshot_id``, ``schema_snapshot_id`` and
  ``manifest_version`` equal what ``log_decision`` returned for that decision;
* **the summary** — the body's ``decision.chosen_action`` and ``decision.confidence``
  are the ones this Space logged, and the body's ``event`` is the engine's
  ``decision.execute``.

Anything else — a wrong nonce, an oversized or non-JSON body, an unknown, settled
or already-served decision, a mismatching block — answers **400 with one identical
body** (``{"received": false}``: no oracle says which check failed), is logged
server-side with its reason and kept as a ``Rejection`` so the receipt can say
``unexpected POST · rejected``. An accepted POST answers 200. The engine marks the
execution ``failed`` when this Space refuses, which the receipt then paints red:
a POST this Space could not verify is never a delivery.

FastAPI (bundled with gradio) is optional at import: without it ``build_router``
raises, everything else is stdlib.
"""

from __future__ import annotations

import hmac
import json
import logging
import math
import os
import secrets
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from algenta_spaces import hosted_api
from algenta_spaces.hosted_api import WebhookEvent
from algenta_spaces.runtime import utc_stamp

try:  # resolved at module level so FastAPI can read the route's annotations
    from fastapi import APIRouter, Request
    from fastapi.responses import JSONResponse
except ImportError:  # pragma: no cover - the image ships gradio, which ships fastapi
    APIRouter = Request = JSONResponse = None  # type: ignore[assignment,misc]

log = logging.getLogger(__name__)

SPACE_HOST_ENV = "SPACE_HOST"
PUBLIC_BASE_ENV = "ALGENTA_PUBLIC_BASE_URL"
EVENT_HEADER = "x-webhook-event"
NONCE_BYTES = 24
MAX_BODY_BYTES = 256 * 1024
#: Accepted and rejected POSTs kept, and armed decisions remembered, per boot.
KEEP = 64
CODE_NO_PUBLIC_URL = "webhook_url_unavailable"
HINT_NO_PUBLIC_URL = "This Space has no public https address, so the engine has nowhere to deliver."
#: The event name the engine's decision webhook carries (`hosted_api.WEBHOOK_EVENT`).
WEBHOOK_EVENT = hosted_api.WEBHOOK_EVENT
#: The three integrity ids `log_decision` returns and the engine's POST repeats.
INTEGRITY_KEYS: tuple[str, ...] = ("policy_snapshot_id", "schema_snapshot_id", "manifest_version")
#: Every refusal answers this body, so nothing tells a sender which check failed.
REJECTED_BODY: Mapping[str, Any] = {"received": False}
REJECTED_STATUS = 400
CONFIDENCE_TOLERANCE = 1e-9

#: What the receiver refused and why — the server log and `Rejection.reason` spell these.
REASON_BODY_TOO_LARGE = "body_too_large"
REASON_NONCE = "nonce_mismatch"
REASON_NOT_JSON = "not_json"
REASON_NOT_OBJECT = "not_an_object"
REASON_UNKNOWN = "unknown_decision"
REASON_SETTLED = "decision_settled"
REASON_SERVED = "already_received"
REASON_EVENT = "event_mismatch"
REASON_INTEGRITY = "integrity_mismatch"
REASON_SUMMARY = "summary_mismatch"
#: What an accepted POST was checked against, in the order the card names them.
VERIFIED: tuple[str, ...] = ("nonce", "session", "integrity", "summary")
#: The engine's decision webhook body, key by key, in words — what the receipt's Body row
#: says instead of the identifier list (`decision, decision_id, event, integrity, metadata,
#: org_id`). A key this table does not know reads as its words (`some_key` → `some key`).
BODY_KEY_WORDS: Mapping[str, str] = {
    "decision": "decision summary",
    "decision_id": "decision id",
    "event": "event",
    "integrity": "integrity block",
    "metadata": "metadata",
    "org_id": "organisation id",
    "signature": "signature",
}
EMPTY_BODY_TEXT = "empty body"


def describe_body(body: Mapping[str, Any]) -> str:
    """`decision summary, decision id, event, integrity block, metadata, organisation id` —
    the body's top-level keys as a reader's words, in the table's order first and then any
    other key in its own words; `empty body` for a body without keys."""
    keys = list(body)
    if not keys:
        return EMPTY_BODY_TEXT
    known = [BODY_KEY_WORDS[k] for k in BODY_KEY_WORDS if k in keys]
    other = sorted(str(k).replace("_", " ") for k in keys if k not in BODY_KEY_WORDS)
    return ", ".join([*known, *other])


def public_base(env: Mapping[str, str] | None = None) -> str:
    """`https://<SPACE_HOST>` (or `ALGENTA_PUBLIC_BASE_URL` for a tunnel), else an empty string."""
    env = os.environ if env is None else env
    explicit = env.get(PUBLIC_BASE_ENV, "").strip().rstrip("/")
    if explicit.startswith("https://"):
        return explicit
    host = env.get(SPACE_HOST_ENV, "").strip().strip("/")
    if not host or "/" in host or " " in host:
        return ""
    return f"https://{host}"


def integrity_of(integrity: Mapping[str, Any]) -> dict[str, str]:
    """The three ids as strings, absent keys left out — the shape `expect` records and `accept`
    compares, so `log_decision`'s answer and the POST's block are held to the same spelling."""
    return {key: str(integrity[key]) for key in INTEGRITY_KEYS if integrity.get(key)}


def same_confidence(presented: Any, expected: float | None) -> bool:
    """Both absent, or two finite numbers within `CONFIDENCE_TOLERANCE`."""
    if expected is None:
        return presented is None
    if presented is None or isinstance(presented, bool):
        return False
    try:
        value = float(presented)
    except (TypeError, ValueError):
        return False
    return math.isfinite(value) and abs(value - expected) <= CONFIDENCE_TOLERANCE


@dataclass(frozen=True)
class Expected:
    """One decision this process logged and armed for the engine's POST."""

    decision_id: str
    integrity: dict[str, str]
    chosen_action: str
    confidence: float | None
    armed_utc: str


@dataclass(frozen=True)
class HookEvent:
    """One accepted POST: the receiver's record and the expectation it was checked against."""

    event: WebhookEvent
    expected: Expected

    @property
    def decision_id(self) -> str:
        return self.event.decision_id

    @property
    def verified(self) -> tuple[str, ...]:
        return VERIFIED


@dataclass(frozen=True)
class Rejection:
    """One refused POST: when, why, the decision id it claimed and the body's top-level keys.

    The body itself is never kept or logged; the keys say what shape arrived."""

    received_utc: str
    reason: str
    decision_id: str = ""
    keys: tuple[str, ...] = ()


@dataclass
class Hook:
    """The nonce, the public base and the per-boot ledgers, as one object to mount."""

    nonce: str
    base: str = ""
    prefix: str = hosted_api.HOOK_PREFIX
    clock: Callable[[], float] = time.time
    _expected: dict[str, Expected] = field(default_factory=dict, repr=False)
    _settled: dict[str, str] = field(default_factory=dict, repr=False)
    _served: set[str] = field(default_factory=set, repr=False)
    _events: list[HookEvent] = field(default_factory=list, repr=False)
    _rejected: list[Rejection] = field(default_factory=list, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        if not self.nonce or "/" in self.nonce:
            raise ValueError("nonce must be a non-empty path segment")
        self.prefix = self.prefix.rstrip("/") or hosted_api.HOOK_PREFIX

    # -- what may be said about the route -------------------------------------------------

    @property
    def path(self) -> str:
        """The route's prefix (`/hook`) — what `/health` may publish. The nonce never is."""
        return self.prefix

    @property
    def host(self) -> str:
        """The public host the engine delivers to (`thyn-ai-algenta.hf.space`), or empty."""
        return urlsplit(self.base).netloc if self.base.startswith("https://") else ""

    @property
    def public(self) -> bool:
        return bool(self.url())

    def url(self) -> str:
        """The absolute webhook URL with the nonce — passed to the engine, printed nowhere."""
        if not self.base.startswith("https://"):
            return ""
        return f"{self.base.rstrip('/')}{self.prefix}/{self.nonce}"

    # -- arming and settling a decision ----------------------------------------------------

    def expect(
        self,
        decision_id: str,
        *,
        integrity: Mapping[str, Any],
        chosen_action: str,
        confidence: float | None,
    ) -> Expected:
        """Arm `decision_id`: the next POST naming it, with this integrity block and summary,
        is the engine's. Re-arming (an execution sent again) replaces the expectation and
        allows one more POST."""
        decision_id = str(decision_id).strip()
        if not decision_id:
            raise ValueError("decision_id is required")
        expected = Expected(
            decision_id=decision_id,
            integrity=integrity_of(integrity),
            chosen_action=str(chosen_action),
            confidence=None if confidence is None else float(confidence),
            armed_utc=self._now(),
        )
        with self._lock:
            self._expected[decision_id] = expected
            self._served.discard(decision_id)
            self._settled.pop(decision_id, None)
            for stale in list(self._expected)[:-KEEP]:
                del self._expected[stale]
        return expected

    def settle(self, decision_id: str) -> None:
        """`execute_decision` returned: a POST for `decision_id` arriving now is late."""
        decision_id = str(decision_id).strip()
        if not decision_id:
            return
        with self._lock:
            self._expected.pop(decision_id, None)
            self._settled[decision_id] = self._now()
            for stale in list(self._settled)[:-KEEP]:
                del self._settled[stale]

    def armed(self, decision_id: str) -> bool:
        with self._lock:
            return decision_id in self._expected

    # -- the POST ---------------------------------------------------------------------------

    def accept(self, nonce: str, body: bytes, headers: Mapping[str, str]) -> HookEvent | None:
        """Verify nonce, session, integrity and summary; record and return the event, or None
        (the route answers `REJECTED_STATUS` with `REJECTED_BODY`) after recording why."""
        del headers  # the engine's decision webhook sends no header worth trusting
        if len(body) > MAX_BODY_BYTES:
            return self._reject(REASON_BODY_TOO_LARGE)
        if not hmac.compare_digest(str(nonce).encode(), self.nonce.encode()):
            return self._reject(REASON_NONCE)
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return self._reject(REASON_NOT_JSON)
        if not isinstance(data, dict):
            return self._reject(REASON_NOT_OBJECT)
        decision_id = str(data.get("decision_id", "") or "")
        keys = tuple(sorted(str(k) for k in data))
        with self._lock:
            expected = self._expected.get(decision_id)
            settled = decision_id in self._settled
            served = decision_id in self._served
        if expected is None:
            return self._reject(REASON_SETTLED if settled else REASON_UNKNOWN, decision_id, keys)
        if served:
            return self._reject(REASON_SERVED, decision_id, keys)
        if str(data.get("event", "")) != WEBHOOK_EVENT:
            return self._reject(REASON_EVENT, decision_id, keys)
        raw_integrity = data.get("integrity")
        if not isinstance(raw_integrity, Mapping):
            return self._reject(REASON_INTEGRITY, decision_id, keys)
        if integrity_of(raw_integrity) != expected.integrity:
            return self._reject(REASON_INTEGRITY, decision_id, keys)
        decision = data.get("decision")
        if not isinstance(decision, Mapping):
            return self._reject(REASON_SUMMARY, decision_id, keys)
        if str(decision.get("chosen_action", "")) != expected.chosen_action:
            return self._reject(REASON_SUMMARY, decision_id, keys)
        if not same_confidence(decision.get("confidence"), expected.confidence):
            return self._reject(REASON_SUMMARY, decision_id, keys)
        event = WebhookEvent(
            received_utc=self._now(),
            decision_id=decision_id,
            event=str(data.get("event", "")),
            signed=False,
            integrity={str(k): str(v) for k, v in raw_integrity.items() if v},
            body=data,
        )
        accepted = HookEvent(event, expected)
        with self._lock:
            self._served.add(decision_id)
            self._events.append(accepted)
            del self._events[:-KEEP]
        log.info("webhook accepted decision=%s verified=%s", decision_id, ",".join(VERIFIED))
        return accepted

    def _reject(self, reason: str, decision_id: str = "", keys: tuple[str, ...] = ()) -> None:
        rejection = Rejection(self._now(), reason, decision_id, keys)
        with self._lock:
            self._rejected.append(rejection)
            del self._rejected[:-KEEP]
        log.warning(
            "webhook rejected reason=%s decision=%s keys=%s",
            reason,
            decision_id or "-",
            ",".join(keys) or "-",
        )
        return None

    # -- reading the ledgers -----------------------------------------------------------------

    def events(self, decision_id: str | None = None) -> list[HookEvent]:
        with self._lock:
            events = list(self._events)
        if decision_id is None:
            return events
        return [e for e in events if e.decision_id == decision_id]

    def rejections(self, decision_id: str | None = None) -> list[Rejection]:
        """Refused POSTs — for one decision id as the body claimed it, or all of them."""
        with self._lock:
            rejected = list(self._rejected)
        if decision_id is None:
            return rejected
        return [r for r in rejected if r.decision_id == decision_id]

    def wait_for(
        self,
        decision_id: str,
        *,
        timeout_s: float = 2.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        step_s: float = 0.05,
    ) -> HookEvent | None:
        """The accepted POST for `decision_id`, waiting up to `timeout_s` for it to land."""
        deadline = clock() + max(0.0, timeout_s)
        while True:
            found = self.events(decision_id)
            if found:
                return found[-1]
            if clock() >= deadline:
                return None
            sleep(step_s)

    def _now(self) -> str:
        return utc_stamp(datetime.fromtimestamp(self.clock(), UTC))


def make_hook(
    env: Mapping[str, str] | None = None,
    *,
    nonce_factory: Callable[[], str] = lambda: secrets.token_urlsafe(NONCE_BYTES),
    prefix: str = hosted_api.HOOK_PREFIX,
    clock: Callable[[], float] = time.time,
) -> Hook:
    """A fresh nonce per boot and the public base from the environment."""
    env = os.environ if env is None else env
    return Hook(nonce=nonce_factory(), base=public_base(env), prefix=prefix, clock=clock)


def build_router(hook: Hook) -> Any:
    """The FastAPI router with `POST <prefix>/{nonce}`: 200 on accept, else `REJECTED_STATUS`
    with `REJECTED_BODY` — the same answer for every refusal."""
    if APIRouter is None or Request is None or JSONResponse is None:
        raise RuntimeError("fastapi is not installed; the webhook route cannot be built")
    router = APIRouter()
    route = f"{hook.prefix}/{{nonce}}"

    @router.post(route)
    async def receive(nonce: str, request: Request) -> JSONResponse:
        body = await request.body()
        accepted = hook.accept(nonce, body, dict(request.headers))
        if accepted is None:
            return JSONResponse(status_code=REJECTED_STATUS, content=dict(REJECTED_BODY))
        return JSONResponse(
            status_code=200,
            content={"received": True, "decision_id": accepted.decision_id},
        )

    return router


def mount(app: Any, hook: Hook) -> None:
    """Attach the route to the FastAPI app that also serves Gradio (`gr.mount_gradio_app`)."""
    app.include_router(build_router(hook))
