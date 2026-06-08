"""_ProductsJobsTriggersMixin for the AlgentaClient class.

Extracted from packages/algenta-core/algenta/client.py during modularization.
"""
from __future__ import annotations

from typing import Any

from algenta.client._helpers import _sdk_payload_to_plain_data, _cloud_get  # noqa: F401


class _ProductsJobsTriggersMixin:
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

