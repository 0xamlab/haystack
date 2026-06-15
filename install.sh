#!/bin/bash
# Codna Decision Engine — one-line self-hosted installer
# Usage: curl -fsSL https://codna.ai/install.sh | bash
# Or:    curl -fsSL https://raw.githubusercontent.com/algenta/decision-engine/main/install.sh | bash

set -euo pipefail

REPO="algenta/decision-engine"
INSTALL_DIR="${ALGENTA_DIR:-$HOME/.algenta}"
API_PORT="${ALGENTA_API_PORT:-8000}"
DOCS_URL="${ALGENTA_DOCS_URL:-https://docs.codna.ai/self-hosting}"
IMAGE_REGISTRY="${ALGENTA_IMAGE_REGISTRY:-ghcr.io/algenta/decision-engine}"
RELEASE_REF="${ALGENTA_VERSION:-}"
IMAGE_TAG="${ALGENTA_IMAGE_TAG:-}"
COMPOSE_BUNDLE_URL="${ALGENTA_COMPOSE_URL:-}"
SKIP_IMAGE_PULL="${ALGENTA_SKIP_IMAGE_PULL:-0}"
COMPOSE_CMD=()
COMPOSE_DISPLAY=""

# ── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m' # No Color

print_logo() {
  echo -e "${BLUE}"
  echo '   _    _               _       '
  echo '  /_\  | |  __ _  ___ | | _  _ '
  echo ' / _ \ | | / _` |/ -_)| || || |'
  echo '/_/ \_\|_| \__, |\___||_| \_,_|'
  echo '           |___/               '
  echo -e "${NC}"
  echo -e "${BOLD}Codna Decision Engine — Self-Hosted Service Installer${NC}"
  echo ""
}

check_requirements() {
  echo -e "${BLUE}Checking requirements...${NC}"
  local missing=()

  command -v docker >/dev/null 2>&1 || missing+=("docker")
  command -v curl >/dev/null 2>&1 || command -v wget >/dev/null 2>&1 || missing+=("curl-or-wget")

  if [ ${#missing[@]} -gt 0 ]; then
    echo -e "${RED}Missing requirements: ${missing[*]}${NC}"
    echo ""
    echo "Install Docker Desktop from: https://docs.docker.com/get-docker/"
    exit 1
  fi

  if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD=("docker" "compose")
    COMPOSE_DISPLAY="docker compose"
  elif command -v docker-compose >/dev/null 2>&1 && docker-compose version >/dev/null 2>&1; then
    COMPOSE_CMD=("docker-compose")
    COMPOSE_DISPLAY="docker-compose"
  else
    echo -e "${RED}Missing requirement: Docker Compose${NC}"
    echo ""
    echo "Install either the Docker Compose v2 plugin or the standalone docker-compose CLI."
    exit 1
  fi

  echo -e "${GREEN}✓ Docker and Docker Compose found (${COMPOSE_DISPLAY})${NC}"

  if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}Docker daemon is not running or not reachable.${NC}"
    echo "Start Docker Desktop, Colima, or your Docker daemon before running the installer."
    exit 1
  fi

  echo -e "${GREEN}✓ Docker daemon is reachable${NC}"
}

compose() {
  "${COMPOSE_CMD[@]}" "$@"
}

detect_os() {
  case "$(uname -s)" in
    Darwin*) OS="mac" ;;
    Linux*)  OS="linux" ;;
    *)       OS="unknown" ;;
  esac
}

fetch_text() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url"
    return
  fi
  if command -v wget >/dev/null 2>&1; then
    wget -qO- "$url"
    return
  fi
  return 1
}

http_ok() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -sf "$url" >/dev/null 2>&1
    return $?
  fi
  if command -v wget >/dev/null 2>&1; then
    wget -qO- "$url" >/dev/null 2>&1
    return $?
  fi
  return 1
}

