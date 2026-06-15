#!/bin/bash
# Supervises the two co-located engine processes on the Fly `codna-engine` Machine:
#   1) the agent-core sidecar (Bun) on 0.0.0.0:8787, and
#   2) the Celery worker (Python) consuming persist,simulate,repository.
# They share /home/app/.algenta (the Fly volume) — the worker materializes the repo working_dir
# and the sidecar mutates it. If either process exits, we tear the other down and exit non-zero so
# Fly restarts the whole Machine (never a half-dead engine).
set -euo pipefail

SIDECAR_PID=""
WORKER_PID=""

term() {
  [ -n "$SIDECAR_PID" ] && kill -TERM "$SIDECAR_PID" 2>/dev/null || true
  [ -n "$WORKER_PID" ] && kill -TERM "$WORKER_PID" 2>/dev/null || true
}
trap term TERM INT

# 1) agent-core sidecar (Bun) — binds 0.0.0.0:8787 (reachable at codna-engine.internal:8787 from the
#    api app, and at localhost:8787 from the co-located worker).
( cd /app/agent-core && exec bun run-server.mjs ) &
SIDECAR_PID=$!

# 2) Celery worker — NOTE the repository queue (the prod worker CMD historically omitted it).
( cd /app && exec python -m celery -A apps.worker.tasks.simulation_task:celery_app worker \
    --loglevel=INFO \
    --queues=persist,simulate,repository \
    --concurrency="${CELERY_CONCURRENCY:-2}" ) &
WORKER_PID=$!

# Exit as soon as either child dies; Fly restarts the Machine.
wait -n "$SIDECAR_PID" "$WORKER_PID"
term
wait 2>/dev/null || true
exit 1
