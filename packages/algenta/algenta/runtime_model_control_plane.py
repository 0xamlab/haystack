from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from algenta.runtime_model_common import coerce_payload_mapping, jsonable


def _require_string(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _require_integer(data: dict[str, Any], key: str, context: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{context}.{key} must be an integer.")
    return value


def _require_number(data: dict[str, Any], key: str, context: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{context}.{key} must be a number.")
    return float(value)


def _require_bool(data: dict[str, Any], key: str, context: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise TypeError(f"{context}.{key} must be a boolean.")
    return value


def _optional_string(data: dict[str, Any], key: str, context: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _optional_datetime_text(data: dict[str, Any], key: str, context: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _require_datetime_text(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if isinstance(value, datetime):
        return value.isoformat()
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


@dataclass(frozen=True)
class MeUserOutput:
    id: str
    email: str
    name: str
    role: str
    email_verified: bool
    created_at: str

    @classmethod
    def from_api(cls, payload: Any) -> MeUserOutput:
        context = "me.user"
        data = coerce_payload_mapping(payload)
        return cls(
            id=_require_string(data, "id", context),
            email=_require_string(data, "email", context),
            name=_require_string(data, "name", context),
            role=_require_string(data, "role", context),
            email_verified=_require_bool(data, "email_verified", context),
            created_at=_require_datetime_text(data, "created_at", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class MeOrgOutput:
    id: str
    name: str
    slug: str
    plan: str
    status: str
    created_at: str

    @classmethod
    def from_api(cls, payload: Any) -> MeOrgOutput:
        context = "me.org"
        data = coerce_payload_mapping(payload)
        return cls(
            id=_require_string(data, "id", context),
            name=_require_string(data, "name", context),
            slug=_require_string(data, "slug", context),
            plan=_require_string(data, "plan", context),
            status=_require_string(data, "status", context),
            created_at=_require_datetime_text(data, "created_at", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class MeOutput:
    user: MeUserOutput
    org: MeOrgOutput

    @classmethod
    def from_api(cls, payload: Any) -> MeOutput:
        context = "me"
        data = coerce_payload_mapping(payload)
        return cls(
            user=MeUserOutput.from_api(data.get("user")),
            org=MeOrgOutput.from_api(data.get("org")),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable({"user": self.user.to_dict(), "org": self.org.to_dict()})


@dataclass(frozen=True)
class TeamMemberOutput:
    user_id: str
    name: str
    email: str
    role: str
    status: str
    last_active: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> TeamMemberOutput:
        context = "team.members.item"
        data = coerce_payload_mapping(payload)
        return cls(
            user_id=_require_string(data, "user_id", context),
            name=_require_string(data, "name", context),
            email=_require_string(data, "email", context),
            role=_require_string(data, "role", context),
            status=_require_string(data, "status", context),
            last_active=_optional_datetime_text(data, "last_active", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class TeamListOutput:
    members: list[TeamMemberOutput] = field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 1
    pages: int = 1

    @classmethod
    def from_api(cls, payload: Any) -> TeamListOutput:
        context = "team"
        if isinstance(payload, list):
            members = [TeamMemberOutput.from_api(item) for item in payload]
            total = len(members)
            return cls(
                members=members,
                total=total,
                page=1,
                limit=total or 1,
                pages=1,
            )
        data = coerce_payload_mapping(payload)
        raw_members = data.get("members")
        if not isinstance(raw_members, list):
            raise TypeError(f"{context}.members must be a list.")
        return cls(
            members=[TeamMemberOutput.from_api(item) for item in raw_members],
            total=_require_integer(data, "total", context),
            page=_require_integer(data, "page", context),
            limit=_require_integer(data, "limit", context),
            pages=_require_integer(data, "pages", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "members": [member.to_dict() for member in self.members],
                "total": self.total,
                "page": self.page,
                "limit": self.limit,
                "pages": self.pages,
            }
        )


@dataclass(frozen=True)
class TeamInviteOutput:
    message: str
    invite_id: str

    @classmethod
    def from_api(cls, payload: Any) -> TeamInviteOutput:
        context = "team_invite"
        data = coerce_payload_mapping(payload)
        return cls(
            message=_require_string(data, "message", context),
            invite_id=_require_string(data, "invite_id", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class TeamRoleUpdateOutput:
    message: str
    user_id: str

    @classmethod
    def from_api(cls, payload: Any) -> TeamRoleUpdateOutput:
        context = "team_role_update"
        data = coerce_payload_mapping(payload)
        return cls(
            message=_require_string(data, "message", context),
            user_id=_require_string(data, "user_id", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class TeamRemoveOutput:
    removed: bool
    user_id: str

    @classmethod
    def from_api(cls, payload: Any) -> TeamRemoveOutput:
        context = "team_remove"
        data = coerce_payload_mapping(payload)
        return cls(
            removed=_require_bool(data, "removed", context),
            user_id=_require_string(data, "user_id", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class AuditLogEntryOutput:
    id: str
    timestamp: str
    actor_email: str
    action: str
    resource_type: str
    resource_id: str | None = None
    ip_address: str | None = None
    result: str = ""
    content_hash: str | None = None
    metadata: dict[str, Any] | None = None

    @classmethod
    def from_api(cls, payload: Any) -> AuditLogEntryOutput:
        context = "audit_logs.entries.item"
        data = coerce_payload_mapping(payload)
        raw_metadata = data.get("metadata")
        metadata: dict[str, Any] | None = None
        if raw_metadata is not None:
            try:
                metadata = dict(coerce_payload_mapping(raw_metadata))
            except Exception as exc:
                raise TypeError(f"{context}.metadata must be a JSON object.") from exc
        return cls(
            id=_require_string(data, "id", context),
            timestamp=_require_datetime_text(data, "timestamp", context),
            actor_email=_require_string(data, "actor_email", context),
            action=_require_string(data, "action", context),
            resource_type=_require_string(data, "resource_type", context),
            resource_id=_optional_string(data, "resource_id", context),
            ip_address=_optional_string(data, "ip_address", context),
            result=_require_string(data, "result", context),
            content_hash=_optional_string(data, "content_hash", context),
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class AuditLogOutput:
    entries: list[AuditLogEntryOutput] = field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 1
    pages: int = 1

    @classmethod
    def from_api(cls, payload: Any) -> AuditLogOutput:
        context = "audit_logs"
        data = coerce_payload_mapping(payload)
        raw_entries = data.get("entries")
        if not isinstance(raw_entries, list):
            raise TypeError(f"{context}.entries must be a list.")
        return cls(
            entries=[AuditLogEntryOutput.from_api(item) for item in raw_entries],
            total=_require_integer(data, "total", context),
            page=_require_integer(data, "page", context),
            limit=_require_integer(data, "limit", context),
            pages=_require_integer(data, "pages", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "entries": [entry.to_dict() for entry in self.entries],
                "total": self.total,
                "page": self.page,
                "limit": self.limit,
                "pages": self.pages,
            }
        )


@dataclass(frozen=True)
class ExecutionPolicyOutput:
    org_id: str
    min_confidence: float
    risk_floor: float | None
    require_calibration: bool
    allow_reexecution: bool
    updated_at: str
    snapshot_id: str | None = None
    content_hash: str | None = None
    schema_revision: str | None = None
    revision: int | None = None
    previous_snapshot_id: str | None = None
    created_at: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> ExecutionPolicyOutput:
        context = "execution_policy"
        data = coerce_payload_mapping(payload)
        risk_floor = data.get("risk_floor")
        if risk_floor is not None and (
            isinstance(risk_floor, bool) or not isinstance(risk_floor, (int, float))
        ):
            raise TypeError(f"{context}.risk_floor must be a number or null.")
        return cls(
            org_id=_require_string(data, "org_id", context),
            min_confidence=_require_number(data, "min_confidence", context),
            risk_floor=float(risk_floor) if isinstance(risk_floor, (int, float)) else None,
            require_calibration=_require_bool(data, "require_calibration", context),
            allow_reexecution=_require_bool(data, "allow_reexecution", context),
            updated_at=_require_datetime_text(data, "updated_at", context),
            snapshot_id=_optional_string(data, "snapshot_id", context),
            content_hash=_optional_string(data, "content_hash", context),
            schema_revision=_optional_string(data, "schema_revision", context),
            revision=(
                _require_integer(data, "revision", context) if data.get("revision") is not None else None
            ),
            previous_snapshot_id=_optional_string(data, "previous_snapshot_id", context),
            created_at=_optional_datetime_text(data, "created_at", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ExecutionPolicySnapshotListOutput:
    org_id: str
    data: list[ExecutionPolicyOutput] = field(default_factory=list)
    total_snapshots: int = 0

    @classmethod
    def from_api(cls, payload: Any) -> ExecutionPolicySnapshotListOutput:
        context = "execution_policy_snapshots"
        data = coerce_payload_mapping(payload)
        raw_entries = data.get("data")
        if not isinstance(raw_entries, list):
            raise TypeError(f"{context}.data must be a list.")
        return cls(
            org_id=_require_string(data, "org_id", context),
            data=[ExecutionPolicyOutput.from_api(item) for item in raw_entries],
            total_snapshots=_require_integer(data, "total_snapshots", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "org_id": self.org_id,
                "data": [item.to_dict() for item in self.data],
                "total_snapshots": self.total_snapshots,
            }
        )


@dataclass(frozen=True)
class DistributionInfoOutput:
    name: str
    description: str
    required_params: list[str] = field(default_factory=list)
    optional_params: list[str] = field(default_factory=list)
    example: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: Any) -> DistributionInfoOutput:
        context = "distributions.item"
        data = coerce_payload_mapping(payload)
        required_params = data.get("required_params")
        optional_params = data.get("optional_params")
        example = data.get("example")
        if not isinstance(required_params, list) or any(not isinstance(item, str) for item in required_params):
            raise TypeError(f"{context}.required_params must be a list of strings.")
        if not isinstance(optional_params, list) or any(not isinstance(item, str) for item in optional_params):
            raise TypeError(f"{context}.optional_params must be a list of strings.")
        if not isinstance(example, dict):
            raise TypeError(f"{context}.example must be a JSON object.")
        return cls(
            name=_require_string(data, "name", context),
            description=_require_string(data, "description", context),
            required_params=list(required_params),
            optional_params=list(optional_params),
            example=dict(example),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class DistributionListOutput:
    distributions: list[DistributionInfoOutput] = field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 1
    pages: int = 1

    @classmethod
    def from_api(cls, payload: Any) -> DistributionListOutput:
        context = "distributions"
        if isinstance(payload, list):
            items = [DistributionInfoOutput.from_api(item) for item in payload]
            total = len(items)
            return cls(distributions=items, total=total, page=1, limit=total or 1, pages=1)
        data = coerce_payload_mapping(payload)
        raw_items = data.get("distributions")
        if not isinstance(raw_items, list):
            raise TypeError(f"{context}.distributions must be a list.")
        return cls(
            distributions=[DistributionInfoOutput.from_api(item) for item in raw_items],
            total=_require_integer(data, "total", context),
            page=_require_integer(data, "page", context),
            limit=_require_integer(data, "limit", context),
            pages=_require_integer(data, "pages", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "distributions": [item.to_dict() for item in self.distributions],
                "total": self.total,
                "page": self.page,
                "limit": self.limit,
                "pages": self.pages,
            }
        )


@dataclass(frozen=True)
class TemplateInfoOutput:
    id: str
    name: str
    category: str
    description: str
    example_request: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: Any) -> TemplateInfoOutput:
        context = "templates.item"
        data = coerce_payload_mapping(payload)
        example_request = data.get("example_request")
        if not isinstance(example_request, dict):
            raise TypeError(f"{context}.example_request must be a JSON object.")
        return cls(
            id=_require_string(data, "id", context),
            name=_require_string(data, "name", context),
            category=_require_string(data, "category", context),
            description=_require_string(data, "description", context),
            example_request=dict(example_request),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class TemplateListOutput:
    templates: list[TemplateInfoOutput] = field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 1
    pages: int = 1

    @classmethod
    def from_api(cls, payload: Any) -> TemplateListOutput:
        context = "templates"
        if isinstance(payload, list):
            items = [TemplateInfoOutput.from_api(item) for item in payload]
            total = len(items)
            return cls(templates=items, total=total, page=1, limit=total or 1, pages=1)
        data = coerce_payload_mapping(payload)
        raw_items = data.get("templates")
        if not isinstance(raw_items, list):
            raise TypeError(f"{context}.templates must be a list.")
        return cls(
            templates=[TemplateInfoOutput.from_api(item) for item in raw_items],
            total=_require_integer(data, "total", context),
            page=_require_integer(data, "page", context),
            limit=_require_integer(data, "limit", context),
            pages=_require_integer(data, "pages", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "templates": [item.to_dict() for item in self.templates],
                "total": self.total,
                "page": self.page,
                "limit": self.limit,
                "pages": self.pages,
            }
        )


@dataclass(frozen=True)
class BillingInfoOutput:
    plan: str
    stripe_customer_id: str | None = None
    subscription_status: str | None = None
    current_period_end: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> BillingInfoOutput:
        context = "billing_info"
        data = coerce_payload_mapping(payload)
        return cls(
            plan=_require_string(data, "plan", context),
            stripe_customer_id=_optional_string(data, "stripe_customer_id", context),
            subscription_status=_optional_string(data, "subscription_status", context),
            current_period_end=_optional_datetime_text(data, "current_period_end", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class BillingSessionOutput:
    url: str

    @classmethod
    def from_api(cls, payload: Any) -> BillingSessionOutput:
        context = "billing_session"
        data = coerce_payload_mapping(payload)
        return cls(url=_require_string(data, "url", context))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class MeteringBatchOutput:
    accepted: int
    billing_period: str

    @classmethod
    def from_api(cls, payload: Any) -> MeteringBatchOutput:
        context = "metering"
        data = coerce_payload_mapping(payload)
        return cls(
            accepted=_require_integer(data, "accepted", context),
            billing_period=_require_string(data, "billing_period", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class CreditRefreshOutput:
    credits_granted: int
    credits_issued_this_month: int
    monthly_limit: int
    monthly_remaining: int
    billing_period: str
    expires_at: float
    refresh_after: float
    server_time: float

    @classmethod
    def from_api(cls, payload: Any) -> CreditRefreshOutput:
        context = "credit_refresh"
        data = coerce_payload_mapping(payload)
        return cls(
            credits_granted=_require_integer(data, "credits_granted", context),
            credits_issued_this_month=_require_integer(
                data,
                "credits_issued_this_month",
                context,
            ),
            monthly_limit=_require_integer(data, "monthly_limit", context),
            monthly_remaining=_require_integer(data, "monthly_remaining", context),
            billing_period=_require_string(data, "billing_period", context),
            expires_at=_require_number(data, "expires_at", context),
            refresh_after=_require_number(data, "refresh_after", context),
            server_time=_require_number(data, "server_time", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class DeviceRegistrationOutput:
    id: str
    org_id: str
    api_key_id: str
    device_id: str
    platform: str | None = None
    platform_version: str | None = None
    hostname_hash: str | None = None
    sdk_version: str | None = None
    status: str = ""
    last_heartbeat_at: str | None = None
    heartbeat_count: int = 0
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_api(cls, payload: Any) -> DeviceRegistrationOutput:
        context = "devices.item"
        data = coerce_payload_mapping(payload)
        return cls(
            id=_require_string(data, "id", context),
            org_id=_require_string(data, "org_id", context),
            api_key_id=_require_string(data, "api_key_id", context),
            device_id=_require_string(data, "device_id", context),
            platform=_optional_string(data, "platform", context),
            platform_version=_optional_string(data, "platform_version", context),
            hostname_hash=_optional_string(data, "hostname_hash", context),
            sdk_version=_optional_string(data, "sdk_version", context),
            status=_require_string(data, "status", context),
            last_heartbeat_at=_optional_datetime_text(data, "last_heartbeat_at", context),
            heartbeat_count=_require_integer(data, "heartbeat_count", context),
            created_at=_require_datetime_text(data, "created_at", context),
            updated_at=_require_datetime_text(data, "updated_at", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class DeviceListEntryOutput:
    id: str
    device_id: str
    platform: str | None = None
    platform_version: str | None = None
    sdk_version: str | None = None
    status: str = ""
    api_key_label: str | None = None
    api_key_prefix: str | None = None
    registered_at: str | None = None
    last_heartbeat_at: str | None = None
    heartbeat_count: int = 0

    @classmethod
    def from_api(cls, payload: Any) -> DeviceListEntryOutput:
        context = "devices.item"
        data = coerce_payload_mapping(payload)
        return cls(
            id=_require_string(data, "id", context),
            device_id=_require_string(data, "device_id", context),
            platform=_optional_string(data, "platform", context),
            platform_version=_optional_string(data, "platform_version", context),
            sdk_version=_optional_string(data, "sdk_version", context),
            status=_require_string(data, "status", context),
            api_key_label=_optional_string(data, "api_key_label", context),
            api_key_prefix=_optional_string(data, "api_key_prefix", context),
            registered_at=_optional_datetime_text(data, "registered_at", context),
            last_heartbeat_at=_optional_datetime_text(data, "last_heartbeat_at", context),
            heartbeat_count=_require_integer(data, "heartbeat_count", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class DeviceListOutput:
    devices: list[DeviceListEntryOutput] = field(default_factory=list)
    device_count: int = 0
    total: int = 0
    page: int = 1
    limit: int = 1
    pages: int = 1
    device_limit: int = 0
    plan: str = ""

    @classmethod
    def from_api(cls, payload: Any) -> DeviceListOutput:
        context = "devices"
        data = coerce_payload_mapping(payload)
        raw_devices = data.get("devices")
        if not isinstance(raw_devices, list):
            raise TypeError(f"{context}.devices must be a list.")
        return cls(
            devices=[DeviceListEntryOutput.from_api(item) for item in raw_devices],
            device_count=_require_integer(data, "device_count", context),
            total=_require_integer(data, "total", context),
            page=_require_integer(data, "page", context),
            limit=_require_integer(data, "limit", context),
            pages=_require_integer(data, "pages", context),
            device_limit=_require_integer(data, "device_limit", context),
            plan=_require_string(data, "plan", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "devices": [device.to_dict() for device in self.devices],
                "device_count": self.device_count,
                "total": self.total,
                "page": self.page,
                "limit": self.limit,
                "pages": self.pages,
                "device_limit": self.device_limit,
                "plan": self.plan,
            }
        )


@dataclass(frozen=True)
class DeviceRevokeOutput:
    revoked: bool
    registration_id: str

    @classmethod
    def from_api(cls, payload: Any) -> DeviceRevokeOutput:
        context = "revoke_device"
        data = coerce_payload_mapping(payload)
        return cls(
            revoked=_require_bool(data, "revoked", context),
            registration_id=_require_string(data, "registration_id", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))
