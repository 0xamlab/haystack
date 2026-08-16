#!/bin/bash
# fleet_watchdog -- keeps the self-hosted runner fleet's critical path alive.
#
# WHY: the runners route all GitHub traffic through the local DNS-resilience proxy
# (127.0.0.1:8899, system daemon com.algenta.dns-proxy). If that daemon dies or hangs,
# every runner's HTTP fails instantly. launchd KeepAlive covers clean crashes; this watchdog
# adds a live port check (catches hangs KeepAlive can't see) and a kickstart, plus two more
# fleet failure modes seen in practice: a dead runner daemon and a filling Colima VM disk
# (a full VM disk corrupts container work silently -- apt 'invalid signature', stuck builds).
#
# Runs as a system LaunchDaemon (root) every 60s: root can kickstart system-domain daemons
# and read the docker socket. Log: /Users/angel/Library/Logs/fleet_watchdog.log
LOG=/Users/angel/Library/Logs/fleet_watchdog.log

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG"; }

# 0. Log recycling -- logs must never accumulate. Runs every cycle (60s), BEFORE any logging, so
# the watchdog's own log is capped too. Each log is allowed one archived copy (.old); anything
# older is overwritten, so disk usage is bounded to ~2x the cap per log. The proxy log only grows
# on startup/FAIL (no per-tunnel logging), so it almost never trips the cap -- but when it does we
# rotate it AND kickstart the proxy so it reopens a fresh file (launchd holds the log FD open, so a
# bare rename would leave the proxy writing to the renamed file forever).
MAX_LOG_BYTES=1048576 # 1 MiB
rotate_log() { # $1 = log path ; $2 = optional launchd label to kickstart after rotating
    local f="$1" label="${2:-}" size
    [ -f "$f" ] || return 0
    size=$(stat -f%z "$f" 2>/dev/null || echo 0)
    if [ "$size" -gt "$MAX_LOG_BYTES" ]; then
        mv -f "$f" "$f.old" 2>/dev/null
        : > "$f"
        if [ -n "$label" ]; then
            launchctl kickstart -k "system/$label" >/dev/null 2>&1
        fi
        log "ROTATED ${f} (was ${size} bytes)${label:+, restarted ${label}}"
    fi
}
rotate_log "$LOG"
rotate_log /Users/angel/Library/Logs/algenta_dns_proxy.log com.algenta.dns-proxy

# 1. Proxy health: the port must accept a connection. Dead or hung -> kickstart the daemon.
if ! nc -z -w 3 127.0.0.1 8899 2>/dev/null; then
    log "PROXY DOWN (port 8899 not accepting) -- kickstarting com.algenta.dns-proxy"
    launchctl kickstart -k system/com.algenta.dns-proxy >> "$LOG" 2>&1
    sleep 2
    if nc -z -w 3 127.0.0.1 8899 2>/dev/null; then
        log "PROXY RECOVERED via kickstart"
    else
        log "PROXY STILL DOWN AFTER KICKSTART -- needs manual attention"
    fi
fi

# 2. Runner daemons: all five must be present in the system domain; kickstart any that vanished.
for n in "" "-2" "-3" "-4" "-5"; do
    label="actions.runner.thyn-ai.thyn-mac-arm64$n"
    if ! launchctl list "$label" >/dev/null 2>&1; then
        log "RUNNER DAEMON MISSING: $label -- kickstarting"
        launchctl kickstart -k "system/$label" >> "$LOG" 2>&1
    fi
done

# 3. Colima VM liveness: a hung VM (sshd dead, dockerd unresponsive) kills every container job
# silently -- seen in production: 'error waiting for container: unexpected EOF', exit 125, docker
# CLI hangs while `colima list` still claims Running.
#
# Probes, best first:
#   a) docker daemon /_ping over its socket -- what CI actually needs; it answers even when the
#      guest sshd is slow, so a busy-but-healthy VM never gets killed;
#   b) `colima ssh` with a 30s budget (catches sshd-dead/dockerd-dead wedges the socket can't).
# Restart guardrails (added 2026-08-15 after this watchdog ITSELF became the instability: under
# heavy docker builds the guest sshd took longer than the old 15s budget, and the watchdog
# restarted healthy-but-busy VMs mid-CI -- five restarts in one evening, each killing live jobs):
#   - a VM answering on the docker socket is healthy, period;
#   - otherwise restart only after THREE consecutive failed probe cycles (~3 min of continuous
#     unresponsiveness). A transient slow probe can never kill the VM again.
SOCK=/Users/angel/.colima/default/docker.sock
VM_STATE=/tmp/.fleet_watchdog_vm_fails
vm_ok=0
if printf 'GET /_ping HTTP/1.0\r\nHost: docker\r\n\r\n' | nc -U -w 5 "$SOCK" 2>/dev/null | grep -q '200 OK'; then
    vm_ok=1
