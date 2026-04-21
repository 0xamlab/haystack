"""
Data Connector Integration Tests — tests the connector subsystem via live API
and direct Python module imports.

Prerequisites:
  1. API server running: make dev-api  (http://localhost:8000)
  2. PostgreSQL running on :5432
  3. Redis running on :6379

Run:
  python3 tests/integration/test_connectors.py

Covers:
  - Connector CRUD API (create, list, update, delete)
  - Connection testing via API (POST /v1/connectors/{id}/test)
  - Connector browsing via API (GET /v1/connectors/{id}/browse)
  - Error handling (invalid types, missing config)
  - Direct Python module tests (BaseConnector, ConnectorRegistry, FileConnector, etc.)
  - File connector parsing (CSV, JSON)
  - SQL connector (direct module)
  - REST connector (direct module)
  - map_to_simulation auto-mapping logic
"""
import asyncio
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from typing import Any

import pytest

# Ensure project root is on sys.path for direct module imports
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Global socket timeout — prevents any test from hanging indefinitely
socket.setdefaulttimeout(15)

BASE_URL = os.environ.get("DE_BASE_URL", "http://localhost:8000")
API_KEY = os.environ.get("DE_API_KEY", "de_live_LrL6UWSAfgXsTjgfyaboI9aolrsznjLU")

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"
results: list[tuple] = []
timings: list[tuple[str, float]] = []

# Track connector IDs for cleanup
_created_connector_ids: list[str] = []


# ─── HTTP helpers ─────────────────────────────────────────────────────────────
def req(method: str, path: str, body=None, headers=None, auth=True, timeout=10) -> tuple[int, Any, dict[str, str], float]:
    """Make HTTP request, return (status_code, response_body, response_headers, elapsed)."""
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    h = {"Content-Type": "application/json"}
    if auth:
        h["X-API-Key"] = API_KEY
    if headers:
        h.update(headers)
    request = urllib.request.Request(url, data=data, headers=h, method=method)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            elapsed = time.perf_counter() - t0
            body_bytes = resp.read()
            body_data: Any
            try:
                body_data = json.loads(body_bytes)
            except Exception:
                body_data = body_bytes.decode("utf-8", errors="replace")
            return resp.status, body_data, dict(resp.headers), elapsed
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - t0
        body_bytes = e.read()
        body_data2: Any
        try:
            body_data2 = json.loads(body_bytes)
        except Exception:
            body_data2 = body_bytes.decode("utf-8", errors="replace")
        return e.code, body_data2, dict(e.headers), elapsed
    except TimeoutError as err:
        elapsed = time.perf_counter() - t0
        raise TimeoutError(
            f"Request to {url} timed out after {timeout}s (elapsed: {elapsed:.1f}s)"
        ) from err
    except urllib.error.URLError as err:
        if "timed out" in str(err):
            elapsed = time.perf_counter() - t0
            raise TimeoutError(
                f"Request to {url} timed out after {timeout}s (elapsed: {elapsed:.1f}s)"
            ) from err
        raise RuntimeError(
            f"Cannot connect to {BASE_URL} — is the API server running?"
        ) from err


def check(name: str, fn):
    """Run a test function, record pass/fail/skip."""
    t0 = time.perf_counter()
    try:
        fn()
        elapsed = time.perf_counter() - t0
        results.append((PASS, name))
        timings.append((name, elapsed))
        print(f"  {PASS} {name} ({elapsed:.3f}s)")
    except AssertionError as e:
        elapsed = time.perf_counter() - t0
        results.append((FAIL, name, str(e)))
        timings.append((name, elapsed))
        print(f"  {FAIL} {name}: {e}")
    except Exception as e:
        elapsed = time.perf_counter() - t0
        results.append((FAIL, name, str(e)))
        timings.append((name, elapsed))
        print(f"  {FAIL} {name}: {type(e).__name__}: {e}")


def skip(name: str, reason: str):
    """Record a skipped test."""
    results.append((SKIP, name, reason))
    print(f"  {SKIP} {name}: {reason}")


# ─── Small CSV / JSON for inline tests ───────────────────────────────────────
SAMPLE_CSV = """product,revenue,cost,units
Widget A,1200.50,800.25,100
Widget B,950.00,620.00,80
Widget C,1500.75,1100.50,150
Widget D,300.00,250.00,30
"""

SAMPLE_JSON = json.dumps([
    {"name": "Alpha", "profit": 5000, "risk": 0.12},
    {"name": "Beta", "profit": 8000, "risk": 0.25},
    {"name": "Gamma", "profit": 3000, "risk": 0.08},
])

# ─── Database connection info for SQL connector tests ────────────────────────
DB_CONNECTION = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://angel:@localhost:5432/decision_engine",
)


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _create_connector(name: str, connector_type: str, config: dict | None = None) -> dict:
    """Create a connector via API and track its ID for cleanup."""
    status, body, _, _ = req("POST", "/v1/connectors", body={
        "name": name,
        "connector_type": connector_type,
        "config": config,
    })
    if status == 201 and isinstance(body, dict) and "id" in body:
        _created_connector_ids.append(body["id"])
    return {"status": status, "body": body}


def _cleanup_connectors():
    """Delete all connectors created during tests."""
    for cid in _created_connector_ids:
        try:
            req("DELETE", f"/v1/connectors/{cid}")
        except Exception:
            pass
    _created_connector_ids.clear()


