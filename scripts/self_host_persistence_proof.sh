#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infra/docker/docker-compose.selfhosted.yml"
PROJECT_NAME="${ALGENTA_SELF_HOST_PERSISTENCE_PROJECT:-algenta-selfhost-persistence}"
API_PORT="${ALGENTA_SELF_HOST_PERSISTENCE_PORT:-18030}"
POSTGRES_HOST_PORT="${ALGENTA_SELF_HOST_PERSISTENCE_POSTGRES_PORT:-35432}"
REDIS_HOST_PORT="${ALGENTA_SELF_HOST_PERSISTENCE_REDIS_PORT:-36379}"
MINIO_API_HOST_PORT="${ALGENTA_SELF_HOST_PERSISTENCE_MINIO_API_PORT:-39000}"
MINIO_CONSOLE_HOST_PORT="${ALGENTA_SELF_HOST_PERSISTENCE_MINIO_CONSOLE_PORT:-39001}"
IMAGE_REGISTRY="${ALGENTA_SELF_HOST_IMAGE_REGISTRY:-algenta-selfhost}"
IMAGE_TAG="${ALGENTA_SELF_HOST_IMAGE_TAG:-smoke}"
KEEP_STACK="${ALGENTA_SELF_HOST_PERSISTENCE_KEEP_STACK:-0}"
SKIP_BUILD="${ALGENTA_SELF_HOST_PERSISTENCE_SKIP_BUILD:-0}"
RESET_STACK="${ALGENTA_SELF_HOST_PERSISTENCE_RESET_STACK:-1}"
PRUNE_DANGLING="${ALGENTA_SELF_HOST_PERSISTENCE_PRUNE_DANGLING:-1}"
ENV_FILE="$(mktemp "${TMPDIR:-/tmp}/algenta-self-host-persistence.XXXXXX")"
BACKUP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/algenta-self-host-persistence-backups.XXXXXX")"
COMPOSE_CMD=()

load_api_key_contract() {
  # shellcheck source=/dev/null
  source "$ROOT_DIR/scripts/api_key_contract.sh"
}

