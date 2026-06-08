"""
Real connection testers for all supported connector types.

Legacy compatibility:
    test_connector_real() still returns (success, message, latency_ms)

Preferred contract:
    test_connector_real_detailed() returns a structured outcome with
    status, error_type, recoverable, and latency_ms for both success and failure.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from .tester_cloud import (
    test_azure_blob_connector,
    test_bigquery_connector,
    test_gcs_connector,
    test_s3_connector,
)
from .tester_common import (
    ConnectorTestOutcome,
    failure_outcome,
)
from .tester_common import (
    classify_connector_failure as _classify_connector_failure,
)
from .tester_databases import (
    test_clickhouse_connector,
    test_elasticsearch_connector,
    test_neo4j_connector,
    test_postgres_connector,
    test_redis_connector,
    test_snowflake_connector,
    test_sqlite_connector,
)
from .tester_files_http import (
    test_file_connector,
    test_rest_api_connector,
)
from .tester_repositories import test_repository_connector_config

ConnectorTester = Callable[[dict[str, Any]], Awaitable[ConnectorTestOutcome]]
classify_connector_failure = _classify_connector_failure
__all__ = [
    "ConnectorTestOutcome",
    "ConnectorTester",
    "classify_connector_failure",
    "test_connector_real",
    "test_connector_real_detailed",
]

_CONNECTOR_TESTERS: dict[str, ConnectorTester] = {
    "azure": test_azure_blob_connector,
    "azure_blob": test_azure_blob_connector,
    "bigquery": test_bigquery_connector,
    "clickhouse": test_clickhouse_connector,
    "elastic": test_elasticsearch_connector,
    "elasticsearch": test_elasticsearch_connector,
    "file": test_file_connector,
    "file_upload": test_file_connector,
    "gcs": test_gcs_connector,
    "neo4j": test_neo4j_connector,
    "postgres": test_postgres_connector,
    "postgresql": test_postgres_connector,
    "redis": test_redis_connector,
    "redshift": test_postgres_connector,
    "rest": test_rest_api_connector,
    "rest_api": test_rest_api_connector,
    "s3": test_s3_connector,
    "snowflake": test_snowflake_connector,
    "sqlite": test_sqlite_connector,
    "github_repo": lambda config: test_repository_connector_config("github_repo", config),
    "gitlab_repo": lambda config: test_repository_connector_config("gitlab_repo", config),
    "bitbucket_repo": lambda config: test_repository_connector_config("bitbucket_repo", config),
    "local_repo": lambda config: test_repository_connector_config("local_repo", config),
    "repo_archive": lambda config: test_repository_connector_config("repo_archive", config),
}


async def test_connector_real_detailed(
    connector_type: str,
    config: dict[str, Any],
) -> ConnectorTestOutcome:
    """Dispatch to the appropriate tester and return a structured outcome."""
    normalized_type = connector_type.lower().replace("-", "_")
    tester = _CONNECTOR_TESTERS.get(normalized_type)
    if tester is None:
        return failure_outcome(
            message=(
                f"Connector type '{connector_type}' test not yet implemented. "
                "Please verify credentials manually."
            ),
            latency_ms=0,
            error_type="invalid_config",
            recoverable=True,
        )
    return await tester(config)


async def test_connector_real(
    connector_type: str,
    config: dict[str, Any],
) -> tuple[bool, str, int]:
    """Legacy compatibility wrapper returning (success, message, latency_ms)."""
    outcome = await test_connector_real_detailed(connector_type, config)
    return outcome.success, outcome.message, int(outcome.latency_ms or 0)


test_connector_real.__test__ = False  # type: ignore[attr-defined]
test_connector_real_detailed.__test__ = False  # type: ignore[attr-defined]