# =============================================================================
# Section 1: Connector CRUD API Tests
# =============================================================================
def test_connector_crud_api():
    print("\n── Connector CRUD (API) ──")

    def list_connectors_returns_array():
        status, body, _, _ = req("GET", "/v1/connectors")
        assert status == 200, f"Expected 200, got {status}: {body}"
        assert isinstance(body, list), f"Expected list, got {type(body)}: {body}"

    def create_postgres_connector():
        r = _create_connector("Test Postgres", "postgres", {
            "host": "localhost",
            "port": 5432,
            "database": "decision_engine",
            "user": "angel",
            "password": "",
        })
        assert r["status"] == 201, f"Expected 201, got {r['status']}: {r['body']}"
        body = r["body"]
        assert body["name"] == "Test Postgres"
        assert body["connector_type"] == "postgres"
        assert body["status"] == "untested"
        assert "id" in body
        assert "created_at" in body

    def create_rest_connector():
        r = _create_connector("Test REST API", "rest", {
            "base_url": "https://httpbin.org",
            "auth_type": "none",
        })
        assert r["status"] == 201, f"Expected 201, got {r['status']}: {r['body']}"
        body = r["body"]
        assert body["connector_type"] == "rest"
        assert body["status"] == "untested"

    def create_file_connector():
        r = _create_connector("Test File", "file", {
            "file_type": "csv",
        })
        assert r["status"] == 201, f"Expected 201, got {r['status']}: {r['body']}"
        body = r["body"]
        assert body["connector_type"] == "file"

    def create_s3_connector():
        r = _create_connector("Test S3", "s3", {
            "bucket": "test-bucket",
            "region": "us-east-1",
        })
        assert r["status"] == 201, f"Expected 201, got {r['status']}: {r['body']}"
        assert r["body"]["connector_type"] == "s3"

    def create_rest_api_normalized():
        """rest_api normalizes to rest."""
        r = _create_connector("Test REST Normalized", "rest_api", {
            "base_url": "https://example.com",
        })
        assert r["status"] == 201, f"Expected 201, got {r['status']}: {r['body']}"
        assert r["body"]["connector_type"] == "rest", \
            f"Expected 'rest' (normalized), got {r['body']['connector_type']}"

    def create_postgresql_normalized():
        """postgresql normalizes to postgres."""
        r = _create_connector("Test PG Normalized", "postgresql", {
            "host": "localhost",
        })
        assert r["status"] == 201, f"Expected 201, got {r['status']}: {r['body']}"
        assert r["body"]["connector_type"] == "postgres", \
            f"Expected 'postgres' (normalized), got {r['body']['connector_type']}"

    def create_invalid_type_returns_422():
        r = _create_connector("Bad Type", "nonexistent_type_xyz", {})
        assert r["status"] == 422, f"Expected 422, got {r['status']}: {r['body']}"

    def create_missing_name_returns_422():
        status, body, _, _ = req("POST", "/v1/connectors", body={
            "connector_type": "postgres",
        })
        assert status == 422, f"Expected 422 for missing name, got {status}: {body}"

    def create_missing_body_returns_422():
        status, body, _, _ = req("POST", "/v1/connectors", body=None)
        assert status == 422, f"Expected 422 for missing body, got {status}: {body}"

    def update_connector_name():
        r = _create_connector("Update Me", "postgres", {"host": "localhost"})
        assert r["status"] == 201
        cid = r["body"]["id"]
        status, body, _, _ = req("PATCH", f"/v1/connectors/{cid}", body={
            "name": "Updated Name",
        })
        assert status == 200, f"Expected 200, got {status}: {body}"
        assert body["name"] == "Updated Name"

    def update_connector_config():
        r = _create_connector("Update Config", "postgres", {"host": "localhost"})
        assert r["status"] == 201
        cid = r["body"]["id"]
        status, body, _, _ = req("PATCH", f"/v1/connectors/{cid}", body={
            "config": {"host": "newhost", "port": 5433},
        })
        assert status == 200, f"Expected 200, got {status}: {body}"
        # Status resets to untested after config update
        assert body["status"] == "untested"

    def delete_connector():
        r = _create_connector("Delete Me", "rest", {"base_url": "http://example.com"})
        assert r["status"] == 201
        cid = r["body"]["id"]
        status, body, _, _ = req("DELETE", f"/v1/connectors/{cid}")
        assert status == 204, f"Expected 204, got {status}: {body}"
        # Remove from cleanup list since already deleted
        if cid in _created_connector_ids:
            _created_connector_ids.remove(cid)
        # Verify it's gone
        status2, body2, _, _ = req("GET", f"/v1/connectors/{cid}")
        assert status2 == 404 or status2 == 405, f"Expected 404/405, got {status2}: {body2}"

    def delete_nonexistent_returns_404():
        status, body, _, _ = req("DELETE", "/v1/connectors/00000000-0000-0000-0000-000000000000")
        assert status == 404, f"Expected 404, got {status}: {body}"

    def list_connectors_shows_created():
        r = _create_connector("Visible In List", "file", {"file_type": "csv"})
        assert r["status"] == 201
        cid = r["body"]["id"]
        status, body, _, _ = req("GET", "/v1/connectors")
        assert status == 200
        ids = [c["id"] for c in body]
        assert cid in ids, f"Created connector {cid} not found in list"

    check("List connectors returns array", list_connectors_returns_array)
    check("Create postgres connector (201)", create_postgres_connector)
    check("Create REST connector (201)", create_rest_connector)
    check("Create file connector (201)", create_file_connector)
    check("Create S3 connector (201)", create_s3_connector)
    check("Create rest_api → normalized to rest", create_rest_api_normalized)
    check("Create postgresql → normalized to postgres", create_postgresql_normalized)
    check("Create invalid type returns 422", create_invalid_type_returns_422)
    check("Create missing name returns 422", create_missing_name_returns_422)
    check("Create missing body returns 422", create_missing_body_returns_422)
    check("Update connector name", update_connector_name)
    check("Update connector config resets status", update_connector_config)
    check("Delete connector returns 204", delete_connector)
    check("Delete nonexistent connector returns 404", delete_nonexistent_returns_404)
    check("List connectors shows created", list_connectors_shows_created)


