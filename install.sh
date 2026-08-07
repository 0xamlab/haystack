#!/bin/bash
# Algenta — one-line self-hosted installer
# Usage: curl -fsSL https://algenta.ai/install.sh | bash
#
# Auth path = the same device login the SDKs use (accounts.thyn.ai, RFC 8628): the installer
# asks you to open a URL + enter a code, then exchanges the token for read-only registry
# credentials via the control plane (POST /v1/registry/credentials). No GitHub token needed.
#
# Release pinning: images are pulled as :latest (or your ALGENTA_IMAGE_TAG) and then PINNED
# BY DIGEST in the compose file that stays on disk — a floating tag never runs here.

set -euo pipefail

REPO="thyn-ai/algenta"
INSTALL_DIR="${ALGENTA_DIR:-$HOME/.algenta}"
API_PORT="${ALGENTA_API_PORT:-8000}"
DOCS_URL="${ALGENTA_DOCS_URL:-https://docs.algenta.ai/self-hosting}"
IMAGE_REGISTRY="${ALGENTA_IMAGE_REGISTRY:-ghcr.io/thyn-ai/algenta}"
IMAGE_TAG="${ALGENTA_IMAGE_TAG:-${ALGENTA_VERSION:-latest}}"
COMPOSE_BUNDLE_URL="${ALGENTA_COMPOSE_URL:-https://algenta.ai/install/docker-compose.selfhosted.yml}"
SKIP_IMAGE_PULL="${ALGENTA_SKIP_IMAGE_PULL:-0}"
ACCOUNTS_URL="${ALGENTA_ACCOUNTS_URL:-https://accounts.thyn.ai}"
CONTROL_PLANE_URL="${ALGENTA_API_URL:-https://api.algenta.ai}"
CLIENT_ID="${ALGENTA_INSTALLER_CLIENT_ID:-algenta-cli}"
DEVICE_WAIT_SECONDS="${ALGENTA_DEVICE_WAIT_SECONDS:-300}"
COMPOSE_CMD=()
COMPOSE_DISPLAY=""
CLI_BIN_DIR="${ALGENTA_BIN_DIR:-$HOME/.local/bin}"

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
  echo -e "${BOLD}Algenta — Self-Hosted Service Installer${NC}"
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

json_field() {
  # json_field '<json>' field  →  value of a top-level STRING field (stdlib-free parsing:
  # the device-flow + credentials payloads are tiny flat JSON objects of strings).
  printf '%s' "$1" | sed -n 's/.*"'"$2"'"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1
}

resolve_release_ref() {
  # No GitHub round-trip: images are pulled by tag (default: latest) and pinned BY DIGEST
  # after the pull (see pin_images_by_digest). ALGENTA_IMAGE_TAG / ALGENTA_VERSION override.
  echo -e "${GREEN}✓ Using image tag ${IMAGE_TAG} (digest-pinned after pull)${NC}"
}

download_release() {
  echo -e "${BLUE}Downloading Algenta...${NC}"

  mkdir -p "$INSTALL_DIR"
  cd "$INSTALL_DIR"

  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$COMPOSE_BUNDLE_URL" -o docker-compose.yml
  elif command -v wget >/dev/null 2>&1; then
    wget -qO docker-compose.yml "$COMPOSE_BUNDLE_URL"
  fi

  echo -e "${GREEN}✓ Downloaded${NC}"
}

