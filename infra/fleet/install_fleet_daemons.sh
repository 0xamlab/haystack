#!/bin/bash
# install_fleet_daemons.sh -- restore the self-hosted runner fleet's support daemons on a
# macOS Apple-Silicon host. Idempotent: safe to re-run. Requires sudo (installs into
# /Library/LaunchDaemons, which the system domain owns).
#
# Installs two LaunchDaemons + their scripts:
#   1. com.algenta.dns-proxy   -- DNS-resilience proxy (127.0.0.1:8899). The runners route all
#      GitHub traffic through it so a flaky local resolver can't take the fleet offline.
#   2. com.algenta.fleet-watchdog -- a 60s watchdog that restarts the proxy / a vanished runner
#      daemon / a hung Colima VM, restarts a wedged (alive-but-offline) runner, warns on VM disk,
#      and recycles both logs so they never accumulate.
#
# The five GitHub runner daemons themselves (actions.runner.thyn-ai.thyn-mac-arm64*) are
# provisioned by the actions-runner installer (svc.sh install) and are NOT managed here; the
# watchdog keeps them alive but does not install them.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "run with sudo: sudo bash $0" >&2
  exit 1
fi

SRC="$(cd "$(dirname "$0")" && pwd)"

# Resolve the REAL (non-root) user's home: under sudo, $HOME is /var/root, which would point the
# daemons at the wrong paths. Use the invoking user's home instead.
if [ -n "${SUDO_USER:-}" ] && [ "${SUDO_USER}" != "root" ]; then
  REAL_USER="$SUDO_USER"
  REAL_HOME="$(dscl . -read "/Users/$REAL_USER" NFSHomeDirectory 2>/dev/null | awk '{print $2}')"
  [ -n "$REAL_HOME" ] || REAL_HOME="/Users/$REAL_USER"
else
  REAL_USER="$(whoami)"
  REAL_HOME="$HOME"
fi
echo "target user: $REAL_USER ($REAL_HOME)"

BIN_DIR="$REAL_HOME/bin"
LOG_DIR="$REAL_HOME/Library/Logs"
PLIST_DIR="/Library/LaunchDaemons"
mkdir -p "$BIN_DIR" "$LOG_DIR"

# 1. Deploy the scripts.
install -m 755 -o "$REAL_USER" "$SRC/fleet_watchdog.sh"      "$BIN_DIR/fleet_watchdog.sh"
install -m 755 -o "$REAL_USER" "$SRC/algenta_dns_proxy.py"   "$BIN_DIR/algenta_dns_proxy.py"

# 2. Install the plists, rewriting the hardcoded /Users/angel prefix to this user's home so the
#    daemons point at the right paths on any machine.
for name in com.algenta.dns-proxy com.algenta.fleet-watchdog; do
  sed "s#/Users/angel#$REAL_HOME#g" "$SRC/$name.plist" > "$PLIST_DIR/$name.plist"
  chown root:wheel "$PLIST_DIR/$name.plist"
  chmod 644 "$PLIST_DIR/$name.plist"
  # (Re)load into the system domain: bootout first so re-runs don't fail on an existing service.
  launchctl bootout "system/$name" >/dev/null 2>&1 || true
  launchctl bootstrap system "$PLIST_DIR/$name.plist"
  echo "installed + loaded: system/$name"
done

chown "$REAL_USER" "$LOG_DIR" 2>/dev/null || true
echo "done. verify: launchctl print system/com.algenta.dns-proxy | head -3"
