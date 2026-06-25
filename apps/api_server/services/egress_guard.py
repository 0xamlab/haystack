"""Shared privacy-policy enforcement for API-server outbound network access."""

from __future__ import annotations

import asyncio
import ipaddress
import smtplib
import socket
import uuid
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Any

import httpx
import structlog

from apps.api_server.config import get_settings
from apps.api_server.services.privacy_service import record_service_egress_event
from apps.privacy_policy import (
    EgressClass,
    EgressDecision,
    evaluate_egress,
    parse_egress_destination,
)

logger = structlog.get_logger(__name__)

_AWS_GLOBAL_REGION_OVERRIDES = {
    "ce": "us-east-1",
    "iam": "us-east-1",
    "route53": "us-east-1",
}


@dataclass(frozen=True)
class EgressAuditContext:
    org_id: uuid.UUID | None = None
    actor_email: str = "system"
    request_id: str | None = None


class EgressPolicyDeniedError(RuntimeError):
    code = "egress_policy_denied"

    def __init__(self, decision: EgressDecision) -> None:
        self.decision = decision
        super().__init__(
            f"Egress blocked by privacy policy for surface '{decision.surface}' "
            f"({decision.reason})."
        )

    def error_payload(self, *, message: str | None = None) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": message or str(self),
                "details": {
                    "reason": self.decision.reason,
                    "surface": self.decision.surface,
                    "egress_class": self.decision.egress_class,
                },
            }
        }


def audit_context_from_auth(
    auth: Mapping[str, Any] | None,
    *,
    request_id: str | None = None,
) -> EgressAuditContext:
    if not auth:
        return EgressAuditContext(request_id=request_id)
    raw_org_id = auth.get("org_id")
    org_id: uuid.UUID | None = None
    if isinstance(raw_org_id, uuid.UUID):
        org_id = raw_org_id
    elif isinstance(raw_org_id, str):
        try:
            org_id = uuid.UUID(raw_org_id)
        except ValueError:
            org_id = None
    actor_email = str(auth.get("email") or "system")
    return EgressAuditContext(org_id=org_id, actor_email=actor_email, request_id=request_id)


def audit_context_from_config(config: Mapping[str, Any]) -> EgressAuditContext:
    raw_org_id = config.get("__org_id", config.get("org_id"))
    org_id: uuid.UUID | None = None
    if isinstance(raw_org_id, uuid.UUID):
        org_id = raw_org_id
    elif isinstance(raw_org_id, str):
        try:
            org_id = uuid.UUID(raw_org_id)
        except ValueError:
            org_id = None
    actor_email = str(config.get("__actor_email") or config.get("actor_email") or "system")
    request_id = config.get("__request_id")
    return EgressAuditContext(
        org_id=org_id,
        actor_email=actor_email,
        request_id=str(request_id) if request_id else None,
    )


async def _record_decision_async(
    decision: EgressDecision,
    audit_context: EgressAuditContext | None,
) -> None:
    if audit_context is None or audit_context.org_id is None:
        return
    try:
        await record_service_egress_event(
            org_id=audit_context.org_id,
            decision=decision,
            actor_email=audit_context.actor_email,
        )
    except Exception:
        logger.debug(
            "privacy_egress_audit_failed",
            destination_host_hash=decision.destination_host_hash,
            surface=decision.surface,
        )


def _record_decision_sync(
    decision: EgressDecision,
    audit_context: EgressAuditContext | None,
) -> None:
    if audit_context is None or audit_context.org_id is None:
        return
    coroutine = record_service_egress_event(
        org_id=audit_context.org_id,
        decision=decision,
        actor_email=audit_context.actor_email,
    )
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        try:
            asyncio.run(coroutine)
        except Exception:
            logger.debug(
                "privacy_egress_audit_failed",
                destination_host_hash=decision.destination_host_hash,
                surface=decision.surface,
            )
        return

    task = loop.create_task(coroutine)

    def _consume_task_result(completed_task: asyncio.Task[None]) -> None:
        try:
            completed_task.result()
        except Exception:
            logger.debug(
                "privacy_egress_audit_failed",
                destination_host_hash=decision.destination_host_hash,
                surface=decision.surface,
            )

    task.add_done_callback(_consume_task_result)


_SSRF_GUARDED_REASONS = frozenset(
    {
        "outbound_network_enabled",
        "undeclared_public_egress_enabled",
    }
)


