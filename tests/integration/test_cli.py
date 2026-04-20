"""
CLI integration tests — tests apps/cli/main.py against a live server at localhost:8000.

Prerequisites:
  1. API server running on localhost:8000
  2. PostgreSQL + Redis running
  3. Dev data seeded

Run:
  DE_API_KEY="de_live_LrL6UWSAfgXsTjgfyaboI9aolrsznjLU" PYTHONPATH=. python3 tests/integration/test_cli.py
"""
import json
import os
import socket
import subprocess
import sys
import tempfile

# Global socket timeout — prevents any test from hanging indefinitely
socket.setdefaulttimeout(15)

BASE_URL = os.environ.get("DE_BASE_URL", "http://localhost:8000")
API_KEY = os.environ.get("DE_API_KEY", "de_live_LrL6UWSAfgXsTjgfyaboI9aolrsznjLU")
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CLI_SCRIPT = os.path.join(PROJECT_ROOT, "apps", "cli", "main.py")

PASS = "✅"
FAIL = "❌"
results: list[tuple] = []


def check(name: str, fn):
    try:
        fn()
        results.append((PASS, name))
        print(f"  {PASS} {name}")
    except AssertionError as e:
        results.append((FAIL, name, str(e)))
        print(f"  {FAIL} {name}: {e}")
    except Exception as e:
        results.append((FAIL, name, str(e)))
        print(f"  {FAIL} {name}: {type(e).__name__}: {e}")


def run_cli(*args: str, api_key: str | None = None, base_url: str | None = None,
            timeout: float = 15) -> subprocess.CompletedProcess:
    """Run the CLI as a subprocess and return the result."""
    env = os.environ.copy()
    env["DE_API_KEY"] = api_key or API_KEY
    env["DE_BASE_URL"] = base_url or BASE_URL
    env["PYTHONPATH"] = PROJECT_ROOT
    cmd = [sys.executable, CLI_SCRIPT] + list(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        cwd=PROJECT_ROOT,
    )


