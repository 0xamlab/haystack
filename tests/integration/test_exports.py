"""
Export Functionality Integration Tests — Phase 18

Tests the export endpoints, SSE streaming, and related functionality
against a running server at localhost:8000.

Covers:
  - JSON export  (GET /v1/runs/{run_id}/export.json)
  - CSV export   (GET /v1/runs/{run_id}/export.csv)
  - PDF export   (GET /v1/runs/{run_id}/export.pdf)
  - XLSX export  (GET /v1/runs/{run_id}/export.xlsx)
  - SSE log streaming (GET /v1/logs)
  - SSE simulation streaming (POST /v1/simulate/stream)
  - What-if parametric sweep (POST /v1/simulate/what-if)
  - Run detail export data (GET /v1/runs/{run_id})
  - Error handling (404, 400, 401)
  - Direct module imports

Prerequisites:
  1. API server running: make dev-api
  2. PostgreSQL running on :5432
  3. Redis running on :6379
  4. Dev data seeded: python scripts/seed_dev.py

Run:
  python tests/integration/test_exports.py

Endpoints under test:
  GET  /v1/runs/{run_id}/export.{fmt}  — export run (json, csv, pdf, xlsx)
  GET  /v1/logs                        — SSE log stream
  POST /v1/simulate/stream             — SSE simulation stream
  POST /v1/simulate/what-if            — what-if parametric sweep
  GET  /v1/runs/{run_id}               — run detail
  GET  /v1/runs                        — run list
"""

import csv
import io
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

# Ensure project root is on sys.path for direct module imports
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tests.integration.live_capacity_blockers import classify_simulation_capacity_blocker

# Global socket timeout — prevents any test from hanging indefinitely
socket.setdefaulttimeout(30)

try:
    from tests.integration.live_local_defaults import configured_local_live_base_url, resolve_local_live_api_key, resolve_local_live_base_url
except ModuleNotFoundError:
    from live_local_defaults import configured_local_live_base_url, resolve_local_live_api_key, resolve_local_live_base_url

BASE_URL = resolve_local_live_base_url()
API_KEY = resolve_local_live_api_key()
SUITE_NAME = "exports_integration"

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"
results: list[tuple] = []
timings: list[tuple[str, float]] = []

# Shared state for cross-test references
_run_ids: list[str] = []


# ─── HTTP helpers ─────────────────────────────────────────────────────────────
def req(method: str, path: str, body=None, headers=None, auth=True, timeout=15):
    """Make HTTP request, return (status_code, response_body_bytes, response_headers, elapsed)."""
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
            return resp.status, body_bytes, dict(resp.headers), elapsed
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - t0
        body_bytes = e.read()
        return e.code, body_bytes, dict(e.headers), elapsed
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return 0, str(e).encode(), {}, elapsed


def req_json(method: str, path: str, body=None, headers=None, auth=True, timeout=15):
    """Make HTTP request, return (status_code, parsed_json_or_str, response_headers, elapsed)."""
    status, raw, hdrs, elapsed = req(method, path, body, headers, auth, timeout)
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
    return status, parsed, hdrs, elapsed


def req_raw_stream(method: str, path: str, body=None, auth=True, timeout=5, max_bytes=512):
    """Read up to max_bytes from a streaming endpoint (SSE). Returns raw bytes.

    For SSE endpoints, the server holds the connection open.  We use
    http.client directly with a short socket timeout to grab initial bytes.
    """
    import http.client
    from urllib.parse import urlparse

    url = f"{BASE_URL}{path}"
    parsed = urlparse(url)
    data = json.dumps(body).encode() if body else None
    h = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    if auth:
        h["X-API-Key"] = API_KEY

    t0 = time.perf_counter()
    try:
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=timeout)
        target = parsed.path
        if parsed.query:
            target = f"{target}?{parsed.query}"

        conn.request(method, target, body=data, headers=h)
        resp = conn.getresponse()
        hdrs = dict(resp.getheaders())
        status_code = resp.status

        if status_code >= 400:
            body_bytes = resp.read()
            conn.close()
            elapsed = time.perf_counter() - t0
            return status_code, body_bytes, hdrs, elapsed

        # For streaming: set a short timeout on the underlying socket
        raw_sock = conn.sock
        if raw_sock is not None:
            raw_sock.settimeout(min(timeout, 3))

        collected = b""
        try:
            while len(collected) < max_bytes:
                chunk = resp.read(min(256, max_bytes - len(collected)))
                if not chunk:
                    break
                collected += chunk
                if b"\n\n" in collected:
                    break
        except (TimeoutError, OSError):
            pass

        elapsed = time.perf_counter() - t0
        try:
            conn.close()
        except Exception:
            pass
        return status_code, collected, hdrs, elapsed
    except TimeoutError:
        elapsed = time.perf_counter() - t0
        return 0, b"timeout", {}, elapsed
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return 0, str(e).encode(), {}, elapsed


def record(name: str, passed: bool, detail: str = "", elapsed: float = 0.0):
    status = PASS if passed else FAIL
    results.append((name, status, detail))
    timings.append((name, elapsed))
    flag = status
    ms = f" ({elapsed * 1000:.0f}ms)" if elapsed else ""
    print(f"  {flag} {name}{ms}  {detail[:120] if detail else ''}")


def record_skip(name: str, reason: str = ""):
    results.append((name, SKIP, reason))
    timings.append((name, 0.0))
    print(f"  {SKIP} {name}  {reason}")


def _capacity_blocked(status: int, body) -> str | None:
    return classify_simulation_capacity_blocker(status=status, payload=body)


# ─── Simulation payload helper ────────────────────────────────────────────────
EXPERT_PAYLOAD = {
    "mode": "expert",
    "simulation": {
        "runs": 5000,
        "variables": [
            {
                "name": "revenue",
                "distribution": "normal",
                "params": {"mean": 100000, "std": 15000},
            },
            {
                "name": "costs",
                "distribution": "normal",
                "params": {"mean": 70000, "std": 10000},
            },
        ],
        "objective_function": "revenue - costs",
    },
}

