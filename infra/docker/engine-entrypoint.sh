#!/bin/bash
# Supervises the two co-located processes in the Algenta engine image:
#   1) the bundled agent runtime (Bun) on 0.0.0.0:8787, and
#   2) the Celery worker (Python) consuming persist,simulate,repository.
# They share /home/app/.algenta: the worker materializes the repo working_dir and the agent runtime
# mutates it. If either process exits, the container exits non-zero so the runtime restarts the
# complete engine instead of leaving a half-dead service.
set -euo pipefail

SIDECAR_PID=""
WORKER_PID=""

term() {
  [ -n "$SIDECAR_PID" ] && kill -TERM "$SIDECAR_PID" 2>/dev/null || true
  [ -n "$WORKER_PID" ] && kill -TERM "$WORKER_PID" 2>/dev/null || true
}
trap term TERM INT

# 1) Bundled agent runtime (Bun), reachable on port 8787 from the API and on loopback from the worker.
( cd /app/agent-core && exec bun run-server.mjs ) &
SIDECAR_PID=$!

# 2) Celery worker — NOTE the repository queue (the prod worker CMD historically omitted it).
( cd /app && exec python -m celery -A apps.worker.tasks.simulation_task:celery_app worker \
    --loglevel=INFO \
    --queues=persist,simulate,repository \
    --concurrency="${CELERY_CONCURRENCY:-2}" ) &
WORKER_PID=$!

# Exit as soon as either child dies so the container is restarted as one unit.
wait -n "$SIDECAR_PID" "$WORKER_PID"
term
wait 2>/dev/null || true
exit 1
