"""Unit tests for Data Connector routes and models."""

from datetime import UTC, datetime
from uuid import uuid4


def test_connector_model_enums():
    """ConnectorType and ConnectorStatus must have correct values."""
    from apps.api_server.models.data_connector import ConnectorStatus, ConnectorType

    assert ConnectorType.POSTGRES.value == "postgres"
    assert ConnectorType.CLICKHOUSE.value == "clickhouse"
    assert ConnectorType.ELASTICSEARCH.value == "elasticsearch"
    assert ConnectorType.NEO4J.value == "neo4j"
    assert ConnectorType.REDIS.value == "redis"
    assert ConnectorType.ORACLE.value == "oracle"
    assert ConnectorType.S3.value == "s3"
    assert ConnectorType.REST.value == "rest"
    assert ConnectorStatus.LIVE.value == "live"
    assert ConnectorStatus.ERROR.value == "error"
    assert ConnectorStatus.UNTESTED.value == "untested"


def test_connector_model_all_types_present():
    """All expected connector types must exist."""
    from apps.api_server.models.data_connector import ConnectorType

    expected = {
        "s3",
        "gcs",
        "azure",
        "github_repo",
        "gitlab_repo",
        "bitbucket_repo",
        "local_repo",
        "repo_archive",
        "clickhouse",
        "elasticsearch",
        "neo4j",
        "redis",
        "bigquery",
        "snowflake",
        "redshift",
        "postgres",
        "sqlite",
        "mysql",
        "mssql",
        "oracle",
        "rest",
        "file",
    }
    actual = {t.value for t in ConnectorType}
    assert expected == actual


def test_connector_response_schema():
    """ConnectorResponse must serialize correctly."""
    from apps.api_server.routers.connectors import ConnectorResponse

    r = ConnectorResponse(
        id=str(uuid4()),
        name="prod-postgres",
        connector_type="postgres",
        status="live",
        visibility="private",
        last_tested_at=datetime.now(tz=UTC),
        error_message=None,
        created_at=datetime.now(tz=UTC),
    )
    assert r.connector_type == "postgres"
    assert r.status == "live"
    assert r.visibility == "private"
    assert r.error_message is None


def test_connector_create_schema():
    """ConnectorCreate must validate name and type fields."""
    from apps.api_server.routers.connectors import ConnectorCreate

    payload = ConnectorCreate(
        name="analytics-db",
        connector_type="postgres",
        config={"host": "localhost", "port": "5432", "database": "mydb"},
    )
    assert payload.name == "analytics-db"
    assert payload.connector_type == "postgres"
    assert payload.config is not None
    assert payload.config["host"] == "localhost"


def test_connector_create_without_config():
    """ConnectorCreate config is optional."""
    from apps.api_server.routers.connectors import ConnectorCreate

    payload = ConnectorCreate(name="s3-bucket", connector_type="s3")
    assert payload.config is None


def test_connector_test_result_schema():
    """ConnectorTestResult must include success, message, latency, and typed failure metadata."""
    from apps.api_server.routers.connectors import ConnectorTestResult

    result = ConnectorTestResult(
        success=True,
        message="Connection successful",
        latency_ms=14,
        status="live",
        error_type=None,
        recoverable=None,
    )
    assert result.success is True
    assert result.latency_ms == 14
    assert result.status == "live"

    fail = ConnectorTestResult(
        success=False,
        message="Connection refused",
        status="error",
        error_type="timeout",
        recoverable=True,
    )
    assert fail.success is False
    assert fail.latency_ms is None
    assert fail.error_type == "timeout"
    assert fail.recoverable is True


def test_browse_result_schema_includes_labels() -> None:
    """BrowseResult must expose backend-specific discovery labels."""
    from apps.api_server.routers.connectors import BrowseResult

    result = BrowseResult(
        connector_type="elasticsearch",
        items=[{"id": "logs-a", "label": "logs-a", "kind": "index"}],
        total=1,
        message="Found 1 browsable Elasticsearch indices",
        labels={
            "entity_noun": "index",
            "entity_noun_plural": "indices",
            "row_noun": "document",
            "row_noun_plural": "documents",
            "rows_unavailable": False,
            "sampled": False,
        },
        discovery={
            "scope_noun": "index catalog",
            "returned_count": 1,
            "count_kind": "exact",
            "matching_total_count": 1,
            "scope_total_count": 1,
            "more_available": False,
            "sampling_reason": None,
        },
    )

    assert result.labels["entity_noun"] == "index"
    assert result.labels["row_noun"] == "document"
    assert result.discovery["scope_noun"] == "index catalog"


def test_connectors_router_paths():
    """Connectors router must expose all required endpoints."""
    from apps.api_server.routers.connectors import router

    paths = {r.path for r in router.routes}
    assert "/v1/connectors" in paths
    assert "/v1/connectors/types" in paths
    assert "/v1/connectors/test" in paths
    assert "/v1/connectors/browse" in paths
    assert "/v1/connectors/{connector_id}" in paths
    assert "/v1/connectors/{connector_id}/test" in paths
    assert "/v1/connectors/{connector_id}/browse" in paths


def test_connectors_router_methods():
    """Connectors router must have correct HTTP methods."""
    from apps.api_server.routers.connectors import router

    route_map: dict[str, set[str]] = {}
    for route in router.routes:
        route_map.setdefault(route.path, set()).update(route.methods)
    assert "GET" in route_map["/v1/connectors"]
    assert "GET" in route_map["/v1/connectors/{connector_id}"]
    assert "GET" in route_map["/v1/connectors/types"]
    assert "POST" in route_map["/v1/connectors"]
    assert "POST" in route_map["/v1/connectors/test"]
    assert "POST" in route_map["/v1/connectors/browse"]
    assert "DELETE" in route_map["/v1/connectors/{connector_id}"]
    assert "POST" in route_map["/v1/connectors/{connector_id}/test"]


def test_main_imports_connectors():
    """main.py must import and register the connectors router."""
    from apps.api_server import main

    routes = [r.path for r in main.app.routes]
    assert "/v1/connectors" in routes


def test_migration_file_exists():
    """Migration 0005 must exist for data_connectors table."""
    import os

    path = "apps/api_server/alembic/versions/0005_add_data_connectors.py"
    assert os.path.exists(path), f"Migration file not found: {path}"


def test_migration_references_correct_table():
    """Migration 0005 must reference 'data_connectors' table name."""
    with open("apps/api_server/alembic/versions/0005_add_data_connectors.py") as f:
        content = f.read()
    assert "data_connectors" in content
    assert "connector_type" in content
    assert "connector_status" in content
