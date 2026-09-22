"""The hosted governed lane — one real tenant behind `algenta.AlgentaClient`, or nothing.

Ported from the flagship's `governed.py:HostedEngine` and narrowed to what a public
Space is allowed to do with a shared demo key:

* **One source for the key and the URL.** `HostedGoverned` reads the API key
  from a single injected environment name (default `ALGENTA_API_KEY`) at
  construction time and hands it straight to the client factory. It is never
  stored on the instance, never logged and never part of `repr()`. Without a key
  every call raises `NotConfiguredError`; there is no demo, sample or offline
  path. The base URL is read the same way (`ALGENTA_BASE_URL`, default
  `https://api.algenta.ai`) and always passed explicitly, so nothing else in the
  process environment can redirect the lane.
* **An allow-list of client methods.** Only `me` (the probe), `recommend`,
  `log_decision`, `execute_decision` and `get_decision` are ever invoked, and a
  Space may narrow the set further (an observe-only Space drops
  `execute_decision`). Anything else raises `NotAllowedError` before the client is
  touched.
* **Normalised outcomes.** Every engine response is turned into a dataclass —
  `Recommendation`, `Decision`, `Receipt` (the execution confirmation with its
  integrity ids exactly as returned) or `Denial` (a policy gate: code, gate,
  message, override hint). SDK exceptions become `NotConfiguredError` (401/403),
  `RateLimitedError` (429), `EngineUnavailableError` (5xx, transport) or `EngineError`.
  Gate denials on `execute_decision` (HTTP 409, `execution_blocked_<gate>`) and a
  missing decision are *returned* as a `Denial`, not raised: they are the
  product, not a failure.
* **Secret scrub.** Every message that may reach the UI passes through
  `scrub()`: the `_SECRET_RE` from `algenta_mcp.client` (`de_live_…`, `de_test_…`,
  `Bearer …`) plus the exact key in use.
* **The engine's webhook, end to end.** `webhook_receiver()` builds the
  `/hook/<nonce>` route the Space mounts beside Gradio; `verify()` checks the
  nonce in constant time and, when a signing secret is configured, the
  `X-Webhook-Signature: sha256=<hmac>` when the engine signs (its jobs webhooks do; the
  decision-execution webhook POSTs `webhook_payload` with an `integrity` block and NO signature
  header — for it the unguessable nonce path is the whole check and the integrity block is shown
  as returned). Accepted events are kept so
  the UI can show the engine's POST next to the receipt.

Stdlib only at import: `algenta` is imported inside the default client factory.
"""

from __future__ import annotations

import dataclasses
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from . import cards
from .runtime import utc_stamp

log = logging.getLogger(__name__)

DEFAULT_KEY_ENV = "ALGENTA_API_KEY"
DEFAULT_BASE_URL_ENV = "ALGENTA_BASE_URL"
# `algenta._contract.DEFAULT_BASE_URL`; always passed explicitly so the ambient process
# environment (DE_BASE_URL, ALGENTA_API_URL, a private profile) can never redirect the lane.
DEFAULT_BASE_URL = "https://api.algenta.ai"
DEFAULT_ORIGIN = "algenta-flagship-space"
PROBE_METHOD = "me"
DEFAULT_ALLOW: frozenset[str] = frozenset(
    {PROBE_METHOD, "recommend", "log_decision", "execute_decision", "get_decision"}
)
REDACTED = "[redacted]"
SECRET_RE = re.compile(r"de_(?:live|test)_[A-Za-z0-9._\-]{6,}|[Bb]earer\s+[A-Za-z0-9._\-]{6,}")

SIGNATURE_HEADER = "x-webhook-signature"  # what the engine sends when it signs (webhook_service.py)
EVENT_HEADER = "x-webhook-event"
SIGNATURE_PREFIX = "sha256="
WEBHOOK_EVENT = "decision.execute"
HOOK_PREFIX = "/hook"
NOT_CONFIGURED_CODE = "HOSTED-NOT-CONFIGURED"
NOT_CONFIGURED_TITLE = "Hosted API not configured"
NOT_CONFIGURED_REASON = "No API key is set for this Space, so the governed lane is off."
REJECTED_KEY_REASON = "The hosted API rejected this Space's key, so the governed lane is off."
TRANSPORT_MODULES = ("httpx", "httpcore", "requests", "urllib", "anyio", "ssl", "socket", "h11")
_INTEGRITY_KEYS = (
    "request_hash",
    "result_hash",
    "policy_snapshot_id",
    "schema_snapshot_id",
    "manifest_version",
)