# =============================================================================
# Section 2: Connector Test Endpoint (POST /v1/connectors/{id}/test)
# =============================================================================
@pytest.mark.slow
def test_connector_test_api():
    print("\n── Connector Test Endpoint (API) ──")

    def test_postgres_connection():
        """Test a postgres connector with valid local credentials."""
        r = _create_connector("PG Test Conn", "postgres", {
            "host": "localhost",
            "port": 5432,
            "database": "decision_engine",
            "user": "angel",
            "password": "",
        })
        assert r["status"] == 201
        cid = r["body"]["id"]
        status, body, _, _ = req("POST", f"/v1/connectors/{cid}/test", timeout=15)
        assert status == 200, f"Expected 200, got {status}: {body}"
        assert body["success"] is True, f"Expected success=True: {body}"
        assert "latency_ms" in body
        assert body["latency_ms"] is None or body["latency_ms"] >= 0

    def test_postgres_bad_credentials():
        """Postgres with bad creds should return success=False."""
        r = _create_connector("PG Bad Creds", "postgres", {
            "host": "localhost",
            "port": 5432,
            "database": "nonexistent_db_xyz",
            "user": "nobody",
            "password": "badpass",
        })
        assert r["status"] == 201
        cid = r["body"]["id"]
        status, body, _, _ = req("POST", f"/v1/connectors/{cid}/test", timeout=15)
        assert status == 200, f"Expected 200, got {status}: {body}"
        assert body["success"] is False, f"Expected success=False: {body}"
        assert "failed" in body["message"].lower() or "error" in body["message"].lower(), \
            f"Expected failure message: {body['message']}"

    def test_rest_connector_valid():
        """REST connector with httpbin should succeed."""
        r = _create_connector("REST Test Conn", "rest", {
            "base_url": "https://httpbin.org",
            "auth_type": "none",
        })
        assert r["status"] == 201
        cid = r["body"]["id"]
        status, body, _, _ = req("POST", f"/v1/connectors/{cid}/test", timeout=15)
        assert status == 200, f"Expected 200, got {status}: {body}"
        assert body["success"] is True, f"Expected success=True: {body}"
        assert "reachable" in body["message"].lower() or "200" in body["message"], \
            f"Expected reachable message: {body['message']}"

    def test_rest_connector_unreachable():
        """REST connector to unreachable URL should fail."""
        r = _create_connector("REST Unreachable", "rest", {
            "base_url": "http://192.0.2.1:9999",
            "auth_type": "none",
        })
        assert r["status"] == 201
        cid = r["body"]["id"]
        status, body, _, _ = req("POST", f"/v1/connectors/{cid}/test", timeout=15)
        assert status == 200, f"Expected 200, got {status}: {body}"
        assert body["success"] is False, f"Expected success=False: {body}"

    def test_rest_connector_no_base_url():
        """REST connector with empty base_url should fail."""
        r = _create_connector("REST No URL", "rest", {
            "base_url": "",
        })
        assert r["status"] == 201
        cid = r["body"]["id"]
        status, body, _, _ = req("POST", f"/v1/connectors/{cid}/test", timeout=15)
        assert status == 200, f"Expected 200, got {status}: {body}"
        assert body["success"] is False, f"Expected success=False: {body}"
        assert "base_url" in body["message"].lower(), f"Expected base_url error: {body['message']}"

    def test_status_updates_to_live():
        """After successful test, connector status should be 'live'."""
        r = _create_connector("PG Live Status", "postgres", {
            "host": "localhost",
            "port": 5432,
            "database": "decision_engine",
            "user": "angel",
            "password": "",
        })
        assert r["status"] == 201
        cid = r["body"]["id"]
        assert r["body"]["status"] == "untested"
        # Run test
        status, body, _, _ = req("POST", f"/v1/connectors/{cid}/test", timeout=15)
        assert status == 200
        assert body["success"] is True
        # Check status updated
        status2, body2, _, _ = req("GET", "/v1/connectors")
        assert status2 == 200
        connector = next((c for c in body2 if c["id"] == cid), None)
        assert connector is not None, f"Connector {cid} not found in list"
        assert connector["status"] == "live", \
            f"Expected status='live' after test, got '{connector['status']}'"

    def test_status_updates_to_error():
        """After failed test, connector status should be 'error'."""
        r = _create_connector("PG Error Status", "postgres", {
            "host": "localhost",
            "port": 5432,
            "database": "nonexistent_db_xyz",
            "user": "nobody",
            "password": "badpass",
        })
        assert r["status"] == 201
        cid = r["body"]["id"]
        # Run test
        status, body, _, _ = req("POST", f"/v1/connectors/{cid}/test", timeout=15)
        assert status == 200
        assert body["success"] is False
        # Check status updated to error
        status2, body2, _, _ = req("GET", "/v1/connectors")
        assert status2 == 200
        connector = next((c for c in body2 if c["id"] == cid), None)
        assert connector is not None
        assert connector["status"] == "error", \
            f"Expected status='error' after failed test, got '{connector['status']}'"
        assert connector["error_message"] is not None

    def test_nonexistent_connector_returns_404():
        status, body, _, _ = req("POST", "/v1/connectors/00000000-0000-0000-0000-000000000000/test")
        assert status == 404, f"Expected 404, got {status}: {body}"

    check("Test postgres connection (valid)", test_postgres_connection)
    check("Test postgres bad credentials", test_postgres_bad_credentials)
    check("Test REST connector (httpbin.org)", test_rest_connector_valid)
    check("Test REST connector (unreachable)", test_rest_connector_unreachable)
    check("Test REST connector (no base_url)", test_rest_connector_no_base_url)
    check("Test status updates to 'live'", test_status_updates_to_live)
    check("Test status updates to 'error'", test_status_updates_to_error)
    check("Test nonexistent connector returns 404", test_nonexistent_connector_returns_404)


