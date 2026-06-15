#!/usr/bin/env bash
# Starts the Codna local API + MCP server for Mission Platform integration.
# Run once per dev session from the decision-engine directory.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

_capture_env_override() {
  local key="$1"
  local value_var="START_LOCAL_CAPTURED_${key}"
  local present_var="START_LOCAL_CAPTURED_${key}_PRESENT"
  if [ "${!key+x}" = "x" ]; then
    printf -v "$value_var" '%s' "${!key}"
    printf -v "$present_var" '%s' "1"
  else
    printf -v "$present_var" '%s' "0"
  fi
}

_restore_env_override() {
  local key="$1"
  local value_var="START_LOCAL_CAPTURED_${key}"
  local present_var="START_LOCAL_CAPTURED_${key}_PRESENT"
  if [ "${!present_var:-0}" = "1" ]; then
    export "$key=${!value_var}"
  fi
}

for START_LOCAL_OVERRIDE_KEY in \
  ALGENTA_API_KEY \
  DE_API_KEY \
  ALGENTA_API_PORT \
  ALGENTA_MCP_PORT \
  ALGENTA_LLM_PROVIDER_MODELS_JSON \
  OLLAMA_HOST \
  ANTHROPIC_API_KEY \
  OPENAI_API_KEY \
  GOOGLE_API_KEY \
  MISTRAL_API_KEY \
  COHERE_API_KEY \
  GROQ_API_KEY \
  XAI_API_KEY; do
  _capture_env_override "$START_LOCAL_OVERRIDE_KEY"
done
unset START_LOCAL_OVERRIDE_KEY

# Load env unless the caller explicitly wants a clean environment check.
ENV_FILE_PATH="${ALGENTA_ENV_FILE:-${DE_ENV_FILE:-$ROOT/.env}}"
if [ "${ALGENTA_SKIP_ENV_FILE:-0}" != "1" ] && [ -f "$ENV_FILE_PATH" ]; then
  ENV_EXPORTS="$(python3 "$ROOT/scripts/emit_start_local_env_exports.py" "$ENV_FILE_PATH")"
  eval "$ENV_EXPORTS"
fi
for START_LOCAL_OVERRIDE_KEY in \
  ALGENTA_API_KEY \
  DE_API_KEY \
  ALGENTA_API_PORT \
  ALGENTA_MCP_PORT \
  ALGENTA_LLM_PROVIDER_MODELS_JSON \
  OLLAMA_HOST \
  ANTHROPIC_API_KEY \
  OPENAI_API_KEY \
  GOOGLE_API_KEY \
  MISTRAL_API_KEY \
  COHERE_API_KEY \
  GROQ_API_KEY \
  XAI_API_KEY; do
  _restore_env_override "$START_LOCAL_OVERRIDE_KEY"
done
unset START_LOCAL_OVERRIDE_KEY

API_KEY="${ALGENTA_API_KEY:-${DE_API_KEY:-}}"
API_PORT="${ALGENTA_API_PORT:-8000}"
API_BASE_URL="http://localhost:$API_PORT"
API_HEALTH_URL="$API_BASE_URL/v1/health"
MCP_PORT="${ALGENTA_MCP_PORT:-8001}"
MCP_TOOLS_URL="http://localhost:$MCP_PORT/mcp/tools"
MCP_SSE_URL="http://localhost:$MCP_PORT/mcp/sse"
UV_CACHE_DIR="${UV_CACHE_DIR:-/private/tmp/uv-cache}"
START_LOCAL_STATE_DIR="$ROOT/build/start-local"
API_PID_FILE="$START_LOCAL_STATE_DIR/api-$API_PORT.pid"
MCP_PID_FILE="$START_LOCAL_STATE_DIR/mcp-$MCP_PORT.pid"
API_LEASE_FILE="$START_LOCAL_STATE_DIR/api-$API_PORT.lease"
MCP_LEASE_FILE="$START_LOCAL_STATE_DIR/mcp-$MCP_PORT.lease"
API_PID=""
MCP_PID=""
START_LOCAL_READY=0

mkdir -p "$START_LOCAL_STATE_DIR"

