# SPDX-License-Identifier: Apache-2.0

"""_AsyncAccountControlPlaneMixin for the AsyncDecisionEngineClient class.

Extracted from packages/python-sdk/decision_engine/async_client_facade.py during modularization.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

    from decision_engine.models_account import (
        APIKeyInfo,
        UsageInfo,
    )
    from decision_engine.models_control_plane import (
        AuditLogResult,
        BillingInfoResult,
        BillingSessionResult,
        CreditRefreshResult,
        DeviceListResult,
        DeviceRevokeResult,
        DistributionListResult,
        ExecutionPolicyResult,
        ExecutionPolicySnapshotListResult,
        MeResult,
        MeteringBatchResult,
        TeamInviteResult,
        TeamListResult,
        TeamRemoveResult,
        TeamRoleUpdateResult,
        TemplateListResult,
    )

# Lazy facade-routed wrappers for the @cache surface-module loaders.
# Tests monkey-patch these on the facade module; each call here re-reads
# the attribute from the facade so the patch propagates into mixin bodies.
def _connector_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._connector_surface_module()


def _repository_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._repository_surface_module()


def _query_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._query_surface_module()


def _contract_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._contract_surface_module()


def _simulation_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._simulation_surface_module()


def _source_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._source_surface_module()


def _job_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._job_surface_module()


def _product_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._product_surface_module()


def _deployment_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._deployment_surface_module()


def _account_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._account_surface_module()


def _control_plane_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._control_plane_surface_module()


def _llm_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._llm_surface_module()


def _agent_run_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._agent_run_surface_module()


def _decision_plan_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._decision_plan_surface_module()


def _decision_memory_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._decision_memory_surface_module()


def _trigger_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._trigger_surface_module()


def _capability_plane_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._capability_plane_surface_module()



class _AsyncAccountControlPlaneMixin:
    async def me(self) -> MeResult:
        return await _account_surface_module().me(self)

    async def update_me(
        self,
        *,
        name: str | None = None,
        org_name: str | None = None,
    ) -> Any:
        return await _account_surface_module().update_me(self, name=name, org_name=org_name)

    async def usage(self) -> UsageInfo:
        return await _account_surface_module().usage(self)

    async def limits(self) -> dict[str, Any]:
        return await _account_surface_module().limits(self)

    async def list_api_keys(self) -> list[APIKeyInfo]:
        return await _account_surface_module().list_api_keys(self)

    async def create_api_key(
        self,
        label: str | None = None,
        *,
        name: str | None = None,
        expires_at: datetime | str | None = None,
        device_limit: int | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"name": name, "expires_at": expires_at}
        if device_limit is not None:
            kwargs["device_limit"] = device_limit
        return await _account_surface_module().create_api_key(self, label, **kwargs)

    async def revoke_api_key(self, key_id: str) -> dict[str, Any]:
        return await _account_surface_module().revoke_api_key(self, key_id)

    async def distributions(self) -> DistributionListResult:
        return await _account_surface_module().distributions(self)

    async def templates(self) -> TemplateListResult:
        return await _account_surface_module().templates(self)

    async def health(self) -> dict[str, Any]:
        return await _account_surface_module().health(self)

    async def version(self) -> dict[str, Any]:
        return await _account_surface_module().version(self)

    async def get_billing_info(self) -> BillingInfoResult:
        return await _control_plane_surface_module().get_billing_info(self)

    async def create_billing_checkout(
        self,
        *,
        plan: str | None = None,
    ) -> BillingSessionResult:
        return await _control_plane_surface_module().create_billing_checkout(self, plan=plan)

    async def create_billing_portal(self) -> BillingSessionResult:
        return await _control_plane_surface_module().create_billing_portal(self)

    async def refresh_credits(
        self,
        *,
        device_id: str,
        billing_period: str,
        credits_used: int = 0,
    ) -> CreditRefreshResult:
        return await _control_plane_surface_module().refresh_credits(
            self,
            device_id=device_id,
            billing_period=billing_period,
            credits_used=credits_used,
        )

    async def ingest_metering_events(
        self,
        *,
        device_id: str,
        events: list[dict[str, Any]],
    ) -> MeteringBatchResult:
        return await _control_plane_surface_module().ingest_metering_events(
            self,
            device_id=device_id,
            events=events,
        )

    async def list_team_members(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
    ) -> TeamListResult:
        return await _control_plane_surface_module().list_team_members(
            self,
            page=page,
            limit=limit,
        )

    async def invite_team_member(
        self,
        *,
        email: str,
        role: str = "member",
    ) -> TeamInviteResult:
        return await _control_plane_surface_module().invite_team_member(
            self,
            email=email,
            role=role,
        )

    async def update_team_member_role(
        self,
        user_id: str,
        *,
        role: str,
    ) -> TeamRoleUpdateResult:
        return await _control_plane_surface_module().update_team_member_role(
            self,
            user_id,
            role=role,
        )

    async def remove_team_member(self, user_id: str) -> TeamRemoveResult:
        return await _control_plane_surface_module().remove_team_member(self, user_id)

    async def get_audit_logs(
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
    ) -> AuditLogResult:
        return await _control_plane_surface_module().get_audit_logs(
            self,
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

    async def get_audit_log_artifacts(
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
        return await _control_plane_surface_module().get_audit_log_artifacts(
            self,
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

    async def get_execution_policy(self) -> ExecutionPolicyResult:
        return await _control_plane_surface_module().get_execution_policy(self)

    async def list_execution_policy_snapshots(self) -> ExecutionPolicySnapshotListResult:
        return await _control_plane_surface_module().list_execution_policy_snapshots(self)

    async def list_devices(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
    ) -> DeviceListResult:
        return await _control_plane_surface_module().list_devices(
            self,
            page=page,
            limit=limit,
        )

    async def revoke_device(self, registration_id: str) -> DeviceRevokeResult:
        return await _control_plane_surface_module().revoke_device(self, registration_id)

    async def update_execution_policy(
        self,
        *,
        min_confidence: float | None = None,
        risk_floor: float | None = None,
        require_calibration: bool | None = None,
        allow_reexecution: bool | None = None,
    ) -> ExecutionPolicyResult:
        return await _control_plane_surface_module().update_execution_policy(
            self,
            min_confidence=min_confidence,
            risk_floor=risk_floor,
            require_calibration=require_calibration,
            allow_reexecution=allow_reexecution,
        )