install_cli_wrapper() {
  echo -e "${BLUE}Installing the Algenta control-plane CLI wrapper...${NC}"
  mkdir -p "$INSTALL_DIR/bin" "$CLI_BIN_DIR"
  cat > "$INSTALL_DIR/bin/de" <<'EOF'
#!/bin/bash
set -euo pipefail

INSTALL_DIR="${ALGENTA_DIR:-$HOME/.algenta}"
if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "de: Docker Compose is required for the self-hosted control-plane CLI." >&2
  exit 1
fi

if [ ! -f "$INSTALL_DIR/docker-compose.yml" ]; then
  echo "de: no Algenta install found at $INSTALL_DIR" >&2
  exit 1
fi

export ALGENTA_API_KEY="${ALGENTA_API_KEY:-${DE_API_KEY:-}}"
export ALGENTA_BASE_URL="http://127.0.0.1:8000"
TTY_ARGS=()
if [ ! -t 0 ]; then
  TTY_ARGS=(-T)
fi
exec "${COMPOSE[@]}" --project-directory "$INSTALL_DIR" \
  -f "$INSTALL_DIR/docker-compose.yml" exec "${TTY_ARGS[@]}" \
  -e ALGENTA_API_KEY -e ALGENTA_BASE_URL \
  api python -m apps.cli.main "$@"
EOF
  chmod 755 "$INSTALL_DIR/bin/de"

  local cli_link="$CLI_BIN_DIR/de"
  if [ -e "$cli_link" ] && [ ! -L "$cli_link" ]; then
    echo -e "${YELLOW}⚠ ${cli_link} already exists and was not replaced.${NC}"
    echo -e "${YELLOW}  Use ${INSTALL_DIR}/bin/de or set ALGENTA_BIN_DIR before reinstalling.${NC}"
    return
  fi
  ln -sfn "$INSTALL_DIR/bin/de" "$cli_link"
  echo -e "${GREEN}✓ Installed ${cli_link}${NC}"
  case ":$PATH:" in
    *":$CLI_BIN_DIR:"*) ;;
    *) echo -e "${YELLOW}  Add to PATH: export PATH=\"${CLI_BIN_DIR}:\$PATH\"${NC}" ;;
  esac
}