cleanup() {
  if [ "$KEEP_STACK" != "1" ]; then
    compose_cmd --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down -v --remove-orphans >/dev/null 2>&1 || true
    rm -f "$ENV_FILE"
    rm -rf "$BACKUP_DIR"
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
    echo "Start Docker Desktop, Colima, or your Docker daemon before running the self-host persistence proof." >&2
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
  echo "Install the Docker Compose v2 plugin or the standalone docker-compose CLI before running the self-host persistence proof." >&2
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

wait_for_postgres() {
  local timeout_seconds="${1:-60}"
  local elapsed=0
  while [ "$elapsed" -lt "$timeout_seconds" ]; do
    if compose_cmd --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T postgres \
      pg_isready -U algenta -d algenta >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  echo "Timed out waiting for PostgreSQL" >&2
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
ALGENTA_IMAGE_REGISTRY=${IMAGE_REGISTRY}
ALGENTA_IMAGE_TAG=${IMAGE_TAG}
ALGENTA_SOURCES_DIR=/home/app/.algenta/sources
S3_BUCKET_NAME=algenta-results
S3_ENDPOINT_URL=http://minio:9000
S3_ACCESS_KEY_ID=algenta_minio
S3_SECRET_ACCESS_KEY=algenta_minio_secret
S3_REGION=us-east-1
RESULT_STORAGE_ENABLED=true
WEBHOOK_SIGNING_SECRET=${webhook_secret}
EOF
}

reset_stack() {
  if [ "$RESET_STACK" = "1" ]; then
    compose_cmd --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down -v --remove-orphans >/dev/null 2>&1 || true
  fi
}

run_all_services() {
  compose_cmd --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
}

run_infra_services() {
  compose_cmd --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d postgres redis minio minio-setup
}

run_app_services() {
  compose_cmd --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d api worker
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

run_api_probe() {
  local action="$1"
  local api_key="$2"
  local payload_json="${3:-}"
  ALGENTA_PERSISTENCE_ACTION="$action" \
  API_KEY="$api_key" \
  API_PORT="$API_PORT" \
  PERSISTENCE_PAYLOAD_JSON="$payload_json" \
  python3 <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Callable

base_url = f"http://localhost:{os.environ['API_PORT']}"
api_key = os.environ["API_KEY"]
action = os.environ["ALGENTA_PERSISTENCE_ACTION"]
payload_raw = os.environ.get("PERSISTENCE_PAYLOAD_JSON", "")
payload = json.loads(payload_raw) if payload_raw else {}


def request(method: str, path: str, body: dict[str, object] | None = None) -> object:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base_url + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        detail = raw.decode("utf-8") if raw else exc.reason
        raise SystemExit(f"{method} {path} failed with {exc.code}: {detail}") from exc


def poll_request(
    method: str,
    path: str,
    *,
    body: dict[str, object] | None = None,
    predicate: Callable[[object], bool] | None = None,
    attempts: int = 20,
    interval_seconds: float = 1.0,
) -> object:
    last_payload: object = None
    for _ in range(attempts):
        try:
            last_payload = request(method, path, body)
        except SystemExit:
            last_payload = None
        if predicate is None:
            if last_payload is not None:
                return last_payload
        elif last_payload is not None and predicate(last_payload):
            return last_payload
        import time
        time.sleep(interval_seconds)
    raise SystemExit(f"{method} {path} did not become ready: {last_payload!r}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def extract_query_value(body: object) -> float:
    if isinstance(body, dict):
        result = body.get("result")
        if isinstance(result, dict) and "value" in result:
            return float(result["value"])
        if isinstance(result, (int, float)):
            return float(result)
    raise SystemExit(f"Unexpected query payload: {body!r}")


if action == "seed":
    me = request("GET", "/v1/me")
    require(isinstance(me, dict), f"Unexpected /v1/me payload: {me!r}")
    org = me.get("org") if isinstance(me, dict) else None
    require(isinstance(org, dict) and isinstance(org.get("id"), str), f"Missing org id: {me!r}")
    dataset = request(
        "POST",
        "/v1/data/connect",
        {
            "connection_type": "file_upload",
            "dataset_name": "SelfHostPersistenceDataset",
            "description": "Self-host persistence proof fixture",
            "csv": (
                "product_line,revenue,cost\n"
                "Electronics,100,40\n"
                "Apparel,200,80\n"
                "Home,300,100\n"
            ),
        },
    )
    require(isinstance(dataset, dict), f"Unexpected data connect payload: {dataset!r}")
    dataset_id = dataset.get("dataset_id")
    require(isinstance(dataset_id, str) and dataset_id, f"Missing dataset_id: {dataset!r}")
    query = request(
        "POST",
        "/v1/query",
        {
            "dataset_id": dataset_id,
            "metric_column": "revenue",
            "aggregation": "sum",
        },
    )
    require(extract_query_value(query) == 600.0, f"Unexpected query payload: {query!r}")
    simulate = request(
        "POST",
        "/v1/simulate",
        {
            "mode": "auto",
            "scenario": {
                "name": "Self-host persistence proof",
                "variables": {
                    "revenue": {"low": 80000, "high": 200000},
                    "cost": {"low": 30000, "high": 90000},
                },
                "objective": "maximize_net_value",
            },
            "runs": 1000,
            "seed": 42,
        },
    )
    require(isinstance(simulate, dict), f"Unexpected simulate payload: {simulate!r}")
    run_id = simulate.get("run_id")
    require(isinstance(run_id, str) and run_id, f"Missing run_id: {simulate!r}")
    run = poll_request(
        "GET",
        f"/v1/runs/{run_id}",
        predicate=lambda payload: isinstance(payload, dict) and payload.get("status") == "completed",
    )
    require(isinstance(run, dict) and run.get("status") == "completed", f"Unexpected run payload: {run!r}")
    print(f"ORG_ID={org['id']}")
    print(f"DATASET_ID={dataset_id}")
    print(f"RUN_ID={run_id}")
    raise SystemExit(0)

if action == "rotate":
    expires_at = payload.get("expires_at")
    require(isinstance(expires_at, str) and expires_at, f"Missing expires_at payload: {payload!r}")
    rotated = request(
        "POST",
        "/v1/api-keys",
        {
            "label": "self-host-persistence-runtime",
            "expires_at": expires_at,
        },
    )
    require(isinstance(rotated, dict), f"Unexpected rotate payload: {rotated!r}")
    rotated_key = rotated.get("raw_key") or rotated.get("key")
    rotated_key_id = rotated.get("id")
    rotated_key_prefix = rotated.get("key_prefix")
    returned_expires_at = rotated.get("expires_at")
    require(isinstance(rotated_key, str) and rotated_key, f"Missing rotated key: {rotated!r}")
    require(isinstance(rotated_key_id, str) and rotated_key_id, f"Missing rotated key id: {rotated!r}")
    require(isinstance(rotated_key_prefix, str) and rotated_key_prefix, f"Missing rotated key prefix: {rotated!r}")
    require(
        returned_expires_at == expires_at,
        f"Rotated key expires_at mismatch: expected {expires_at!r}, got {returned_expires_at!r}",
    )
    print(f"ROTATED_API_KEY={rotated_key}")
    print(f"ROTATED_API_KEY_ID={rotated_key_id}")
    print(f"ROTATED_API_KEY_PREFIX={rotated_key_prefix}")
    print(f"ROTATED_EXPIRES_AT={returned_expires_at}")
    raise SystemExit(0)

if action == "verify":
    dataset_id = payload.get("dataset_id")
    run_id = payload.get("run_id")
    stage = payload.get("stage")
    require(isinstance(dataset_id, str) and dataset_id, f"Missing dataset_id payload: {payload!r}")
    require(isinstance(run_id, str) and run_id, f"Missing run_id payload: {payload!r}")
    me = request("GET", "/v1/me")
    require(isinstance(me, dict), f"[{stage}] unexpected /v1/me payload: {me!r}")
    data_list = request("GET", "/v1/data")
    require(isinstance(data_list, dict), f"[{stage}] unexpected /v1/data payload: {data_list!r}")
    datasets = data_list.get("datasets")
    require(isinstance(datasets, list), f"[{stage}] missing datasets: {data_list!r}")
    ids = {str(item.get("dataset_id")) for item in datasets if isinstance(item, dict)}
    require(dataset_id in ids, f"[{stage}] dataset {dataset_id!r} missing from /v1/data")
    query = request(
        "POST",
        "/v1/query",
        {
            "dataset_id": dataset_id,
            "metric_column": "revenue",
            "aggregation": "sum",
        },
    )
    require(extract_query_value(query) == 600.0, f"[{stage}] unexpected query payload: {query!r}")
    run = poll_request(
        "GET",
        f"/v1/runs/{run_id}",
        predicate=lambda response: isinstance(response, dict) and response.get("status") == "completed",
    )
    require(isinstance(run, dict) and run.get("status") == "completed", f"[{stage}] unexpected run payload: {run!r}")
    export_body = poll_request(
        "GET",
        f"/v1/runs/{run_id}/export.json",
        predicate=lambda response: isinstance(response, dict) and response.get("status") == "completed",
    )
    require(isinstance(export_body, dict) and export_body.get("status") == "completed", f"[{stage}] unexpected export payload: {export_body!r}")
    print(f"STAGE={stage}")
    print(f"DATASET_ID={dataset_id}")
    print(f"RUN_ID={run_id}")
    raise SystemExit(0)

raise SystemExit(f"Unknown action: {action}")
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
  ALGENTA_PERSISTENCE_ACTION=verify_revoked_key \
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

run_minio_stat() {
  local org_id="$1"
  local run_id="$2"
  docker run --rm --entrypoint /bin/sh --network "${PROJECT_NAME}_default" minio/mc:latest -c \
    "mc alias set local http://minio:9000 algenta_minio algenta_minio_secret >/dev/null 2>&1 && mc stat local/algenta-results/${org_id}/${run_id}.json >/dev/null"
}

backup_postgres() {
  local output_file="$1"
  compose_cmd --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T postgres \
    pg_dump -U algenta algenta >"$output_file"
}

backup_volume() {
  local volume_name="$1"
  local output_file="$2"
  docker run --rm \
    -v "${volume_name}:/from" \
    -v "${BACKUP_DIR}:/to" \
    alpine sh -c "tar czf /to/$(basename "$output_file") -C /from ."
}

restore_volume() {
  local volume_name="$1"
  local input_file="$2"
  docker run --rm \
    -v "${volume_name}:/to" \
    -v "${BACKUP_DIR}:/from" \
    alpine sh -c "cd /to && tar xzf /from/$(basename "$input_file")"
}

ensure_composed_volume() {
  local volume_name="$1"
  local compose_volume_name="$2"
  if docker volume inspect "$volume_name" >/dev/null 2>&1; then
    return
  fi
  docker volume create \
    --label "com.docker.compose.project=${PROJECT_NAME}" \
    --label "com.docker.compose.volume=${compose_volume_name}" \
    "$volume_name" >/dev/null
}

restore_postgres() {
  local input_file="$1"
  compose_cmd --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T postgres \
    psql -U algenta -d algenta <"$input_file"
}

main() {
  require_cmd docker
  require_cmd curl
  require_cmd python3
  require_docker_daemon
  detect_compose

  local postgres_backup minio_backup sources_backup
  postgres_backup="${BACKUP_DIR}/postgres.sql"
  minio_backup="${BACKUP_DIR}/minio-data.tgz"
  sources_backup="${BACKUP_DIR}/sources-data.tgz"

  echo "==> Writing persistence environment"
  write_env_file

  echo "==> Resetting persistence stack"
  reset_stack

  if [ "$SKIP_BUILD" != "1" ]; then
    echo "==> Pruning dangling Docker images"
    prune_dangling_images
    echo "==> Building self-hosted persistence images"
    build_images
  else
    echo "==> Reusing existing self-hosted release images"
  fi

  echo "==> Starting self-hosted stack"
  run_all_services

  echo "==> Waiting for API health"
  wait_for_health "http://localhost:${API_PORT}/v1/health"

  echo "==> Running migrations"
  run_migrations

  echo "==> Bootstrapping owner and API key"
  local bootstrap_output bootstrap_key bootstrap_key_id api_key api_key_id api_key_prefix api_key_expires_at
  bootstrap_output="$(run_bootstrap)"
  print_bootstrap_output "$bootstrap_output"
  bootstrap_key="$(echo "$bootstrap_output" | sed -n 's/^BOOTSTRAP_API_KEY=//p' | head -1)"
  bootstrap_key_id="$(echo "$bootstrap_output" | sed -n 's/^BOOTSTRAP_API_KEY_ID=//p' | head -1)"
  if [ -z "$bootstrap_key" ] || [ -z "$bootstrap_key_id" ]; then
    echo "Bootstrap output did not include BOOTSTRAP_API_KEY and BOOTSTRAP_API_KEY_ID" >&2
    exit 1
  fi

  echo "==> Rotating bootstrap key"
  local rotation_payload rotation_output
  rotation_payload="$(printf '{"expires_at":"%s"}' "${ALGENTA_SELF_HOST_ROTATED_KEY_EXPIRES_AT:-2028-05-19T00:00:00Z}")"
  rotation_output="$(run_api_probe rotate "$bootstrap_key" "$rotation_payload")"
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

  echo "==> Seeding persistent state"
  local seed_output org_id dataset_id run_id
  seed_output="$(run_api_probe seed "$api_key")"
  echo "$seed_output"
  org_id="$(echo "$seed_output" | sed -n 's/^ORG_ID=//p' | head -1)"
  dataset_id="$(echo "$seed_output" | sed -n 's/^DATASET_ID=//p' | head -1)"
  run_id="$(echo "$seed_output" | sed -n 's/^RUN_ID=//p' | head -1)"
  if [ -z "$org_id" ] || [ -z "$dataset_id" ] || [ -z "$run_id" ]; then
    echo "Seed output did not include org, dataset, and run identifiers." >&2
    exit 1
  fi

  echo "==> Verifying object storage write"
  run_minio_stat "$org_id" "$run_id"

  echo "==> Restarting stack without removing volumes"
  compose_cmd --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down >/dev/null
  run_all_services
  wait_for_health "http://localhost:${API_PORT}/v1/health"

  echo "==> Verifying persistence after restart"
  local verify_payload verify_output
  verify_payload="$(printf '{"stage":"restart","dataset_id":"%s","run_id":"%s"}' "$dataset_id" "$run_id")"
  verify_output="$(run_api_probe verify "$api_key" "$verify_payload")"
  echo "$verify_output"
  run_minio_stat "$org_id" "$run_id"

  echo "==> Backing up PostgreSQL"
  backup_postgres "$postgres_backup"

  echo "==> Backing up object storage"
  backup_volume "${PROJECT_NAME}_minio_data" "$minio_backup"

  echo "==> Backing up local source registry"
  backup_volume "${PROJECT_NAME}_sources_data" "$sources_backup"

  echo "==> Recreating the stack from backups"
  compose_cmd --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down -v --remove-orphans >/dev/null

  echo "==> Restoring object storage and source registry volumes"
  ensure_composed_volume "${PROJECT_NAME}_minio_data" "minio_data"
  ensure_composed_volume "${PROJECT_NAME}_sources_data" "sources_data"
  restore_volume "${PROJECT_NAME}_minio_data" "$minio_backup"
  restore_volume "${PROJECT_NAME}_sources_data" "$sources_backup"

  echo "==> Starting infrastructure services"
  run_infra_services
  wait_for_postgres
  wait_for_health "http://localhost:${MINIO_API_HOST_PORT}/minio/health/live"

  echo "==> Restoring PostgreSQL"
  restore_postgres "$postgres_backup"

  echo "==> Starting API and worker"
  run_app_services
  wait_for_health "http://localhost:${API_PORT}/v1/health"

  echo "==> Verifying persistence after restore"
  verify_payload="$(printf '{"stage":"restore","dataset_id":"%s","run_id":"%s"}' "$dataset_id" "$run_id")"
  verify_output="$(run_api_probe verify "$api_key" "$verify_payload")"
  echo "$verify_output"
  run_minio_stat "$org_id" "$run_id"

  echo "==> Self-hosted persistence proof passed"
  echo "API=http://localhost:${API_PORT}"
  echo "API_KEY=${api_key}"
  echo "API_KEY_ID=${api_key_id}"
  echo "API_KEY_PREFIX=${api_key_prefix}"
  echo "API_KEY_EXPIRES_AT=${api_key_expires_at}"
  if [ "$KEEP_STACK" = "1" ]; then
    echo "Stack left running with project ${PROJECT_NAME}"
    echo "ENV_FILE=${ENV_FILE}"
    echo "BACKUP_DIR=${BACKUP_DIR}"
  fi
}

main "$@"
