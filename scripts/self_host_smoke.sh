#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infra/docker/docker-compose.selfhosted.yml"
PROJECT_NAME="${ALGENTA_SELF_HOST_PROJECT:-algenta-selfhost-smoke}"
API_PORT="${ALGENTA_SELF_HOST_SMOKE_PORT:-18000}"
POSTGRES_HOST_PORT="${ALGENTA_SELF_HOST_SMOKE_POSTGRES_PORT:-15432}"
REDIS_HOST_PORT="${ALGENTA_SELF_HOST_SMOKE_REDIS_PORT:-16379}"
MINIO_API_HOST_PORT="${ALGENTA_SELF_HOST_SMOKE_MINIO_API_PORT:-19000}"
MINIO_CONSOLE_HOST_PORT="${ALGENTA_SELF_HOST_SMOKE_MINIO_CONSOLE_PORT:-19001}"
IMAGE_REGISTRY="${ALGENTA_SELF_HOST_IMAGE_REGISTRY:-algenta-selfhost}"
IMAGE_TAG="${ALGENTA_SELF_HOST_IMAGE_TAG:-smoke}"
KEEP_STACK="${ALGENTA_SELF_HOST_KEEP_STACK:-0}"
SKIP_BUILD="${ALGENTA_SELF_HOST_SMOKE_SKIP_BUILD:-0}"
RESET_STACK="${ALGENTA_SELF_HOST_RESET_STACK:-1}"
PRUNE_DANGLING="${ALGENTA_SELF_HOST_PRUNE_DANGLING:-1}"
ENV_FILE="$(mktemp "${TMPDIR:-/tmp}/algenta-self-host-smoke.XXXXXX")"
COMPOSE_CMD=()

load_api_key_contract() {
  # shellcheck source=/dev/null
  source "$ROOT_DIR/scripts/api_key_contract.sh"
}

cleanup() {
  if [ "$KEEP_STACK" != "1" ]; then
    compose_cmd --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down -v --remove-orphans >/dev/null 2>&1 || true
    if [ -f "$ENV_FILE" ]; then
      rm -f "$ENV_FILE"
    fi
  fi
}

trap cleanup EXIT

load_api_key_contract

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_docker_daemon() {
  docker info >/dev/null 2>&1 || {
    echo "Docker daemon is not running or not reachable." >&2
    echo "Start Docker Desktop, Colima, or your Docker daemon before running the self-host smoke." >&2
    exit 1
  }
}

detect_compose() {
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD=("docker" "compose")
    return
  fi
  if command -v docker-compose >/dev/null 2>&1 && docker-compose version >/dev/null 2>&1; then
    COMPOSE_CMD=("docker-compose")
    return
  fi
  echo "Docker Compose is not installed or not reachable." >&2
  echo "Install the Docker Compose v2 plugin or the standalone docker-compose CLI before running the self-host smoke." >&2
  exit 1
}

compose_cmd() {
  "${COMPOSE_CMD[@]}" "$@"
}

wait_for_health() {
  local url="$1"
  local timeout_seconds="${2:-90}"
  local elapsed=0
  while [ "$elapsed" -lt "$timeout_seconds" ]; do
    if curl -sf "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  echo "Timed out waiting for $url" >&2
  return 1
}

build_images() {
  docker build -f "$ROOT_DIR/infra/docker/Dockerfile.api.prod" -t "${IMAGE_REGISTRY}/api:${IMAGE_TAG}" "$ROOT_DIR"
  docker build -f "$ROOT_DIR/infra/docker/Dockerfile.worker.prod" -t "${IMAGE_REGISTRY}/worker:${IMAGE_TAG}" "$ROOT_DIR"
}

prune_dangling_images() {
  if [ "$PRUNE_DANGLING" = "1" ]; then
    docker image prune -f >/dev/null 2>&1 || true
  fi
}