# =============================================================================
# Section 3: Connector Browse Endpoint
# =============================================================================
def test_connector_browse_api():
    print("\n── Connector Browse (API) ──")

    def browse_postgres_tables():
        """Browse tables in local postgres after successful test."""
        r = _create_connector("PG Browse", "postgres", {
            "host": "localhost",
            "port": 5432,
            "database": "decision_engine",
            "user": "angel",
            "password": "",
        })
        assert r["status"] == 201
        cid = r["body"]["id"]
        # Must test first to get 'live' status
        status, body, _, _ = req("POST", f"/v1/connectors/{cid}/test", timeout=15)
        assert status == 200 and body["success"] is True, f"Test failed: {body}"
        # Browse
        status2, body2, _, _ = req("GET", f"/v1/connectors/{cid}/browse", timeout=15)
        assert status2 == 200, f"Expected 200, got {status2}: {body2}"
        assert body2["connector_type"] == "postgres"
        assert isinstance(body2["items"], list)
        assert body2["total"] >= 0
        assert "message" in body2

    def browse_untested_connector_returns_409():
        """Browse on untested connector should return 409."""
        r = _create_connector("PG Untested Browse", "postgres", {
            "host": "localhost",
        })
        assert r["status"] == 201
        cid = r["body"]["id"]
        status, body, _, _ = req("GET", f"/v1/connectors/{cid}/browse", timeout=15)
        assert status == 409, f"Expected 409 for untested connector, got {status}: {body}"

    def browse_rest_connector():
        """Browse a REST connector after successful test."""
        r = _create_connector("REST Browse", "rest", {
            "base_url": "https://httpbin.org",
            "auth_type": "none",
        })
        assert r["status"] == 201
        cid = r["body"]["id"]
        # Test first
        status, body, _, _ = req("POST", f"/v1/connectors/{cid}/test", timeout=15)
        assert status == 200 and body["success"] is True
        # Browse
        status2, body2, _, _ = req("GET", f"/v1/connectors/{cid}/browse", timeout=15)
        assert status2 == 200, f"Expected 200, got {status2}: {body2}"
        assert body2["connector_type"] == "rest"
        assert isinstance(body2["items"], list)

    check("Browse postgres tables", browse_postgres_tables)
    check("Browse untested connector returns 409", browse_untested_connector_returns_409)
    check("Browse REST connector", browse_rest_connector)


# =============================================================================
# Section 4: Direct Python Module Tests — BaseConnector & Registry
# =============================================================================
def test_python_module_direct():
    print("\n── Python Module Direct Tests ──")

    def import_connector_modules():
        """Verify all connector modules import successfully."""
        from apps.api_server.connectors import (
            BaseConnector,
            ConnectorRegistry,
            FileConnector,
            RESTConnector,
            SQLConnector,
        )
        assert BaseConnector is not None
        assert ConnectorRegistry is not None
        assert RESTConnector is not None
        assert SQLConnector is not None
        assert FileConnector is not None

    def base_connector_is_abstract():
        """BaseConnector cannot be instantiated directly."""
        from apps.api_server.connectors import BaseConnector
        try:
            BaseConnector(config={})  # type: ignore[abstract]
            raise AssertionError(
                "Should not be able to instantiate abstract BaseConnector"
            )
        except TypeError:
            pass  # Expected

    def registry_available_types():
        """ConnectorRegistry.available_types() returns all registered types."""
        from apps.api_server.connectors import ConnectorRegistry
        types = ConnectorRegistry.available_types()
        assert "rest_api" in types, f"rest_api not in {types}"
        assert "sql" in types, f"sql not in {types}"
        assert "file" in types, f"file not in {types}"

    def registry_get_returns_classes():
        """ConnectorRegistry.get() returns correct class objects."""
        from apps.api_server.connectors import (
            ConnectorRegistry,
            FileConnector,
            RESTConnector,
            SQLConnector,
        )
        assert ConnectorRegistry.get("rest_api") is RESTConnector
        assert ConnectorRegistry.get("sql") is SQLConnector
        assert ConnectorRegistry.get("file") is FileConnector
        assert ConnectorRegistry.get("nonexistent") is None

    def registry_create_instantiates():
        """ConnectorRegistry.create() makes a proper connector instance."""
        from apps.api_server.connectors import ConnectorRegistry, RESTConnector
        connector = ConnectorRegistry.create("rest_api", {"url": "http://example.com"})
        assert isinstance(connector, RESTConnector)
        assert connector.config["url"] == "http://example.com"

    def registry_create_invalid_type():
        """ConnectorRegistry.create() raises ValueError for unknown type."""
        from apps.api_server.connectors import ConnectorRegistry
        try:
            ConnectorRegistry.create("nonexistent", {})
            raise AssertionError("Should raise ValueError")
        except ValueError as e:
            assert "Unknown connector type" in str(e)

    def rest_connector_attributes():
        """RESTConnector has correct connector_type."""
        from apps.api_server.connectors import RESTConnector
        assert RESTConnector.connector_type == "rest_api"
        c = RESTConnector({"url": "http://test.com", "method": "POST", "timeout": 5})
        assert c.config["method"] == "POST"
        assert c.config["timeout"] == 5

    def sql_connector_attributes():
        """SQLConnector has correct connector_type."""
        from apps.api_server.connectors import SQLConnector
        assert SQLConnector.connector_type == "sql"
        c = SQLConnector({"connection_string": "postgres://...", "query": "SELECT 1"})
        assert c.config["query"] == "SELECT 1"

    def file_connector_attributes():
        """FileConnector has correct connector_type."""
        from apps.api_server.connectors import FileConnector
        assert FileConnector.connector_type == "file"
        c = FileConnector({"file_type": "json", "content": "{}"})
        assert c.config["file_type"] == "json"

    check("Import all connector modules", import_connector_modules)
    check("BaseConnector is abstract", base_connector_is_abstract)
    check("ConnectorRegistry.available_types()", registry_available_types)
    check("ConnectorRegistry.get() returns classes", registry_get_returns_classes)
    check("ConnectorRegistry.create() instantiates", registry_create_instantiates)
    check("ConnectorRegistry.create() rejects unknown type", registry_create_invalid_type)
    check("RESTConnector attributes", rest_connector_attributes)
    check("SQLConnector attributes", sql_connector_attributes)
    check("FileConnector attributes", file_connector_attributes)