else
    probe=/tmp/.fleet_watchdog_vm_$$
    ( su angel -c 'colima ssh -- true 2>/dev/null && echo ok' > "$probe" 2>/dev/null ) &
    bg=$!
    for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
        [ -s "$probe" ] && break
        sleep 1
    done
    if [ -s "$probe" ]; then
        vm_ok=1
    else
        kill -9 "$bg" 2>/dev/null
        pkill -9 -f 'colima ssh' 2>/dev/null
    fi
    rm -f "$probe"
fi
if [ "$vm_ok" = "1" ]; then
    rm -f "$VM_STATE" 2>/dev/null
else
    count=$(cat "$VM_STATE" 2>/dev/null || echo 0)
    count=$((count + 1))
    echo "$count" > "$VM_STATE"
    if [ "$count" -ge 3 ]; then
        log "COLIMA VM UNRESPONSIVE (docker socket silent + ssh probe failed, $count consecutive checks) -- restarting VM"
        if su angel -c 'colima restart' >> "$LOG" 2>&1; then
            log "COLIMA VM RESTARTED by watchdog"
        else
            log "COLIMA RESTART FAILED -- needs manual attention"
        fi
        rm -f "$VM_STATE" 2>/dev/null
    else
        log "COLIMA VM probe failed (check $count/3: docker socket silent, ssh unresponsive) -- restarting only if it persists"
    fi
fi

# 4. Colima VM disk: warn at 85%, loud at 95% (full disk already broke container builds once).
vm_pct=$(su angel -c 'colima ssh -- df / 2>/dev/null' 2>/dev/null | awk 'NR==2{gsub("%","",$5); print $5}')
if [ -n "$vm_pct" ]; then
    if [ "$vm_pct" -ge 95 ]; then
        log "COLIMA VM DISK CRITICAL: ${vm_pct}% used -- container work will corrupt; prune now (docker system prune)"
    elif [ "$vm_pct" -ge 85 ]; then
        log "COLIMA VM DISK WARNING: ${vm_pct}% used -- schedule a prune"
    fi
fi

# 4b. Runner restart request: the runners are root LaunchDaemons and re-read their .env only at
# daemon start, so applying a runner-env change needs a root restart. Touching this marker asks
# the watchdog (which IS root) to restart all five on the next cycle -- the sudo-free escape hatch.
REQ=/tmp/.fleet_request_runner_restart
if [ -e "$REQ" ]; then
    rm -f "$REQ"
    log "RUNNER RESTART REQUESTED (marker found) -- restarting all runner daemons"
    for n in "" "-2" "-3" "-4" "-5"; do
        launchctl kickstart -k "system/actions.runner.thyn-ai.thyn-mac-arm64$n" >> "$LOG" 2>&1
    done
    log "RUNNER RESTART COMPLETE"
fi

# 5. Wedged runner detection. launchd KeepAlive restarts a DEAD runner, but NOT a hung one: a
# listener that is alive yet no longer connected to the broker sits "offline" on GitHub forever,
# silently shrinking the fleet (exactly the "runners randomly go offline" failure mode). Detect it
# as: GitHub reports the runner offline WHILE its launchd service still has a live PID. To avoid
# killing a runner caught mid-reconnect, require the offline state on TWO consecutive checks
# (~2 min) before restarting it. Defensive guard: if the GitHub query itself fails (network or
# auth down), SKIP this check entirely -- never restart a runner without positive evidence.
WEDGE_STATE=/tmp/.fleet_watchdog_wedge
runner_status=$(su angel -c 'gh api orgs/thyn-ai/actions/runners --jq ".runners[] | \"\(.name) \(.status)\"" 2>/dev/null')
if [ -n "$runner_status" ]; then
    for n in "" "-2" "-3" "-4" "-5"; do
        name="thyn-mac-arm64$n"
        label="actions.runner.thyn-ai.$name"
        status=$(printf '%s\n' "$runner_status" | awk -v k="$name" '$1==k{print $2}')
        pid=$(launchctl list "$label" 2>/dev/null | tail -1 | awk '{print $1}')
        alive=0
        if printf '%s' "$pid" | grep -qE '^[0-9]+$'; then alive=1; fi
        if [ "$status" = "offline" ] && [ "$alive" = "1" ]; then
            count=$(cat "$WEDGE_STATE.$name" 2>/dev/null || echo 0)
            count=$((count + 1))
            echo "$count" > "$WEDGE_STATE.$name"
            if [ "$count" -ge 2 ]; then
                log "RUNNER WEDGED: $name offline on GitHub but listener alive (PID $pid, $count consecutive checks) -- restarting"
                launchctl kickstart -k "system/$label" >> "$LOG" 2>&1
                rm -f "$WEDGE_STATE.$name"
            else
                log "RUNNER $name offline but alive (check $count/2) -- will restart if it persists"
            fi
        else
            rm -f "$WEDGE_STATE.$name" 2>/dev/null
        fi
    done
fi

exit 0