def _is_private_or_local_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _resolve_destination_addresses(host: str) -> list[str]:
    if not host:
        return []
    stripped = host.strip("[]")
    try:
        ipaddress.ip_address(stripped)
        return [stripped]
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError, OSError):
        return []
    return list({info[4][0] for info in infos if info and info[4]})


def _is_never_legitimate_ip(ip_str: str) -> bool:
    """Addresses that are never a legitimate egress target — even an operator allowlist must not
    reach them. Notably link-local 169.254.0.0/16 (the cloud-metadata endpoint 169.254.169.254)."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    # Link-local (incl. 169.254.169.254), multicast, and unspecified are never a legitimate egress
    # target. (Loopback/reserved are NOT included here: ::1 is is_reserved, and an operator may
    # legitimately allowlist a loopback/private sidecar — those stay gated by the reason check below.)
    return ip.is_link_local or ip.is_multicast or ip.is_unspecified


def _enforce_no_private_destination(
    destination: str,
    *,
    decision: EgressDecision,
) -> None:
    target = parse_egress_destination(destination)
    host = target.host
    if not host:
        return
    addrs = _resolve_destination_addresses(host)
    if not addrs:
        return
    # ALWAYS block never-legitimate (link-local/metadata/multicast/...) destinations, regardless of
    # the allow reason — so an allowlisted (e.g. wildcard) host that resolves to 169.254.169.254
    # cannot reach the cloud-metadata endpoint. Private/loopback hosts stay operator-allowlist-gated
    # below (an internal sidecar at 10.x or Supabase is a legitimate, opted-in destination).
    if any(_is_never_legitimate_ip(ip) for ip in addrs):
        raise EgressPolicyDeniedError(
            replace(decision, decision="deny", reason="ssrf_guard_link_local_destination")
        )
    if decision.reason not in _SSRF_GUARDED_REASONS:
        return
    if not any(_is_private_or_local_ip(ip) for ip in addrs):
        return
    blocked = replace(
        decision,
        decision="deny",
        reason="ssrf_guard_private_destination",
    )
    raise EgressPolicyDeniedError(blocked)


def evaluate_egress_policy(
    destination: str,
    *,
    surface: str,
    service_name: str = "api-server",
    explicit_configured: bool = False,
    egress_class: EgressClass | None = None,
    request_id: str | None = None,
) -> EgressDecision:
    policy = get_settings().privacy_policy
    return evaluate_egress(
        policy,
        destination,
        surface=surface,
        service_name=service_name,
        explicit_configured=explicit_configured,
        egress_class=egress_class,
        request_id=request_id,
    )


async def enforce_egress(
    destination: str,
    *,
    surface: str,
    service_name: str = "api-server",
    explicit_configured: bool = False,
    egress_class: EgressClass | None = None,
    audit_context: EgressAuditContext | None = None,
) -> EgressDecision:
    decision = evaluate_egress_policy(
        destination,
        surface=surface,
        service_name=service_name,
        explicit_configured=explicit_configured,
        egress_class=egress_class,
        request_id=audit_context.request_id if audit_context else None,
    )
    await _record_decision_async(decision, audit_context)
    if decision.decision == "deny":
        raise EgressPolicyDeniedError(decision)
    _enforce_no_private_destination(destination, decision=decision)
    return decision


def enforce_egress_sync(
    destination: str,
    *,
    surface: str,
    service_name: str = "api-server",
    explicit_configured: bool = False,
    egress_class: EgressClass | None = None,
    audit_context: EgressAuditContext | None = None,
) -> EgressDecision:
    decision = evaluate_egress_policy(
        destination,
        surface=surface,
        service_name=service_name,
        explicit_configured=explicit_configured,
        egress_class=egress_class,
        request_id=audit_context.request_id if audit_context else None,
    )
    _record_decision_sync(decision, audit_context)
    if decision.decision == "deny":
        raise EgressPolicyDeniedError(decision)
    _enforce_no_private_destination(destination, decision=decision)
    return decision


async def async_http_request(
    *,
    method: str,
    url: str,
    surface: str,
    service_name: str = "api-server",
    policy_destination: str | None = None,
    explicit_configured: bool = False,
    egress_class: EgressClass | None = None,
    audit_context: EgressAuditContext | None = None,
    client: httpx.AsyncClient | None = None,
    client_kwargs: dict[str, Any] | None = None,
    **request_kwargs: Any,
) -> httpx.Response:
    await enforce_egress(
        policy_destination or url,
        surface=surface,
        service_name=service_name,
        explicit_configured=explicit_configured,
        egress_class=egress_class,
        audit_context=audit_context,
    )
    async def _dispatch(async_client: httpx.AsyncClient) -> httpx.Response:
        method_name = method.strip().lower()
        specialized = getattr(async_client, method_name, None)
        if callable(specialized):
            return await specialized(url, **request_kwargs)
        return await async_client.request(method=method, url=url, **request_kwargs)

    if client is not None:
        return await _dispatch(client)
    async with httpx.AsyncClient(**(client_kwargs or {})) as managed_client:
        return await _dispatch(managed_client)


def sync_http_request(
    *,
    method: str,
    url: str,
    surface: str,
    service_name: str = "api-server",
    policy_destination: str | None = None,
    explicit_configured: bool = False,
    egress_class: EgressClass | None = None,
    audit_context: EgressAuditContext | None = None,
    client: httpx.Client | None = None,
    client_kwargs: dict[str, Any] | None = None,
    **request_kwargs: Any,
) -> httpx.Response:
    enforce_egress_sync(
        policy_destination or url,
        surface=surface,
        service_name=service_name,
        explicit_configured=explicit_configured,
        egress_class=egress_class,
        audit_context=audit_context,
    )
    def _dispatch(sync_client: httpx.Client) -> httpx.Response:
        method_name = method.strip().lower()
        specialized = getattr(sync_client, method_name, None)
        if callable(specialized):
            return specialized(url, **request_kwargs)
        return sync_client.request(method=method, url=url, **request_kwargs)

    if client is not None:
        return _dispatch(client)
    with httpx.Client(**(client_kwargs or {})) as managed_client:
        return _dispatch(managed_client)


def urllib_open(
    request: urllib.request.Request | str,
    *,
    surface: str,
    service_name: str = "api-server",
    explicit_configured: bool = False,
    egress_class: EgressClass | None = None,
    audit_context: EgressAuditContext | None = None,
    timeout: float | int | None = None,
    urlopen_fn: Callable[..., Any] = urllib.request.urlopen,
) -> Any:
    destination = request.full_url if isinstance(request, urllib.request.Request) else str(request)
    enforce_egress_sync(
        destination,
        surface=surface,
        service_name=service_name,
        explicit_configured=explicit_configured,
        egress_class=egress_class,
        audit_context=audit_context,
    )
    if timeout is None:
        return urlopen_fn(request)
    return urlopen_fn(request, timeout=timeout)


@contextmanager
def smtp_connection(
    *,
    host: str,
    port: int,
    surface: str,
    service_name: str = "api-server",
    explicit_configured: bool = False,
    egress_class: EgressClass | None = None,
    audit_context: EgressAuditContext | None = None,
    smtp_factory: Callable[..., Any] = smtplib.SMTP,
) -> Iterator[Any]:
    enforce_egress_sync(
        f"{host}:{port}",
        surface=surface,
        service_name=service_name,
        explicit_configured=explicit_configured,
        egress_class=egress_class,
        audit_context=audit_context,
    )
    with smtp_factory(host, port) as smtp:
        yield smtp


def aws_endpoint_url(
    *,
    aws_service_name: str,
    region_name: str | None,
    endpoint_url: str | None = None,
) -> str:
    if endpoint_url:
        return endpoint_url
    normalized_service = aws_service_name.strip().lower()
    normalized_region = (
        _AWS_GLOBAL_REGION_OVERRIDES.get(normalized_service)
        or (region_name.strip() if region_name else "")
        or "us-east-1"
    )
    if normalized_service == "s3":
        if normalized_region == "us-east-1":
            return "https://s3.amazonaws.com"
        return f"https://s3.{normalized_region}.amazonaws.com"
    return f"https://{normalized_service}.{normalized_region}.amazonaws.com"


def google_endpoint_url(host: str) -> str:
    normalized = host.strip()
    if normalized.startswith(("http://", "https://")):
        return normalized
    return f"https://{normalized}"


def azure_endpoint_url(account_url: str) -> str:
    normalized = account_url.strip()
    if normalized.startswith(("http://", "https://")):
        return normalized
    return f"https://{normalized}"