# =============================================================================
# Section 5: FileConnector Direct Tests
# =============================================================================
def test_file_connector_direct():
    print("\n── FileConnector (Direct) ──")

    def _run(coro):
        """Run async coroutine synchronously."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def file_parse_csv_directly():
        """FileConnector._parse_csv() parses CSV text to list of dicts."""
        from apps.api_server.connectors import FileConnector
        records = FileConnector._parse_csv(SAMPLE_CSV)
        assert len(records) == 4, f"Expected 4 records, got {len(records)}"
        assert records[0]["product"] == "Widget A"
        assert records[0]["revenue"] == 1200.50
        assert records[0]["cost"] == 800.25
        assert records[0]["units"] == 100.0

    def file_parse_json_directly():
        """FileConnector._parse_json() parses JSON text."""
        from apps.api_server.connectors import FileConnector
        records = FileConnector._parse_json(SAMPLE_JSON)
        assert len(records) == 3
        assert records[0]["name"] == "Alpha"
        assert records[1]["profit"] == 8000

    def file_parse_json_single_object():
        """FileConnector._parse_json() wraps single dict in list."""
        from apps.api_server.connectors import FileConnector
        records = FileConnector._parse_json('{"x": 1, "y": 2}')
        assert len(records) == 1
        assert records[0]["x"] == 1

    def file_fetch_data_async():
        """FileConnector.fetch_data() works with CSV content."""
        from apps.api_server.connectors import FileConnector
        c = FileConnector({"file_type": "csv", "content": SAMPLE_CSV})
        records = _run(c.fetch_data())
        assert len(records) == 4
        assert records[2]["product"] == "Widget C"

    def file_fetch_data_json_async():
        """FileConnector.fetch_data() works with JSON content."""
        from apps.api_server.connectors import FileConnector
        c = FileConnector({"file_type": "json", "content": SAMPLE_JSON})
        records = _run(c.fetch_data())
        assert len(records) == 3
        assert records[0]["name"] == "Alpha"

    def file_validate_async():
        """FileConnector.validate_connection() returns (True, message)."""
        from apps.api_server.connectors import FileConnector
        c = FileConnector({"file_type": "csv", "content": SAMPLE_CSV})
        success, msg = _run(c.validate_connection())
        assert success is True
        assert "4" in msg, f"Expected '4' records in message: {msg}"

    def file_empty_returns_empty():
        """FileConnector with no content returns empty list."""
        from apps.api_server.connectors import FileConnector
        c = FileConnector({"file_type": "csv", "content": ""})
        records = _run(c.fetch_data())
        assert records == [], f"Expected empty list, got {records}"

    def file_parquet_invalid_content_raises():
        """FileConnector fail-closes on invalid parquet payloads."""
        from apps.api_server.connectors import FileConnector

        try:
            import pyarrow.lib as pa_lib

            expected_error = pa_lib.ArrowInvalid
        except ImportError:
            expected_error = ImportError

        c = FileConnector({"file_type": "parquet", "content": "some data"})
        with pytest.raises(expected_error):
            _run(c.fetch_data())

    def file_connector_with_filepath():
        """FileConnector with file_path reads from disk."""
        from apps.api_server.connectors import FileConnector
        csv_path = os.path.join(PROJECT_ROOT, "test_files", "bookings_new.csv")
        if not os.path.exists(csv_path):
            raise AssertionError(f"Test file not found: {csv_path}")
        c = FileConnector({"file_type": "csv", "file_path": csv_path})
        records = _run(c.fetch_data())
        assert len(records) > 100, f"Expected many records from full CSV, got {len(records)}"

    def file_connector_missing_filepath():
        """FileConnector with nonexistent file_path raises error."""
        from apps.api_server.connectors import FileConnector
        c = FileConnector({"file_type": "csv", "file_path": "/nonexistent/path/data.csv"})
        try:
            _run(c.fetch_data())
            raise AssertionError("Should have raised FileNotFoundError")
        except FileNotFoundError:
            pass
        except OSError:
            pass

    def file_parse_real_csv():
        """Parse a real CSV file directly with FileConnector."""
        from apps.api_server.connectors import FileConnector
        csv_path = os.path.join(PROJECT_ROOT, "test_files", "bookings_new.csv")
        if not os.path.exists(csv_path):
            raise AssertionError(f"Test file not found: {csv_path}")
        with open(csv_path) as f:
            lines = [next(f) for _ in range(6)]
        small_csv = "".join(lines)
        records = FileConnector._parse_csv(small_csv)
        assert len(records) == 5, f"Expected 5 records, got {len(records)}"
        assert "PART_NUMBER" in records[0], f"Expected PART_NUMBER: {list(records[0].keys())[:5]}"

    check("FileConnector._parse_csv() directly", file_parse_csv_directly)
    check("FileConnector._parse_json() directly", file_parse_json_directly)
    check("FileConnector._parse_json() single object", file_parse_json_single_object)
    check("FileConnector.fetch_data() CSV async", file_fetch_data_async)
    check("FileConnector.fetch_data() JSON async", file_fetch_data_json_async)
    check("FileConnector.validate_connection() async", file_validate_async)
    check("FileConnector empty content returns []", file_empty_returns_empty)
    check(
        "FileConnector invalid parquet content fails cleanly",
        file_parquet_invalid_content_raises,
    )
    check("FileConnector with file_path reads from disk", file_connector_with_filepath)
    check("FileConnector nonexistent file_path raises error", file_connector_missing_filepath)
    check("Parse real CSV (bookings_new.csv)", file_parse_real_csv)


# =============================================================================
# Section 6: SQLConnector Direct Tests
# =============================================================================
def test_sql_connector_direct():
    print("\n── SQLConnector (Direct) ──")

    def _run(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def sql_validate_connection():
        """SQLConnector.validate_connection() against local Postgres."""
        from apps.api_server.connectors import SQLConnector
        c = SQLConnector({"connection_string": DB_CONNECTION, "query": "SELECT 1"})
        success, msg = _run(c.validate_connection())
        assert success is True, f"Expected success=True: {msg}"
        assert "Connected" in msg, f"Expected 'Connected' in message: {msg}"

    def sql_fetch_data():
        """SQLConnector.fetch_data() returns records from a query."""
        from apps.api_server.connectors import SQLConnector
        c = SQLConnector({
            "connection_string": DB_CONNECTION,
            "query": "SELECT 42 as answer, 3.14 as pi_val",
        })
        records = _run(c.fetch_data())
        assert len(records) == 1, f"Expected 1 record, got {len(records)}"
        assert records[0]["answer"] == 42, f"Expected answer=42: {records[0]}"

    def sql_missing_fields():
        """SQLConnector raises ValueError when config is incomplete."""
        from apps.api_server.connectors import SQLConnector
        c = SQLConnector({"connection_string": "", "query": ""})
        try:
            _run(c.fetch_data())
            raise AssertionError("Should have raised ValueError")
        except ValueError as e:
            assert "required" in str(e).lower(), f"Expected 'required' in error: {e}"

    def sql_bad_connection():
        """SQLConnector.validate_connection() with bad DSN returns failure."""
        from apps.api_server.connectors import SQLConnector
        c = SQLConnector({
            "connection_string": "postgresql+asyncpg://nobody:badpass@localhost:5432/nonexistent_db_xyz",
            "query": "SELECT 1",
        })
        success, msg = _run(c.validate_connection())
        assert success is False, f"Expected success=False: {msg}"
        assert "failed" in msg.lower(), f"Expected 'failed' in message: {msg}"

    def sql_fetch_multiple_rows():
        """SQLConnector returns multiple rows correctly."""
        from apps.api_server.connectors import SQLConnector
        c = SQLConnector({
            "connection_string": DB_CONNECTION,
            "query": "SELECT generate_series(1, 5) as n",
        })
        records = _run(c.fetch_data())
        assert len(records) == 5, f"Expected 5 records, got {len(records)}"
        values = sorted([r["n"] for r in records])
        assert values == [1, 2, 3, 4, 5], f"Expected [1..5], got {values}"

    check("SQLConnector.validate_connection() (local Postgres)", sql_validate_connection)
    check("SQLConnector.fetch_data() returns records", sql_fetch_data)
    check("SQLConnector raises ValueError for missing config", sql_missing_fields)
    check("SQLConnector bad connection returns failure", sql_bad_connection)
    check("SQLConnector fetch multiple rows", sql_fetch_multiple_rows)


# =============================================================================
# Section 7: RESTConnector Direct Tests
# =============================================================================
@pytest.mark.slow
def test_rest_connector_direct():
    print("\n── RESTConnector (Direct) ──")

    def _run(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def rest_validate_unreachable():
        """RESTConnector.validate_connection() with unreachable URL returns failure."""
        from apps.api_server.connectors import RESTConnector
        c = RESTConnector({"url": "http://192.0.2.1:9999/nothing", "timeout": 2})
        success, msg = _run(c.validate_connection())
        assert success is False, f"Expected success=False: {msg}"
        assert "failed" in msg.lower(), f"Expected 'failed' in message: {msg}"

    def rest_config_defaults():
        """RESTConnector config has sensible defaults."""
        from apps.api_server.connectors import RESTConnector
        c = RESTConnector({"url": "http://example.com"})
        assert c.config.get("url") == "http://example.com"
        assert c.config.get("method", "GET") == "GET"
        assert c.config.get("timeout", 30) == 30

    def rest_fetch_httpbin():
        """RESTConnector.fetch_data() retrieves data from httpbin.org."""
        from apps.api_server.connectors import RESTConnector
        c = RESTConnector({
            "url": "https://httpbin.org/get",
            "method": "GET",
            "timeout": 10,
        })
        records = _run(c.fetch_data())
        assert len(records) >= 1, f"Expected ≥1 records, got {len(records)}"
        assert "url" in records[0] or "headers" in records[0], \
            f"Expected httpbin response fields: {list(records[0].keys())}"

    def rest_fetch_with_data_path():
        """RESTConnector extracts nested data via data_path."""
        from apps.api_server.connectors import RESTConnector
        c = RESTConnector({
            "url": "https://httpbin.org/get",
            "data_path": "headers",
            "timeout": 10,
        })
        records = _run(c.fetch_data())
        assert len(records) >= 1
        # headers dict should contain Host at minimum
        assert "Host" in records[0] or len(records[0]) > 0, \
            f"Expected data_path to extract headers dict: {records[0]}"

    check("RESTConnector validate unreachable URL", rest_validate_unreachable)
    check("RESTConnector config defaults", rest_config_defaults)
    check("RESTConnector fetch from httpbin.org", rest_fetch_httpbin)
    check("RESTConnector fetch with data_path", rest_fetch_with_data_path)


# =============================================================================
# Section 8: map_to_simulation Auto-Mapping Tests
# =============================================================================
def test_map_to_simulation():
    print("\n── map_to_simulation (Direct) ──")

    def _run(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def map_empty_data():
        """map_to_simulation() with empty data returns empty payload."""
        from apps.api_server.connectors import FileConnector
        c = FileConnector({"file_type": "csv", "content": SAMPLE_CSV})
        payload = _run(c.map_to_simulation([]))
        assert payload["variables"] == []
        assert payload["objective_function"] == ""

    def map_polarity_detection():
        """map_to_simulation() correctly classifies positive/negative fields."""
        from apps.api_server.connectors import FileConnector
        c = FileConnector({"file_type": "csv", "content": ""})
        data = [
            {"revenue": 1000, "expense": 500, "growth": 0.1, "risk": 0.05},
            {"revenue": 1200, "expense": 600, "growth": 0.15, "risk": 0.08},
        ]
        payload = _run(c.map_to_simulation(data))
        obj = payload["objective_function"]
        assert "revenue" in obj, f"Expected 'revenue' in objective: {obj}"
        assert "expense" in obj, f"Expected 'expense' in objective: {obj}"
        # Check polarity
        assert "- expense" in obj or "- risk" in obj, \
            f"Expected negative polarity for expense/risk in: {obj}"

    def map_distribution_assignment():
        """map_to_simulation() assigns correct distribution types."""
        from apps.api_server.connectors import FileConnector
        c = FileConnector({"file_type": "csv", "content": ""})
        data = [
            {"price": 100, "probability": 0.5, "fixed_val": 42},
            {"price": 200, "probability": 0.8, "fixed_val": 42},
            {"price": 150, "probability": 0.3, "fixed_val": 42},
        ]
        payload = _run(c.map_to_simulation(data))
        vars_by_name = {v["name"]: v for v in payload["variables"]}

        assert vars_by_name["price"]["distribution"] == "triangular", \
            f"Expected triangular for price: {vars_by_name['price']}"
        assert vars_by_name["probability"]["distribution"] == "beta", \
            f"Expected beta for probability: {vars_by_name['probability']}"
        assert vars_by_name["fixed_val"]["distribution"] == "fixed", \
            f"Expected fixed for fixed_val: {vars_by_name['fixed_val']}"

    def map_metadata():
        """map_to_simulation() includes _connector_metadata."""
        from apps.api_server.connectors import RESTConnector
        c = RESTConnector({"url": "http://example.com"})
        data = [{"val": 10}, {"val": 20}]
        payload = _run(c.map_to_simulation(data, domain="test"))
        meta = payload["_connector_metadata"]
        assert meta["source_type"] == "rest_api"
        assert meta["records_analyzed"] == 2
        assert meta["domain"] == "test"
        assert meta["fields_mapped"] == 1

    def map_simulation_structure():
        """map_to_simulation() produces complete simulation payload."""
        from apps.api_server.connectors import FileConnector
        c = FileConnector({"file_type": "csv", "content": ""})
        data = [
            {"revenue": 1000, "cost": 500},
            {"revenue": 1500, "cost": 700},
        ]
        payload = _run(c.map_to_simulation(data))
        assert payload["engine_type"] == "monte_carlo"
        assert payload["runs"] == 10000
        assert "variables" in payload
        assert "objective_function" in payload
        assert "scoring" in payload
        assert len(payload["variables"]) == 2

    def map_variable_structure():
        """Each variable has name, distribution, and params."""
        from apps.api_server.connectors import FileConnector
        c = FileConnector({"file_type": "csv", "content": ""})
        data = [
            {"sales": 100, "margin": 0.3},
            {"sales": 200, "margin": 0.5},
        ]
        payload = _run(c.map_to_simulation(data))
        for var in payload["variables"]:
            assert "name" in var, f"Variable missing 'name': {var}"
            assert "distribution" in var, f"Variable missing 'distribution': {var}"
            assert "params" in var, f"Variable missing 'params': {var}"
            assert var["distribution"] in ("triangular", "beta", "fixed"), \
                f"Unexpected distribution: {var['distribution']}"

    def map_csv_full_lifecycle():
        """Full lifecycle: parse CSV → map_to_simulation → payload."""
        from apps.api_server.connectors import FileConnector
        csv_data = """sales,marketing_cost,churn_rate,profit_margin
