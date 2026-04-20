#!/bin/bash
# Algenta Decision Engine — One-line installer
# Usage: curl -fsSL https://algenta.ai/install | bash
# Or:    curl -fsSL https://raw.githubusercontent.com/algenta/decision-engine/main/install.sh | bash

set -euo pipefail

REPO="algenta/decision-engine"
INSTALL_DIR="${ALGENTA_DIR:-$HOME/.algenta}"
API_PORT="${ALGENTA_API_PORT:-8000}"
PORTAL_PORT="${ALGENTA_PORTAL_PORT:-3000}"

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
  echo -e "${BOLD}Algenta Decision Engine — Self-Hosted Installer${NC}"
  echo ""
}

check_requirements() {
  echo -e "${BLUE}Checking requirements...${NC}"
  local missing=()

  command -v docker >/dev/null 2>&1 || missing+=("docker")
  command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 || missing+=("docker-compose")

  if [ ${#missing[@]} -gt 0 ]; then
    echo -e "${RED}Missing requirements: ${missing[*]}${NC}"
    echo ""
    echo "Install Docker Desktop from: https://docs.docker.com/get-docker/"
    exit 1
  fi

  echo -e "${GREEN}✓ Docker and Docker Compose found${NC}"
}

detect_os() {
  case "$(uname -s)" in
    Darwin*) OS="mac" ;;
    Linux*)  OS="linux" ;;
    *)       OS="unknown" ;;
  esac
}

download_release() {
  echo -e "${BLUE}Downloading Algenta Decision Engine...${NC}"

  mkdir -p "$INSTALL_DIR"
  cd "$INSTALL_DIR"

  # Download the self-hosted Docker Compose bundle
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "https://algenta.ai/docker-compose.yml" -o docker-compose.yml 2>/dev/null || \
    curl -fsSL "https://raw.githubusercontent.com/$REPO/main/infra/docker/docker-compose.selfhosted.yml" -o docker-compose.yml
  elif command -v wget >/dev/null 2>&1; then
    wget -qO docker-compose.yml "https://algenta.ai/docker-compose.yml" 2>/dev/null || \
    wget -qO docker-compose.yml "https://raw.githubusercontent.com/$REPO/main/infra/docker/docker-compose.selfhosted.yml"
  fi

  echo -e "${GREEN}✓ Downloaded${NC}"
}

generate_env() {
  echo -e "${BLUE}Generating configuration...${NC}"

  if [ -f ".env" ]; then
    echo -e "${YELLOW}⚠ .env already exists, skipping generation${NC}"
    return
  fi

  # Generate secrets
  JWT_SECRET=$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 64 2>/dev/null || openssl rand -hex 32)
  WEBHOOK_SECRET=$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32 2>/dev/null || openssl rand -hex 16)

  cat > .env << EOF
# Algenta Decision Engine — Self-Hosted Configuration
# Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")

# ── Application ──────────────────────────────────────────────────────────────
API_ENV=production
LOG_LEVEL=info
CORS_ORIGINS=http://localhost:${PORTAL_PORT}

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

# ── Ports ────────────────────────────────────────────────────────────────────
API_PORT=${API_PORT}
PORTAL_PORT=${PORTAL_PORT}

# ── Engine ───────────────────────────────────────────────────────────────────
MOJO_BINARY_PATH=/app/mojo_build/simulate
MOJO_TIMEOUT_SECONDS=30
MOJO_MAX_CONCURRENT=4

# ── Object Storage (MinIO — managed by Docker Compose) ───────────────────────
S3_BUCKET_NAME=algenta-results
S3_ENDPOINT_URL=http://minio:9000
S3_ACCESS_KEY_ID=algenta_minio
S3_SECRET_ACCESS_KEY=algenta_minio_secret
S3_REGION=us-east-1

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
  echo -e "${YELLOW}  Edit .env before production use — especially CORS_ORIGINS and SMTP settings${NC}"
}