is_truthy() {
  local lowered
  lowered="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$lowered" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

is_git_sha() {
  local value="$1"
  [[ "$value" =~ ^[a-f0-9]{7,40}$ ]]
}

resolve_release_ref() {
  if [ -n "$RELEASE_REF" ]; then
    if [ -z "$IMAGE_TAG" ]; then
      if is_git_sha "$RELEASE_REF"; then
        IMAGE_TAG="git-${RELEASE_REF:0:7}"
      else
        IMAGE_TAG="$RELEASE_REF"
      fi
    fi
    echo -e "${GREEN}✓ Using requested release ref ${RELEASE_REF}${NC}"
    echo -e "${GREEN}✓ Using pinned image tag ${IMAGE_TAG}${NC}"
    return
  fi

  local latest_sha=""
  latest_sha=$(fetch_text "https://api.github.com/repos/$REPO/commits/main" 2>/dev/null | \
    grep -m1 '"sha"' | sed -E 's/.*"sha": "([a-f0-9]+)".*/\1/' || true)

  if [ -n "$latest_sha" ]; then
    RELEASE_REF="$latest_sha"
    if [ -z "$IMAGE_TAG" ]; then
      IMAGE_TAG="git-${latest_sha:0:7}"
    fi
    echo -e "${GREEN}✓ Resolved release ref ${RELEASE_REF}${NC}"
    echo -e "${GREEN}✓ Using pinned image tag ${IMAGE_TAG}${NC}"
    return
  fi

  echo -e "${RED}Could not resolve a pinned release ref from GitHub.${NC}"
  echo "Set ALGENTA_VERSION and, if needed, ALGENTA_IMAGE_TAG explicitly before retrying."
  exit 1
}

download_release() {
  echo -e "${BLUE}Downloading Codna Decision Engine...${NC}"

  mkdir -p "$INSTALL_DIR"
  cd "$INSTALL_DIR"

  local compose_url="${COMPOSE_BUNDLE_URL:-https://raw.githubusercontent.com/$REPO/$RELEASE_REF/infra/docker/docker-compose.selfhosted.yml}"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$compose_url" -o docker-compose.yml
  elif command -v wget >/dev/null 2>&1; then
    wget -qO docker-compose.yml "$compose_url"
  fi

  echo -e "${GREEN}✓ Downloaded${NC}"
}

generate_env() {
  echo -e "${BLUE}Generating configuration...${NC}"

  # Auto-generated secrets that MUST stay stable across restarts. Compose reads ${INSTALL_DIR}/.env
  # (not the operator's shell), so anything not persisted here is lost on the next `compose up`.
  #  - ALGENTA_CONFIG_ENCRYPTION_KEY (64-hex) encrypts per-tenant provider keys at rest; rotating or
  #    losing it makes every stored tenant key undecryptable (silent fail-closed) — generate once, keep it.
  #  - AGENT_CORE_AUTH_TOKEN is the shared api/worker -> sidecar bearer; without it the sidecar's
  #    inbound auth is open by default.
  # openssl is primary (clean + present on essentially every docker host); the fallback reads a FINITE
  # byte count from /dev/urandom so it can't SIGPIPE-trip `set -o pipefail` and abort the install.
  local config_encryption_key agent_core_token
  config_encryption_key=$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')
  agent_core_token=$(openssl rand -hex 24 2>/dev/null || head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')

  if [ ! -f ".env" ]; then
    # Generate secrets
    JWT_SECRET=$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 64 2>/dev/null || openssl rand -hex 32)
    WEBHOOK_SECRET=$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32 2>/dev/null || openssl rand -hex 16)

    cat > .env << EOF
# Codna Decision Engine — Self-Hosted Configuration
# Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")

# ── Application ──────────────────────────────────────────────────────────────
API_ENV=production
LOG_LEVEL=info
CORS_ORIGINS=http://localhost:3000,http://localhost:${API_PORT}

# ── Database (managed by Docker Compose) ─────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://algenta:algenta_secret@postgres:5432/algenta
DATABASE_URL_SYNC=postgresql://algenta:algenta_secret@postgres:5432/algenta
POSTGRES_DB=algenta
POSTGRES_USER=algenta
POSTGRES_PASSWORD=algenta_secret

# ── Redis (managed by Docker Compose) ────────────────────────────────────────
REDIS_URL=redis://redis:6379/0

# ── Auth ─────────────────────────────────────────────────────────────────────
JWT_SECRET=${JWT_SECRET}
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080
API_KEY_PREFIX=de_live_
API_KEY_TEST_PREFIX=de_test_

# ── Agent runtime + per-tenant key encryption ────────────────────────────────
# Generated once; keep STABLE across restarts. Rotating/losing ALGENTA_CONFIG_ENCRYPTION_KEY makes
# every stored per-tenant provider key undecryptable. AGENT_CORE_AUTH_TOKEN gates api/worker → sidecar.
ALGENTA_CONFIG_ENCRYPTION_KEY=${config_encryption_key}
AGENT_CORE_AUTH_TOKEN=${agent_core_token}
AGENT_CORE_REQUIRE_AUTH=1
ALGENTA_AGENT_CORE_URL=http://sidecar:8787
# Loopback URL the agent head dials to call back into /v1 (docker-network DNS, NOT localhost). Set
# (non-empty) so the engine-callback block is actually attached to the agent task spec.
ALGENTA_ENGINE_URL=http://api:8000
# Engine-callback key the agent head presents (with ALGENTA_ENGINE_URL above) to call back into /v1
# during a run. Org-scoped + owner-attributed — protect this file. The installer fills it from the
# bootstrap step (the dedicated, long-lived "Engine Callback Key").
ALGENTA_ENGINE_API_KEY=
ALGENTA_API_KEY=
# LLM provider key for the agent — required for the agentic repository / GitHub flow. Set yours.
ANTHROPIC_API_KEY=

# ── Ports ────────────────────────────────────────────────────────────────────
API_PORT=${API_PORT}
POSTGRES_HOST_PORT=${POSTGRES_HOST_PORT:-5432}
REDIS_HOST_PORT=${REDIS_HOST_PORT:-6379}
MINIO_API_HOST_PORT=${MINIO_API_HOST_PORT:-9000}
MINIO_CONSOLE_HOST_PORT=${MINIO_CONSOLE_HOST_PORT:-9001}

# ── Engine ───────────────────────────────────────────────────────────────────
MOJO_BINARY_PATH=/app/mojo_build/simulate
MOJO_TIMEOUT_SECONDS=30
MOJO_MAX_CONCURRENT=4
RUNTIME_FALLBACK_MODE=allow
ALGENTA_SOURCES_DIR=/home/app/.algenta/sources

# ── Privacy / Deployment ────────────────────────────────────────────────────
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

# ── Release Artifacts ────────────────────────────────────────────────────────
ALGENTA_IMAGE_REGISTRY=${IMAGE_REGISTRY}
ALGENTA_IMAGE_TAG=${IMAGE_TAG}

# ── Object Storage (MinIO — managed by Docker Compose) ───────────────────────
S3_BUCKET_NAME=algenta-results
S3_ENDPOINT_URL=http://minio:9000
S3_ACCESS_KEY_ID=algenta_minio
S3_SECRET_ACCESS_KEY=algenta_minio_secret
S3_REGION=us-east-1
RESULT_STORAGE_ENABLED=true

# ── Webhooks ─────────────────────────────────────────────────────────────────
WEBHOOK_SIGNING_SECRET=${WEBHOOK_SECRET}

# ── Billing (optional — leave blank to disable) ───────────────────────────────
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=

# ── Email (optional — leave blank to disable) ─────────────────────────────────
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
EMAIL_FROM=noreply@algenta.local
EOF

    echo -e "${GREEN}✓ Configuration generated: .env${NC}"
    echo -e "${YELLOW}  A new ALGENTA_CONFIG_ENCRYPTION_KEY was generated. BACK IT UP. If you are reinstalling${NC}"
    echo -e "${YELLOW}  over an existing database, restore your PREVIOUS key into .env before starting, or${NC}"
    echo -e "${YELLOW}  stored per-tenant provider keys will be unreadable.${NC}"
  else
    echo -e "${YELLOW}⚠ .env already exists, preserving local configuration${NC}"
  fi

  # Secrets live in .env — keep it owner-only (set_env_value's mktemp+mv already lands 600, but this
  # covers the fresh-write and preserved-.env paths too).
  chmod 600 .env 2>/dev/null || true

  ensure_env_default "DATABASE_URL_SYNC" "postgresql://algenta:algenta_secret@postgres:5432/algenta"
  ensure_env_default "ALGENTA_IMAGE_REGISTRY" "$IMAGE_REGISTRY"
  ensure_env_default "ALGENTA_IMAGE_TAG" "$IMAGE_TAG"
  ensure_env_default "RESULT_STORAGE_ENABLED" "true"
  ensure_env_default "ALGENTA_DEPLOYMENT_MODE" "self_hosted"
  ensure_env_default "ALGENTA_DISABLE_CLOUD" "1"
  ensure_env_default "ALGENTA_DISABLE_TELEMETRY" "1"
  ensure_env_default "ALGENTA_TELEMETRY_MODE" "local_audit"
  ensure_env_default "ALGENTA_METERING_MODE" "local_audit"
  ensure_env_default "ALGENTA_REQUIRE_LOCAL_LICENSE" "0"
  ensure_env_default "ALGENTA_CONTROL_PLANE_URL" ""
  ensure_env_default "ALGENTA_ALLOW_OUTBOUND_NETWORK" "0"
  ensure_env_default "ALGENTA_EGRESS_ALLOWLIST" "minio:9000"
  ensure_env_default "ALGENTA_LOCAL_LICENSE_PUBLIC_KEY_FILE" ""
  # Agent runtime + per-tenant key encryption — backfilled for installs upgrading from an older
  # .env (so they too get a stable KEK + sidecar token + the engine-callback/provider slots).
  ensure_env_default "ALGENTA_CONFIG_ENCRYPTION_KEY" "$config_encryption_key"
  ensure_env_default "AGENT_CORE_AUTH_TOKEN" "$agent_core_token"
  ensure_env_default "AGENT_CORE_REQUIRE_AUTH" "1"
  ensure_env_default "ALGENTA_AGENT_CORE_URL" "http://sidecar:8787"
  ensure_env_default "ALGENTA_ENGINE_URL" "http://api:8000"
  ensure_env_default "ALGENTA_ENGINE_API_KEY" ""
  ensure_env_default "ALGENTA_API_KEY" ""
  ensure_env_default "ANTHROPIC_API_KEY" ""

  echo -e "${YELLOW}  Review .env before production use — especially CORS_ORIGINS, TLS, and SMTP settings${NC}"
}

