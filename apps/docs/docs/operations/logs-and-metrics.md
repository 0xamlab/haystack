---
sidebar_position: 3
slug: /operations/logs-and-metrics
---

# Logs & Metrics

Use these commands to inspect the running service after install and after each upgrade.

## Stack status

```bash
docker compose -f infra/docker/docker-compose.selfhosted.yml ps
```

Expected output:

- `api` is `running` or `healthy`
- `worker` is `running`
- `postgres`, `redis`, and `minio` are `running`

Failure meaning:

- a core service exited or never started

Next action:

- inspect the API and worker logs

## API logs

```bash
docker compose -f infra/docker/docker-compose.selfhosted.yml logs -f api
```

Expected output:

- FastAPI startup completes
- no repeated crash loop

Failure meaning:

- the API is failing during startup, migrations, or request handling

Next action:

- fix the reported error, then restart the stack

## Worker logs

```bash
docker compose -f infra/docker/docker-compose.selfhosted.yml logs -f worker
```

Expected output:

- Celery worker starts
- job execution logs appear when `/v1/jobs` is used

Failure meaning:

- the async job path is not running

Next action:

- verify Redis connectivity and restart the worker

## Health endpoint

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

- the API is unavailable or not ready

Next action:

- inspect API logs and container status

## Metrics endpoint

From the same host:

```bash
curl http://localhost:8000/metrics
```

From a remote scraper:

```bash
curl http://localhost:8000/metrics \
  -H "X-Metrics-Secret: YOUR_METRICS_SECRET"
```

Expected output:

- Prometheus text-format metrics

Failure meaning:

- `403` means remote scraping is enabled but `METRICS_SECRET` is missing or wrong

Next action:

- set `METRICS_SECRET` and retry with the matching header

## Validation gates

Run these checks after install and after each release:

```bash
make self-host-status
make self-host-verify
```

## Related pages

- [Operations](/operations)
- [Upgrade & Rollback](/operations/upgrade-and-rollback)
- [Troubleshooting](/operations-advanced/troubleshooting)
