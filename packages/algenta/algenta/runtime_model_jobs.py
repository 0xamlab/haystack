from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from algenta.runtime_model_common import coerce_payload_mapping, jsonable


def _require_string(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _require_identifier_text(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if isinstance(value, UUID):
        return str(value)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _require_integer(data: dict[str, Any], key: str, context: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{context}.{key} must be an integer.")
    return value


def _require_datetime_text(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if isinstance(value, datetime):
        return value.isoformat()
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


def _optional_string(data: dict[str, Any], key: str, context: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


@dataclass(frozen=True)
class JobSubmitOutput:
    job_id: str
    run_id: str
    status: str
    poll_url: str
    message: str = ""

    @classmethod
    def from_api(cls, payload: Any) -> JobSubmitOutput:
        context = "job_submit"
        data = coerce_payload_mapping(payload)
        message = data.get("message", "")
        if not isinstance(message, str):
            raise TypeError(f"{context}.message must be a string.")
        return cls(
            job_id=_require_identifier_text(data, "job_id", context),
            run_id=_require_identifier_text(data, "run_id", context),
            status=_require_string(data, "status", context),
            poll_url=_require_string(data, "poll_url", context),
            message=message,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class JobStatusOutput:
    job_id: str
    run_id: str
    org_id: str
    status: str
    queue_name: str
    retry_count: int
    callback_status: str
    created_at: str
    poll_url: str
    callback_url: str | None = None
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    ttl_expires_at: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> JobStatusOutput:
        context = "job_status"
        data = coerce_payload_mapping(payload)
        return cls(
            job_id=_require_identifier_text(data, "job_id", context),
            run_id=_require_identifier_text(data, "run_id", context),
            org_id=_require_identifier_text(data, "org_id", context),
            status=_require_string(data, "status", context),
            queue_name=_require_string(data, "queue_name", context),
            retry_count=_require_integer(data, "retry_count", context),
            callback_status=_require_string(data, "callback_status", context),
            created_at=_require_datetime_text(data, "created_at", context),
            poll_url=_require_string(data, "poll_url", context),
            callback_url=_optional_string(data, "callback_url", context),
            error_message=_optional_string(data, "error_message", context),
            started_at=_optional_datetime_text(data, "started_at", context),
            completed_at=_optional_datetime_text(data, "completed_at", context),
            ttl_expires_at=_optional_datetime_text(data, "ttl_expires_at", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class JobListOutput:
    jobs: list[JobStatusOutput]
    total: int
    page: int
    limit: int
    pages: int

    @classmethod
    def from_api(cls, payload: Any) -> JobListOutput:
        context = "job_list"
        data = coerce_payload_mapping(payload)
        jobs_payload = data.get("jobs")
        if not isinstance(jobs_payload, list):
            raise TypeError(f"{context}.jobs must be a list.")
        return cls(
            jobs=[JobStatusOutput.from_api(item) for item in jobs_payload],
            total=_require_integer(data, "total", context),
            page=_require_integer(data, "page", context),
            limit=_require_integer(data, "limit", context),
            pages=_require_integer(data, "pages", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class WebhookTestOutput:
    success: bool
    status_code: int
    message: str

    @classmethod
    def from_api(cls, payload: Any) -> WebhookTestOutput:
        context = "webhook_test"
        data = coerce_payload_mapping(payload)
        success = data.get("success")
        if not isinstance(success, bool):
            raise TypeError(f"{context}.success must be a boolean.")
        return cls(
            success=success,
            status_code=_require_integer(data, "status_code", context),
            message=_require_string(data, "message", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))
