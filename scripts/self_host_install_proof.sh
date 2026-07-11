#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALLER="${ALGENTA_SELF_HOST_INSTALLER:-$ROOT_DIR/install.sh}"
COMPOSE_SOURCE_URL="${ALGENTA_SELF_HOST_COMPOSE_URL:-file://$ROOT_DIR/infra/docker/docker-compose.selfhosted.yml}"
PROJECT_NAME="${ALGENTA_SELF_HOST_INSTALL_PROOF_PROJECT:-algenta-install-proof}"
API_PORT="${ALGENTA_SELF_HOST_INSTALL_PROOF_PORT:-18020}"
POSTGRES_HOST_PORT="${ALGENTA_SELF_HOST_INSTALL_PROOF_POSTGRES_PORT:-25432}"
REDIS_HOST_PORT="${ALGENTA_SELF_HOST_INSTALL_PROOF_REDIS_PORT:-26379}"
MINIO_API_HOST_PORT="${ALGENTA_SELF_HOST_INSTALL_PROOF_MINIO_API_PORT:-29000}"
MINIO_CONSOLE_HOST_PORT="${ALGENTA_SELF_HOST_INSTALL_PROOF_MINIO_CONSOLE_PORT:-29001}"
IMAGE_REGISTRY="${ALGENTA_SELF_HOST_IMAGE_REGISTRY:-algenta-selfhost}"
IMAGE_TAG="${ALGENTA_SELF_HOST_IMAGE_TAG:-smoke}"
SKIP_BUILD="${ALGENTA_SELF_HOST_INSTALL_PROOF_SKIP_BUILD:-0}"
KEEP_INSTALL="${ALGENTA_SELF_HOST_INSTALL_PROOF_KEEP_INSTALL:-0}"
RESET_STACK="${ALGENTA_SELF_HOST_INSTALL_PROOF_RESET_STACK:-1}"
PRUNE_DANGLING="${ALGENTA_SELF_HOST_INSTALL_PROOF_PRUNE_DANGLING:-1}"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/algenta-install-proof.XXXXXX")"
INSTALL_DIR="$TMP_ROOT/algenta"
OUTPUT_FILE="$TMP_ROOT/install-output.txt"
COMPOSE_CMD=()

load_api_key_contract() {
  # shellcheck source=/dev/null
  source "$ROOT_DIR/scripts/api_key_contract.sh"
}

cleanup() {
  if [ "$KEEP_INSTALL" = "1" ]; then
    echo "Install proof left at $INSTALL_DIR"
    return
  fi

  if [ -f "$INSTALL_DIR/docker-compose.yml" ] && [ -f "$INSTALL_DIR/.env" ]; then
    COMPOSE_PROJECT_NAME="$PROJECT_NAME" compose_cmd -f "$INSTALL_DIR/docker-compose.yml" --env-file "$INSTALL_DIR/.env" down -v --remove-orphans >/dev/null 2>&1 || true
  fi
  rm -rf "$TMP_ROOT"
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
    echo "Start Docker Desktop, Colima, or your Docker daemon before running the self-host install proof." >&2
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
  echo "Install the Docker Compose v2 plugin or the standalone docker-compose CLI before running the self-host install proof." >&2
  exit 1
}

compose_cmd() {
  "${COMPOSE_CMD[@]}" "$@"
}

build_images() {
  docker build -f "$ROOT_DIR/infra/docker/Dockerfile.api.prod" -t "${IMAGE_REGISTRY}/api:${IMAGE_TAG}" "$ROOT_DIR"
  docker build -f "$ROOT_DIR/infra/docker/Dockerfile.engine.prod" -t "${IMAGE_REGISTRY}/engine:${IMAGE_TAG}" "$ROOT_DIR"
}

prune_dangling_images() {
  if [ "$PRUNE_DANGLING" = "1" ]; then
    docker image prune -f >/dev/null 2>&1 || true
  fi
}