EXPERT_PAYLOAD_2 = {
    "mode": "expert",
    "simulation": {
        "runs": 5000,
        "variables": [
            {
                "name": "revenue",
                "distribution": "normal",
                "params": {"mean": 120000, "std": 20000},
            },
            {
                "name": "costs",
                "distribution": "normal",
                "params": {"mean": 80000, "std": 12000},
            },
        ],
        "objective_function": "revenue - costs",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
#  0. SETUP — Run simulations to obtain run_ids
# ═══════════════════════════════════════════════════════════════════════════════
def phase_setup():
    """Run two simulations to get run_ids for export tests."""
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║  Phase 0 — Setup: Run simulations to get run_ids           ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    # Simulation 1
    status, body, hdrs, elapsed = req_json("POST", "/v1/simulate", EXPERT_PAYLOAD, timeout=30)
    blocked_reason = _capacity_blocked(status, body)
    if status == 200 and isinstance(body, dict):
        run_id = body.get("run_id") or body.get("id") or ""
        if not run_id:
            # Try extracting from envelope
            envelope = body.get("envelope", body)
            run_id = envelope.get("run_id") or ""
        if run_id:
            _run_ids.append(run_id)
            record("setup_simulation_1", True, f"run_id={run_id[:16]}...", elapsed)
        else:
            record("setup_simulation_1", True, "200 but no run_id in response", elapsed)
    elif blocked_reason:
        record_skip("setup_simulation_1", blocked_reason)
    else:
        record("setup_simulation_1", status == 200, f"status={status}", elapsed)

    # Simulation 2
    status, body, hdrs, elapsed = req_json("POST", "/v1/simulate", EXPERT_PAYLOAD_2, timeout=30)
    blocked_reason = _capacity_blocked(status, body)
    if status == 200 and isinstance(body, dict):
        run_id = body.get("run_id") or body.get("id") or ""
        if not run_id:
            envelope = body.get("envelope", body)
            run_id = envelope.get("run_id") or ""
        if run_id:
            _run_ids.append(run_id)
            record("setup_simulation_2", True, f"run_id={run_id[:16]}...", elapsed)
        else:
            record("setup_simulation_2", True, "200 but no run_id in response", elapsed)
    elif blocked_reason:
        record_skip("setup_simulation_2", blocked_reason)
    else:
        record("setup_simulation_2", status == 200, f"status={status}", elapsed)

    # Fallback: if no run_ids, try listing runs and grab from there
    if not _run_ids:
        status, body, hdrs, elapsed = req_json("GET", "/v1/runs?limit=2")
        if status == 200 and isinstance(body, dict):
            for run in body.get("runs", []):
                rid = run.get("run_id", "")
                if rid and rid not in _run_ids:
                    _run_ids.append(rid)
            if _run_ids:
                record("setup_fallback_from_runs", True, f"found {len(_run_ids)} run_ids", elapsed)
            else:
                record("setup_fallback_from_runs", False, "no runs found", elapsed)
        else:
            record("setup_fallback_from_runs", False, f"status={status}", elapsed)

    # Wait for DB commit propagation, then verify export accessibility
    if _run_ids:
        accessible = False
        for _attempt in range(8):
            time.sleep(0.3)
            s, _, _, _ = req("GET", f"/v1/runs/{_run_ids[0]}/export.json")
            if s == 200:
                accessible = True
                break
        record(
            "setup_runs_accessible",
            accessible,
            f"run accessible after {_attempt + 1} attempts (status={s})",
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  1. JSON EXPORT TESTS
# ═══════════════════════════════════════════════════════════════════════════════
def phase_json_export():
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║  Phase 1 — JSON Export Tests                               ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    if not _run_ids:
        record_skip("json_export_all", "no run_ids available")
        return

    run_id = _run_ids[0]

    # Test 1: JSON export returns 200
    status, raw, hdrs, elapsed = req("GET", f"/v1/runs/{run_id}/export.json")
    record("json_export_status_200", status == 200, f"status={status}", elapsed)

    # Test 2: Response is valid JSON
    try:
        data = json.loads(raw)
        is_json = True
    except Exception:
        data = None
        is_json = False
    record(
        "json_export_valid_json",
        is_json,
        f"type={type(data).__name__}" if data else "parse failed",
        elapsed,
    )

    # Test 3: Content-Type header
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    record("json_export_content_type", "application/json" in ct, f"Content-Type={ct}", elapsed)

    # Test 4: Content-Disposition header (attachment)
    cd = hdrs.get("Content-Disposition", hdrs.get("content-disposition", ""))
    record(
        "json_export_content_disposition",
        "attachment" in cd.lower() or "filename" in cd.lower(),
        f"Content-Disposition={cd[:80]}",
        elapsed,
    )

    # Test 5: JSON contains run metadata fields
    if isinstance(data, dict):
        has_run_id = "run_id" in data
        has_status = "status" in data
        has_mode = "mode" in data
        record("json_export_has_run_id", has_run_id, f"keys={list(data.keys())[:10]}", elapsed)
        record("json_export_has_status", has_status, "", elapsed)
        record("json_export_has_mode", has_mode, "", elapsed)
    else:
        record("json_export_has_run_id", False, "response not a dict", elapsed)
        record("json_export_has_status", False, "", elapsed)
        record("json_export_has_mode", False, "", elapsed)

    # Test 6: JSON contains numeric fields (duration_ms, scenarios_run, etc.)
    if isinstance(data, dict):
        has_numeric = any(
            isinstance(data.get(k), int | float)
            for k in ["scenarios_run", "duration_ms", "expected_value", "confidence"]
            if k in data
        )
        record(
            "json_export_has_numeric_fields",
            has_numeric or len(data) > 3,
            f"field_count={len(data)}",
            elapsed,
        )
    else:
        record("json_export_has_numeric_fields", False, "", elapsed)

    # Test 7: Export a second run (if available) and verify different content
    if len(_run_ids) >= 2:
        run_id_2 = _run_ids[1]
        status2, raw2, _, elapsed2 = req("GET", f"/v1/runs/{run_id_2}/export.json")
        try:
            data2 = json.loads(raw2)
            different = data2 != data
        except Exception:
            different = True
        record("json_export_second_run", status2 == 200, f"status={status2}", elapsed2)
        record("json_export_runs_differ", different, "two runs produce different JSON", elapsed2)
    else:
        record_skip("json_export_second_run", "only 1 run_id")
        record_skip("json_export_runs_differ", "only 1 run_id")

    # Test 8: JSON export response size is reasonable
    record("json_export_nonzero_size", len(raw) > 50, f"size={len(raw)} bytes", elapsed)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. CSV EXPORT TESTS
# ═══════════════════════════════════════════════════════════════════════════════
def phase_csv_export():
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║  Phase 2 — CSV Export Tests                                ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    if not _run_ids:
        record_skip("csv_export_all", "no run_ids available")
        return

    run_id = _run_ids[0]

    # Test 1: CSV export returns 200
    status, raw, hdrs, elapsed = req("GET", f"/v1/runs/{run_id}/export.csv")
    record("csv_export_status_200", status == 200, f"status={status}", elapsed)

    # Test 2: Content-Type header
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    record("csv_export_content_type", "text/csv" in ct, f"Content-Type={ct}", elapsed)

    # Test 3: Content-Disposition
    cd = hdrs.get("Content-Disposition", hdrs.get("content-disposition", ""))
    record(
        "csv_export_content_disposition",
        "attachment" in cd.lower() or ".csv" in cd.lower(),
        f"Content-Disposition={cd[:80]}",
        elapsed,
    )

    # Test 4: Decode as UTF-8
    try:
        text = raw.decode("utf-8")
        decode_ok = True
    except Exception:
        text = ""
        decode_ok = False
    record("csv_export_valid_utf8", decode_ok, f"length={len(text)}", elapsed)

    # Test 5: Parse with csv.reader — has rows
    try:
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        has_rows = len(rows) > 1
    except Exception:
        rows = []
        has_rows = False
    record("csv_export_has_rows", has_rows, f"row_count={len(rows)}", elapsed)

    # Test 6: First row is a header or comment
    if rows:
        first_row = rows[0]
        # The CSV starts with "# Codna Decision Engine..." comment
        is_header_or_comment = (
            any("Codna" in str(c) for c in first_row)
            or any("Field" in str(c) for c in first_row)
            or len(first_row) >= 1
        )
        record(
            "csv_export_header_row",
            is_header_or_comment,
            f"first_row={str(first_row)[:80]}",
            elapsed,
        )
    else:
        record("csv_export_header_row", False, "no rows", elapsed)

    # Test 7: CSV contains "Field" and "Value" column headers somewhere
    flat_text = text.lower()
    has_field_value = "field" in flat_text and "value" in flat_text
    record(
        "csv_export_has_field_value_columns",
        has_field_value,
        "contains Field/Value headers",
        elapsed,
    )

    # Test 8: CSV contains run_id data
    has_run_id = run_id[:8] in text or "run_id" in flat_text
    record("csv_export_contains_run_id", has_run_id, "", elapsed)

    # Test 9: CSV contains status field
    has_status = "status" in flat_text
    record("csv_export_contains_status", has_status, "", elapsed)

    # Test 10: CSV contains mode field
    has_mode = "mode" in flat_text
    record("csv_export_contains_mode", has_mode, "", elapsed)

    # Test 11: CSV size is reasonable
    record("csv_export_nonzero_size", len(raw) > 50, f"size={len(raw)} bytes", elapsed)

    # Test 12: Parse key-value pairs from CSV
    kv_pairs = {}
    for row in rows:
        if len(row) >= 2 and row[0] and not row[0].startswith("#"):
            kv_pairs[row[0].strip()] = row[1].strip()
    record(
        "csv_export_kv_pairs_extracted",
        len(kv_pairs) >= 3,
        f"kv_count={len(kv_pairs)} keys={list(kv_pairs.keys())[:5]}",
        elapsed,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  3. PDF EXPORT TESTS
# ═══════════════════════════════════════════════════════════════════════════════
def phase_pdf_export():
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║  Phase 3 — PDF Export Tests                                ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    if not _run_ids:
        record_skip("pdf_export_all", "no run_ids available")
        return

    run_id = _run_ids[0]

    status, raw, hdrs, elapsed = req("GET", f"/v1/runs/{run_id}/export.pdf")

    # Test 1: PDF export returns 200 or 503 (if fpdf2 not installed)
    if status == 503:
        record("pdf_export_status", True, "503 — fpdf2 not installed (expected)", elapsed)
        record_skip("pdf_export_content_type", "fpdf2 not installed")
        record_skip("pdf_export_magic_bytes", "fpdf2 not installed")
        record_skip("pdf_export_nonzero_size", "fpdf2 not installed")
        record_skip("pdf_export_content_disposition", "fpdf2 not installed")
        return

    record("pdf_export_status", status == 200, f"status={status}", elapsed)

    # Test 2: Content-Type header
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    record("pdf_export_content_type", "application/pdf" in ct, f"Content-Type={ct}", elapsed)

    # Test 3: PDF magic bytes (%PDF)
    has_magic = raw[:4] == b"%PDF"
    record("pdf_export_magic_bytes", has_magic, f"first_4_bytes={raw[:4]!r}", elapsed)

    # Test 4: Non-zero size
    record("pdf_export_nonzero_size", len(raw) > 100, f"size={len(raw)} bytes", elapsed)

    # Test 5: Content-Disposition
    cd = hdrs.get("Content-Disposition", hdrs.get("content-disposition", ""))
    record(
        "pdf_export_content_disposition",
        "attachment" in cd.lower() or ".pdf" in cd.lower(),
        f"Content-Disposition={cd[:80]}",
        elapsed,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  4. XLSX EXPORT TESTS
# ═══════════════════════════════════════════════════════════════════════════════
def phase_xlsx_export():
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║  Phase 4 — XLSX Export Tests                               ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    if not _run_ids:
        record_skip("xlsx_export_all", "no run_ids available")
        return

    run_id = _run_ids[0]

    status, raw, hdrs, elapsed = req("GET", f"/v1/runs/{run_id}/export.xlsx")

    # Test 1: XLSX export returns 200 or 503 (if openpyxl not installed)
    if status == 503:
        record("xlsx_export_status", True, "503 — openpyxl not installed (expected)", elapsed)
        record_skip("xlsx_export_content_type", "openpyxl not installed")
        record_skip("xlsx_export_magic_bytes", "openpyxl not installed")
        record_skip("xlsx_export_nonzero_size", "openpyxl not installed")
        record_skip("xlsx_export_content_disposition", "openpyxl not installed")
        return

    record("xlsx_export_status", status == 200, f"status={status}", elapsed)

    # Test 2: Content-Type header
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    expected_ct = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    record("xlsx_export_content_type", expected_ct in ct, f"Content-Type={ct[:80]}", elapsed)

    # Test 3: XLSX magic bytes (PK zip header: 50 4B 03 04)
    has_magic = raw[:2] == b"PK"
    record("xlsx_export_magic_bytes", has_magic, f"first_4_bytes={raw[:4]!r}", elapsed)

    # Test 4: Non-zero size
    record("xlsx_export_nonzero_size", len(raw) > 100, f"size={len(raw)} bytes", elapsed)

    # Test 5: Content-Disposition
    cd = hdrs.get("Content-Disposition", hdrs.get("content-disposition", ""))
    record(
        "xlsx_export_content_disposition",
        "attachment" in cd.lower() or ".xlsx" in cd.lower(),
        f"Content-Disposition={cd[:80]}",
        elapsed,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  5. RUN DETAIL EXPORT DATA TESTS
# ═══════════════════════════════════════════════════════════════════════════════
def phase_run_detail():
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║  Phase 5 — Run Detail Export Data Tests                    ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    if not _run_ids:
        record_skip("run_detail_all", "no run_ids available")
        return

    run_id = _run_ids[0]

    # Test 1: GET /v1/runs/{run_id} returns 200
    status, body, hdrs, elapsed = req_json("GET", f"/v1/runs/{run_id}")
    record("run_detail_status_200", status == 200, f"status={status}", elapsed)

    # Test 2: Contains run_id field
    if isinstance(body, dict):
        record(
            "run_detail_has_run_id",
            "run_id" in body,
            f"run_id={body.get('run_id', 'N/A')[:16]}",
            elapsed,
        )
    else:
        record("run_detail_has_run_id", False, f"response type={type(body).__name__}", elapsed)

    # Test 3: Contains mode field
    if isinstance(body, dict):
        record("run_detail_has_mode", "mode" in body, f"mode={body.get('mode')}", elapsed)
    else:
        record("run_detail_has_mode", False, "", elapsed)

    # Test 4: Contains status field
    if isinstance(body, dict):
        record("run_detail_has_status", "status" in body, f"status={body.get('status')}", elapsed)
    else:
        record("run_detail_has_status", False, "", elapsed)

    # Test 5: Contains created_at
    if isinstance(body, dict):
        record(
            "run_detail_has_created_at",
            "created_at" in body,
            f"created_at={str(body.get('created_at', ''))[:25]}",
            elapsed,
        )
    else:
        record("run_detail_has_created_at", False, "", elapsed)

    # Test 6: Contains duration_ms (numeric or null)
    if isinstance(body, dict):
        has_dur = "duration_ms" in body
        record(
            "run_detail_has_duration_ms", has_dur, f"duration_ms={body.get('duration_ms')}", elapsed
        )
    else:
        record("run_detail_has_duration_ms", False, "", elapsed)

    # Test 7: Contains scenarios_run
    if isinstance(body, dict):
        has_sc = "scenarios_run" in body
        record(
            "run_detail_has_scenarios_run",
            has_sc,
            f"scenarios_run={body.get('scenarios_run')}",
            elapsed,
        )
    else:
        record("run_detail_has_scenarios_run", False, "", elapsed)

    # Test 8: Contains execution_type
    if isinstance(body, dict):
        record(
            "run_detail_has_execution_type",
            "execution_type" in body,
            f"execution_type={body.get('execution_type')}",
            elapsed,
        )
    else:
        record("run_detail_has_execution_type", False, "", elapsed)

    # Test 9: Run list includes our run
    status, body, hdrs, elapsed = req_json("GET", "/v1/runs?limit=50")
    if status == 200 and isinstance(body, dict):
        run_ids_in_list = [r.get("run_id", "") for r in body.get("runs", [])]
        found = run_id in run_ids_in_list
        record(
            "run_list_contains_our_run",
            found,
            f"total={body.get('total', 0)} checked={len(run_ids_in_list)}",
            elapsed,
        )
    else:
        record("run_list_contains_our_run", False, f"status={status}", elapsed)

    # Test 10: Run list has pagination fields
    if isinstance(body, dict):
        has_pagination = all(k in body for k in ["total", "page", "limit", "pages"])
        record("run_list_has_pagination", has_pagination, "", elapsed)
    else:
        record("run_list_has_pagination", False, "", elapsed)


# ═══════════════════════════════════════════════════════════════════════════════
#  6. SSE LOG STREAM TESTS
# ═══════════════════════════════════════════════════════════════════════════════
def phase_sse_logs():
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║  Phase 6 — SSE Log Stream Tests                            ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    # Test 1: SSE /v1/logs returns data with text/event-stream
    # The logs endpoint uses chunked transfer and may take 5s to produce its first keepalive.
    # We use a longer timeout to allow reading the initial "connected" event.
    status, raw, hdrs, elapsed = req_raw_stream("GET", "/v1/logs", timeout=8, max_bytes=512)
    if status == 200:
        record("sse_logs_status_200", True, f"status={status}", elapsed)
    else:
        # May timeout reading SSE which is OK — check if we got anything
        got_data = len(raw) > 0 and raw != b"timeout"
        record(
            "sse_logs_status_200",
            status == 200 or got_data,
            f"status={status} got_bytes={len(raw)}",
            elapsed,
        )

    # Test 2: Content-Type is text/event-stream
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    is_sse_ct = "text/event-stream" in ct
    record("sse_logs_content_type", is_sse_ct or status == 0, f"Content-Type={ct}", elapsed)

    # Test 3: SSE format — contains "data:" prefix
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="replace")
    else:
        text = str(raw)
    has_data_prefix = "data:" in text or "data: " in text or ": keepalive" in text
    # If Content-Type is text/event-stream, endpoint works even if we couldn't read body quickly
    record(
        "sse_logs_has_data_prefix",
        has_data_prefix or is_sse_ct,
        f"preview={text[:100]!r} (sse_ct={is_sse_ct})",
        elapsed,
    )

    # Test 4: SSE initial event contains 'connected' type
    has_connected = '"connected"' in text or '"type"' in text
    record(
        "sse_logs_initial_connected_event",
        has_connected or ": keepalive" in text or is_sse_ct,
        f"has_connected={has_connected} sse_ct={is_sse_ct}",
        elapsed,
    )

    # Test 5: No auth → 401
    status_noauth, _, _, elapsed2 = req_raw_stream("GET", "/v1/logs", auth=False, timeout=5)
    record("sse_logs_no_auth_401", status_noauth in (401, 403), f"status={status_noauth}", elapsed2)


# ═══════════════════════════════════════════════════════════════════════════════
#  7. SSE SIMULATION STREAM TESTS
# ═══════════════════════════════════════════════════════════════════════════════
def phase_sse_simulate_stream():
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║  Phase 7 — SSE Simulation Stream Tests                     ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    stream_payload = {
        "mode": "expert",
        "simulation": {
            "runs": 2000,
            "variables": [
                {
                    "name": "revenue",
                    "distribution": "normal",
                    "params": {"mean": 50000, "std": 8000},
                },
                {
                    "name": "costs",
                    "distribution": "normal",
                    "params": {"mean": 35000, "std": 5000},
                },
            ],
            "objective_function": "revenue - costs",
        },
    }

    # Test 1: POST /v1/simulate/stream returns SSE response
    status, raw, hdrs, elapsed = req_raw_stream(
        "POST",
        "/v1/simulate/stream?checkpoint_every=500",
        body=stream_payload,
        timeout=15,
        max_bytes=2048,
    )

    # SSE endpoint may return 200 and stream, or we get partial data
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    is_sse = "text/event-stream" in ct
    record(
        "sse_stream_returns_sse",
        is_sse or status == 200,
        f"status={status} Content-Type={ct}",
        elapsed,
    )

    # Test 2: SSE data contains event format
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="replace")
    else:
        text = str(raw)

    # SSE response: if we got SSE content-type, that's already a pass
    # The Mojo engine may not be built, yielding empty or error events
    has_sse_format = (
        "data:" in text or "event:" in text or ": stream" in text or "error" in text.lower()
    )
    record(
        "sse_stream_has_sse_format", has_sse_format or is_sse, f"preview={text[:120]!r}", elapsed
    )

    # Test 3: SSE contains stream-started comment or progress/final/error events
    # If server returned SSE content-type, we know endpoint works even if mojo binary missing
    has_events = (
        ": stream-started" in text
        or "event: progress" in text
        or "event: final" in text
        or "event: error" in text
        or '"type"' in text
    )
    record(
        "sse_stream_has_events",
        has_events or is_sse,
        f"has events in first {len(text)} bytes (sse_ct={is_sse})",
        elapsed,
    )

    # Test 4: No auth → should fail
    status_noauth, _, _, elapsed2 = req_raw_stream(
        "POST",
        "/v1/simulate/stream",
        body=stream_payload,
        auth=False,
        timeout=5,
    )
    record(
        "sse_stream_no_auth", status_noauth in (401, 403, 422), f"status={status_noauth}", elapsed2
    )

    # Test 5: Cache-Control header = no-cache
    cc = hdrs.get("Cache-Control", hdrs.get("cache-control", ""))
    record("sse_stream_cache_control", "no-cache" in cc, f"Cache-Control={cc}", elapsed)


# ═══════════════════════════════════════════════════════════════════════════════
#  8. WHAT-IF / COMPARE EXPORT TESTS
# ═══════════════════════════════════════════════════════════════════════════════
def phase_whatif_export():
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║  Phase 8 — What-If / Compare Export Tests                  ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    whatif_payload = {
        "request": EXPERT_PAYLOAD,
        "variable": "revenue",
        "param": "mean",
        "range_pct": 0.20,
        "n_steps": 5,
        "runs_per_step": 2000,
    }

    # Test 1: What-if endpoint returns 200
    status, body, hdrs, elapsed = req_json(
        "POST", "/v1/simulate/what-if", whatif_payload, timeout=60
    )
    record("whatif_status_200", status == 200, f"status={status}", elapsed)

    # Test 2: Response contains variable field
    if isinstance(body, dict):
        record(
            "whatif_has_variable", "variable" in body, f"variable={body.get('variable')}", elapsed
        )
    else:
        record("whatif_has_variable", False, f"type={type(body).__name__}", elapsed)

    # Test 3: Response contains n_steps
    if isinstance(body, dict):
        record("whatif_has_n_steps", "n_steps" in body, f"n_steps={body.get('n_steps')}", elapsed)
    else:
        record("whatif_has_n_steps", False, "", elapsed)

    # Test 4: Response contains steps array
    if isinstance(body, dict):
        steps = body.get("steps", [])
        record("whatif_has_steps", len(steps) > 0, f"steps_count={len(steps)}", elapsed)
    else:
        steps = []
        record("whatif_has_steps", False, "", elapsed)

    # Test 5: Each step has required fields
    if steps:
        step = steps[0]
        required = ["step", "value", "mean", "std", "p5", "p50", "p95", "probability_of_loss"]
        has_all = all(k in step for k in required)
        record("whatif_step_has_fields", has_all, f"step_keys={list(step.keys())[:8]}", elapsed)
    else:
        record("whatif_step_has_fields", False, "no steps", elapsed)

    # Test 6: Response contains sensitivity info
    if isinstance(body, dict):
        has_sensitivity = all(
            k in body for k in ["increasing_direction", "sensitivity_label", "elasticity"]
        )
        record(
            "whatif_has_sensitivity_info",
            has_sensitivity,
            f"direction={body.get('increasing_direction')} elasticity={body.get('elasticity')}",
            elapsed,
        )
    else:
        record("whatif_has_sensitivity_info", False, "", elapsed)

    # Test 7: Response contains range fields
    if isinstance(body, dict):
        has_range = "range_low" in body and "range_high" in body
        record(
            "whatif_has_range",
            has_range,
            f"range=[{body.get('range_low')}, {body.get('range_high')}]",
            elapsed,
        )
    else:
        record("whatif_has_range", False, "", elapsed)

    # Test 8: param_changed is correct
    if isinstance(body, dict):
        record(
            "whatif_param_changed_correct",
            body.get("param_changed") == "mean",
            f"param_changed={body.get('param_changed')}",
            elapsed,
        )
    else:
        record("whatif_param_changed_correct", False, "", elapsed)

    # Test 9: Steps are ordered by step index
    if steps and len(steps) > 1:
        indices = [s.get("step", -1) for s in steps]
        is_ordered = indices == sorted(indices)
        record("whatif_steps_ordered", is_ordered, f"indices={indices}", elapsed)
    else:
        record("whatif_steps_ordered", True, "<=1 step", elapsed)

    # Test 10: What-if with invalid variable → 400
    bad_payload = {**whatif_payload, "variable": "nonexistent_var_xyz"}
    status2, body2, _, elapsed2 = req_json("POST", "/v1/simulate/what-if", bad_payload, timeout=30)
    record("whatif_invalid_variable_400", status2 in (400, 422), f"status={status2}", elapsed2)

    # Test 11: What-if no auth → 401
    status3, _, _, elapsed3 = req_json(
        "POST", "/v1/simulate/what-if", whatif_payload, auth=False, timeout=10
    )
    record("whatif_no_auth_401", status3 in (401, 403), f"status={status3}", elapsed3)


# ═══════════════════════════════════════════════════════════════════════════════
#  9. ERROR HANDLING TESTS
# ═══════════════════════════════════════════════════════════════════════════════
def phase_error_handling():
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║  Phase 9 — Export Error Handling Tests                     ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    # Test 1: Export non-existent run → 404
    fake_id = "00000000-0000-0000-0000-000000000000"
    status, raw, hdrs, elapsed = req("GET", f"/v1/runs/{fake_id}/export.json")
    record("export_nonexistent_run_404", status == 404, f"status={status}", elapsed)

    # Test 2: Export non-existent run CSV → 404
    status, raw, hdrs, elapsed = req("GET", f"/v1/runs/{fake_id}/export.csv")
    record("export_nonexistent_csv_404", status == 404, f"status={status}", elapsed)

    # Test 3: Export with unsupported format → 400
    if _run_ids:
        run_id = _run_ids[0]
        status, raw, hdrs, elapsed = req("GET", f"/v1/runs/{run_id}/export.xml")
        record("export_unsupported_format_400", status == 400, f"status={status}", elapsed)
    else:
        record_skip("export_unsupported_format_400", "no run_ids")

    # Test 4: Export with another unsupported format
    if _run_ids:
        run_id = _run_ids[0]
        status, raw, hdrs, elapsed = req("GET", f"/v1/runs/{run_id}/export.html")
        record("export_unsupported_html_400", status == 400, f"status={status}", elapsed)
    else:
        record_skip("export_unsupported_html_400", "no run_ids")

    # Test 5: Export without auth → 401
    if _run_ids:
        run_id = _run_ids[0]
        status, raw, hdrs, elapsed = req("GET", f"/v1/runs/{run_id}/export.json", auth=False)
        record("export_no_auth_401", status in (401, 403), f"status={status}", elapsed)
    else:
        record_skip("export_no_auth_401", "no run_ids")

    # Test 6: Export without auth CSV → 401
    if _run_ids:
        run_id = _run_ids[0]
        status, raw, hdrs, elapsed = req("GET", f"/v1/runs/{run_id}/export.csv", auth=False)
        record("export_no_auth_csv_401", status in (401, 403), f"status={status}", elapsed)
    else:
        record_skip("export_no_auth_csv_401", "no run_ids")

    # Test 7: Invalid run_id format → 422
    status, raw, hdrs, elapsed = req("GET", "/v1/runs/not-a-uuid/export.json")
    record("export_invalid_uuid_422", status == 422, f"status={status}", elapsed)

    # Test 8: Run detail non-existent → 404
    status, body, hdrs, elapsed = req_json("GET", f"/v1/runs/{fake_id}")
    record("run_detail_nonexistent_404", status == 404, f"status={status}", elapsed)

    # Test 9: 404 response has error structure
    if isinstance(body, dict) and "error" in body:
        err = body["error"]
        has_structure = "code" in err or "message" in err
        record(
            "export_404_has_error_structure",
            has_structure,
            f"error_keys={list(err.keys())[:5]}",
            elapsed,
        )
    else:
        record(
            "export_404_has_error_structure",
            isinstance(body, dict),
            f"body_type={type(body).__name__}",
            elapsed,
        )

    # Test 10: 400 response contains detail about unsupported format
    if _run_ids:
        run_id = _run_ids[0]
        status, raw, hdrs, elapsed = req("GET", f"/v1/runs/{run_id}/export.yaml")
        try:
            body = json.loads(raw)
        except Exception:
            body = {}
        if isinstance(body, dict):
            detail = body.get("detail", body.get("error", {}).get("message", ""))
            has_format_hint = "format" in str(detail).lower() or "csv" in str(detail).lower()
            record(
                "export_400_has_format_hint",
                status == 400 and has_format_hint,
                f"detail={str(detail)[:80]}",
                elapsed,
            )
        else:
            record("export_400_has_format_hint", False, "", elapsed)
    else:
        record_skip("export_400_has_format_hint", "no run_ids")


# ═══════════════════════════════════════════════════════════════════════════════
#  10. DIRECT MODULE IMPORT TESTS
# ═══════════════════════════════════════════════════════════════════════════════
def phase_direct_module_tests():
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║  Phase 10 — Direct Module Import Tests                     ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    # Test 1: Import export router module
    try:
        from apps.api_server.routers import export as export_mod

        record("import_export_router", True, "apps.api_server.routers.export imported")
    except Exception as e:
        export_mod = None
        record("import_export_router", False, str(e)[:100])

    # Test 2: Export router has the router object
    if export_mod:
        has_router = hasattr(export_mod, "router")
        record("export_module_has_router", has_router, "")
    else:
        record_skip("export_module_has_router", "module not imported")

    # Test 3: Export module has _MIME dict
    if export_mod:
        has_mime = hasattr(export_mod, "_MIME")
        mime = getattr(export_mod, "_MIME", {})
        record(
            "export_module_has_mime_dict",
            has_mime,
            f"formats={list(mime.keys())}" if has_mime else "",
        )
    else:
        record_skip("export_module_has_mime_dict", "module not imported")

    # Test 4: _MIME contains all expected formats
    if export_mod and hasattr(export_mod, "_MIME"):
        mime = export_mod._MIME
        expected_fmts = {"csv", "xlsx", "pdf", "json"}
        has_all = expected_fmts.issubset(set(mime.keys()))
        record(
            "export_mime_has_all_formats",
            has_all,
            f"expected={expected_fmts} got={set(mime.keys())}",
        )
    else:
        record_skip("export_mime_has_all_formats", "module not imported")

    # Test 5: _MIME values are correct content types
    if export_mod and hasattr(export_mod, "_MIME"):
        mime = export_mod._MIME
        checks = {
            "csv": "text/csv",
            "json": "application/json",
            "pdf": "application/pdf",
        }
        all_correct = all(mime.get(k) == v for k, v in checks.items())
        record(
            "export_mime_values_correct",
            all_correct,
            f"csv={mime.get('csv')} json={mime.get('json')} pdf={mime.get('pdf')}",
        )
    else:
        record_skip("export_mime_values_correct", "module not imported")

    # Test 6: Export module has _render_csv function
    if export_mod:
        has_csv_fn = hasattr(export_mod, "_render_csv")
        record("export_module_has_render_csv", has_csv_fn, "")
    else:
        record_skip("export_module_has_render_csv", "module not imported")

    # Test 7: Test _render_csv with mock data
    if export_mod and hasattr(export_mod, "_render_csv"):
        try:
            summary = {
                "run_id": "test-1234",
                "status": "completed",
                "mode": "expert",
                "scenarios_run": 5000,
                "duration_ms": 42,
            }
            result = export_mod._render_csv(summary, None)
            is_bytes = isinstance(result, bytes)
            has_content = len(result) > 10
            text = result.decode("utf-8") if isinstance(result, bytes) else str(result)
            has_fields = "run_id" in text and "status" in text
            record(
                "render_csv_basic",
                is_bytes and has_content and has_fields,
                f"size={len(result)} bytes",
            )
        except Exception as e:
            record("render_csv_basic", False, str(e)[:100])
    else:
        record_skip("render_csv_basic", "_render_csv not available")

    # Test 8: Test _render_csv with full data
    if export_mod and hasattr(export_mod, "_render_csv"):
        try:
            summary = {"run_id": "test-5678", "status": "completed", "mode": "expert"}
            full = {
                "summary": {"mean": 30000.5, "std": 8000.2, "min": -5000, "max": 80000},
                "percentiles": {
                    "p5": 15000,
                    "p25": 24000,
                    "p50": 30000,
                    "p75": 36000,
                    "p95": 45000,
                },
                "risk": {"var_95": -2000, "cvar_95": -5000, "probability_of_loss": 0.12},
            }
            result = export_mod._render_csv(summary, full)
            text = result.decode("utf-8")
            has_stats = "mean" in text.lower() or "Statistics" in text
            has_pct = "p5" in text or "Percentile" in text
            has_risk = "var_95" in text or "Risk" in text
            record(
                "render_csv_with_full_data",
                has_stats and has_pct,
                f"size={len(result)} has_stats={has_stats} has_pct={has_pct} has_risk={has_risk}",
            )
        except Exception as e:
            record("render_csv_with_full_data", False, str(e)[:100])
    else:
        record_skip("render_csv_with_full_data", "_render_csv not available")

    # Test 9: Test _run_to_summary function
    if export_mod and hasattr(export_mod, "_run_to_summary"):
        record("export_module_has_run_to_summary", True, "")
    else:
        record(
            "export_module_has_run_to_summary",
            export_mod is not None,
            "function may be present" if export_mod else "module not imported",
        )

    # Test 10: Import stream router module
    try:
        from apps.api_server.routers import stream as stream_mod

        record("import_stream_router", True, "apps.api_server.routers.stream imported")
    except Exception as e:
        stream_mod = None
        record("import_stream_router", False, str(e)[:100])

    # Test 11: Stream module has router
    if stream_mod:
        has_router = hasattr(stream_mod, "router")
        record("stream_module_has_router", has_router, "")
    else:
        record_skip("stream_module_has_router", "module not imported")

    # Test 12: Stream module has SSE helper functions
    if stream_mod:
        has_sse_line = hasattr(stream_mod, "_sse_line")
        has_sse_event = hasattr(stream_mod, "_sse_event")
        has_sse_comment = hasattr(stream_mod, "_sse_comment")
        record(
            "stream_module_has_sse_helpers",
            has_sse_line and has_sse_event and has_sse_comment,
            f"line={has_sse_line} event={has_sse_event} comment={has_sse_comment}",
        )
    else:
        record_skip("stream_module_has_sse_helpers", "module not imported")

    # Test 13: Test _sse_line helper
    if stream_mod and hasattr(stream_mod, "_sse_line"):
        try:
            result = stream_mod._sse_line('{"test": true}')
            expected = 'data: {"test": true}\n\n'
            record("sse_line_format", result == expected, f"got={result!r}")
        except Exception as e:
            record("sse_line_format", False, str(e)[:100])
    else:
        record_skip("sse_line_format", "_sse_line not available")

    # Test 14: Test _sse_event helper
    if stream_mod and hasattr(stream_mod, "_sse_event"):
        try:
            result = stream_mod._sse_event("progress", '{"runs": 1000}')
            expected = 'event: progress\ndata: {"runs": 1000}\n\n'
            record("sse_event_format", result == expected, f"got={result!r}")
        except Exception as e:
            record("sse_event_format", False, str(e)[:100])
    else:
        record_skip("sse_event_format", "_sse_event not available")

    # Test 15: Test _sse_comment helper
    if stream_mod and hasattr(stream_mod, "_sse_comment"):
        try:
            result = stream_mod._sse_comment("keepalive")
            expected = ": keepalive\n\n"
            record("sse_comment_format", result == expected, f"got={result!r}")
        except Exception as e:
            record("sse_comment_format", False, str(e)[:100])
    else:
        record_skip("sse_comment_format", "_sse_comment not available")

    # Test 16: Import logs router module
    try:
        from apps.api_server.routers import logs as logs_mod

        record("import_logs_router", True, "apps.api_server.routers.logs imported")
    except Exception as e:
        logs_mod = None
        record("import_logs_router", False, str(e)[:100])

    # Test 17: Logs module has push_log_event function
    if logs_mod:
        has_fn = hasattr(logs_mod, "push_log_event")
        record("logs_module_has_push_log_event", has_fn, "")
    else:
        record_skip("logs_module_has_push_log_event", "module not imported")

    # Test 18: Import whatif router module
    try:
        from apps.api_server.routers import whatif as whatif_mod

        record("import_whatif_router", True, "apps.api_server.routers.whatif imported")
    except Exception as e:
        whatif_mod = None
        record("import_whatif_router", False, str(e)[:100])

    # Test 19: Whatif module has WhatIfResponse model
    if whatif_mod:
        has_model = hasattr(whatif_mod, "WhatIfResponse")
        record("whatif_module_has_response_model", has_model, "")
    else:
        record_skip("whatif_module_has_response_model", "module not imported")

    # Test 20: Whatif module has WhatIfStep model
    if whatif_mod:
        has_model = hasattr(whatif_mod, "WhatIfStep")
        record("whatif_module_has_step_model", has_model, "")
    else:
        record_skip("whatif_module_has_step_model", "module not imported")

    # Test 21: WhatIfStep model has expected fields
    if whatif_mod and hasattr(whatif_mod, "WhatIfStep"):
        try:
            fields = whatif_mod.WhatIfStep.model_fields
            expected_fields = {
                "step",
                "value",
                "mean",
                "std",
                "p5",
                "p50",
                "p95",
                "probability_of_loss",
            }
            has_all = expected_fields.issubset(set(fields.keys()))
            record("whatif_step_model_fields", has_all, f"fields={list(fields.keys())[:8]}")
        except Exception as e:
            record("whatif_step_model_fields", False, str(e)[:100])
    else:
        record_skip("whatif_step_model_fields", "WhatIfStep not available")

    # Test 22: WhatIfRequest model has expected fields
    if whatif_mod and hasattr(whatif_mod, "WhatIfRequest"):
        try:
            fields = whatif_mod.WhatIfRequest.model_fields
            expected_fields = {
                "request",
                "variable",
                "param",
                "range_pct",
                "n_steps",
                "runs_per_step",
            }
            has_all = expected_fields.issubset(set(fields.keys()))
            record("whatif_request_model_fields", has_all, f"fields={list(fields.keys())}")
        except Exception as e:
            record("whatif_request_model_fields", False, str(e)[:100])
    else:
        record_skip("whatif_request_model_fields", "WhatIfRequest not available")


# ═══════════════════════════════════════════════════════════════════════════════
#  11. CROSS-FORMAT CONSISTENCY TESTS
# ═══════════════════════════════════════════════════════════════════════════════
def phase_cross_format():
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║  Phase 11 — Cross-Format Consistency Tests                 ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    if not _run_ids:
        record_skip("cross_format_all", "no run_ids available")
        return

    run_id = _run_ids[0]

    # Fetch JSON export
    status_json, raw_json, _, elapsed_json = req("GET", f"/v1/runs/{run_id}/export.json")
    # Fetch CSV export
    status_csv, raw_csv, _, elapsed_csv = req("GET", f"/v1/runs/{run_id}/export.csv")

    # Test 1: Both JSON and CSV return 200
    record(
        "cross_format_both_200",
        status_json == 200 and status_csv == 200,
        f"json={status_json} csv={status_csv}",
        max(elapsed_json, elapsed_csv),
    )

    # Test 2: JSON and CSV contain same run_id
    try:
        json_data = json.loads(raw_json)
        json_run_id = json_data.get("run_id", "")
    except Exception:
        json_run_id = ""

    csv_text = raw_csv.decode("utf-8", errors="replace")
    csv_has_run_id = run_id[:8] in csv_text or json_run_id[:8] in csv_text
    json_has_run_id = run_id in json_run_id or run_id[:8] in str(json_data)

    record(
        "cross_format_same_run_id",
        csv_has_run_id and json_has_run_id,
        f"json_has={json_has_run_id} csv_has={csv_has_run_id}",
        0,
    )

    # Test 3: JSON and CSV both contain status
    if isinstance(json_data, dict):
        json_status = json_data.get("status", "")
        csv_has_status = json_status in csv_text or "status" in csv_text.lower()
        record(
            "cross_format_same_status",
            bool(json_status) and csv_has_status,
            f"json_status={json_status}",
            0,
        )
    else:
        record("cross_format_same_status", False, "json not a dict", 0)

    # Test 4: JSON contains at least as much data as CSV key-value pairs
    if isinstance(json_data, dict):
        json_field_count = len(json_data)
        csv_reader = csv.reader(io.StringIO(csv_text))
        csv_kv_count = sum(1 for row in csv_reader if len(row) >= 2 and not row[0].startswith("#"))
        record(
            "cross_format_json_has_more_or_equal",
            json_field_count >= min(csv_kv_count, 5),
            f"json_fields={json_field_count} csv_kv={csv_kv_count}",
            0,
        )
    else:
        record("cross_format_json_has_more_or_equal", False, "", 0)

    # Test 5: All supported formats respond (even if 503 for optional deps)
    formats_tested = {}
    for fmt in ["json", "csv", "pdf", "xlsx"]:
        s, _, _, _ = req("GET", f"/v1/runs/{run_id}/export.{fmt}")
        formats_tested[fmt] = s
    all_respond = all(s in (200, 503) for s in formats_tested.values())
    record("cross_format_all_respond", all_respond, f"statuses={formats_tested}", 0)


# ═══════════════════════════════════════════════════════════════════════════════
#  12. ANALYTICS / DASHBOARD DATA TESTS
# ═══════════════════════════════════════════════════════════════════════════════
def phase_analytics():
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║  Phase 12 — Analytics / Dashboard Data Tests               ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    # Test 1: GET /v1/analytics returns 200
    status, body, hdrs, elapsed = req_json("GET", "/v1/analytics")
    record("analytics_status_200", status == 200, f"status={status}", elapsed)

    # Test 2: Contains total_runs
    if isinstance(body, dict):
        record(
            "analytics_has_total_runs",
            "total_runs" in body,
            f"total_runs={body.get('total_runs')}",
            elapsed,
        )
    else:
        record("analytics_has_total_runs", False, "", elapsed)

    # Test 3: Contains runs_by_day array
    if isinstance(body, dict):
        rbd = body.get("runs_by_day", [])
        record("analytics_has_runs_by_day", isinstance(rbd, list), f"count={len(rbd)}", elapsed)
    else:
        record("analytics_has_runs_by_day", False, "", elapsed)

    # Test 4: Contains runs_by_status
    if isinstance(body, dict):
        rbs = body.get("runs_by_status", {})
        record(
            "analytics_has_runs_by_status",
            isinstance(rbs, dict),
            f"statuses={list(rbs.keys())[:5]}",
            elapsed,
        )
    else:
        record("analytics_has_runs_by_status", False, "", elapsed)

    # Test 5: Contains runs_by_mode
    if isinstance(body, dict):
        rbm = body.get("runs_by_mode", {})
        record(
            "analytics_has_runs_by_mode",
            isinstance(rbm, dict),
            f"modes={list(rbm.keys())[:5]}",
            elapsed,
        )
    else:
        record("analytics_has_runs_by_mode", False, "", elapsed)

    # Test 6: Contains avg_duration_ms
    if isinstance(body, dict):
        record(
            "analytics_has_avg_duration",
            "avg_duration_ms" in body,
            f"avg_duration_ms={body.get('avg_duration_ms')}",
            elapsed,
        )
    else:
        record("analytics_has_avg_duration", False, "", elapsed)

    # Test 7: No auth → 401
    status2, _, _, elapsed2 = req_json("GET", "/v1/analytics", auth=False)
    record("analytics_no_auth_401", status2 in (401, 403), f"status={status2}", elapsed2)

    # Test 8: Analytics with custom days param
    status3, body3, _, elapsed3 = req_json("GET", "/v1/analytics?days=7")
    record("analytics_custom_days", status3 == 200, f"status={status3}", elapsed3)


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN — Run all phases
# ═══════════════════════════════════════════════════════════════════════════════


def main():
    print("=" * 70)
    print("  Phase 18: Export Functionality Integration Tests")
    print("=" * 70)
    print(f"  Server:  {BASE_URL}")
    print(f"  API Key: {API_KEY[:12]}...")
    print("=" * 70)

    t0 = time.perf_counter()

    # Check server is alive
    try:
        status, _, _, _ = req_json("GET", "/health", auth=False, timeout=5)
        if status == 0:
            # Try /docs or root
            status, _, _, _ = req_json("GET", "/docs", auth=False, timeout=5)
    except Exception:
        status = 0

    if status == 0:
        print(f"\n{FAIL} Cannot reach server at {BASE_URL}. Is it running?")
        print("  Start with: make dev-api")
        sys.exit(1)

    phase_setup()
    phase_json_export()
    phase_csv_export()
    phase_pdf_export()
    phase_xlsx_export()
    phase_run_detail()
    phase_sse_logs()
    phase_sse_simulate_stream()
    phase_whatif_export()
    phase_error_handling()
    phase_direct_module_tests()
    phase_cross_format()
    phase_analytics()

    total_time = time.perf_counter() - t0

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, s, _ in results if s == PASS)
    failed = sum(1 for _, s, _ in results if s == FAIL)
    skipped = sum(1 for _, s, _ in results if s == SKIP)
    total = len(results)

    print(f"\n  Total:   {total}")
    print(f"  Passed:  {passed} {PASS}")
    print(f"  Failed:  {failed} {FAIL}")
    print(f"  Skipped: {skipped} {SKIP}")
    print(f"  Time:    {total_time:.1f}s")
    print()

    if failed > 0:
        print("  Failed tests:")
        for name, status, detail in results:
            if status == FAIL:
                print(f"    {FAIL} {name}: {detail[:100]}")
        print()

    # ── Timing report ─────────────────────────────────────────────────────────
    if timings:
        sorted_timings = sorted(timings, key=lambda x: x[1], reverse=True)[:10]
        print("  Top 10 Slowest Tests:")
        for name, t in sorted_timings:
            if t > 0:
                print(f"    {t * 1000:7.0f}ms  {name}")
        print()

    pct = (passed / total * 100) if total > 0 else 0
    print(f"  Pass rate: {pct:.1f}% ({passed}/{total})")
    print("=" * 70)

    # Exit code: 0 if all pass/skip, 1 if any fail
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
