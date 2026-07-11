---
sidebar_position: 3
slug: /operations-advanced/troubleshooting
---

# Troubleshooting

If you use the standalone `docker-compose` CLI, substitute it for `docker compose` in the commands below.

## Docker is not reachable

```bash
docker info
```

Expected output:

- Docker server information is returned

Failure meaning:

- the Docker daemon is not running or the current context is wrong

Next action:

- start Docker or Colima, then rerun the command

## The stack did not start

```bash
docker compose -f infra/docker/docker-compose.selfhosted.yml ps
```

Expected output:

- `api`, `engine`, `postgres`, `redis`, and `minio` are present

Failure meaning:

- one or more services exited during startup

Next action:

- inspect `api` and `engine` logs first

## The API is not healthy

```bash
curl http://localhost:8000/v1/health
```

Expected output:

```json
{
  "status": "ok"
}
```

Failure meaning:

- the API is not ready or is failing during startup

Next action:

- inspect the API logs

## API startup is failing

```bash
docker compose -f infra/docker/docker-compose.selfhosted.yml logs --tail=200 api
```

Expected output:

- startup completes without repeated exceptions

Failure meaning:

- migrations, config, or app startup failed

Next action:

- fix the reported error, then restart the stack

## Engine jobs do not complete

```bash
docker compose -f infra/docker/docker-compose.selfhosted.yml logs --tail=200 engine
```

Expected output:

- Celery worker startup completes
- submitted jobs are processed

Failure meaning:

- the engine cannot start or cannot reach Redis/PostgreSQL

Next action:

- verify `REDIS_URL`, database connectivity, and restart the engine

## The bootstrap key was not created

```bash
docker compose -f infra/docker/docker-compose.selfhosted.yml exec -T api \
  python scripts/bootstrap_self_host.py
```

Expected output:

- `BOOTSTRAP_API_KEY_ID=...`
- `BOOTSTRAP_API_KEY_PREFIX=...`
- `BOOTSTRAP_API_KEY=...`

Failure meaning:

- bootstrap setup failed inside the API container

Next action:

- inspect API logs, then rerun bootstrap after the API is healthy

## Metrics returns 403

```bash
curl http://localhost:8000/metrics \
  -H "X-Metrics-Secret: YOUR_METRICS_SECRET"
```

Expected output:

- Prometheus text-format metrics

Failure meaning:

- `METRICS_SECRET` is missing, wrong, or not loaded by the API

Next action:

- set `METRICS_SECRET`, restart the API, and retry with the matching header

## Self-host validation fails

```bash
make self-host-status
make self-host-verify
```

Expected output:

- status checks pass
- smoke, persistence, install proof, and endpoint matrix complete

Failure meaning:

- the current deployment no longer matches the supported self-host contract

Next action:

- fix the failing stage, then rerun the same target until it passes