reset_stack() {
  if [ "$RESET_STACK" = "1" ]; then
    # Compose images are fail-closed on ALGENTA_IMAGE_TAG (:?); a teardown does not pull, so a
    # throwaway tag just lets compose interpolate. Subshell keeps the export local.
    ( export ALGENTA_IMAGE_TAG="${ALGENTA_IMAGE_TAG:-reset}"; \
      compose_cmd --project-name "$PROJECT_NAME" -f "$ROOT_DIR/infra/docker/docker-compose.selfhosted.yml" down -v --remove-orphans ) >/dev/null 2>&1 || true
  fi
}

run_installer() {
  COMPOSE_PROJECT_NAME="$PROJECT_NAME" \
  ALGENTA_DIR="$INSTALL_DIR" \
  ALGENTA_API_PORT="$API_PORT" \
  POSTGRES_HOST_PORT="$POSTGRES_HOST_PORT" \
  REDIS_HOST_PORT="$REDIS_HOST_PORT" \
  MINIO_API_HOST_PORT="$MINIO_API_HOST_PORT" \
  MINIO_CONSOLE_HOST_PORT="$MINIO_CONSOLE_HOST_PORT" \
  ALGENTA_VERSION="local-smoke" \
  ALGENTA_IMAGE_REGISTRY="$IMAGE_REGISTRY" \
  ALGENTA_IMAGE_TAG="$IMAGE_TAG" \
  ALGENTA_COMPOSE_URL="$COMPOSE_SOURCE_URL" \
  ALGENTA_SKIP_IMAGE_PULL=1 \
  bash "$INSTALLER" | tee "$OUTPUT_FILE"
}