10000,3000,0.05,0.35
12000,3500,0.08,0.32
8000,2800,0.03,0.40
15000,4000,0.10,0.28
"""
        c = FileConnector({"file_type": "csv", "content": csv_data})
        records = _run(c.fetch_data())
        assert len(records) == 4

        payload = _run(c.map_to_simulation(records, domain="business"))
        var_names = [v["name"] for v in payload["variables"]]
        assert "sales" in var_names
        assert "profit_margin" in var_names

        # profit_margin 0.28-0.40 range (all <1) → beta
        pm_var = next(v for v in payload["variables"] if v["name"] == "profit_margin")
        assert pm_var["distribution"] == "beta", \
            f"Expected beta for profit_margin, got {pm_var['distribution']}"

        meta = payload["_connector_metadata"]
        assert meta["source_type"] == "file"
        assert meta["records_analyzed"] == 4
        assert meta["domain"] == "business"

    check("map_to_simulation with empty data", map_empty_data)
    check("map_to_simulation polarity detection", map_polarity_detection)
    check("map_to_simulation distribution assignment", map_distribution_assignment)
    check("map_to_simulation metadata", map_metadata)
    check("map_to_simulation structure", map_simulation_structure)
    check("map_to_simulation variable structure", map_variable_structure)
    check("CSV → fetch → map_to_simulation lifecycle", map_csv_full_lifecycle)


# =============================================================================
# Section 9: Connector Service / Schemas Direct Tests
# =============================================================================
def test_connector_service_direct():
    print("\n── Connector Service (Direct) ──")

    def import_service_schemas():
        """Import service-level schemas and constants."""
        from apps.api_server.services.connectors import (  # noqa: F401
            VALID_TYPES,
            ConnectorCreate,
            ConnectorResponse,
            ConnectorTestResult,
            ConnectorUpdate,
            normalize_type,
        )
        assert len(VALID_TYPES) >= 10, f"Expected ≥10 valid types, got {len(VALID_TYPES)}"

    def valid_types_include_major_connectors():
        """VALID_TYPES includes postgres, rest, s3, file."""
        from apps.api_server.services.connectors import VALID_TYPES
        for expected in ["postgres", "rest", "s3", "file"]:
            assert expected in VALID_TYPES, f"{expected} not in VALID_TYPES: {VALID_TYPES}"

    def normalize_type_mappings():
        """normalize_type maps aliases correctly."""
        from apps.api_server.services.connectors import normalize_type
        assert normalize_type("postgresql") == "postgres"
        assert normalize_type("rest_api") == "rest"
        assert normalize_type("file_upload") == "file"
        assert normalize_type("postgres") == "postgres"  # identity
        assert normalize_type("s3") == "s3"  # identity

    def connector_create_schema():
        """ConnectorCreate schema validates correctly."""
        from apps.api_server.services.connectors import ConnectorCreate
        c = ConnectorCreate(name="Test", connector_type="postgres", config={"host": "localhost"})
        assert c.name == "Test"
        assert c.connector_type == "postgres"
        assert c.config == {"host": "localhost"}

    def connector_create_optional_config():
        """ConnectorCreate allows None config."""
        from apps.api_server.services.connectors import ConnectorCreate
        c = ConnectorCreate(name="Test", connector_type="rest")
        assert c.config is None

    def connector_test_result_schema():
        """ConnectorTestResult schema works."""
        from apps.api_server.services.connectors import ConnectorTestResult
        r = ConnectorTestResult(success=True, message="OK", latency_ms=42)
        assert r.success is True
        assert r.latency_ms == 42

    check("Import service schemas", import_service_schemas)
    check("VALID_TYPES includes major connectors", valid_types_include_major_connectors)
    check("normalize_type mappings", normalize_type_mappings)
    check("ConnectorCreate schema", connector_create_schema)
    check("ConnectorCreate optional config", connector_create_optional_config)
    check("ConnectorTestResult schema", connector_test_result_schema)


# =============================================================================
# Section 10: Connector Tester Direct Tests
# =============================================================================
@pytest.mark.slow
def test_connector_tester_direct():
    print("\n── Connector Tester (Direct) ──")

    def _run(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def tester_postgres_valid():
        """test_connector_real for postgres with valid creds."""
        from apps.api_server.services.connectors.tester import test_connector_real
        success, msg, ms = _run(test_connector_real("postgres", {
            "host": "localhost",
            "port": 5432,
            "database": "decision_engine",
            "user": "angel",
            "password": "",
        }))
        assert success is True, f"Expected success=True: {msg}"
        assert ms > 0, f"Expected latency > 0, got {ms}"

    def tester_postgres_bad():
        """test_connector_real for postgres with bad creds."""
        from apps.api_server.services.connectors.tester import test_connector_real
        success, msg, _ms = _run(test_connector_real("postgres", {
            "host": "localhost",
            "port": 5432,
            "database": "nonexistent_db",
            "user": "nobody",
            "password": "badpass",
        }))
        assert success is False, f"Expected success=False: {msg}"

    def tester_rest_valid():
        """test_connector_real for rest with httpbin."""
        from apps.api_server.services.connectors.tester import test_connector_real
        success, msg, ms = _run(test_connector_real("rest", {
            "base_url": "https://httpbin.org",
        }))
        assert success is True, f"Expected success=True: {msg}"
        assert ms > 0

    def tester_rest_unreachable():
        """test_connector_real for rest with unreachable URL."""
        from apps.api_server.services.connectors.tester import test_connector_real
        success, msg, _ms = _run(test_connector_real("rest", {
            "base_url": "http://192.0.2.1:9999",
        }))
        assert success is False, f"Expected success=False: {msg}"

    def tester_unsupported_type():
        """test_connector_real for unsupported type returns clean error."""
        from apps.api_server.services.connectors.tester import test_connector_real
        success, msg, _ms = _run(test_connector_real("unknown_type", {}))
        assert success is False
        assert "not yet implemented" in msg.lower()

    check("Tester: postgres valid connection", tester_postgres_valid)
    check("Tester: postgres bad credentials", tester_postgres_bad)
    check("Tester: REST valid (httpbin)", tester_rest_valid)
    check("Tester: REST unreachable", tester_rest_unreachable)
    check("Tester: unsupported type", tester_unsupported_type)


# =============================================================================
# Main
# =============================================================================
def main():
    print("=" * 72)
    print("  DATA CONNECTOR INTEGRATION TESTS")
    print("=" * 72)

    api_available = False
    try:
        status, _, _, _ = req("GET", "/v1/connectors", auth=True, timeout=5)
        api_available = (status == 200)
        print(f"  API server reachable ({BASE_URL}) — status {status}")
    except Exception as e:
        print(f"  ⚠️  API server not reachable ({BASE_URL}): {e}")
        print("  Skipping API tests; running Python module tests only.\n")

    try:
        # API-based tests (require running server)
        if api_available:
            test_connector_crud_api()
            test_connector_test_api()
            test_connector_browse_api()
        else:
            skip("Connector CRUD (API)", "API server not available")
            skip("Connector Test Endpoint (API)", "API server not available")
            skip("Connector Browse (API)", "API server not available")

        # Python module tests (always run)
        test_python_module_direct()
        test_file_connector_direct()
        test_sql_connector_direct()
        test_rest_connector_direct()
        test_map_to_simulation()
        test_connector_service_direct()
        test_connector_tester_direct()
    finally:
        # Cleanup any created connectors
        if api_available:
            print("\n  🧹 Cleaning up test connectors...")
            _cleanup_connectors()

    _print_summary()


def _print_summary():
    print("\n" + "=" * 72)
    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)
    skipped = sum(1 for r in results if r[0] == SKIP)
    total = len(results)

    print(f"  RESULTS: {passed}/{total} passed, {failed} failed, {skipped} skipped")

    if timings:
        avg = sum(t for _, t in timings) / len(timings)
        slowest = sorted(timings, key=lambda x: x[1], reverse=True)[:5]
        print(f"  Average time: {avg:.3f}s")
        print("  Slowest tests:")
        for name, t in slowest:
            print(f"    {t:.3f}s  {name}")

    if failed > 0:
        print("\n  FAILURES:")
        for r in results:
            if r[0] == FAIL:
                print(f"    {FAIL} {r[1]}: {r[2]}")

    print("=" * 72)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