start_services() {
  echo -e "${BLUE}Starting Algenta Decision Engine...${NC}"
  docker compose pull --quiet
  docker compose up -d
  echo -e "${GREEN}✓ Services started${NC}"
}

wait_healthy() {
  echo -e "${BLUE}Waiting for API to be ready...${NC}"
  local max_wait=60
  local waited=0

  while [ $waited -lt $max_wait ]; do
    if curl -sf "http://localhost:${API_PORT}/health" >/dev/null 2>&1; then
      echo -e "${GREEN}✓ API is ready${NC}"
      return 0
    fi
    sleep 2
    waited=$((waited + 2))
    echo -n "."
  done

  echo ""
  echo -e "${YELLOW}⚠ API did not respond in ${max_wait}s — check: docker compose logs api${NC}"
  return 1
}

run_migrations() {
  echo -e "${BLUE}Running database migrations...${NC}"
  docker compose exec -T api python -m alembic -c apps/api_server/alembic.ini upgrade head
  echo -e "${GREEN}✓ Migrations complete${NC}"
}

seed_initial_user() {
  echo -e "${BLUE}Creating initial admin user...${NC}"
  echo ""

  local seed_output
  seed_output=$(docker compose exec -T api python scripts/seed_dev.py 2>&1) || true

  echo "$seed_output"

  # Extract the API key from seed output
  local api_key
  api_key=$(echo "$seed_output" | grep -o 'de_[a-zA-Z0-9_]*' | head -1 || true)

  if [ -n "$api_key" ]; then
    echo ""
    echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}${BOLD} Algenta Decision Engine is ready! 🚀${NC}"
    echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  ${BOLD}Portal UI:${NC}    http://localhost:${PORTAL_PORT}"
    echo -e "  ${BOLD}API:${NC}          http://localhost:${API_PORT}"
    echo -e "  ${BOLD}API Docs:${NC}     http://localhost:${API_PORT}/docs"
    echo ""
    echo -e "  ${BOLD}Login:${NC}        dev@example.com"
    echo -e "  ${BOLD}API Key:${NC}      ${YELLOW}${api_key}${NC}"
    echo ""
    echo -e "  ${BOLD}Test:${NC}"
    echo -e "  ${BLUE}curl -X POST http://localhost:${API_PORT}/v1/simulate \\${NC}"
    echo -e "  ${BLUE}  -H 'Authorization: Bearer ${api_key}' \\${NC}"
    echo -e "  ${BLUE}  -H 'Content-Type: application/json' \\${NC}"
    echo -e "  ${BLUE}  -d '{\"mode\":\"auto\",\"runs\":1000,\"scenario\":{\"variables\":{\"x\":{\"low\":100,\"high\":500}},\"objective\":\"maximize_net_value\"}}'${NC}"
    echo ""
    echo -e "  ${BOLD}Docs:${NC}         https://docs.algenta.ai"
    echo -e "  ${BOLD}Support:${NC}      https://algenta.ai/support"
    echo ""
  fi
}

print_next_steps() {
  echo -e "${BOLD}Next steps:${NC}"
  echo "  1. Open http://localhost:${PORTAL_PORT} in your browser"
  echo "  2. Edit ${INSTALL_DIR}/.env for production configuration"
  echo "  3. Set up TLS with nginx or Caddy in front of port ${API_PORT}"
  echo "  4. Read the docs: https://docs.algenta.ai/self-hosting"
  echo ""
  echo -e "${BOLD}Useful commands:${NC}"
  echo "  algenta logs     — View logs"
  echo "  algenta stop     — Stop services"
  echo "  algenta update   — Update to latest version"
  echo "  algenta status   — Check service health"
  echo ""
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
  print_logo
  detect_os
  check_requirements
  download_release
  generate_env
  start_services
  wait_healthy && run_migrations && seed_initial_user || true
  print_next_steps
}

main "$@"