rotate_api_key() {
  local bootstrap_key="$1"
  local expires_at="${ALGENTA_SELF_HOST_ROTATED_KEY_EXPIRES_AT:-2028-05-19T00:00:00Z}"
  ALGENTA_INSTALL_PROOF_ACTION=rotate_key \
  API_KEY="$bootstrap_key" \
  API_PORT="$API_PORT" \
  ROTATED_KEY_EXPIRES_AT="$expires_at" \
  python3 <<'PY'
import json
import os
import urllib.error
import urllib.request

base_url = f"http://localhost:{os.environ['API_PORT']}"
bootstrap_key = os.environ["API_KEY"]
expires_at = os.environ["ROTATED_KEY_EXPIRES_AT"]
payload = {"label": "self-host-install-proof-runtime", "expires_at": expires_at}

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
  ALGENTA_INSTALL_PROOF_ACTION=verify_revoked_key \
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

verify_rotation_guidance() {
  grep -Fq "curl -X POST http://localhost:${API_PORT}/v1/api-keys" "$OUTPUT_FILE" || {
    echo "Installer output did not contain bootstrap rotation guidance." >&2
    exit 1
  }
  grep -Fq '"expires_at":"2028-05-19T00:00:00Z"' "$OUTPUT_FILE" || {
    echo "Installer output did not contain the bounded-lifetime expires_at example." >&2
    exit 1
  }
  grep -Fq "raw_key" "$OUTPUT_FILE" || {
    echo "Installer output did not describe the replacement raw_key contract." >&2
    exit 1
  }
  grep -Fq "key_prefix" "$OUTPUT_FILE" || {
    echo "Installer output did not describe the replacement key_prefix contract." >&2
    exit 1
  }
}

extract_api_key() {
  API_KEY_TEST_PREFIX="$API_KEY_TEST_PREFIX" python3 - "$OUTPUT_FILE" <<'PY'
from pathlib import Path
import os
import re
import sys

text = Path(sys.argv[1]).read_text(encoding="utf-8")
clean = re.sub(r"\x1b\[[0-9;]*m", "", text)
prefix = re.escape(os.environ["API_KEY_TEST_PREFIX"])
match = re.search(rf"API Key:\s+({prefix}[A-Za-z0-9._\-]+)", clean)
if not match:
    raise SystemExit(1)
print(match.group(1))
PY
}

extract_bootstrap_credentials() {
  API_KEY_TEST_PREFIX="$API_KEY_TEST_PREFIX" python3 - "$OUTPUT_FILE" <<'PY'
from pathlib import Path
import os
import re
import sys

text = Path(sys.argv[1]).read_text(encoding="utf-8")
clean = re.sub(r"\x1b\[[0-9;]*m", "", text)
prefix = re.escape(os.environ["API_KEY_TEST_PREFIX"])

patterns = {
    "API_KEY": rf"API Key:\s+({prefix}[A-Za-z0-9._\-]+)",
    "BOOTSTRAP_KEY_ID": r"Bootstrap key id:\s+([^\s]+)",
    "BOOTSTRAP_EMAIL": r"Bootstrap user:\s+([^\s]+)",
    "BOOTSTRAP_PASSWORD": r"Bootstrap password:\s+([^\s]+)",
}

values = {}
for key, pattern in patterns.items():
    match = re.search(pattern, clean)
    if not match:
        raise SystemExit(1)
    values[key] = match.group(1)

for key in ("API_KEY", "BOOTSTRAP_KEY_ID", "BOOTSTRAP_EMAIL", "BOOTSTRAP_PASSWORD"):
    print(f"{key}={values[key]}")
PY
}

run_health_check() {
  curl -sf "http://localhost:${API_PORT}/v1/health"
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
            "name": "Self-hosted installer proof",
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

  echo "==> Resetting installer proof stack"
  reset_stack

  if [ "$SKIP_BUILD" != "1" ]; then
    echo "==> Pruning dangling Docker images"
    prune_dangling_images
    echo "==> Building self-hosted release images"
    build_images
  else
    echo "==> Reusing existing self-hosted release images"
  fi

  echo "==> Running fresh installer proof"
  run_installer

  echo "==> Verifying bootstrap rotation guidance"
  verify_rotation_guidance

  local bootstrap_key
  bootstrap_key="$(extract_api_key)"
  if [ -z "$bootstrap_key" ]; then
    echo "Installer output did not contain a bootstrap API key." >&2
    exit 1
  fi

  local credentials bootstrap_key_id bootstrap_email bootstrap_password
  credentials="$(extract_bootstrap_credentials)"
  bootstrap_key_id="$(echo "$credentials" | sed -n 's/^BOOTSTRAP_KEY_ID=//p' | head -1)"
  bootstrap_email="$(echo "$credentials" | sed -n 's/^BOOTSTRAP_EMAIL=//p' | head -1)"
  bootstrap_password="$(echo "$credentials" | sed -n 's/^BOOTSTRAP_PASSWORD=//p' | head -1)"
  if [ -z "$bootstrap_key_id" ] || [ -z "$bootstrap_email" ] || [ -z "$bootstrap_password" ]; then
    echo "Installer output did not contain bootstrap key id and credentials." >&2
    exit 1
  fi

  echo "==> Rotating bootstrap key"
  local rotation_output api_key api_key_id api_key_prefix api_key_expires_at
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

  echo "==> Verifying health"
  local health
  health="$(run_health_check)"
  echo "$health"

  echo "==> Verifying first decision"
  local response
  response="$(run_first_decision "$api_key")"
  echo "$response"

  echo "==> Verifying async job lifecycle"
  local job_response
  job_response="$(run_async_job "$api_key")"
  echo "$job_response"

  echo "==> Verifying endpoint matrix"
  local matrix_response
  if ! matrix_response="$(
    python3 "$ROOT_DIR/scripts/self_host_endpoint_matrix.py" \
      --base-url "http://localhost:${API_PORT}" \
      --api-key "$api_key" \
      --bootstrap-email "$bootstrap_email" \
      --bootstrap-password "$bootstrap_password"
  )"; then
    echo "$matrix_response"
    exit 1
  fi
  echo "$matrix_response"

  echo "==> Self-host install proof passed"
  echo "INSTALL_DIR=${INSTALL_DIR}"
  echo "INSTALL_OUTPUT_FILE=${OUTPUT_FILE}"
  echo "API_KEY_ID=${api_key_id}"
  echo "API_KEY_PREFIX=${api_key_prefix}"
  echo "API_KEY_EXPIRES_AT=${api_key_expires_at}"
  if [ "$KEEP_INSTALL" = "1" ]; then
    echo "Stack left running with project ${PROJECT_NAME}"
  fi
}

main "$@"
