#!/usr/bin/env bash
# Shows launcher-managed Algenta local API + MCP server state.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
START_LOCAL_STATE_DIR="$ROOT/build/start-local"
API_PORT_FILTER="${ALGENTA_API_PORT:-}"
MCP_PORT_FILTER="${ALGENTA_MCP_PORT:-}"
FORMAT="table"
FOUND_ANY=0
ENTRIES_FILE=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --format)
      if [ "$#" -lt 2 ]; then
        echo "--format requires table or json." >&2
        exit 2
      fi
      FORMAT="$2"
      shift 2
      ;;
    --json)
      FORMAT="json"
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [ "$FORMAT" != "table" ] && [ "$FORMAT" != "json" ]; then
  echo "--format must be table or json." >&2
  exit 2
fi

ENTRIES_FILE="$(mktemp "${TMPDIR:-/tmp}/algenta-status-local.XXXXXX")"
cleanup() {
  rm -f "$ENTRIES_FILE"
}
trap cleanup EXIT

_listener_pid() {
  local port="$1"
  lsof -ti "TCP:$port" -sTCP:LISTEN | head -n 1
}

_classify_service() {
  local pid="$1"
  local lease_exists="$2"
  local listener_pid="$3"

  if [ "$lease_exists" = "1" ] && [ -n "$listener_pid" ] && [ "$pid" = "$listener_pid" ]; then
    printf '%s' "active"
    return 0
  fi
  if [ "$lease_exists" = "0" ] && [ -z "$listener_pid" ]; then
    printf '%s' "orphaned"
    return 0
  fi
  if [ "$lease_exists" = "1" ] && [ -z "$listener_pid" ]; then
    printf '%s' "missing_listener"
    return 0
  fi
  if [ "$lease_exists" = "0" ] && [ -n "$listener_pid" ]; then
    printf '%s' "missing_lease"
    return 0
  fi
  printf '%s' "stale_pid"
}

_print_matching_services() {
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
    local lease_exists=0
    if [ -f "$lease_file" ]; then
      lease_exists=1
    fi
    local pid=""
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    local listener_pid=""
    listener_pid="$(_listener_pid "$port")"
    local state=""
    state="$(_classify_service "$pid" "$lease_exists" "$listener_pid")"
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$label" "$port" "$state" "${pid:-none}" "${listener_pid:-none}" "$lease_exists" >> "$ENTRIES_FILE"
    FOUND_ANY=1
  done
}

_print_status_table() {
  echo "📋 Launcher-managed Algenta local stack status"
  while IFS=$'\t' read -r label port state pid listener_pid lease; do
    printf '%s port=%s state=%s pid=%s listener_pid=%s lease=%s\n' \
      "$label" "$port" "$state" "$pid" "$listener_pid" "$lease"
  done < "$ENTRIES_FILE"
}

_print_status_json() {
  python3 - "$ENTRIES_FILE" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

entries_path = Path(sys.argv[1])
services = []
for raw_line in entries_path.read_text(encoding="utf-8").splitlines():
    if not raw_line:
        continue
    label, port, state, pid, listener_pid, lease = raw_line.split("\t")
    services.append(
        {
            "kind": label.lower(),
            "port": int(port),
            "state": state,
            "pid": None if pid == "none" else int(pid),
            "listener_pid": None if listener_pid == "none" else int(listener_pid),
            "lease": lease == "1",
        }
    )
summary = {
    "total": len(services),
    "active": sum(1 for service in services if service["state"] == "active"),
    "orphaned": sum(1 for service in services if service["state"] == "orphaned"),
    "missing_listener": sum(1 for service in services if service["state"] == "missing_listener"),
    "missing_lease": sum(1 for service in services if service["state"] == "missing_lease"),
    "stale_pid": sum(1 for service in services if service["state"] == "stale_pid"),
}
print(json.dumps({"services": services, "summary": summary}, sort_keys=True))
PY
}

if [ ! -d "$START_LOCAL_STATE_DIR" ]; then
  if [ "$FORMAT" = "json" ]; then
    printf '%s\n' '{"services":[],"summary":{"active":0,"missing_lease":0,"missing_listener":0,"orphaned":0,"stale_pid":0,"total":0}}'
  else
    echo "📋 Launcher-managed Algenta local stack status"
    echo "  No launcher-managed state directory found."
  fi
  exit 0
fi

_print_matching_services "API" "api" "$API_PORT_FILTER"
_print_matching_services "MCP" "mcp" "$MCP_PORT_FILTER"

if [ "$FOUND_ANY" = "0" ]; then
  if [ "$FORMAT" = "json" ]; then
    printf '%s\n' '{"services":[],"summary":{"active":0,"missing_lease":0,"missing_listener":0,"orphaned":0,"stale_pid":0,"total":0}}'
  else
    echo "📋 Launcher-managed Algenta local stack status"
    echo "  No launcher-managed local stacks found."
  fi
  exit 0
fi

if [ "$FORMAT" = "json" ]; then
  _print_status_json
else
  _print_status_table
fi
