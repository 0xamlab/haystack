"""Unit tests for Data Connector routes and models."""
from datetime import UTC, datetime
from uuid import uuid4


def test_connector_model_enums():
    """ConnectorType and ConnectorStatus must have correct values."""
    from apps.api_server.models.data_connector import ConnectorStatus, ConnectorType

    assert ConnectorType.POSTGRES.value == "postgres"
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
        "bigquery",
        "snowflake",
        "redshift",
        "postgres",
        "sqlite",
        "mysql",
        "mssql",
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
    """ConnectorTestResult must include success, message, latency."""
    from apps.api_server.routers.connectors import ConnectorTestResult

    result = ConnectorTestResult(success=True, message="Connection successful", latency_ms=14)
    assert result.success is True
    assert result.latency_ms == 14

    fail = ConnectorTestResult(success=False, message="Connection refused")
    assert fail.success is False
    assert fail.latency_ms is None


def test_connectors_router_paths():
    """Connectors router must expose all required endpoints."""
    from apps.api_server.routers.connectors import router

    paths = {r.path for r in router.routes}
    assert "/v1/connectors" in paths
    assert "/v1/connectors/{connector_id}" in paths
    assert "/v1/connectors/{connector_id}/test" in paths


def test_connectors_router_methods():
    """Connectors router must have correct HTTP methods."""
    from apps.api_server.routers.connectors import router

    route_map: dict[str, set[str]] = {}
    for route in router.routes:
        route_map.setdefault(route.path, set()).update(route.methods)
    assert "GET" in route_map["/v1/connectors"]
    assert "POST" in route_map["/v1/connectors"]
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
