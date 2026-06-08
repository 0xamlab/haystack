#!/usr/bin/env bash
# Stops launcher-managed Algenta local API + MCP servers.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
START_LOCAL_STATE_DIR="$ROOT/build/start-local"
API_PORT_FILTER="${ALGENTA_API_PORT:-}"
MCP_PORT_FILTER="${ALGENTA_MCP_PORT:-}"
STOPPED_ANY=0

_pid_is_running() {
  local pid="${1:-}"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

_port_in_use() {
  local port="$1"
  lsof -ti "TCP:$port" -sTCP:LISTEN >/dev/null 2>&1
}

_stop_recorded_service() {
  local label="$1"
  local pid_file="$2"
  local lease_file="$3"
  local port="$4"

  rm -f "$lease_file"
  local pid=""
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if _pid_is_running "$pid"; then
    kill "$pid" 2>/dev/null || true
  fi

  for _ in $(seq 1 40); do
    if ! _port_in_use "$port"; then
      rm -f "$pid_file"
      echo "  Stopped $label on port $port"
      STOPPED_ANY=1
      return 0
    fi
    sleep 0.25
  done

  echo "Failed to stop $label on port $port." >&2
  return 2
}

_stop_matching_services() {
  local label="$1"
  local prefix="$2"
  local port_filter="$3"
  local pid_file=""
  for pid_file in "$START_LOCAL_STATE_DIR"/"$prefix"-*.pid; do
    if [ ! -f "$pid_file" ]; then
      continue
    fi
    local base_name
    base_name="$(basename "$pid_file" .pid)"
    local port="${base_name#"$prefix"-}"
    if [ -n "$port_filter" ] && [ "$port" != "$port_filter" ]; then
      continue
    fi
    local lease_file="$START_LOCAL_STATE_DIR/$base_name.lease"
    _stop_recorded_service "$label" "$pid_file" "$lease_file" "$port"
  done
}

echo "🛑 Stopping launcher-managed Algenta local stack..."

if [ ! -d "$START_LOCAL_STATE_DIR" ]; then
  echo "  No launcher-managed state directory found."
  exit 0
fi

_stop_matching_services "API" "api" "$API_PORT_FILTER"
_stop_matching_services "MCP" "mcp" "$MCP_PORT_FILTER"

if [ "$STOPPED_ANY" = "0" ]; then
  echo "  No matching launcher-managed services were running."
fi
