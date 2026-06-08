"""
algenta.client — Cloud API client for the Algenta platform.

The upgrade path from local to cloud. When your workload grows beyond
local processing, switch to the hosted API with one line change.

Usage:

  import os

  # Local (default — no API key)
  from algenta import simulate
  result = simulate.risk(revenue=100000, cost=70000)

  # Cloud — same API, infinite scale
  from algenta import AlgentaClient
  api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
  if not api_key:
      raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")
  client = AlgentaClient(api_key=api_key)
  result = client.simulate.risk(revenue=100000, cost=70000, runs=1_000_000)

The cloud example above is the Cloud Managed path. In `self_hosted` and
`air_gapped`, pass an explicit self-hosted `base_url` and use the API key
provisioned by your self-hosted operator deployment instead. Private profiles
fail closed and do not silently fall back to Algenta cloud.
"""

from __future__ import annotations

import inspect
import os
from importlib import import_module
from typing import Any

from algenta.privacy_profile import api_key_help_text, resolve_cloud_base_url


def _sdk_payload_to_plain_data(payload: Any) -> Any:
    if isinstance(payload, list):
        return [_sdk_payload_to_plain_data(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(_sdk_payload_to_plain_data(item) for item in payload)
    if isinstance(payload, dict):
        return {
            str(key): _sdk_payload_to_plain_data(value)
            for key, value in payload.items()
        }
    model_dump = getattr(payload, "model_dump", None)
    if callable(model_dump):
        return model_dump()
    to_dict = getattr(payload, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return payload


class AlgentaClient:
    """
    Algenta cloud API client.

    Wraps all local algenta functions with cloud execution.
    All methods have the same signature as their local equivalents,
    except they scale to millions of runs and return results faster.

    Example:
        import os

        api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
        if not api_key:
            raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")
        client = AlgentaClient(api_key=api_key)
        result = client.simulate.risk(revenue=100000, cost=70000, runs=500000)
        print(result.expected_value, result.probability_of_loss)

    That example is the Cloud Managed path. In `self_hosted` and `air_gapped`,
    pass an explicit self-hosted `base_url` and use the API key provisioned by
    your self-hosted operator deployment instead.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
        self.base_url = resolve_cloud_base_url(
            explicit_base_url=base_url,
            component="AlgentaClient",
        )

        if not self.api_key:
            raise ValueError(
                "API key required. Pass api_key explicitly or set ALGENTA_API_KEY / DE_API_KEY environment variables.\n"
                + api_key_help_text(
                    component="AlgentaClient",
                    fallback_base_url=self.base_url,
                )
            )

        self.simulate = _BoundModule("simulate", self.api_key, self.base_url)
        self.decision = _BoundModule("decision", self.api_key, self.base_url)
        self.optimize = _BoundModule("optimize", self.api_key, self.base_url)
        self.forecast = _BoundModule("forecast", self.api_key, self.base_url)
        self._decision_engine_client: Any | None = None

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

    def log_decision(self, request: dict[str, Any]) -> Any:
        return self._sdk_client().log_decision(request)

    def list_decisions(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
        page_size: int | None = None,
        with_outcome_only: bool | None = None,
    ) -> Any:
        return self._sdk_client().list_decisions(
            page=page,
            limit=limit,
            page_size=page_size,
            with_outcome_only=with_outcome_only,
        )

    def get_decision(self, decision_id: str) -> Any:
        return self._sdk_client().get_decision(decision_id)

    def record_outcome(
        self,
        decision_id: str,
        *,
        actual_outcome: float,
        outcome_notes: str | None = None,
    ) -> Any:
        return self._sdk_client().record_outcome(
            decision_id,
            actual_outcome=actual_outcome,
            outcome_notes=outcome_notes,
        )

    def execute_decision(
        self,
        decision_id: str,
        *,
        webhook_url: str,
        timeout_seconds: float = 10.0,
        force: bool = False,
        override_safety: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        return self._sdk_client().execute_decision(
            decision_id,
            webhook_url=webhook_url,
            timeout_seconds=timeout_seconds,
            force=force,
            override_safety=override_safety,
            metadata=metadata,
        )

    def delete_decision(self, decision_id: str) -> Any:
        return self._sdk_client().delete_decision(decision_id)

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

    def _sdk_client(self) -> Any:
        client = self._decision_engine_client
        if client is not None:
            return client
        try:
            decision_engine = import_module("decision_engine")
        except ImportError as exc:
            raise ImportError(
                "Plan-aligned cloud routes require the decision-engine SDK package. "
                "Install algenta-core with cloud/runtime dependencies."
            ) from exc
        client = decision_engine.DecisionEngineClient(
            api_key=self.api_key,
            base_url=self.base_url,
            max_retries=0,
        )
        self._decision_engine_client = client
        return client

    def plan_decision(self, request: dict[str, Any]) -> Any:
        return self._sdk_client().plan_decision(request)

    def product_decision(self, request: dict[str, Any]) -> Any:
        return self._sdk_client().product_decision(request)

    def product_agent_run(self, request: dict[str, Any]) -> Any:
        return self._sdk_client().product_agent_run(request)

    def product_optimize(self, request: dict[str, Any]) -> Any:
        return self._sdk_client().product_optimize(request)

    def product_retrieve(self, request: dict[str, Any]) -> Any:
        return self._sdk_client().product_retrieve(request)

    def product_forecast(self, request: dict[str, Any]) -> Any:
        return self._sdk_client().product_forecast(request)

    def submit_job(
        self,
        request: dict[str, Any] | None = None,
        callback_url: str | None = None,
        **kwargs: Any,
    ) -> Any:
        return self._sdk_client().submit_job(request, callback_url=callback_url, **kwargs)

    def get_job(self, job_id: str) -> Any:
        return self._sdk_client().get_job(job_id)

    def get_job_result(self, job_id: str) -> Any:
        return self._sdk_client().get_job_result(job_id)

    def list_jobs(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        status: str | None = None,
    ) -> Any:
        return self._sdk_client().list_jobs(page=page, limit=limit, status=status)

    def cancel_job(self, job_id: str) -> Any:
        return self._sdk_client().cancel_job(job_id)

    def test_webhook_delivery(self, callback_url: str) -> Any:
        return self._sdk_client().test_webhook_delivery(callback_url)

    def register_trigger(
        self,
        *,
        name: str,
        condition: dict[str, Any],
        simulation_template: dict[str, Any],
        webhook_url: str | None = None,
        execution_webhook_url: str | None = None,
        auto_execute: bool = False,
        description: str | None = None,
    ) -> Any:
        return self._sdk_client().register_trigger(
            name=name,
            condition=condition,
            simulation_template=simulation_template,
            webhook_url=webhook_url,
            execution_webhook_url=execution_webhook_url,
            auto_execute=auto_execute,
            description=description,
        )

    def list_triggers(
        self,
        *,
        status: str = "all",
        page: int | None = None,
        limit: int | None = None,
    ) -> Any:
        return self._sdk_client().list_triggers(status=status, page=page, limit=limit)

    def fire_trigger(
        self,
        trigger_id: str,
        *,
        force: bool = False,
    ) -> Any:
        return self._sdk_client().fire_trigger(trigger_id, force=force)

    def pause_trigger(
        self,
        trigger_id: str,
        *,
        paused: bool = True,
    ) -> Any:
        return self._sdk_client().pause_trigger(trigger_id, paused=paused)

    def delete_trigger(self, trigger_id: str) -> Any:
        return self._sdk_client().delete_trigger(trigger_id)

    def poll_job(
        self,
        job_id: str,
        timeout: float = 300.0,
        poll_interval: float = 2.0,
    ) -> Any:
        return self._sdk_client().poll_job(
            job_id,
            timeout=timeout,
            poll_interval=poll_interval,
        )

    def recommend(self, actions: Any, **kwargs: Any) -> Any:
        return self._sdk_client().recommend(actions, **kwargs)

    def score(
        self,
        request: dict[str, Any],
        scoring_weights: dict[str, float] | None = None,
    ) -> Any:
        return self._sdk_client().score(request, scoring_weights=scoring_weights)

    def batch(self, items: list[dict[str, Any]]) -> Any:
        return self._sdk_client().batch(items)

    def compare(self, scenarios: Any, **kwargs: Any) -> Any:
        return self._sdk_client().compare(scenarios, **kwargs)

    def get_contract(self) -> Any:
        return self._sdk_client().get_contract()

    def list_capability_providers(self) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().list_capability_providers())

    def get_capability_provider(self, provider_id: str) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().get_capability_provider(provider_id))

    def list_capability_bindings(
        self,
        *,
        provider_id: str | None = None,
        scope: str | None = None,
    ) -> Any:
        return _sdk_payload_to_plain_data(
            self._sdk_client().list_capability_bindings(
                provider_id=provider_id,
                scope=scope,
            )
        )

    def create_capability_binding(self, request: dict[str, Any]) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().create_capability_binding(request))

    def get_capability_binding(self, binding_id: str) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().get_capability_binding(binding_id))

    def update_capability_binding(self, binding_id: str, request: dict[str, Any]) -> Any:
        return _sdk_payload_to_plain_data(
            self._sdk_client().update_capability_binding(binding_id, request)
        )

    def delete_capability_binding(self, binding_id: str) -> None:
        self._sdk_client().delete_capability_binding(binding_id)

    def preview_test_capability_binding(self, request: dict[str, Any]) -> Any:
        return _sdk_payload_to_plain_data(
            self._sdk_client().preview_test_capability_binding(request)
        )

    def test_capability_binding(self, binding_id: str) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().test_capability_binding(binding_id))

    def preview_discover_capability_binding(self, request: dict[str, Any]) -> Any:
        return _sdk_payload_to_plain_data(
            self._sdk_client().preview_discover_capability_binding(request)
        )

    def discover_capability_binding(self, binding_id: str) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().discover_capability_binding(binding_id))

    def start_capability_authorization(self, binding_id: str, request: dict[str, Any]) -> Any:
        return _sdk_payload_to_plain_data(
            self._sdk_client().start_capability_authorization(binding_id, request)
        )

    def complete_capability_authorization(self, binding_id: str, request: dict[str, Any]) -> Any:
        return _sdk_payload_to_plain_data(
            self._sdk_client().complete_capability_authorization(binding_id, request)
        )

    def list_capabilities(
        self,
        *,
        kinds: list[str] | tuple[str, ...] | None = None,
        provider_ids: list[str] | tuple[str, ...] | None = None,
        binding_ids: list[str] | tuple[str, ...] | None = None,
    ) -> Any:
        return _sdk_payload_to_plain_data(
            self._sdk_client().list_capabilities(
                kinds=kinds,
                provider_ids=provider_ids,
                binding_ids=binding_ids,
            )
        )

    def get_capability(self, capability_id: str, *, include_instruction: bool = False) -> Any:
        return _sdk_payload_to_plain_data(
            self._sdk_client().get_capability(
                capability_id,
                include_instruction=include_instruction,
            )
        )

    def route_capabilities(self, request: dict[str, Any]) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().route_capabilities(request))

    def execute_capability(self, request: dict[str, Any]) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().execute_capability(request))

    def record_capability_outcome(self, request: dict[str, Any]) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().record_capability_outcome(request))

    def list_skills(self) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().list_skills())

    def enable_skill(
        self,
        *,
        skill_name: str,
        instruction: str,
        description: str | None = None,
        tags: list[str] | None = None,
        artifact_affinities: list[str] | None = None,
        execution_owner: str = "client_managed",
    ) -> Any:
        return _sdk_payload_to_plain_data(
            self._sdk_client().enable_skill(
                skill_name=skill_name,
                instruction=instruction,
                description=description,
                tags=tags,
                artifact_affinities=artifact_affinities,
                execution_owner=execution_owner,
            )
        )

    def disable_skill(self, binding_id: str) -> None:
        self._sdk_client().disable_skill(binding_id)

    def list_mcp_providers(self) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().list_mcp_providers())

    def get_runtime_manifest(self) -> Any:
        return self._sdk_client().get_runtime_manifest()

    def get_runtime_modules(self) -> Any:
        return self._sdk_client().get_runtime_modules()

    def get_runtime_benchmarks(self) -> Any:
        return self._sdk_client().get_runtime_benchmarks()

    def get_runtime_release_validation(self) -> Any:
        return self._sdk_client().get_runtime_release_validation()

    def resolve(self, request: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        return self._sdk_client().resolve(request, **kwargs)

    def query(self, request: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        return self._sdk_client().query(request, **kwargs)

    def query_with_metadata(
        self,
        request: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        return self._sdk_client().query_with_metadata(request, **kwargs)

    def query_batch(self, request: dict[str, Any]) -> Any:
        return self._sdk_client().query_batch(request)

    def query_sql_report(self, request: dict[str, Any]) -> Any:
        return self._sdk_client().query_sql_report(request)

    def verify(self, request: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        return self._sdk_client().verify(request, **kwargs)

    def list_connectors(
        self,
        *,
        page: int = 1,
        limit: int = 200,
    ) -> Any:
        return self._sdk_client().list_connectors(page=page, limit=limit)

    def create_connector(
        self,
        *,
        name: str,
        connector_type: str,
        config: dict[str, Any] | None = None,
        description: str | None = None,
        visibility: str | None = None,
    ) -> Any:
        return self._sdk_client().create_connector(
            name=name,
            connector_type=connector_type,
            config=config,
            description=description,
            visibility=visibility,
        )

    def get_connector(self, connector_id: str) -> Any:
        return self._sdk_client().get_connector(connector_id)

    def update_connector(
        self,
        connector_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        visibility: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> Any:
        return self._sdk_client().update_connector(
            connector_id,
            name=name,
            description=description,
            visibility=visibility,
            config=config,
        )

    def test_connector(self, connector_id: str) -> Any:
        return self._sdk_client().test_connector(connector_id)

    def preview_test_connector(
        self,
        *,
        connector_type: str,
        config: dict[str, Any] | None = None,
    ) -> Any:
        return self._sdk_client().preview_test_connector(
            connector_type=connector_type,
            config=config,
        )

    def browse_connector(self, connector_id: str) -> Any:
        return self._sdk_client().browse_connector(connector_id)

    def preview_browse_connector(
        self,
        *,
        connector_type: str,
        config: dict[str, Any] | None = None,
    ) -> Any:
        return self._sdk_client().preview_browse_connector(
            connector_type=connector_type,
            config=config,
        )

    def delete_connector(self, connector_id: str) -> Any:
        return self._sdk_client().delete_connector(connector_id)

    def create_repository_snapshot(self, repository_id: str, request: dict[str, Any]) -> Any:
        return self._sdk_client().create_repository_snapshot(repository_id, request)

    def get_repository_intelligence_capabilities(self) -> Any:
        return self._sdk_client().get_repository_intelligence_capabilities()

    def get_repository_snapshot(self, repository_id: str, snapshot_id: str) -> Any:
        return self._sdk_client().get_repository_snapshot(repository_id, snapshot_id)

    def triage_repository(self, repository_id: str, request: dict[str, Any]) -> Any:
        return self._sdk_client().triage_repository(repository_id, request)

    def create_repository_decision_plan(self, repository_id: str, request: dict[str, Any]) -> Any:
        return self._sdk_client().create_repository_decision_plan(repository_id, request)

    def query_repository_graph(self, repository_id: str, request: dict[str, Any]) -> Any:
        return self._sdk_client().query_repository_graph(repository_id, request)

    def simulate_repository(self, repository_id: str, request: dict[str, Any]) -> Any:
        return self._sdk_client().simulate_repository(repository_id, request)

    def apply_repository(self, repository_id: str, request: dict[str, Any]) -> Any:
        return self._sdk_client().apply_repository(repository_id, request)

    def connect_data(
        self,
        request: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        return self._sdk_client().connect_data(request, **kwargs)

    def list_datasets(
        self,
        *,
        page: int = 1,
        limit: int = 200,
        search: str | None = None,
        status: str | None = None,
        source_name: str | None = None,
        compact: bool = False,
    ) -> Any:
        return self._sdk_client().list_datasets(
            page=page,
            limit=limit,
            search=search,
            status=status,
            source_name=source_name,
            compact=compact,
        )

    def get_dataset(self, dataset_id: str) -> Any:
        return self._sdk_client().get_dataset(dataset_id)

    def get_dataset_summary(self, dataset_id: str) -> Any:
        return self._sdk_client().get_dataset_summary(dataset_id)

    def refresh_dataset(self, dataset_id: str) -> Any:
        return self._sdk_client().refresh_dataset(dataset_id)

    def delete_dataset(self, dataset_id: str) -> Any:
        return self._sdk_client().delete_dataset(dataset_id)

    def list_deployment_regions(self) -> Any:
        return self._sdk_client().list_deployment_regions()

    def get_deployment(self) -> Any:
        return self._sdk_client().get_deployment()

    def create_deployment(
        self,
        *,
        provider: str = "algenta_shared",
        region: str = "algenta-shared",
        config: dict[str, Any] | None = None,
        billing_markup_pct: float = 20.0,
    ) -> Any:
        return self._sdk_client().create_deployment(
            provider=provider,
            region=region,
            config=config,
            billing_markup_pct=billing_markup_pct,
        )

    def delete_deployment(self, deployment_id: str) -> Any:
        return self._sdk_client().delete_deployment(deployment_id)

    def get_deployment_cost(self, deployment_id: str) -> Any:
        return self._sdk_client().get_deployment_cost(deployment_id)

    def list_models(self) -> Any:
        return self._sdk_client().list_models()

    def resolve_artifact_bridge(
        self,
        *,
        repo_id: str,
        filename: str,
        revision: str | None = None,
        local_files_only: bool = True,
    ) -> Any:
        return self._sdk_client().resolve_artifact_bridge(
            repo_id=repo_id,
            filename=filename,
            revision=revision,
            local_files_only=local_files_only,
        )

    def tokenize(self, text: str, *, model: str = "text.tokenizer") -> Any:
        return self._sdk_client().tokenize(text, model=model)

    def count_tokens(self, text: str, *, model: str = "text.tokenizer") -> Any:
        return self._sdk_client().count_tokens(text, model=model)

    def chat_completions(
        self,
        messages: list[dict[str, str]],
        *,
        model: str = "text.tokenizer",
    ) -> Any:
        return self._sdk_client().chat_completions(messages, model=model)

    def stream_chat_completions(
        self,
        messages: list[dict[str, str]],
        *,
        model: str = "text.tokenizer",
    ) -> Any:
        return self._sdk_client().stream_chat_completions(messages, model=model)

    def responses(
        self,
        input_value: str | list[str],
        *,
        model: str = "text.tokenizer",
        dimensions: int = 64,
    ) -> Any:
        return self._sdk_client().responses(
            input_value,
            model=model,
            dimensions=dimensions,
        )

    def stream_responses(
        self,
        input_value: str | list[str],
        *,
        model: str = "text.tokenizer",
        dimensions: int = 64,
    ) -> Any:
        return self._sdk_client().stream_responses(
            input_value,
            model=model,
            dimensions=dimensions,
        )

    def embeddings(
        self,
        input_value: str | list[str],
        *,
        model: str = "text.hash_embedding_v1",
        dimensions: int = 64,
    ) -> Any:
        return self._sdk_client().embeddings(
            input_value,
            model=model,
            dimensions=dimensions,
        )

    def embedding_similarity(
        self,
        left: list[float],
        right: list[float],
        *,
        model: str = "embeddings.cosine_similarity",
    ) -> Any:
        return self._sdk_client().embedding_similarity(left, right, model=model)

    def rerank(
        self,
        query_embedding: list[float],
        documents: list[dict[str, Any]],
        *,
        model: str = "embeddings.cosine_similarity",
        top_n: int | None = None,
    ) -> Any:
        return self._sdk_client().rerank(
            query_embedding,
            documents,
            model=model,
            top_n=top_n,
        )

    def create_agent_run(
        self,
        *,
        task: str,
        context: dict[str, Any] | None = None,
        tools: list[str] | None = None,
        max_steps: int = 10,
        output_format: str = "text",
        approval_mode: str = "auto",
        start_paused: bool = False,
    ) -> Any:
        return self._sdk_client().create_agent_run(
            task=task,
            context=context,
            tools=tools,
            max_steps=max_steps,
            output_format=output_format,
            approval_mode=approval_mode,
            start_paused=start_paused,
        )

    def get_agent_run(self, run_id: str) -> Any:
        return self._sdk_client().get_agent_run(run_id)

    def list_agent_runs(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        status: str | None = None,
        request_hash: str | None = None,
        policy_snapshot_id: str | None = None,
        schema_snapshot_id: str | None = None,
    ) -> Any:
        return self._sdk_client().list_agent_runs(
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
        )

    def get_agent_run_events(self, run_id: str, *, limit: int = 1000) -> Any:
        return self._sdk_client().get_agent_run_events(run_id, limit=limit)

    def stream_agent_run_events(self, run_id: str, *, limit: int = 1000) -> Any:
        return self._sdk_client().stream_agent_run_events(run_id, limit=limit)

    def list_agent_run_checkpoints(self, run_id: str) -> Any:
        return self._sdk_client().list_agent_run_checkpoints(run_id)

    def query_agent_run_checkpoints(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        status: str | None = None,
        request_hash: str | None = None,
        policy_snapshot_id: str | None = None,
        schema_snapshot_id: str | None = None,
        run_id: str | None = None,
        checkpoint_id: str | None = None,
    ) -> Any:
        return self._sdk_client().query_agent_run_checkpoints(
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            run_id=run_id,
            checkpoint_id=checkpoint_id,
        )

    def list_agent_run_mission_events(self, run_id: str, *, limit: int = 1000) -> Any:
        return self._sdk_client().list_agent_run_mission_events(run_id, limit=limit)

    def query_agent_run_mission_events(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        status: str | None = None,
        request_hash: str | None = None,
        policy_snapshot_id: str | None = None,
        schema_snapshot_id: str | None = None,
        run_id: str | None = None,
        event_type: str | None = None,
    ) -> Any:
        return self._sdk_client().query_agent_run_mission_events(
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            run_id=run_id,
            event_type=event_type,
        )

    def list_agent_run_telemetry(self, run_id: str, *, limit: int = 1000) -> Any:
        return self._sdk_client().list_agent_run_telemetry(run_id, limit=limit)

    def query_agent_run_telemetry(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        status: str | None = None,
        request_hash: str | None = None,
        policy_snapshot_id: str | None = None,
        schema_snapshot_id: str | None = None,
        run_id: str | None = None,
        telemetry_kind: str | None = None,
        module_name: str | None = None,
    ) -> Any:
        return self._sdk_client().query_agent_run_telemetry(
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            run_id=run_id,
            telemetry_kind=telemetry_kind,
            module_name=module_name,
        )

    def replay_agent_run(self, run_id: str, *, checkpoint_id: str | None = None) -> Any:
        return self._sdk_client().replay_agent_run(run_id, checkpoint_id=checkpoint_id)

    def fork_agent_run(self, run_id: str, *, checkpoint_id: str | None = None) -> Any:
        return self._sdk_client().fork_agent_run(run_id, checkpoint_id=checkpoint_id)

    def resume_agent_run(self, run_id: str) -> Any:
        return self._sdk_client().resume_agent_run(run_id)

    def cancel_agent_run(self, run_id: str) -> Any:
        return self._sdk_client().cancel_agent_run(run_id)

    def approve_agent_run(self, run_id: str) -> Any:
        return self._sdk_client().approve_agent_run(run_id)


class _BoundModule:
    """Proxy that calls local module functions with mode='cloud'."""

    def __init__(self, module_name: str, api_key: str, base_url: str) -> None:
        self._module_name = module_name
        self._api_key = api_key
        self._base_url = base_url

    def __getattr__(self, name: str):  # type: ignore[override]
        import importlib

        mod = importlib.import_module(f"algenta.{self._module_name}")
        fn = getattr(mod, name)
        signature = inspect.signature(fn)
        accepted_kwargs = set(signature.parameters)
        api_key = self._api_key
        base_url = self._base_url

        def _bound(*args: Any, **kwargs: Any) -> Any:
            if "mode" in accepted_kwargs:
                kwargs.setdefault("mode", "cloud")
            if "api_key" in accepted_kwargs:
                kwargs.setdefault("api_key", api_key)
            if "base_url" in accepted_kwargs:
                kwargs.setdefault("base_url", base_url)
            return fn(*args, **kwargs)

        return _bound


def _cloud_get(path: str, api_key: str, base_url: str) -> dict[str, Any]:
    try:
        import httpx
    except ImportError:
        raise ImportError("Cloud mode requires: pip install algenta-core[cloud]") from None
    resp = httpx.get(
        f"{base_url}{path}",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