def write_temp_json(data: dict) -> str:
    """Write a dict to a temp JSON file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".json", prefix="de_test_")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    return path


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 1: CLI — Basic Commands
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 1: CLI — Basic Commands")
print("=" * 70)


def test_cli_help():
    """Running with no args should show help/usage."""
    result = run_cli()
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}: {result.stderr}"
    output = result.stdout + result.stderr
    # Should contain usage info
    assert "simulate" in output.lower() or "usage" in output.lower() or "decision" in output.lower(), \
        f"Help output missing expected keywords: {output[:300]}"

check("CLI no args → help/usage text", test_cli_help)


def test_cli_health():
    result = run_cli("health")
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}: stderr={result.stderr}"
    output = result.stdout
    assert "ok" in output.lower() or "✅" in output, f"Expected 'ok' in output: {output[:200]}"

check("CLI health → OK", test_cli_health)


def test_cli_version():
    result = run_cli("version")
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}: stderr={result.stderr}"
    output = result.stdout
    assert "engine" in output.lower() or "api" in output.lower(), \
        f"Expected version info: {output[:200]}"

check("CLI version → version info", test_cli_version)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 2: CLI — Simulate Command
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 2: CLI — Simulate Command")
print("=" * 70)


def test_cli_simulate_auto():
    """Run a simulation via CLI with an auto-mode payload file."""
    payload = {
        "mode": "auto",
        "runs": 1000,
        "scenario": {
            "variables": {"revenue": {"low": 80000, "high": 200000}},
            "objective": "maximize_net_value",
        },
    }
    path = write_temp_json(payload)
    try:
        result = run_cli("simulate", path, "--format", "json")
        assert result.returncode == 0, \
            f"Expected exit 0, got {result.returncode}: stderr={result.stderr[:500]}"
        output = result.stdout.strip()
        # Should be valid JSON
        data = json.loads(output)
        assert "recommended_action" in data, f"Missing recommended_action: {list(data.keys())}"
        assert data["recommended_action"] in ("proceed", "hold", "reject"), \
            f"Unexpected action: {data['recommended_action']}"
        assert "confidence" in data, "Missing confidence"
        assert 0 <= data["confidence"] <= 1, f"Confidence out of range: {data['confidence']}"
    finally:
        os.unlink(path)

check("CLI simulate auto → JSON with recommended_action", test_cli_simulate_auto)


def test_cli_simulate_expert():
    """Run an expert-mode simulation via CLI."""
    payload = {
        "mode": "expert",
        "runs": 500,
        "simulation": {
            "variables": [
                {"name": "revenue", "distribution": "triangular",
                 "params": {"low": 80000, "mode": 120000, "high": 200000}},
                {"name": "costs", "distribution": "normal",
                 "params": {"mean": 55000, "std": 8000}},
            ],
            "objective_function": "revenue - costs",
        },
    }
    path = write_temp_json(payload)
    try:
        result = run_cli("simulate", path, "--format", "json")
        assert result.returncode == 0, \
            f"Expected exit 0, got {result.returncode}: stderr={result.stderr[:500]}"
        data = json.loads(result.stdout.strip())
        assert "recommended_action" in data, "Missing recommended_action"
        assert "metrics" in data, "Missing metrics"
    finally:
        os.unlink(path)

check("CLI simulate expert → JSON with metrics", test_cli_simulate_expert)


def test_cli_simulate_table_format():
    """Default (table) format should produce readable output."""
    payload = {
        "mode": "auto",
        "runs": 100,
        "scenario": {
            "variables": {"x": {"low": 0, "high": 100}},
            "objective": "maximize_net_value",
        },
    }
    path = write_temp_json(payload)
    try:
        result = run_cli("simulate", path)
        assert result.returncode == 0, \
            f"Expected exit 0, got {result.returncode}: stderr={result.stderr[:500]}"
        output = result.stdout
        # Table format should contain "Recommendation" or the action or JSON fallback
        has_content = (
            "proceed" in output.lower()
            or "hold" in output.lower()
            or "reject" in output.lower()
            or "recommended_action" in output
        )
        assert has_content, f"Expected decision info in table output: {output[:300]}"
    finally:
        os.unlink(path)

check("CLI simulate table format → readable output", test_cli_simulate_table_format)


def test_cli_simulate_envelope_fields():
    """Verify the JSON output contains all envelope fields."""
    payload = {
        "mode": "auto",
        "runs": 1000,
        "scenario": {
            "variables": {"revenue": {"low": 80000, "high": 200000}},
            "objective": "maximize_net_value",
        },
    }
    path = write_temp_json(payload)
    try:
        result = run_cli("simulate", path, "--format", "json")
        assert result.returncode == 0, f"Exit {result.returncode}: {result.stderr[:300]}"
        data = json.loads(result.stdout.strip())
        required_fields = ["run_id", "status", "recommended_action", "confidence",
                           "metrics", "percentiles", "scenarios_run", "execution_ms"]
        for field in required_fields:
            assert field in data, f"Missing field '{field}' in envelope: {list(data.keys())}"
        # Validate metrics sub-object
        metrics = data["metrics"]
        assert "expected_value" in metrics, "Missing expected_value in metrics"
        assert "probability_of_loss" in metrics, "Missing probability_of_loss in metrics"
        # Validate percentiles
        pct = data["percentiles"]
        assert pct["p5"] <= pct["p95"], f"p5={pct['p5']} > p95={pct['p95']}"
    finally:
        os.unlink(path)

check("CLI simulate → full envelope with metrics and percentiles", test_cli_simulate_envelope_fields)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 3: CLI — Error Cases
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 3: CLI — Error Cases")
print("=" * 70)


def test_cli_bad_api_key():
    """Bad API key should produce an error and non-zero exit."""
    payload = {
        "mode": "auto",
        "runs": 100,
        "scenario": {
            "variables": {"x": {"low": 0, "high": 100}},
            "objective": "maximize_net_value",
        },
    }
    path = write_temp_json(payload)
    try:
        result = run_cli("simulate", path, "--format", "json",
                         api_key="de_live_INVALID_KEY_FAKE")
        assert result.returncode != 0, \
            f"Expected non-zero exit for bad key, got {result.returncode}"
        combined = result.stdout + result.stderr
        assert "401" in combined or "error" in combined.lower() or "❌" in combined, \
            f"Expected error message for bad key: {combined[:300]}"
    finally:
        os.unlink(path)

check("CLI bad API key → error + non-zero exit", test_cli_bad_api_key)


def test_cli_bad_payload():
    """Invalid payload should produce an error."""
    payload = {"mode": "invalid_mode_xyz"}
    path = write_temp_json(payload)
    try:
        result = run_cli("simulate", path, "--format", "json")
        assert result.returncode != 0, \
            f"Expected non-zero exit for bad payload, got {result.returncode}"
        combined = result.stdout + result.stderr
        assert "error" in combined.lower() or "❌" in combined or "422" in combined, \
            f"Expected error in output: {combined[:300]}"
    finally:
        os.unlink(path)

check("CLI bad payload → error + non-zero exit", test_cli_bad_payload)


def test_cli_missing_file():
    """Non-existent file should produce an error."""
    result = run_cli("simulate", "/tmp/nonexistent_file_12345.json", "--format", "json")
    assert result.returncode != 0, \
        f"Expected non-zero exit for missing file, got {result.returncode}"

check("CLI missing file → non-zero exit", test_cli_missing_file)


def test_cli_unknown_command():
    """Unknown command should produce an error."""
    result = run_cli("nonexistent_command_xyz")
    assert result.returncode != 0, \
        f"Expected non-zero exit for unknown command, got {result.returncode}"

check("CLI unknown command → non-zero exit", test_cli_unknown_command)


def test_cli_invalid_json_file():
    """File with invalid JSON should fail."""
    fd, path = tempfile.mkstemp(suffix=".json", prefix="de_test_")
    with os.fdopen(fd, "w") as f:
        f.write("{ this is not valid json !!!")
    try:
        result = run_cli("simulate", path, "--format", "json")
        assert result.returncode != 0, \
            f"Expected non-zero exit for invalid JSON, got {result.returncode}"
    finally:
        os.unlink(path)

check("CLI invalid JSON file → non-zero exit", test_cli_invalid_json_file)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 4: CLI — Keys & Metadata Commands
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 4: CLI — Keys & Metadata Commands")
print("=" * 70)


def test_cli_keys_list():
    result = run_cli("keys", "list")
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}: {result.stderr[:300]}"
    output = result.stdout
    assert "key" in output.lower() or "api" in output.lower() or "de_live" in output, \
        f"Expected key info in output: {output[:300]}"

check("CLI keys list → key info", test_cli_keys_list)


# ═══════════════════════════════════════════════════════════════════════════════
#  RESULTS SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  RESULTS SUMMARY — CLI Integration Tests")
print("=" * 70)

passed = sum(1 for r in results if r[0] == PASS)
failed = sum(1 for r in results if r[0] == FAIL)
total = len(results)

print(f"\n  Total:  {total} tests")
print(f"  Passed: {passed} {PASS}")
print(f"  Failed: {failed} {FAIL}")

if failed > 0:
    print("\n  ── Failures ──")
    for r in results:
        if r[0] == FAIL:
            print(f"    {FAIL} {r[1]}: {r[2] if len(r) > 2 else ''}")

print(f"\n{'=' * 70}")
if failed == 0:
    print(f"  🎉 ALL {passed} CLI TESTS PASSED!")
else:
    print(f"  ⚠️  {failed}/{total} FAILURES")
print(f"{'=' * 70}\n")

sys.exit(1 if failed > 0 else 0)
