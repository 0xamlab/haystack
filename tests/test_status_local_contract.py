from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS_LOCAL_SCRIPT = ROOT / "scripts" / "status-local.sh"


def test_status_local_script_reports_launcher_managed_state_from_recorded_files() -> None:
    text = STATUS_LOCAL_SCRIPT.read_text(encoding="utf-8")

    assert 'START_LOCAL_STATE_DIR="$ROOT/build/start-local"' in text
    assert 'API_PORT_FILTER="${ALGENTA_API_PORT:-}"' in text
    assert 'MCP_PORT_FILTER="${ALGENTA_MCP_PORT:-}"' in text
    assert 'FORMAT="table"' in text
    assert 'ENTRIES_FILE="$(mktemp "${TMPDIR:-/tmp}/algenta-status-local.XXXXXX")"' in text
    assert 'trap cleanup EXIT' in text
    assert '_listener_pid() {' in text
    assert '_classify_service() {' in text
    assert '_pid_is_running' not in text
    assert '[ "$lease_exists" = "1" ] && [ -n "$listener_pid" ] && [ "$pid" = "$listener_pid" ]' in text
    assert 'printf \'%s\' "active"' in text
    assert 'printf \'%s\' "orphaned"' in text
    assert 'printf \'%s\' "missing_listener"' in text
    assert 'printf \'%s\' "missing_lease"' in text
    assert 'printf \'%s\' "stale_pid"' in text
    assert '_print_status_json() {' in text
    assert '"services": services, "summary": summary' in text
    assert '"kind": label.lower(),' in text
    assert '"port": int(port),' in text
    assert '"lease": lease == "1",' in text
    assert '_print_matching_services "API" "api" "$API_PORT_FILTER"' in text
    assert '_print_matching_services "MCP" "mcp" "$MCP_PORT_FILTER"' in text
    assert "📋 Launcher-managed Algenta local stack status" in text
    assert 'No launcher-managed local stacks found.' in text


def test_status_local_script_supports_port_filters() -> None:
    text = STATUS_LOCAL_SCRIPT.read_text(encoding="utf-8")

    assert '--format requires table or json.' in text
    assert '--format must be table or json.' in text
    assert '--json)' in text
    assert 'if [ -n "$port_filter" ] && [ "$port" != "$port_filter" ]; then' in text
    assert 'local port="${base_name#"$prefix"-}"' in text
    assert "port=%s state=%s pid=%s listener_pid=%s lease=%s" in text
    assert 'printf \'%s\\n\' \'{"services":[],"summary":{"active":0,"missing_lease":0,"missing_listener":0,"orphaned":0,"stale_pid":0,"total":0}}\'' in text