_pid_is_running() {
  local pid="${1:-}"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

_prune_stale_state_files() {
  local state_file=""
  for state_file in "$START_LOCAL_STATE_DIR"/api-*.pid "$START_LOCAL_STATE_DIR"/mcp-*.pid; do
    if [ ! -f "$state_file" ]; then
      continue
    fi
    local base_path="${state_file%.pid}"
    local lease_file="${base_path}.lease"
    if [ -f "$lease_file" ]; then
      continue
    fi
    local pid
    pid="$(cat "$state_file" 2>/dev/null || true)"
    if _pid_is_running "$pid"; then
      continue
    fi
    rm -f "$state_file"
    echo "  Cleared orphaned state $(basename "$state_file")"
  done
}

_generate_lease_token() {
  python3 - <<'PY'
import uuid
print(uuid.uuid4().hex)
PY
}

_retire_recorded_process() {
  local pid_file="$1"
  local lease_file="$2"
  local port="$3"
  local label="$4"
  if [ ! -f "$pid_file" ] && [ ! -f "$lease_file" ]; then
    return 0
  fi
  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  rm -f "$lease_file"
  if ! _pid_is_running "$pid"; then
    if ! _port_in_use "$port"; then
      rm -f "$pid_file"
      echo "  Cleared stale $label lease"
      return 0
    fi
  else
    kill "$pid" 2>/dev/null || true
  fi
  for _ in $(seq 1 40); do
    if ! _port_in_use "$port"; then
      rm -f "$pid_file"
      echo "  Stopped previous $label"
      return 0
    fi
    sleep 0.25
  done
  echo "Failed to stop previous $label on port $port." >&2
  return 2
}

_port_in_use() {
  local port="$1"
  lsof -ti "TCP:$port" -sTCP:LISTEN >/dev/null 2>&1
}

_listening_pid() {
  local port="$1"
  lsof -ti "TCP:$port" -sTCP:LISTEN | head -n 1
}

_cleanup_partial_start() {
  if [ "$START_LOCAL_READY" = "1" ]; then
    return 0
  fi
  if _pid_is_running "$MCP_PID"; then
    kill "$MCP_PID" 2>/dev/null || true
  fi
  if _pid_is_running "$API_PID"; then
    kill "$API_PID" 2>/dev/null || true
  fi
  rm -f "$API_PID_FILE" "$MCP_PID_FILE" "$API_LEASE_FILE" "$MCP_LEASE_FILE"
}

trap _cleanup_partial_start EXIT

if [ -z "$API_KEY" ]; then
  echo "ALGENTA_API_KEY or DE_API_KEY must be set before starting the local stack." >&2
  echo "No default API key is bundled with this script." >&2
  exit 2
fi

DEFAULT_LOCAL_PROVIDER_MODELS_JSON="$(python3 "$ROOT/scripts/emit_local_provider_registry.py")"
EFFECTIVE_PROVIDER_MODELS_JSON="${ALGENTA_LLM_PROVIDER_MODELS_JSON:-$DEFAULT_LOCAL_PROVIDER_MODELS_JSON}"
if [ -n "$EFFECTIVE_PROVIDER_MODELS_JSON" ]; then
  if ! PROVIDER_ROUTER_ENABLED="$(
    python3 "$ROOT/scripts/emit_local_provider_registry.py" --has-router "$EFFECTIVE_PROVIDER_MODELS_JSON"
  )"; then
    echo "ALGENTA_LLM_PROVIDER_MODELS_JSON must be a valid provider registry JSON array." >&2
    exit 2
  fi
else
  PROVIDER_ROUTER_ENABLED=0
fi

if ! UV_CACHE_DIR="$UV_CACHE_DIR" uv run --isolated --with-requirements "$ROOT/requirements-mcp.txt" python - <<'PY' >/dev/null 2>&1
from apps.mcp_server.registry import TOOLS
assert TOOLS
PY
then
  echo "Failed to resolve MCP HTTP dependencies from requirements-mcp.txt via isolated uv run." >&2
  exit 2
fi

echo "🚀 Starting Codna local stack..."
_prune_stale_state_files

# Stop prior launcher-managed instances only.
_retire_recorded_process "$API_PID_FILE" "$API_LEASE_FILE" "$API_PORT" "API"
_retire_recorded_process "$MCP_PID_FILE" "$MCP_LEASE_FILE" "$MCP_PORT" "MCP"

if _port_in_use "$API_PORT"; then
  echo "Port $API_PORT is already in use by a non-start-local process." >&2
  echo "Free port $API_PORT or stop the conflicting service before running scripts/start-local.sh." >&2
  exit 2
fi

if _port_in_use "$MCP_PORT"; then
  echo "Port $MCP_PORT is already in use by a non-start-local process." >&2
  echo "Free port $MCP_PORT or stop the conflicting service before running scripts/start-local.sh." >&2
  exit 2
fi

sleep 1

# Start API server (Mojo pool: 15 workers)
cd "$ROOT"
API_LEASE_TOKEN="$(_generate_lease_token)"
printf '%s\n' "$API_LEASE_TOKEN" > "$API_LEASE_FILE"
API_PID="$(
  ALGENTA_LLM_PROVIDER_MODELS_JSON="$EFFECTIVE_PROVIDER_MODELS_JSON" \
    python3 "$ROOT/scripts/detach_process.py" \
      --cwd "$ROOT" \
      --stdout-log /tmp/algenta-api.log \
      -- \
      python3 "$ROOT/scripts/lease_supervisor.py" \
      --cwd "$ROOT" \
      --stdout-log /tmp/algenta-api.log \
      --lease-file "$API_LEASE_FILE" \
      --lease-token "$API_LEASE_TOKEN" \
      -- \
      uv run uvicorn apps.api_server.main:app --port "$API_PORT" --timeout-graceful-shutdown 10
)"
printf '%s\n' "$API_PID" > "$API_PID_FILE"
echo "  API server PID: $API_PID (port $API_PORT)"