generate_env() {
  echo -e "${BLUE}Generating configuration...${NC}"

  # Auto-generated secrets that MUST stay stable across restarts. Compose reads ${INSTALL_DIR}/.env
  # (not the operator's shell), so anything not persisted here is lost on the next `compose up`.
  #  - ALGENTA_CONFIG_ENCRYPTION_KEY (64-hex) encrypts per-tenant provider keys at rest; rotating or
  #    losing it makes every stored tenant key undecryptable (silent fail-closed) — generate once, keep it.
  #  - AGENT_CORE_AUTH_TOKEN protects the API-to-engine runtime seam and is generated automatically.
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
# Algenta — Self-Hosted Configuration
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
# every stored per-tenant provider key undecryptable. AGENT_CORE_AUTH_TOKEN gates the bundled engine.
ALGENTA_CONFIG_ENCRYPTION_KEY=${config_encryption_key}
AGENT_CORE_AUTH_TOKEN=${agent_core_token}
AGENT_CORE_REQUIRE_AUTH=1
ALGENTA_AGENT_CORE_URL=http://engine:8787
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
RUNTIME_FALLBACK_MODE=deny
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

# ── Billing (optional — leave blank to disable) ──────────────────────────────
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=

# ── Email (optional — leave blank to disable) ─────────────────────────────────
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
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
  # Agent runtime + per-tenant key encryption, backfilled for installs upgrading from an older .env.
  ensure_env_default "ALGENTA_CONFIG_ENCRYPTION_KEY" "$config_encryption_key"
  ensure_env_default "AGENT_CORE_AUTH_TOKEN" "$agent_core_token"
  ensure_env_default "AGENT_CORE_REQUIRE_AUTH" "1"
  ensure_env_default "ALGENTA_AGENT_CORE_URL" "http://engine:8787"
  ensure_env_default "ALGENTA_ENGINE_URL" "http://api:8000"
  ensure_env_default "ALGENTA_ENGINE_API_KEY" ""
  ensure_env_default "ALGENTA_API_KEY" ""
  ensure_env_default "ANTHROPIC_API_KEY" ""

  # Migrate only obsolete installer defaults; preserve every operator-supplied override.
  if grep -q '^ALGENTA_AGENT_CORE_URL=http://sidecar:8787$' .env; then
    set_env_value "ALGENTA_AGENT_CORE_URL" "http://engine:8787"
  fi
  if grep -q '^ALGENTA_IMAGE_REGISTRY=ghcr.io/algenta/decision-engine$' .env; then
    set_env_value "ALGENTA_IMAGE_REGISTRY" "ghcr.io/thyn-ai/algenta"
  fi
  if grep -q '^RUNTIME_FALLBACK_MODE=allow$' .env; then
    set_env_value "RUNTIME_FALLBACK_MODE" "deny"
  fi

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

# Rewrite a compose image line to a digest reference: REG/NAME:TAG -> REG/NAME@sha256:...
# so nothing floating ever runs from the on-disk compose file.
pin_one_image_by_digest() {
  local service="$1"
  local ref
  ref=$(docker inspect --format='{{index .RepoDigests 0}}' "${IMAGE_REGISTRY}/${service}:${IMAGE_TAG}" 2>/dev/null || true)
  if [ -z "$ref" ]; then
    echo -e "${YELLOW}⚠ Could not resolve a digest for ${service}; leaving the tag reference in place${NC}"
    return 0
  fi
  local tmp
  tmp="$(mktemp)"
  awk -v svc="$service" -v reg="$IMAGE_REGISTRY" -v tag="$IMAGE_TAG" -v digest_ref="$ref" '
    index($0, "image:") && index($0, reg "/" svc ":" tag) { sub(/image:.*/, "image: " digest_ref) }
    { print }
  ' docker-compose.yml > "$tmp"
  mv "$tmp" docker-compose.yml
  echo -e "${GREEN}✓ Pinned ${service} to ${ref#*@}${NC}"
}

pin_images_by_digest() {
  echo -e "${BLUE}Pinning images by digest...${NC}"
  pin_one_image_by_digest "api"
  pin_one_image_by_digest "engine"
}

# ── Device login (same path as `algenta login`): accounts portal RFC 8628, then exchange the
# token for read-only registry credentials on the control plane. ─────────────────────────────
device_login_and_pull_creds() {
  echo -e "${BLUE}Authenticating to pull the Algenta images (device login — same as the SDK)...${NC}"

  local code_json user_code device_code verify interval
  code_json=$(curl -fsSL -X POST "${ACCOUNTS_URL}/oauth/device/code" \
      -H "Content-Type: application/json" \
      -H "User-Agent: algenta-installer/1.0" \
      -d "{\"client_id\": \"${CLIENT_ID}\", \"scope\": \"algenta\"}" 2>/dev/null || true)
  device_code=$(json_field "$code_json" device_code)
  user_code=$(json_field "$code_json" user_code)
  verify=$(json_field "$code_json" verification_uri_complete)
  [ -n "$verify" ] || verify=$(json_field "$code_json" verification_uri)
  interval=$(json_field "$code_json" interval)
  case "$interval" in ''|*[!0-9]*) interval=5 ;; esac

  if [ -z "$device_code" ] || [ -z "$user_code" ] || [ -z "$verify" ]; then
    echo -e "${RED}Could not start device authorization against ${ACCOUNTS_URL}.${NC}"
    echo "If you already have registry access, run 'docker login ${IMAGE_REGISTRY%%/*}' first,"
    echo "then re-run with ALGENTA_SKIP_REGISTRY_LOGIN=1."
    exit 1
  fi

  echo ""
  echo -e "  ${BOLD}1.${NC} Open:  ${verify}"
  echo -e "  ${BOLD}2.${NC} Enter code:  ${YELLOW}${user_code}${NC}"
  echo ""
  if command -v open >/dev/null 2>&1; then
    open "$verify" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$verify" >/dev/null 2>&1 || true
  fi

  local deadline=$(( $(date +%s) + DEVICE_WAIT_SECONDS ))
  local access_token="" tok_json error
  while [ "$(date +%s)" -lt "$deadline" ]; do
    sleep "$interval"
    tok_json=$(curl -fsSL -X POST "${ACCOUNTS_URL}/oauth/device/token" \
        -H "Content-Type: application/json" \
        -H "User-Agent: algenta-installer/1.0" \
        -d "{\"client_id\": \"${CLIENT_ID}\", \"device_code\": \"${device_code}\", \"grant_type\": \"urn:ietf:params:oauth:grant-type:device_code\"}" 2>/dev/null || true)
    access_token=$(json_field "$tok_json" access_token)
    if [ -n "$access_token" ]; then
      break
    fi
    error=$(json_field "$tok_json" error)
    case "$error" in
      authorization_pending|slow_down|"") continue ;;
      *) echo -e "${RED}Device authorization failed: ${error}${NC}"; exit 1 ;;
    esac
  done
  if [ -z "$access_token" ]; then
    echo -e "${RED}Timed out waiting for device authorization.${NC}"
    exit 1
  fi
  echo -e "${GREEN}✓ Device authorized${NC}"

  echo -e "${BLUE}Fetching registry credentials from the control plane...${NC}"
  local creds_json registry username password
  creds_json=$(curl -fsSL -X POST "${CONTROL_PLANE_URL}/v1/registry/credentials" \
      -H "Authorization: Bearer ${access_token}" \
      -H "Content-Type: application/json" \
      -H "User-Agent: algenta-installer/1.0" \
      -d '{}' 2>/dev/null || true)
  registry=$(json_field "$creds_json" registry)
  username=$(json_field "$creds_json" username)
  password=$(json_field "$creds_json" password)
  if [ -z "$registry" ] || [ -z "$username" ] || [ -z "$password" ]; then
    echo -e "${RED}The control plane did not issue registry credentials.${NC}"
    echo "If the images are public or you already ran 'docker login ${IMAGE_REGISTRY%%/*}',"
    echo "re-run with ALGENTA_SKIP_REGISTRY_LOGIN=1."
    exit 1
  fi

  printf '%s' "$password" | docker login "$registry" -u "$username" --password-stdin >/dev/null 2>&1 || {
    echo -e "${RED}docker login with the issued credentials failed.${NC}"
    exit 1
  }
  echo -e "${GREEN}✓ Logged in to ${registry}${NC}"
}