ensure_env_default() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" .env 2>/dev/null; then
    return
  fi
  echo "${key}=${value}" >> .env
}

# Set (replace-or-append) a .env key to a value. Uses grep -v + append (no sed) so the value needs
# no escaping; safe for the url-safe key alphabet. Only the matched key line is rewritten.
set_env_value() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" .env 2>/dev/null; then
    local tmp
    tmp="$(mktemp)"
    grep -v "^${key}=" .env > "$tmp"
    echo "${key}=${value}" >> "$tmp"
    mv "$tmp" .env
  else
    echo "${key}=${value}" >> .env
  fi
}

start_services() {
  echo -e "${BLUE}Starting Codna Decision Engine...${NC}"
  if ! is_truthy "$SKIP_IMAGE_PULL"; then
    if ! compose pull --quiet; then
      echo -e "${RED}Failed to pull images for tag ${IMAGE_TAG}.${NC}"
      echo "Check ALGENTA_IMAGE_REGISTRY / ALGENTA_IMAGE_TAG in ${INSTALL_DIR}/.env."
      exit 1
    fi
  else
    echo -e "${YELLOW}⚠ Skipping image pull because ALGENTA_SKIP_IMAGE_PULL=${SKIP_IMAGE_PULL}${NC}"
  fi
  compose up -d
  echo -e "${GREEN}✓ Services started${NC}"
}