# Wait for API to be ready
API_READY=0
for i in $(seq 1 10); do
  if ! kill -0 "$API_PID" 2>/dev/null; then
    echo "API server exited before becoming ready. Check /tmp/algenta-api.log." >&2
    tail -n 20 /tmp/algenta-api.log >&2 || true
    exit 2
  fi
  if curl -sf "$API_HEALTH_URL" > /dev/null 2>&1; then
    API_READY=1
    break
  fi
  sleep 1
done

if [ "$API_READY" != "1" ]; then
  echo "API health endpoint did not become ready at $API_HEALTH_URL." >&2
  tail -n 20 /tmp/algenta-api.log >&2 || true
  kill "$API_PID" 2>/dev/null || true
  exit 2
fi

API_PID="$(_listening_pid "$API_PORT")"
if [ -z "$API_PID" ]; then
  echo "API listener PID could not be resolved on port $API_PORT." >&2
  tail -n 20 /tmp/algenta-api.log >&2 || true
  exit 2
fi
printf '%s\n' "$API_PID" > "$API_PID_FILE"

# Start MCP server (SSE, port 8001)
MCP_LEASE_TOKEN="$(_generate_lease_token)"
printf '%s\n' "$MCP_LEASE_TOKEN" > "$MCP_LEASE_FILE"
MCP_PID="$(
  PYTHONPATH=. \
    UV_CACHE_DIR="$UV_CACHE_DIR" \
    ALGENTA_API_KEY="$API_KEY" \
    DE_API_KEY="$API_KEY" \
    ALGENTA_BASE_URL="$API_BASE_URL" \
    DE_BASE_URL="$API_BASE_URL" \
    ALGENTA_API_URL="$API_BASE_URL" \
    python3 "$ROOT/scripts/detach_process.py" \
      --cwd "$ROOT" \
      --stdout-log /tmp/algenta-mcp.log \
      -- \
      python3 "$ROOT/scripts/lease_supervisor.py" \
      --cwd "$ROOT" \
      --stdout-log /tmp/algenta-mcp.log \
      --lease-file "$MCP_LEASE_FILE" \
      --lease-token "$MCP_LEASE_TOKEN" \
      -- \
      uv run --isolated --with-requirements "$ROOT/requirements-mcp.txt" \
      python -m apps.mcp_server.server --mode http --port "$MCP_PORT"
)"
printf '%s\n' "$MCP_PID" > "$MCP_PID_FILE"
echo "  MCP server PID: $MCP_PID (port $MCP_PORT)"

TOOL_COUNT=""
for i in $(seq 1 10); do
  if ! kill -0 "$MCP_PID" 2>/dev/null; then
    echo "MCP server exited before becoming ready. Check /tmp/algenta-mcp.log." >&2
    tail -n 20 /tmp/algenta-mcp.log >&2 || true
    kill "$API_PID" 2>/dev/null || true
    exit 2
  fi
  TOOL_COUNT="$(
    curl -sf "$MCP_TOOLS_URL" 2>/dev/null | \
      python3 -c 'import json, sys; payload = json.load(sys.stdin); tools = payload.get("tools"); print(len(tools) if isinstance(tools, list) else "")' \
      2>/dev/null || true
  )"
  if [ -n "$TOOL_COUNT" ] && [ "$TOOL_COUNT" -gt 0 ] 2>/dev/null; then
    break
  fi
  sleep 1
done

if [ -z "$TOOL_COUNT" ] || [ "$TOOL_COUNT" -le 0 ] 2>/dev/null; then
  echo "MCP tools endpoint did not become ready at $MCP_TOOLS_URL." >&2
  tail -n 20 /tmp/algenta-mcp.log >&2 || true
  kill "$MCP_PID" 2>/dev/null || true
  kill "$API_PID" 2>/dev/null || true
  exit 2
fi

MCP_PID="$(_listening_pid "$MCP_PORT")"
if [ -z "$MCP_PID" ]; then
  echo "MCP listener PID could not be resolved on port $MCP_PORT." >&2
  tail -n 20 /tmp/algenta-mcp.log >&2 || true
  kill "$API_PID" 2>/dev/null || true
  exit 2
fi
printf '%s\n' "$MCP_PID" > "$MCP_PID_FILE"

# Verify
API_STATUS=$(curl -s "$API_HEALTH_URL" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','?'))" 2>/dev/null || echo "down")

echo ""
echo "✅ Codna stack ready"
echo "   API:  $API_BASE_URL  — status: $API_STATUS (Mojo 15-worker pool)"
echo "   MCP:  $MCP_SSE_URL — $TOOL_COUNT tools"
if [ "$PROVIDER_ROUTER_ENABLED" = "1" ]; then
  echo "   LLM:  provider.router enabled on /v1/models"
else
  echo "   LLM:  provider.router not configured; set ALGENTA_ENV_FILE or ALGENTA_LLM_PROVIDER_MODELS_JSON for provider-backed chat"
fi
echo ""
echo "Mission Platform will auto-connect via ALGENTA_MCP_URL=$MCP_SSE_URL"
START_LOCAL_READY=1
trap - EXIT
