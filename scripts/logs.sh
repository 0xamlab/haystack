#!/usr/bin/env bash
# Tail logs. Usage: scripts/logs.sh [api|engine]   (default: api)
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_deploy_common.sh"
need flyctl
case "${1:-api}" in
  api)    fly logs -a "$CODNA_API_APP" ;;
  engine) fly logs -a "$CODNA_ENGINE_APP" ;;
  *) die "usage: logs.sh [api|engine]" ;;
esac