write_env_file() {
  local jwt_secret webhook_secret
  jwt_secret="$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 64 2>/dev/null || openssl rand -hex 32)"
  webhook_secret="$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32 2>/dev/null || openssl rand -hex 16)"

  cat >"$ENV_FILE" <<EOF
API_ENV=production
LOG_LEVEL=info
CORS_ORIGINS=http://localhost:${API_PORT}
DATABASE_URL=postgresql+asyncpg://algenta:algenta_secret@postgres:5432/algenta
DATABASE_URL_SYNC=postgresql://algenta:algenta_secret@postgres:5432/algenta
POSTGRES_DB=algenta
POSTGRES_USER=algenta
POSTGRES_PASSWORD=algenta_secret
REDIS_URL=redis://redis:6379/0
JWT_SECRET=${jwt_secret}
API_KEY_PREFIX=${API_KEY_PREFIX}
API_KEY_TEST_PREFIX=${API_KEY_TEST_PREFIX}
API_PORT=${API_PORT}
POSTGRES_HOST_PORT=${POSTGRES_HOST_PORT}
REDIS_HOST_PORT=${REDIS_HOST_PORT}
MINIO_API_HOST_PORT=${MINIO_API_HOST_PORT}
MINIO_CONSOLE_HOST_PORT=${MINIO_CONSOLE_HOST_PORT}
MOJO_BINARY_PATH=/app/mojo_build/simulate
MOJO_TIMEOUT_SECONDS=30
MOJO_MAX_CONCURRENT=4
RUNTIME_FALLBACK_MODE=allow
ALGENTA_DEPLOYMENT_MODE=self_hosted
ALGENTA_DISABLE_CLOUD=1
ALGENTA_DISABLE_TELEMETRY=1
ALGENTA_TELEMETRY_MODE=local_audit
ALGENTA_METERING_MODE=local_audit
ALGENTA_REQUIRE_LOCAL_LICENSE=0
ALGENTA_CONTROL_PLANE_URL=
ALGENTA_ALLOW_OUTBOUND_NETWORK=0
ALGENTA_EGRESS_ALLOWLIST=minio:9000
ALGENTA_LOCAL_LICENSE_PUBLIC_KEY_FILE=
ALGENTA_API_PUBLIC_BASE_URL=http://localhost:${API_PORT}
ALGENTA_APP_BASE_URL=
ALGENTA_IMAGE_REGISTRY=${IMAGE_REGISTRY}
ALGENTA_IMAGE_TAG=${IMAGE_TAG}
S3_BUCKET_NAME=algenta-results
S3_ENDPOINT_URL=http://minio:9000
S3_ACCESS_KEY_ID=algenta_minio
S3_SECRET_ACCESS_KEY=algenta_minio_secret
S3_REGION=us-east-1
RESULT_STORAGE_ENABLED=true
WEBHOOK_SIGNING_SECRET=${webhook_secret}
EOF
}

run_compose() {
  compose_cmd --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
}

reset_stack() {
  if [ "$RESET_STACK" = "1" ]; then
    compose_cmd --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down -v --remove-orphans >/dev/null 2>&1 || true
  fi
}

run_migrations() {
  compose_cmd --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T api \
    python -m alembic -c apps/api_server/alembic.ini upgrade head
}

run_bootstrap() {
  compose_cmd --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T api \
    python scripts/bootstrap_self_host.py
}

print_bootstrap_output() {
  printf '%s\n' "$1" | sed \
    -e 's/^BOOTSTRAP_API_KEY=.*/BOOTSTRAP_API_KEY=<redacted>/' \
    -e 's/^BOOTSTRAP_USER_PASSWORD=.*/BOOTSTRAP_USER_PASSWORD=<redacted>/'
}