class ConfigState(StrEnum):
    READY = "ready"
    NOT_CONFIGURED = "not_configured"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"


# ---------------------------------------------------------------------------
# Errors — every message is already scrubbed and safe to render
# ---------------------------------------------------------------------------


class HostedError(Exception):
    """Base class; `str(exc)` is user-facing and secret-free."""

    def __init__(self, message: str, *, status_code: int = 0, request_id: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.request_id = request_id


class NotConfiguredError(HostedError):
    """No key, or a key the engine rejects (401/403)."""


class NotAllowedError(HostedError):
    """A client method outside the allow-list."""


class RateLimitedError(HostedError):
    """HTTP 429 from the engine; `retry_after_s` is the engine's hint."""

    def __init__(self, message: str, *, retry_after_s: float, **kwargs: Any):
        super().__init__(message, **kwargs)
        self.retry_after_s = max(0.0, float(retry_after_s))


class EngineUnavailableError(HostedError):
    """5xx or a transport failure: the engine could not be reached or answer."""


# The plan's short names; the `Error` suffix is the repo's naming rule.
NotConfigured = NotConfiguredError
NotAllowed = NotAllowedError
RateLimited = RateLimitedError
EngineUnavailable = EngineUnavailableError


class EngineError(HostedError):
    """Any other engine error, carrying the engine's own code and error body."""

    def __init__(
        self, message: str, *, code: str, body: Mapping[str, Any] | None = None, **kwargs: Any
    ):
        super().__init__(message, **kwargs)
        self.code = code
        self.body: dict[str, Any] = dict(body or {})


# ---------------------------------------------------------------------------
# Normalised shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HostedStatus:
    state: ConfigState
    reason: str
    base_url: str
    org: str = ""
    checked_utc: str = ""

    @property
    def ready(self) -> bool:
        return self.state is ConfigState.READY


@dataclass(frozen=True)
class Recommendation:
    recommended_action: str
    confidence: float | None
    rationale: str
    total_actions: int
    raw: dict[str, Any] = field(repr=False)


@dataclass(frozen=True)
class Decision:
    decision_id: str
    chosen_action: str
    confidence: float | None
    risk_p5: float | None
    execution_status: str | None
    integrity: dict[str, str]
    raw: dict[str, Any] = field(repr=False)


@dataclass(frozen=True)
class Receipt:
    """The engine's execution confirmation with its integrity ids exactly as returned."""

    decision_id: str
    webhook_url: str
    execution_status: str
    response_code: int | None
    executed_at: str
    policy_snapshot_id: str
    schema_snapshot_id: str
    manifest_version: str
    payload_summary: dict[str, Any]
    safety_overridden: bool
    raw: dict[str, Any] = field(repr=False)

    @property
    def delivered(self) -> bool:
        return self.execution_status == "delivered"


@dataclass(frozen=True)
class Denial:
    """A named policy gate held the execution, synchronously, in the same call."""

    code: str
    gate: str
    message: str
    override_hint: str | None = None
    status_code: int = 0
    request_id: str | None = None


def gate_from_error_code(code: str) -> str | None:
    """`execution_blocked_confidence` → `confidence`; the three gates plus `existence`."""
    if "idempotency" in code:
        return "idempotency"
    if "confidence" in code:
        return "confidence"
    if "risk_floor" in code:
        return "risk_floor"
    if "not_found" in code or "existence" in code:
        return "existence"
    return None


def to_plain(obj: Any) -> Any:
    """Pydantic models, dataclasses and objects → JSON-safe data (ported from governed.py)."""
    if obj is None or isinstance(obj, str | int | float | bool):
        return obj
    if isinstance(obj, Mapping):
        return {str(k): to_plain(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple | set | frozenset):
        return [to_plain(v) for v in obj]
    model_dump = getattr(obj, "model_dump", None)
    if callable(model_dump):
        return to_plain(model_dump(mode="json"))
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return to_plain(dataclasses.asdict(obj))
    if hasattr(obj, "__dict__"):
        return to_plain({k: v for k, v in vars(obj).items() if not k.startswith("_")})
    return str(obj)


def _as_dict(data: Any, what: str) -> dict[str, Any]:
    plain = to_plain(data)
    if not isinstance(plain, dict):
        raise EngineError(f"The engine returned no {what} object.", code="malformed_response")
    return plain


def _float_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _decision_id_of(data: Mapping[str, Any]) -> str:
    nested = data.get("decision")
    nested_id = nested.get("decision_id", "") if isinstance(nested, Mapping) else ""
    return str(data.get("decision_id") or data.get("id") or nested_id or "")


def to_recommendation(data: Any) -> Recommendation:
    plain = _as_dict(data, "recommendation")
    return Recommendation(
        recommended_action=str(plain.get("recommended_action", "")),
        confidence=_float_or_none(plain.get("confidence")),
        rationale=str(plain.get("rationale", "")),
        total_actions=_int_or_none(plain.get("total_actions")) or 0,
        raw=plain,
    )


def to_decision(data: Any) -> Decision:
    """`DecisionLogResponse` (log or get) → `Decision`; the id is required."""
    plain = _as_dict(data, "decision")
    decision_id = _decision_id_of(plain)
    if not decision_id:
        raise EngineError("The engine returned a decision without an id.", code="missing_id")
    integrity = {k: str(plain[k]) for k in _INTEGRITY_KEYS if plain.get(k)}
    status = plain.get("execution_status")
    return Decision(
        decision_id=decision_id,
        chosen_action=str(plain.get("chosen_action", "")),
        confidence=_float_or_none(plain.get("confidence")),
        risk_p5=_float_or_none(plain.get("risk_p5")),
        execution_status=str(status) if status else None,
        integrity=integrity,
        raw=plain,
    )


def to_receipt(data: Any) -> Receipt:
    """The `execute` response → `Receipt`; status and decision id are required."""
    plain = _as_dict(data, "receipt")
    decision_id = _decision_id_of(plain)
    status = str(plain.get("execution_status", ""))
    if not decision_id or not status:
        raise EngineError("The engine returned an incomplete receipt.", code="malformed_receipt")
    summary = plain.get("payload_summary")
    return Receipt(
        decision_id=decision_id,
        webhook_url=str(plain.get("webhook_url", "")),
        execution_status=status,
        response_code=_int_or_none(plain.get("response_code")),
        executed_at=str(plain.get("executed_at", "")),
        policy_snapshot_id=str(plain.get("policy_snapshot_id", "")),
        schema_snapshot_id=str(plain.get("schema_snapshot_id", "")),
        manifest_version=str(plain.get("manifest_version", "")),
        payload_summary=dict(summary) if isinstance(summary, Mapping) else {},
        safety_overridden=bool(plain.get("safety_overridden", False)),
        raw=plain,
    )


def to_denial(
    error: Mapping[str, Any], *, status_code: int = 0, request_id: str | None = None
) -> Denial:
    """The engine's `{"error": {code, gate, message, override_hint}}` body → `Denial`."""
    code = str(error.get("code") or "execution_blocked")
    gate = str(error.get("gate") or gate_from_error_code(code) or "policy")
    hint = error.get("override_hint")
    return Denial(
        code=code,
        gate=gate,
        message=str(error.get("message") or f"Held by the {gate} gate."),
        override_hint=str(hint) if hint else None,
        status_code=status_code,
        request_id=request_id,
    )


# ---------------------------------------------------------------------------
# Secret scrub
# ---------------------------------------------------------------------------


def scrub(text: object, *, pattern: re.Pattern[str] = SECRET_RE, exact: Iterable[str] = ()) -> str:
    """Redact key-shaped tokens and any exact strings from `text`."""
    out = pattern.sub(REDACTED, str(text))
    for secret in exact:
        if secret:
            out = out.replace(secret, REDACTED)
    return out


def _is_transport_error(exc: BaseException) -> bool:
    if isinstance(exc, OSError | TimeoutError):
        return True
    module = type(exc).__module__ or ""
    return module.split(".", 1)[0] in TRANSPORT_MODULES


def _error_body(exc: BaseException) -> dict[str, Any]:
    body = getattr(exc, "response_body", None)
    if isinstance(body, Mapping):
        error = body.get("error")
        if isinstance(error, Mapping):
            return dict(error)
    return {}


# ---------------------------------------------------------------------------
# The lane
# ---------------------------------------------------------------------------

ClientFactory = Callable[[str, str], Any]


def default_client_factory(api_key: str, base_url: str) -> Any:
    """`algenta.AlgentaClient(api_key=…, base_url=…)`, imported here and nowhere else."""
    from algenta import AlgentaClient

    return AlgentaClient(api_key=api_key, base_url=base_url)


class HostedGoverned:
    """Real tenant, allow-listed methods, normalised outcomes, scrubbed errors."""

    def __init__(
        self,
        client_factory: ClientFactory = default_client_factory,
        *,
        env: Mapping[str, str] | None = None,
        key_env: str = DEFAULT_KEY_ENV,
        base_url_env: str = DEFAULT_BASE_URL_ENV,
        allow: frozenset[str] | Iterable[str] = DEFAULT_ALLOW,
        scrub_pattern: re.Pattern[str] = SECRET_RE,
        origin: str = DEFAULT_ORIGIN,
    ):
        env = os.environ if env is None else env
        allow = frozenset(allow)
        unknown = allow - DEFAULT_ALLOW
        if unknown:
            raise ValueError(f"allow-list names methods this lane never calls: {sorted(unknown)}")
        key = env.get(key_env, "").strip()
        self.key_env = key_env
        self.base_url = env.get(base_url_env, "").strip() or DEFAULT_BASE_URL
        if not self.base_url.startswith(("https://", "http://localhost", "http://127.0.0.1")):
            raise ValueError(f"{base_url_env} must be an https URL (or localhost for a dev server)")
        self.allow = allow
        self.origin = origin
        self.configured = bool(key)
        self._pattern = scrub_pattern
        self._factory = client_factory
        self._client: Any = None
        self._lock = threading.Lock()
        # A closure so the key lives in exactly one place besides the client itself.
        self._scrub: Callable[[object], str] = lambda text: scrub(
            text, pattern=scrub_pattern, exact=(key,)
        )
        self._make_client: Callable[[], Any] = lambda: client_factory(key, self.base_url)

    def __repr__(self) -> str:
        return (
            f"HostedGoverned(configured={self.configured}, base_url={self.base_url!r},"
            f" allow={sorted(self.allow)})"
        )

    # -- plumbing -----------------------------------------------------------

    def _client_for(self, method: str) -> Any:
        if method not in DEFAULT_ALLOW:
            raise ValueError(f"unknown client method {method!r}")
        if method not in self.allow:
            raise NotAllowedError(f"`{method}` is not enabled on this Space.")
        if not self.configured:
            raise NotConfiguredError(NOT_CONFIGURED_REASON)
        with self._lock:
            if self._client is None:
                self._client = self._make_client()
            return self._client

    def _normalise(self, exc: BaseException, *, method: str) -> HostedError | None:
        """The `HostedError` for an SDK/transport exception; None when it is not one."""
        status = getattr(exc, "status_code", None)
        request_id = getattr(exc, "request_id", None)
        message = self._scrub(exc)
        if isinstance(status, int) and not isinstance(status, bool) and status > 0:
            body = _error_body(exc)
            body = {k: self._scrub(v) if isinstance(v, str) else v for k, v in body.items()}
            code = str(getattr(exc, "error_code", "") or body.get("code") or "unknown_error")
            log.warning("hosted %s -> HTTP %s %s request_id=%s", method, status, code, request_id)
            if status in (401, 403):
                return NotConfiguredError(
                    REJECTED_KEY_REASON, status_code=status, request_id=request_id
                )
            if status == 429:
                retry = getattr(exc, "retry_after", None)
                return RateLimitedError(
                    message,
                    retry_after_s=float(retry) if retry else 60.0,
                    status_code=status,
                    request_id=request_id,
                )
            if status >= 500:
                return EngineUnavailableError(message, status_code=status, request_id=request_id)
            return EngineError(
                message, code=code, body=body, status_code=status, request_id=request_id
            )
        if _is_transport_error(exc):
            log.warning("hosted %s -> transport failure %s", method, type(exc).__name__)
            return EngineUnavailableError(f"The hosted API could not be reached: {message}")
        return None

    def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        client = self._client_for(method)
        # The lock guards lazy client construction only (see _client_for); the SDK client is
        # thread-safe for concurrent calls, and holding a process-wide lock across a network
        # round-trip would serialise every visitor's governed call behind the slowest one.
        try:
            return getattr(client, method)(*args, **kwargs)
        except HostedError:
            raise
        except Exception as exc:
            normalised = self._normalise(exc, method=method)
            if normalised is None:
                raise
            raise normalised from None

    # -- public surface -----------------------------------------------------

    def status(self, *, now: float | None = None) -> HostedStatus:
        """One cheap authenticated call (`me`); never raises, never leaks."""
        stamp = utc_stamp() if now is None else utc_stamp(_utc_from_ts(now))
        base = self.base_url
        if not self.configured:
            return HostedStatus(ConfigState.NOT_CONFIGURED, NOT_CONFIGURED_REASON, base, "", stamp)
        try:
            me = to_plain(self._call(PROBE_METHOD))
        except NotConfiguredError as exc:
            return HostedStatus(ConfigState.NOT_CONFIGURED, str(exc), base, "", stamp)
        except RateLimitedError as exc:
            reason = f"The hosted API is rate limited; retry in {exc.retry_after_s:.0f} s."
            return HostedStatus(ConfigState.RATE_LIMITED, reason, base, "", stamp)
        except HostedError as exc:
            return HostedStatus(ConfigState.UNAVAILABLE, str(exc), base, "", stamp)
        org = ""
        if isinstance(me, Mapping):
            org_obj = me.get("org")
            if isinstance(org_obj, Mapping):
                org = str(org_obj.get("name") or org_obj.get("id") or "")
        return HostedStatus(ConfigState.READY, "Connected to the hosted API.", base, org, stamp)

    def recommend(self, actions: Any, **kwargs: Any) -> Recommendation:
        return to_recommendation(self._call("recommend", actions, **kwargs))

    def log_decision(
        self,
        chosen_action: str,
        *,
        confidence: float,
        risk_p5: float,
        context: str,
        rationale: str,
        options_considered: list[str] | None = None,
    ) -> Decision:
        request: dict[str, Any] = {
            "chosen_action": chosen_action.strip(),
            "confidence": round(float(confidence), 3),
            "risk_p5": round(float(risk_p5), 3),
            "context": context,
            "rationale": rationale,
        }
        if options_considered:
            request["options_considered"] = list(options_considered)
        return to_decision(self._call("log_decision", request))

    def execute_decision(
        self,
        decision_id: str,
        *,
        webhook_url: str,
        timeout_seconds: float = 10.0,
        force: bool = False,
        override_safety: bool = False,
    ) -> Receipt | Denial:
        """A `Receipt` when the gates clear; a `Denial` when one holds or the id is unknown."""
        decision_id = decision_id.strip()
        if not decision_id:
            return Denial("decision_not_found", "existence", "No decision id was given.")
        if not webhook_url.strip():
            raise ValueError("webhook_url is required")
        try:
            result = self._call(
                "execute_decision",
                decision_id,
                webhook_url=webhook_url.strip(),
                timeout_seconds=float(timeout_seconds),
                force=bool(force),
                override_safety=bool(override_safety),
                metadata={"origin": self.origin},
            )
        except EngineError as exc:
            if exc.status_code == 409:
                body = exc.body or {"code": exc.code, "message": str(exc)}
                return to_denial(body, status_code=409, request_id=exc.request_id)
            if exc.status_code == 404:
                body = {
                    "code": "decision_not_found",
                    "gate": "existence",
                    "message": f"No decision with id {decision_id} on this tenant.",
                }
                return to_denial(body, status_code=404, request_id=exc.request_id)
            raise
        return to_receipt(result)

    def get_decision(self, decision_id: str) -> Decision:
        decision_id = decision_id.strip()
        if not decision_id:
            raise ValueError("decision_id is required")
        return to_decision(self._call("get_decision", decision_id))


def _utc_from_ts(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, UTC)


# ---------------------------------------------------------------------------
# Webhook receiver — the route the Space mounts beside Gradio
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WebhookEvent:
    received_utc: str
    decision_id: str
    event: str
    signed: bool
    integrity: dict[str, str]
    body: dict[str, Any] = field(repr=False)


class WebhookReceiver:
    """`/hook/<nonce>`: constant-time nonce match, optional HMAC, a bounded event log."""

    def __init__(
        self,
        nonce: str,
        *,
        prefix: str = HOOK_PREFIX,
        secret: bytes | None = None,
        keep: int = 32,
        clock: Callable[[], float] = time.time,
    ):
        if not nonce or "/" in nonce:
            raise ValueError("nonce must be a non-empty path segment")
        if keep < 1:
            raise ValueError("keep must be at least 1")
        self.prefix = prefix.rstrip("/") or HOOK_PREFIX
        self._nonce = nonce
        self._secret = secret
        self._keep = keep
        self._clock = clock
        self._events: list[WebhookEvent] = []
        self._lock = threading.Lock()

    @property
    def path(self) -> str:
        return f"{self.prefix}/{self._nonce}"

    @property
    def signed(self) -> bool:
        return self._secret is not None

    def url(self, public_base: str) -> str:
        """The absolute URL the Space passes as `webhook_url`."""
        base = public_base.strip().rstrip("/")
        if not base.startswith("https://"):
            raise ValueError("the public base must be an https URL")
        return base + self.path

    def signature(self, body: bytes) -> str:
        if self._secret is None:
            raise ValueError("this receiver has no signing secret")
        return SIGNATURE_PREFIX + hmac.new(self._secret, body, hashlib.sha256).hexdigest()

    def verify(self, nonce: str, body: bytes, headers: Mapping[str, str]) -> WebhookEvent | None:
        """Accept and record the engine's POST, or return None (the route answers 404)."""
        if not hmac.compare_digest(nonce.encode(), self._nonce.encode()):
            return None
        lowered = {str(k).lower(): str(v) for k, v in headers.items()}
        signed = False
        if self._secret is not None:
            presented = lowered.get(SIGNATURE_HEADER, "").strip()
            if not hmac.compare_digest(presented.encode(), self.signature(body).encode()):
                return None
            signed = True
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        raw_integrity = data.get("integrity")
        integrity = (
            {str(k): str(v) for k, v in raw_integrity.items() if v}
            if isinstance(raw_integrity, Mapping)
            else {}
        )
        event = WebhookEvent(
            received_utc=utc_stamp(_utc_from_ts(self._clock())),
            decision_id=str(data.get("decision_id", "")),
            event=str(data.get("event", "")),
            signed=signed,
            integrity=integrity,
            body=data,
        )
        with self._lock:
            self._events.append(event)
            del self._events[: -self._keep]
        return event

    def events(self, decision_id: str | None = None) -> list[WebhookEvent]:
        with self._lock:
            events = list(self._events)
        if decision_id is None:
            return events
        return [e for e in events if e.decision_id == decision_id]


def webhook_receiver(
    nonce_factory: Callable[[], str] = secrets.token_urlsafe,
    *,
    prefix: str = HOOK_PREFIX,
    secret: bytes | None = None,
    keep: int = 32,
    clock: Callable[[], float] = time.time,
) -> tuple[str, WebhookReceiver]:
    """`(path, receiver)`: mount `path` as the POST route; call `receiver.verify` inside it."""
    receiver = WebhookReceiver(
        nonce_factory(), prefix=prefix, secret=secret, keep=keep, clock=clock
    )
    return receiver.path, receiver


# ---------------------------------------------------------------------------
# The not-configured card
# ---------------------------------------------------------------------------


def render_status_card(status: HostedStatus) -> str:
    """The card a Space shows when the lane is not ready; an empty string when it is."""
    if status.ready:
        return ""
    code = {
        ConfigState.NOT_CONFIGURED: NOT_CONFIGURED_CODE,
        ConfigState.UNAVAILABLE: "HOSTED-UNAVAILABLE",
        ConfigState.RATE_LIMITED: "HOSTED-RATE-LIMITED",
    }[status.state]
    return cards.render_unavailable_card(
        title=NOT_CONFIGURED_TITLE if status.state is ConfigState.NOT_CONFIGURED else "Hosted API",
        error_code=code,
        hint=status.reason,
        hardware=f"{status.base_url} · {status.checked_utc}".strip(" ·"),
    )