wait_healthy() {
  echo -e "${BLUE}Waiting for API to be ready...${NC}"
  local max_wait="${ALGENTA_HEALTH_WAIT_SECONDS:-60}"
  local waited=0

  while [ $waited -lt $max_wait ]; do
    if http_ok "http://localhost:${API_PORT}/v1/health"; then
      echo -e "${GREEN}✓ API is ready${NC}"
      return 0
    fi
    sleep 2
    waited=$((waited + 2))
    echo -n "."
  done

  echo ""
  echo -e "${YELLOW}⚠ API did not respond in ${max_wait}s — check: ${COMPOSE_DISPLAY} logs api${NC}"
  return 1
}

run_migrations() {
  echo -e "${BLUE}Running database migrations...${NC}"
  if ! compose exec -T api python -m alembic -c apps/api_server/alembic.ini upgrade head; then
    echo -e "${RED}Database migrations failed.${NC}"
    return 1
  fi
  echo -e "${GREEN}✓ Migrations complete${NC}"
}

seed_initial_user() {
  echo -e "${BLUE}Creating bootstrap owner and API key...${NC}"
  echo ""

  local seed_output
  local seed_status=0
  seed_output=$(compose exec -T api python scripts/bootstrap_self_host.py 2>&1) || seed_status=$?

  local api_key
  local api_key_id
  local api_key_prefix
  local user_email
  local user_password
  local engine_api_key
  api_key=$(echo "$seed_output" | sed -n 's/^BOOTSTRAP_API_KEY=//p' | head -1 || true)
  api_key_id=$(echo "$seed_output" | sed -n 's/^BOOTSTRAP_API_KEY_ID=//p' | head -1 || true)
  api_key_prefix=$(echo "$seed_output" | sed -n 's/^BOOTSTRAP_API_KEY_PREFIX=//p' | head -1 || true)
  user_email=$(echo "$seed_output" | sed -n 's/^BOOTSTRAP_USER_EMAIL=//p' | head -1 || true)
  user_password=$(echo "$seed_output" | sed -n 's/^BOOTSTRAP_USER_PASSWORD=//p' | head -1 || true)
  engine_api_key=$(echo "$seed_output" | sed -n 's/^BOOTSTRAP_ENGINE_API_KEY=//p' | head -1 || true)

  if [ "$seed_status" -ne 0 ]; then
    echo "$seed_output"
    echo -e "${RED}Bootstrap command failed.${NC}"
    return 1
  fi

  # Wire the dedicated engine-callback key into .env so the agentic repository/GitHub flow works out
  # of the box AND survives restarts (the agent head presents it to call back into /v1). Bootstrap
  # returns a value ONLY on the run that mints it (no prior ACTIVE key); when it does, that key is
  # authoritative, so overwrite any stale/revoked .env value. On re-installs where the key already
  # exists it returns empty and we preserve the persisted .env value. Re-up so the already-running
  # api/worker pick it up (compose recreates only services whose env changed).
  if [ -n "$engine_api_key" ]; then
    set_env_value "ALGENTA_ENGINE_API_KEY" "$engine_api_key"
    echo -e "${GREEN}✓ Engine-callback key wired into .env (agentic repository flow enabled)${NC}"
    compose up -d >/dev/null 2>&1 || echo -e "${YELLOW}⚠ Could not auto-apply the engine key; run '${COMPOSE_DISPLAY} up -d' to apply${NC}"
  fi

  if [ -n "$api_key" ]; then
    echo ""
    echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}${BOLD} Codna is running.${NC}"
    echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  ${BOLD}API:${NC}          http://localhost:${API_PORT}"
    echo -e "  ${BOLD}Health:${NC}       curl http://localhost:${API_PORT}/v1/health"
    echo -e "  ${BOLD}API Docs:${NC}     http://localhost:${API_PORT}/docs"
    echo ""
    echo -e "  ${BOLD}API Key:${NC}      ${YELLOW}${api_key}${NC}"
    if [ -n "$api_key_id" ]; then
      echo -e "  ${BOLD}Bootstrap key id:${NC} ${api_key_id}"
    fi
    if [ -n "$api_key_prefix" ]; then
      echo -e "  ${BOLD}Bootstrap key prefix:${NC} ${api_key_prefix}"
    fi
    if [ -n "$user_email" ]; then
      echo -e "  ${BOLD}Bootstrap user:${NC} ${user_email}"
    fi
    if [ -n "$user_password" ]; then
      echo -e "  ${BOLD}Bootstrap password:${NC} ${YELLOW}${user_password}${NC}"
    fi
    echo ""
    echo -e "  ${BOLD}Run your first decision:${NC}"
    echo -e "  ${BLUE}curl -X POST http://localhost:${API_PORT}/v1/simulate \\${NC}"
    echo -e "  ${BLUE}  -H \"Authorization: Bearer \${ALGENTA_API_KEY}\" \\${NC}"
    echo -e "  ${BLUE}  -H \"Content-Type: application/json\" \\${NC}"
    echo -e "  ${BLUE}  -d '{${NC}"
    echo -e "  ${BLUE}    \"mode\": \"auto\",${NC}"
    echo -e "  ${BLUE}    \"scenario\": {${NC}"
    echo -e "  ${BLUE}      \"variables\": {${NC}"
    echo -e "  ${BLUE}        \"revenue\": { \"low\": 80000, \"high\": 200000 },${NC}"
    echo -e "  ${BLUE}        \"cost\": { \"low\": 30000, \"high\": 90000 }${NC}"
    echo -e "  ${BLUE}      },${NC}"
    echo -e "  ${BLUE}      \"objective\": \"maximize_net_value\"${NC}"
    echo -e "  ${BLUE}    },${NC}"
    echo -e "  ${BLUE}    \"runs\": 10000,${NC}"
    echo -e "  ${BLUE}    \"seed\": 42${NC}"
    echo -e "  ${BLUE}  }'${NC}"
    echo ""
    echo -e "  ${BOLD}Set temporarily:${NC} export ALGENTA_API_KEY='<paste the bootstrap key above>'"
    echo ""
    echo -e "  ${BOLD}Rotate the bootstrap key:${NC}"
    echo -e "  ${BLUE}curl -X POST http://localhost:${API_PORT}/v1/api-keys \\${NC}"
    echo -e "  ${BLUE}  -H \"Authorization: Bearer \${ALGENTA_API_KEY}\" \\${NC}"
    echo -e "  ${BLUE}  -H \"Content-Type: application/json\" \\${NC}"
    echo -e "  ${BLUE}  -d '{\"label\":\"mission-runtime\",\"expires_at\":\"2028-05-19T00:00:00Z\"}'${NC}"
    echo -e "  ${BOLD}Store it:${NC}     The returned raw_key is shown once; store it with id, key_prefix, and expires_at before revoking the bootstrap key."
    echo -e "  ${BOLD}Replace it:${NC}  export ALGENTA_API_KEY='<paste the replacement key returned above>'"
    echo -e "  ${BOLD}Note:${NC}         No SDK or Python install is required to use Codna."
    echo ""
    echo -e "  ${BOLD}Docs:${NC}         ${DOCS_URL}"
    echo -e "  ${BOLD}Support:${NC}      https://codna.ai/support"
    echo ""
    return 0
  fi

  echo "$seed_output"
  echo -e "${RED}Bootstrap completed without a printable API key.${NC}"
  return 1
}

