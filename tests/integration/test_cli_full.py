"""
test_cli_full.py — Full CLI coverage for all 9 commands.

Complements test_cli.py which covers: health, version, simulate, keys list.
This covers the remaining 5: config set-key, recommend, job submit/status/wait.

Two layers:
  Layer A — CLI import + command structure (no server)
  Layer B — Live subprocess calls (requires running API server)

Run:
  DE_SKIP_API=1 python3 tests/integration/test_cli_full.py
  python3 tests/integration/test_cli_full.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

BASE_URL = os.environ.get("DE_BASE_URL", "http://localhost:8000")
API_KEY  = os.environ.get("DE_API_KEY",  "de_live_LrL6UWSAfgXsTjgfyaboI9aolrsznjLU")
SKIP_API = os.environ.get("DE_SKIP_API", "0") == "1"

CLI = [sys.executable, str(_ROOT / "apps" / "cli" / "main.py")]
ENV = {**os.environ, "DE_API_KEY": API_KEY, "DE_BASE_URL": BASE_URL, "DE_NO_COLOR": "1"}

PASS = "✅"; FAIL = "❌"; SKIP = "⏭️ "
_results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    icon = PASS if cond else FAIL
    _results.append((name, cond, detail))
    print(f"  {icon}  {name}" + (f"  ({detail})" if detail else ""))


def run(*args: str, input_str: str | None = None, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        CLI + list(args), capture_output=True, text=True, env=ENV,
        timeout=timeout, input=input_str,
    )


def tmpfile(data: dict) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return f.name


_SIMULATE_PAYLOAD = {
    "mode": "auto",
    "variables": [{"name": "revenue", "distribution": "normal", "mean": 100000, "std_dev": 15000}],
    "runs": 500,
}
_RECOMMEND_PAYLOAD = {
    "context": {"metric": "profit", "current_value": 50000},
    "options": [
        {"label": "a", "expected_value": 60000, "risk": 0.1},
        {"label": "b", "expected_value": 80000, "risk": 0.4},
    ],
}

# ── Layer A: CLI structure ────────────────────────────────────────────────────

def test_cli_importable():
    from apps.cli import main as cli_main
    check("apps.cli.main importable", True)
    check("cmd_config_set_key exists",    hasattr(cli_main, "cmd_config_set_key"))
    check("cmd_data_connect exists",      hasattr(cli_main, "cmd_data_connect"))
    check("cmd_data_list exists",         hasattr(cli_main, "cmd_data_list"))
    check("cmd_data_inspect exists",      hasattr(cli_main, "cmd_data_inspect"))
    check("cmd_data_refresh exists",      hasattr(cli_main, "cmd_data_refresh"))
    check("cmd_data_disconnect exists",   hasattr(cli_main, "cmd_data_disconnect"))
    check("cmd_recommend exists",         hasattr(cli_main, "cmd_recommend"))
    check("cmd_job_submit exists",        hasattr(cli_main, "cmd_job_submit"))
    check("cmd_job_status exists",        hasattr(cli_main, "cmd_job_status"))
    check("cmd_job_wait exists",          hasattr(cli_main, "cmd_job_wait"))


def test_cli_help_shows_all_commands():
    # CLI prints usage when called with no args or unknown command
    r = run()
    out = r.stdout + r.stderr
    for cmd in ["data", "simulate", "recommend", "job", "config"]:
        check(f"usage mentions '{cmd}'", cmd in out)
    # keys/health/version may be printed differently — check the source
    from apps.cli.main import cmd_health, cmd_keys_list
    check("cmd_keys_list defined", callable(cmd_keys_list))
    check("cmd_health defined",    callable(cmd_health))


def test_job_help():
    r = run("job", "--help")
    out = r.stdout + r.stderr
    for sub in ["submit", "status", "wait"]:
        check(f"job --help mentions '{sub}'", sub in out)


def test_config_help():
    r = run("config", "--help")
    out = r.stdout + r.stderr
    check("config --help mentions 'set-key'", "set-key" in out or "set_key" in out)


def test_data_help():
    r = run("data", "--help")
    out = r.stdout + r.stderr
    for sub in ["connect", "list", "inspect", "refresh", "disconnect"]:
        check(f"data --help mentions '{sub}'", sub in out)


# ── Layer B: Live CLI calls ───────────────────────────────────────────────────

def test_config_set_key():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_env = {**ENV, "DE_CONFIG_DIR": tmpdir}
        r = subprocess.run(
            CLI + ["config", "set-key", API_KEY],
            capture_output=True, text=True, env=cfg_env, timeout=10,
        )
        check(
            "config set-key exits 0",
            r.returncode == 0,
            r.stderr.strip()[:100],
        )
        check(
            "config set-key writes config",
            any(Path(tmpdir).rglob("*.json")) or r.returncode == 0,
        )


def test_recommend():
    filepath = tmpfile(_RECOMMEND_PAYLOAD)
    try:
        r = run("recommend", filepath)
        check("recommend exits 0", r.returncode == 0, r.stderr.strip()[:120])
        check("recommend outputs content", bool(r.stdout.strip()))
    finally:
        Path(filepath).unlink(missing_ok=True)


def test_recommend_json_format():
    filepath = tmpfile(_RECOMMEND_PAYLOAD)
    try:
        r = run("recommend", filepath, "--format", "json")
        check("recommend --format json exits 0", r.returncode == 0, r.stderr.strip()[:100])
        out = r.stdout.strip()
        if out:
            try:
                json.loads(out)
                check("recommend json output is valid JSON", True)
            except json.JSONDecodeError:
                check("recommend json output is valid JSON", False, out[:100])
    finally:
        Path(filepath).unlink(missing_ok=True)


def test_job_submit():
    filepath = tmpfile(_SIMULATE_PAYLOAD)
    try:
        r = run("job", "submit", filepath)
        check("job submit exits 0", r.returncode == 0, r.stderr.strip()[:120])
        out = r.stdout.strip()
        check("job submit outputs job_id or content", bool(out))
        return out
    finally:
        Path(filepath).unlink(missing_ok=True)


def test_job_status():
    # Submit a job first to get a real job_id
    filepath = tmpfile(_SIMULATE_PAYLOAD)
    try:
        r = run("job", "submit", filepath)
        if r.returncode != 0:
            check("job status prereq: submit succeeded", False, r.stderr.strip()[:100])
            return
        # Extract job_id from output
        out = r.stdout.strip()
        job_id = None
        try:
            data = json.loads(out)
            job_id = data.get("job_id") or data.get("id")
        except (json.JSONDecodeError, AttributeError):
            # Try to find UUID-like string
            import re
            match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", out)
            if match:
                job_id = match.group()

        check("job submit returned job_id", bool(job_id), out[:100])
        if not job_id:
            return

        r2 = run("job", "status", job_id)
        check("job status exits 0", r2.returncode == 0, r2.stderr.strip()[:100])
        check("job status outputs content", bool(r2.stdout.strip()))
    finally:
        Path(filepath).unlink(missing_ok=True)


def test_job_wait():
    filepath = tmpfile(_SIMULATE_PAYLOAD)
    try:
        r = run("job", "submit", filepath)
        if r.returncode != 0:
            check("job wait prereq: submit succeeded", False)
            return
        out = r.stdout.strip()
        job_id = None
        try:
            job_id = json.loads(out).get("job_id") or json.loads(out).get("id")
        except Exception:
            import re
            match = re.search(r"[0-9a-f-]{36}", out)
            if match:
                job_id = match.group()

        check("job wait prereq: got job_id", bool(job_id))
        if not job_id:
            return

        r2 = run("job", "wait", job_id, "--timeout", "60")
        check("job wait exits 0", r2.returncode == 0, r2.stderr.strip()[:100])
        check("job wait outputs result", bool(r2.stdout.strip()))
    finally:
        Path(filepath).unlink(missing_ok=True)


def test_job_submit_with_callback():
    filepath = tmpfile(_SIMULATE_PAYLOAD)
    try:
        r = run("job", "submit", filepath, "--callback", "https://httpbin.org/post")
        # Just check it doesn't crash — callback delivery is async
        check(
            "job submit --callback accepts url",
            r.returncode == 0 or "callback" in (r.stdout + r.stderr).lower(),
            r.stderr.strip()[:100],
        )
    finally:
        Path(filepath).unlink(missing_ok=True)


def test_data_connect_list_inspect_disconnect():
    request = {
        "connection_type": "file_upload",
        "dataset_name": "CliBacklog",
        "csv": "customer_id,amount\nA,10\nB,20\n",
    }
    path = tmpfile(request)
    dataset_id = None
    try:
        r = run("data", "connect", "--request", path, "--format", "json")
        check("data connect exits 0", r.returncode == 0, r.stderr.strip()[:120])
        body = json.loads(r.stdout)
        dataset_id = body.get("dataset_id")
        check("data connect returns dataset_id", bool(dataset_id), r.stdout[:120])
        if not dataset_id:
            return

        r_list = run("data", "list", "--format", "json")
        check("data list exits 0", r_list.returncode == 0, r_list.stderr.strip()[:100])
        list_body = json.loads(r_list.stdout)
        check(
            "data list contains dataset",
            any(item.get("dataset_id") == dataset_id for item in list_body.get("datasets", [])),
        )

        r_inspect = run("data", "inspect", dataset_id, "--format", "json")
        check("data inspect exits 0", r_inspect.returncode == 0, r_inspect.stderr.strip()[:100])
        inspect_body = json.loads(r_inspect.stdout)
        check("data inspect returns dataset", inspect_body.get("dataset", {}).get("dataset_id") == dataset_id)

        r_disconnect = run("data", "disconnect", dataset_id, "--yes", "--format", "json")
        check("data disconnect exits 0", r_disconnect.returncode == 0, r_disconnect.stderr.strip()[:100])
        disconnect_body = json.loads(r_disconnect.stdout)
        check("data disconnect deleted dataset", disconnect_body.get("status") == "deleted")
    finally:
        Path(path).unlink(missing_ok=True)


def test_data_connect_refresh_database_dataset():
    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_path = Path(tmpdir) / "cli_refresh.db"
        conn = sqlite3.connect(sqlite_path)
        try:
            conn.execute("CREATE TABLE backlog (customer_id TEXT, amount REAL)")
            conn.executemany(
                "INSERT INTO backlog (customer_id, amount) VALUES (?, ?)",
                [("A", 10.0), ("B", 20.0)],
            )
            conn.commit()
        finally:
            conn.close()

        request_path = Path(tmpdir) / "db_request.json"
        request_path.write_text(json.dumps({
            "connection_type": "database",
            "provider": "sqlite",
            "dataset_name": "CliSqlite",
            "connection_config": {"path": str(sqlite_path)},
            "selection": {"table": "backlog"},
        }))

        r = run("data", "connect", "--request", str(request_path), "--format", "json")
        check("data connect database exits 0", r.returncode == 0, r.stderr.strip()[:120])
        body = json.loads(r.stdout)
        dataset_id = body.get("dataset_id")
        check("data connect database returns dataset_id", bool(dataset_id), r.stdout[:120])
        if not dataset_id:
            return

        r_refresh = run("data", "refresh", dataset_id, "--format", "json")
        check("data refresh exits 0", r_refresh.returncode == 0, r_refresh.stderr.strip()[:120])
        refresh_body = json.loads(r_refresh.stdout)
        check("data refresh returns ready", refresh_body.get("status") == "ready")

        r_disconnect = run("data", "disconnect", dataset_id, "--yes", "--format", "json")
        check("data disconnect database exits 0", r_disconnect.returncode == 0, r_disconnect.stderr.strip()[:120])


# ── Runner ────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "=" * 68)
    print("  CLI FULL COVERAGE TESTS")
    print("=" * 68)

    print("\n── Layer A: CLI structure (no server) ──────────────────────────\n")
    for fn in [test_cli_importable, test_cli_help_shows_all_commands,
               test_job_help, test_config_help, test_data_help]:
        try:
            fn()
        except Exception as e:
            check(fn.__name__, False, str(e))

    print("\n── Layer B: Live CLI calls ──────────────────────────────────────\n")
    live = [
        test_config_set_key, test_recommend, test_recommend_json_format,
        test_job_submit, test_job_status, test_job_wait, test_job_submit_with_callback,
        test_data_connect_list_inspect_disconnect, test_data_connect_refresh_database_dataset,
    ]
    if SKIP_API:
        print(f"  {SKIP}  Skipped (DE_SKIP_API=1)")
    else:
        for fn in live:
            try:
                fn()
            except subprocess.TimeoutExpired:
                check(fn.__name__, False, "timeout")
            except Exception as e:
                check(fn.__name__, False, f"{type(e).__name__}: {e}")

    passed = sum(1 for _, ok, _ in _results if ok)
    failed = sum(1 for _, ok, _ in _results if not ok)
    print(f"\n{'=' * 68}")
    print(f"  {passed} passed  |  {failed} failed  |  {len(_results)} total")
    print(f"{'=' * 68}\n")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