rotate_api_key() {
  local bootstrap_key="$1"
  local expires_at="${ALGENTA_SELF_HOST_ROTATED_KEY_EXPIRES_AT:-2028-05-19T00:00:00Z}"
  ALGENTA_SELF_HOST_SMOKE_ACTION=rotate_key \
  API_KEY="$bootstrap_key" \
  API_PORT="$API_PORT" \
  ROTATED_KEY_EXPIRES_AT="$expires_at" \
  python3 <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

base_url = f"http://localhost:{os.environ['API_PORT']}"
bootstrap_key = os.environ["API_KEY"]
expires_at = os.environ["ROTATED_KEY_EXPIRES_AT"]
payload = {"label": "self-host-smoke-runtime", "expires_at": expires_at}

req = urllib.request.Request(
    base_url + "/v1/api-keys",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {bootstrap_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()
except urllib.error.HTTPError as exc:
    raw = exc.read()
    detail = raw.decode("utf-8") if raw else exc.reason
    raise SystemExit(f"POST /v1/api-keys failed with {exc.code}: {detail}") from exc

body = json.loads(raw) if raw else None
if not isinstance(body, dict):
    raise SystemExit(f"Unexpected API key rotation payload: {body!r}")

rotated_key = body.get("raw_key") or body.get("key")
rotated_key_id = body.get("id")
rotated_key_prefix = body.get("key_prefix")
returned_expires_at = body.get("expires_at")
if not isinstance(rotated_key, str) or not rotated_key:
    raise SystemExit(f"Rotation response did not include key: {body!r}")
if not isinstance(rotated_key_id, str) or not rotated_key_id:
    raise SystemExit(f"Rotation response did not include id: {body!r}")
if not isinstance(rotated_key_prefix, str) or not rotated_key_prefix:
    raise SystemExit(f"Rotation response did not include key_prefix: {body!r}")
if returned_expires_at != expires_at:
    raise SystemExit(
        f"Rotation response expires_at mismatch: expected {expires_at!r}, got {returned_expires_at!r}"
    )

print(f"ROTATED_API_KEY={rotated_key}")
print(f"ROTATED_API_KEY_ID={rotated_key_id}")
print(f"ROTATED_API_KEY_PREFIX={rotated_key_prefix}")
print(f"ROTATED_EXPIRES_AT={returned_expires_at}")
PY
}

revoke_api_key() {
  local operator_key="$1"
  local key_id="$2"
  curl -sf -X DELETE "http://localhost:${API_PORT}/v1/api-keys/${key_id}" \
    -H "Authorization: Bearer ${operator_key}" \
    -H "Accept: application/json" \
    >/dev/null
}

verify_api_key_rejected() {
  local candidate_key="$1"
  ALGENTA_SELF_HOST_SMOKE_ACTION=verify_revoked_key \
  API_KEY="$candidate_key" \
  API_PORT="$API_PORT" \
  python3 <<'PY'
import json
import os
import urllib.error
import urllib.request

base_url = f"http://localhost:{os.environ['API_PORT']}"
candidate_key = os.environ["API_KEY"]
req = urllib.request.Request(
    base_url + "/v1/me",
    headers={
        "X-API-Key": candidate_key,
        "Accept": "application/json",
    },
    method="GET",
)

try:
    with urllib.request.urlopen(req, timeout=20):
        raise SystemExit("Revoked bootstrap key still authenticated successfully.")
except urllib.error.HTTPError as exc:
    raw = exc.read()
    if exc.code != 401:
        detail = raw.decode("utf-8") if raw else exc.reason
        raise SystemExit(f"Revoked bootstrap key returned {exc.code}: {detail}") from exc
    body = json.loads(raw) if raw else {}
    error = body.get("error") or body.get("detail", {}).get("error")
    if not (isinstance(error, dict) and error.get("code") == "invalid_api_key"):
        raise SystemExit(f"Unexpected revoked bootstrap key payload: {body!r}")
PY
}

run_first_decision() {
  local api_key="$1"
  curl -sf -X POST "http://localhost:${API_PORT}/v1/simulate" \
    -H "Authorization: Bearer ${api_key}" \
    -H "Content-Type: application/json" \
    -d '{
      "mode": "auto",
      "scenario": {
        "variables": {
          "revenue": { "low": 80000, "high": 200000 },
          "cost": { "low": 30000, "high": 90000 }
        },
        "objective": "maximize_net_value"
      },
      "runs": 10000,
      "seed": 42
    }'
}

run_async_job() {
  local api_key="$1"
  API_KEY="${api_key}" API_PORT="${API_PORT}" python3 <<'PY'
import json
import os
import sys
import time
import urllib.error
import urllib.request

base_url = f"http://localhost:{os.environ['API_PORT']}"
api_key = os.environ["API_KEY"]
payload = {
    "request": {
        "mode": "auto",
        "scenario": {
            "name": "Self-hosted async smoke",
            "variables": {
                "revenue": {"low": 80000, "high": 200000},
                "cost": {"low": 40000, "high": 90000},
            },
            "objective": "maximize_net_value",
        },
        "runs": 1000,
        "seed": 42,
    }
}


def request(method: str, path: str, body: dict[str, object] | None = None) -> tuple[int, object]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    req = urllib.request.Request(base_url + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        body_data = json.loads(raw) if raw else None
        return exc.code, body_data


status, submit_body = request("POST", "/v1/jobs", payload)
print(json.dumps({"submit_status": status, "submit_body": submit_body}, indent=2))
if status != 202 or not isinstance(submit_body, dict) or "job_id" not in submit_body:
    sys.exit(1)

job_id = submit_body["job_id"]
terminal_states = {"completed", "failed", "cancelled", "expired"}

for _ in range(60):
    time.sleep(1)
    poll_status, poll_body = request("GET", f"/v1/jobs/{job_id}")
    if poll_status != 200 or not isinstance(poll_body, dict):
        print(json.dumps({"poll_status": poll_status, "poll_body": poll_body}, indent=2))
        sys.exit(1)
    if poll_body.get("status") in terminal_states:
        print(json.dumps({"final_poll_status": poll_status, "final_poll_body": poll_body}, indent=2))
        result_status, result_body = request("GET", f"/v1/jobs/{job_id}/result")
        print(json.dumps({"result_status": result_status, "result_body": result_body}, indent=2))
        if poll_body.get("status") != "completed":
            sys.exit(2)
        if result_status != 200 or not isinstance(result_body, dict):
            sys.exit(3)
        nested = result_body.get("result") if isinstance(result_body, dict) else None
        if not isinstance(nested, dict) or nested.get("status") != "completed":
            sys.exit(4)
        sys.exit(0)

print(json.dumps({"error": "async_job_timeout", "job_id": job_id}, indent=2))
sys.exit(5)
PY
}

main() {
  require_cmd docker
  require_cmd curl
  require_cmd python3
  require_docker_daemon
  detect_compose

  echo "==> Writing smoke environment"
  write_env_file

  echo "==> Resetting smoke stack"
  reset_stack

  if [ "$SKIP_BUILD" != "1" ]; then
    echo "==> Pruning dangling Docker images"
    prune_dangling_images
    echo "==> Building self-hosted smoke images"
    build_images
  else
    echo "==> Reusing existing self-hosted smoke images"
  fi

  echo "==> Starting self-hosted stack"
  run_compose

  echo "==> Waiting for API health"
  wait_for_health "http://localhost:${API_PORT}/v1/health"

  echo "==> Running migrations"
  run_migrations

  echo "==> Bootstrapping owner and API key"
  local bootstrap_output bootstrap_key bootstrap_key_id api_key api_key_id api_key_prefix rotation_output api_key_expires_at
  bootstrap_output="$(run_bootstrap)"
  print_bootstrap_output "$bootstrap_output"
  bootstrap_key="$(echo "$bootstrap_output" | sed -n 's/^BOOTSTRAP_API_KEY=//p' | head -1)"
  bootstrap_key_id="$(echo "$bootstrap_output" | sed -n 's/^BOOTSTRAP_API_KEY_ID=//p' | head -1)"
  if [ -z "$bootstrap_key" ] || [ -z "$bootstrap_key_id" ]; then
    echo "Bootstrap output did not include BOOTSTRAP_API_KEY and BOOTSTRAP_API_KEY_ID" >&2
    exit 1
  fi

  echo "==> Rotating bootstrap key"
  rotation_output="$(rotate_api_key "$bootstrap_key")"
  echo "$rotation_output"
  api_key="$(echo "$rotation_output" | sed -n 's/^ROTATED_API_KEY=//p' | head -1)"
  api_key_id="$(echo "$rotation_output" | sed -n 's/^ROTATED_API_KEY_ID=//p' | head -1)"
  api_key_prefix="$(echo "$rotation_output" | sed -n 's/^ROTATED_API_KEY_PREFIX=//p' | head -1)"
  api_key_expires_at="$(echo "$rotation_output" | sed -n 's/^ROTATED_EXPIRES_AT=//p' | head -1)"
  if [ -z "$api_key" ] || [ -z "$api_key_id" ] || [ -z "$api_key_prefix" ] || [ -z "$api_key_expires_at" ]; then
    echo "Rotation output did not include replacement key, id, prefix, and expiry." >&2
    exit 1
  fi

  echo "==> Revoking bootstrap key"
  revoke_api_key "$api_key" "$bootstrap_key_id"

  echo "==> Verifying revoked bootstrap key is rejected"
  verify_api_key_rejected "$bootstrap_key"

  echo "==> Running first decision"
  local response
  response="$(run_first_decision "$api_key")"
  echo "$response"

  if ! echo "$response" | grep -q '"status"'; then
    echo "First decision response did not include status" >&2
    exit 1
  fi
  if ! echo "$response" | grep -q '"recommended_action"'; then
    echo "First decision response did not include recommended_action" >&2
    exit 1
  fi

  echo "==> Running async job"
  local job_response
  job_response="$(run_async_job "$api_key")"
  echo "$job_response"

  echo "==> Self-hosted smoke passed"
  echo "API=http://localhost:${API_PORT}"
  echo "API_KEY=${api_key}"
  echo "API_KEY_ID=${api_key_id}"
  echo "API_KEY_PREFIX=${api_key_prefix}"
  echo "API_KEY_EXPIRES_AT=${api_key_expires_at}"
  if [ "$KEEP_STACK" = "1" ]; then
    echo "Stack left running with project ${PROJECT_NAME}"
    echo "ENV_FILE=${ENV_FILE}"
  fi
}

main "$@"