registry_login() {
  if is_truthy "$SKIP_IMAGE_PULL"; then
    return 0
  fi
  if is_truthy "${ALGENTA_SKIP_REGISTRY_LOGIN:-0}"; then
    echo -e "${YELLOW}⚠ Skipping registry login (ALGENTA_SKIP_REGISTRY_LOGIN set) — assuming an existing docker login${NC}"
    return 0
  fi
  device_login_and_pull_creds
}

start_services() {
  echo -e "${BLUE}Starting Algenta...${NC}"
  if ! is_truthy "$SKIP_IMAGE_PULL"; then
    if ! compose pull --quiet; then
      echo -e "${RED}Failed to pull images for tag ${IMAGE_TAG}.${NC}"
      echo "Check ALGENTA_IMAGE_REGISTRY / ALGENTA_IMAGE_TAG in ${INSTALL_DIR}/.env,"
      echo "or authenticate first: docker login ${IMAGE_REGISTRY%%/*}"
      exit 1
    fi
    pin_images_by_digest
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
  # API and engine pick it up (Compose recreates only services whose env changed).
  if [ -n "$engine_api_key" ]; then
    set_env_value "ALGENTA_ENGINE_API_KEY" "$engine_api_key"
    echo -e "${GREEN}✓ Engine-callback key wired into .env (agentic repository flow enabled)${NC}"
    compose up -d >/dev/null 2>&1 || echo -e "${YELLOW}⚠ Could not auto-apply the engine key; run '${COMPOSE_DISPLAY} up -d' to apply${NC}"
  fi

  if [ -n "$api_key" ]; then
    echo ""
    echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}${BOLD} Algenta is running.${NC}"
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
    echo -e "  ${BOLD}Note:${NC}         No SDK or Python install is required to use Algenta."
    echo ""
    echo -e "  ${BOLD}Docs:${NC}         ${DOCS_URL}"
    echo -e "  ${BOLD}Support:${NC}      https://algenta.ai/support"
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
  echo "  ${CLI_BIN_DIR}/de health"
  echo "  cd ${INSTALL_DIR} && ${COMPOSE_DISPLAY} ps"
  echo "  cd ${INSTALL_DIR} && ${COMPOSE_DISPLAY} logs -f api"
  echo "  cd ${INSTALL_DIR} && ${COMPOSE_DISPLAY} logs -f engine"
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
  install_cli_wrapper
  generate_env
  registry_login
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
