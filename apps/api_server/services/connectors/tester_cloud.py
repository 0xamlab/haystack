from __future__ import annotations

import json
import time
from typing import Any

from apps.api_server.services.egress_guard import (
    EgressPolicyDeniedError,
    audit_context_from_config,
    aws_endpoint_url,
    enforce_egress_sync,
    google_endpoint_url,
)

from .tester_common import (
    ConnectorTestOutcome,
    elapsed_ms,
    failure_outcome,
    success_outcome,
)


async def test_s3_connector(config: dict[str, Any]) -> ConnectorTestOutcome:
    try:
        import boto3

        from apps.api_server.connectors.cloud_connector import _s3_client_kwargs
    except ImportError:
        return failure_outcome(
            message="AWS S3 connector requires boto3 — run: pip install boto3",
            latency_ms=0,
            error_type="invalid_config",
            recoverable=True,
        )

    started_at = time.perf_counter()
    try:
        enforce_egress_sync(
            aws_endpoint_url(
                aws_service_name="s3",
                region_name=str(config.get("region", "us-east-1") or "us-east-1"),
                endpoint_url=(str(config.get("endpoint_url") or "").strip() or None),
            ),
            surface="connector_s3_test",
            explicit_configured=True,
            egress_class="customer_connector",
            audit_context=audit_context_from_config(config),
        )
        s3 = boto3.client("s3", **_s3_client_kwargs(config))
        bucket = str(config.get("bucket", "") or "")
        key = str(config.get("key", "") or "")
        if bucket:
            if key:
                s3.head_object(Bucket=bucket, Key=key)
            else:
                s3.list_objects_v2(Bucket=bucket, MaxKeys=1)
            target = f"s3://{bucket}/{key}" if key else f"s3://{bucket}"
            return success_outcome(f"AWS S3 accessible: {target}", elapsed_ms(started_at))
        s3.list_buckets()
        return success_outcome(
            "AWS S3 accessible (no bucket specified)",
            elapsed_ms(started_at),
        )
    except EgressPolicyDeniedError as exc:
        return failure_outcome(
            message=f"AWS S3 blocked by privacy policy: {exc.decision.reason}",
            latency_ms=elapsed_ms(started_at),
            error_type=exc.code,
            recoverable=False,
        )
    except Exception as exc:
        return failure_outcome(
            message=f"AWS S3 error: {exc}",
            latency_ms=elapsed_ms(started_at),
            exception=exc,
        )


async def test_azure_blob_connector(config: dict[str, Any]) -> ConnectorTestOutcome:
    from apps.api_server.connectors.cloud_connector import AzureBlobConnector

    started_at = time.perf_counter()
    try:
        connector = AzureBlobConnector(config)
        ok, message = await connector.validate_connection()
        if ok:
            return success_outcome(message, elapsed_ms(started_at))
        return failure_outcome(message=message, latency_ms=elapsed_ms(started_at))
    except Exception as exc:
        return failure_outcome(
            message=f"Azure error: {exc}",
            latency_ms=elapsed_ms(started_at),
            exception=exc,
        )


async def test_gcs_connector(config: dict[str, Any]) -> ConnectorTestOutcome:
    from apps.api_server.connectors.cloud_connector import GCSConnector

    started_at = time.perf_counter()
    try:
        connector = GCSConnector(config)
        ok, message = await connector.validate_connection()
        if ok:
            return success_outcome(message, elapsed_ms(started_at))
        return failure_outcome(message=message, latency_ms=elapsed_ms(started_at))
    except Exception as exc:
        return failure_outcome(
            message=f"GCS error: {exc}",
            latency_ms=elapsed_ms(started_at),
            exception=exc,
        )


async def test_bigquery_connector(config: dict[str, Any]) -> ConnectorTestOutcome:
    try:
        from google.cloud import bigquery as bq
    except ImportError:
        return failure_outcome(
            message=(
                "BigQuery connector requires google-cloud-bigquery — "
                "run: pip install google-cloud-bigquery"
            ),
            latency_ms=0,
            error_type="invalid_config",
            recoverable=True,
        )

    started_at = time.perf_counter()
    try:
        enforce_egress_sync(
            google_endpoint_url("bigquery.googleapis.com"),
            surface="connector_bigquery_test",
            explicit_configured=True,
            egress_class="customer_connector",
            audit_context=audit_context_from_config(config),
        )
        service_account_json = config.get("service_account_json")
        if service_account_json:
            parsed = (
                json.loads(service_account_json)
                if isinstance(service_account_json, str)
                else service_account_json
            )
            from google.oauth2 import service_account

            credentials = service_account.Credentials.from_service_account_info(parsed)  # type: ignore[no-untyped-call]
            client = bq.Client(project=config.get("project_id"), credentials=credentials)
        else:
            client = bq.Client(project=config.get("project_id"))
        list(client.list_datasets(max_results=1))
        return success_outcome(
            f"BigQuery accessible (project: {config.get('project_id')})",
            elapsed_ms(started_at),
        )
    except EgressPolicyDeniedError as exc:
        return failure_outcome(
            message=f"BigQuery blocked by privacy policy: {exc.decision.reason}",
            latency_ms=elapsed_ms(started_at),
            error_type=exc.code,
            recoverable=False,
        )
    except Exception as exc:
        return failure_outcome(
            message=f"BigQuery error: {exc}",
            latency_ms=elapsed_ms(started_at),
            exception=exc,
        )
