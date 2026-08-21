#!/bin/bash
# docker_retry.sh — run a docker command with retry on transient DAEMON failures.
#
# WHY: the self-hosted macOS fleet drives amd64 container builds through Colima's
# dockerd; under parallel emulation load the daemon can wedge or die mid-job
# ('error waiting for container: unexpected EOF', exit 125). The fleet watchdog
# (fleet_watchdog.sh section 3b) and the guest systemd drop-in
# (docker.service.d/99-algenta-restart.conf, Restart=always, StartLimitBurst=0)
# heal the daemon within minutes; this wrapper makes CI steps WAIT for that
# healing and retry, instead of failing the job on infrastructure flake.
#
# Non-daemon failures (compile errors, script exits — any other code) fail
# immediately: retry must never mask a real error.
#
# Usage: bash .github/scripts/docker_retry.sh docker <args...>

TRANSIENT_RE='unexpected EOF|connection refused|context deadline|Cannot connect to the Docker daemon|docker\.sock|Internal Server Error for'

wait_health() { # $1 = budget seconds
    local budget="$1" t=0
    while [ "$t" -lt "$budget" ]; do
        docker info >/dev/null 2>&1 && return 0
        sleep 5; t=$((t + 5))
    done
    return 1
}

ATTEMPTS=3
rc=0
for attempt in $(seq 1 "$ATTEMPTS"); do
    out=$("$@" 2>&1)
    rc=$?
    printf '%s\n' "$out"
    [ "$rc" -eq 0 ] && exit 0
    transient=0
    [ "$rc" -eq 125 ] && transient=1
    printf '%s' "$out" | grep -qE "$TRANSIENT_RE" && transient=1
    if [ "$transient" -ne 1 ]; then
        echo "docker_retry: non-transient failure (rc=$rc) — not retrying" >&2
        exit "$rc"
    fi
    [ "$attempt" -eq "$ATTEMPTS" ] && break
    echo "docker_retry: transient daemon failure (rc=$rc), attempt $attempt/$ATTEMPTS — waiting up to 240s for daemon health" >&2
    if wait_health 240; then
        echo "docker_retry: daemon healthy — retrying" >&2
    else
        echo "docker_retry: daemon still unhealthy after 240s — retrying anyway" >&2
    fi
done
echo "docker_retry: exhausted $ATTEMPTS attempts (rc=$rc)" >&2
exit "$rc"