print_next_steps() {
  echo -e "${BOLD}Next steps:${NC}"
  echo "  1. Rotate the bootstrap key with POST /v1/api-keys and a bounded expires_at"
  echo "     (the engine-callback key is a separate, long-lived key — rotating the bootstrap key won't break it)"
  echo "  2. For the agentic repository/GitHub flow, set ANTHROPIC_API_KEY in ${INSTALL_DIR}/.env then '${COMPOSE_DISPLAY} up -d'"
  echo "  3. Edit ${INSTALL_DIR}/.env for production configuration"
  echo "  4. Set up TLS with nginx or Caddy in front of port ${API_PORT}"
  echo "  5. Read the self-hosted docs: ${DOCS_URL}"
  echo ""
  echo -e "${BOLD}Useful commands:${NC}"
  echo "  cd ${INSTALL_DIR} && ${COMPOSE_DISPLAY} ps"
  echo "  cd ${INSTALL_DIR} && ${COMPOSE_DISPLAY} logs -f api"
  echo "  cd ${INSTALL_DIR} && ${COMPOSE_DISPLAY} logs -f worker"
  echo "  cd ${INSTALL_DIR} && ${COMPOSE_DISPLAY} stop"
  echo "  cd ${INSTALL_DIR} && ${COMPOSE_DISPLAY} pull && ${COMPOSE_DISPLAY} up -d"
  echo ""
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
  print_logo
  detect_os
  check_requirements
  resolve_release_ref
  download_release
  generate_env
  start_services
  if ! wait_healthy; then
    echo -e "${RED}Self-hosted install failed because the API did not become ready.${NC}"
    exit 1
  fi
  if ! run_migrations; then
    echo -e "${RED}Self-hosted install failed during database migrations.${NC}"
    exit 1
  fi
  if ! seed_initial_user; then
    echo -e "${RED}Self-hosted install failed during bootstrap initialization.${NC}"
    exit 1
  fi
  print_next_steps
}

main "$@"
