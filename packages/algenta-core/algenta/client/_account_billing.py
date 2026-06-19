"""_AccountBillingMixin for the AlgentaClient class.

Extracted from packages/algenta-core/algenta/client.py during modularization.
"""
from __future__ import annotations

from typing import Any

from algenta.client._helpers import _sdk_payload_to_plain_data, _cloud_get  # noqa: F401


class _AccountBillingMixin:
    def health(self) -> dict[str, Any]:
        return _cloud_get("/v1/health", self.api_key, self.base_url)

    def usage(self) -> dict[str, Any]:
        return _cloud_get("/v1/usage", self.api_key, self.base_url)

    def me(self) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().me())

    def update_me(
        self,
        *,
        name: str | None = None,
        org_name: str | None = None,
    ) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().update_me(name=name, org_name=org_name))

    def limits(self) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().limits())

    def distributions(self) -> Any:
        return self._sdk_client().distributions()

    def templates(self) -> Any:
        return self._sdk_client().templates()

    def get_billing_info(self) -> Any:
        return self._sdk_client().get_billing_info()

    def create_billing_checkout(
        self,
        *,
        plan: str | None = None,
    ) -> Any:
        return self._sdk_client().create_billing_checkout(plan=plan)

    def create_billing_portal(self) -> Any:
        return self._sdk_client().create_billing_portal()

    def refresh_credits(
        self,
        *,
        device_id: str,
        billing_period: str,
        credits_used: int = 0,
    ) -> Any:
        return self._sdk_client().refresh_credits(
            device_id=device_id,
            billing_period=billing_period,
            credits_used=credits_used,
        )

    def ingest_metering_events(
        self,
        *,
        device_id: str,
        events: list[dict[str, Any]],
    ) -> Any:
        return self._sdk_client().ingest_metering_events(device_id=device_id, events=events)

    def list_api_keys(self) -> Any:
        return self._sdk_client().list_api_keys()

    def create_api_key(
        self,
        label: str | None = None,
        *,
        name: str | None = None,
        expires_at: Any = None,
        device_limit: int | None = None,
    ) -> Any:
        return _sdk_payload_to_plain_data(
            self._sdk_client().create_api_key(
                label=label,
                name=name,
                expires_at=expires_at,
                device_limit=device_limit,
            )
        )

    def revoke_api_key(self, key_id: str) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().revoke_api_key(key_id))

    def list_team_members(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
    ) -> Any:
        return self._sdk_client().list_team_members(page=page, limit=limit)

    def invite_team_member(
        self,
        *,
        email: str,
        role: str = "member",
    ) -> Any:
        return self._sdk_client().invite_team_member(email=email, role=role)

    def update_team_member_role(
        self,
        user_id: str,
        *,
        role: str,
    ) -> Any:
        return self._sdk_client().update_team_member_role(user_id, role=role)

    def remove_team_member(self, user_id: str) -> Any:
        return self._sdk_client().remove_team_member(user_id)

    def get_audit_logs(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        actor_email: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        result: str | None = None,
        policy_snapshot_id: str | None = None,
        schema_snapshot_id: str | None = None,
        manifest_version: str | None = None,
        request_hash: str | None = None,
    ) -> Any:
        return self._sdk_client().get_audit_logs(
            page=page,
            limit=limit,
            actor_email=actor_email,
            action=action,
            resource_type=resource_type,
            result=result,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            manifest_version=manifest_version,
            request_hash=request_hash,
        )

    def get_audit_log_artifacts(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        actor_email: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        result: str | None = None,
        policy_snapshot_id: str | None = None,
        schema_snapshot_id: str | None = None,
        manifest_version: str | None = None,
        request_hash: str | None = None,
        content_hash: str | None = None,
    ) -> Any:
        return self._sdk_client().get_audit_log_artifacts(
            page=page,
            limit=limit,
            actor_email=actor_email,
            action=action,
            resource_type=resource_type,
            result=result,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            manifest_version=manifest_version,
            request_hash=request_hash,
            content_hash=content_hash,
        )

    def get_execution_policy(self) -> Any:
        return self._sdk_client().get_execution_policy()

    def list_execution_policy_snapshots(self) -> Any:
        return self._sdk_client().list_execution_policy_snapshots()

    def list_devices(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
    ) -> Any:
        return self._sdk_client().list_devices(page=page, limit=limit)

    def revoke_device(self, registration_id: str) -> Any:
        return self._sdk_client().revoke_device(registration_id)

    def update_execution_policy(
        self,
        *,
        min_confidence: float | None = None,
        risk_floor: float | None = None,
        require_calibration: bool | None = None,
        allow_reexecution: bool | None = None,
    ) -> Any:
        return self._sdk_client().update_execution_policy(
            min_confidence=min_confidence,
            risk_floor=risk_floor,
            require_calibration=require_calibration,
            allow_reexecution=allow_reexecution,
        )

