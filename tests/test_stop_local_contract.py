from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOP_LOCAL_SCRIPT = ROOT / "scripts" / "stop-local.sh"


def test_stop_local_script_stops_launcher_managed_services_by_recorded_state() -> None:
    text = STOP_LOCAL_SCRIPT.read_text(encoding="utf-8")

    assert 'START_LOCAL_STATE_DIR="$ROOT/build/start-local"' in text
    assert 'API_PORT_FILTER="${ALGENTA_API_PORT:-}"' in text
    assert 'MCP_PORT_FILTER="${ALGENTA_MCP_PORT:-}"' in text
    assert '_stop_matching_services "API" "api" "$API_PORT_FILTER"' in text
    assert '_stop_matching_services "MCP" "mcp" "$MCP_PORT_FILTER"' in text
    assert 'rm -f "$lease_file"' in text
    assert 'kill "$pid" 2>/dev/null || true' in text
    assert 'if ! _port_in_use "$port"; then' in text
    assert 'rm -f "$pid_file"' in text
    assert 'echo "  Stopped $label on port $port"' in text
    assert 'echo "Failed to stop $label on port $port."' in text
    assert 'echo "  No matching launcher-managed services were running."' in text


def test_stop_local_script_uses_port_filters_without_touching_unmatched_services() -> None:
    text = STOP_LOCAL_SCRIPT.read_text(encoding="utf-8")

    assert 'if [ -n "$port_filter" ] && [ "$port" != "$port_filter" ]; then' in text
    assert 'local port="${base_name#"$prefix"-}"' in text
