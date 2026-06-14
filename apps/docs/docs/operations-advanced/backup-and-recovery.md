---
sidebar_position: 2
slug: /operations-advanced/backup-and-recovery
---

# Backup & Recovery

> **Warning**
> This section is for operators managing backup, restore, and disaster recovery. It is not required for first-time setup. Configure backups after initial deployment and validation.

## What each layer restores

| Layer | Restores |
| --- | --- |
| PostgreSQL | users, orgs, API-key metadata, run metadata, dataset metadata |
| MinIO / object storage | persisted large simulation outputs and stored result objects |
| Local source registry | uploaded datasets and local on-disk source files |

## PostgreSQL backup

```bash
mkdir -p backups
docker compose -f infra/docker/docker-compose.selfhosted.yml exec -T postgres \
  pg_dump -U algenta algenta > "backups/algenta-$(date +%Y%m%d-%H%M%S).sql"
```

## PostgreSQL restore

```bash
docker compose -f infra/docker/docker-compose.selfhosted.yml exec -T postgres \
  psql -U algenta -d algenta < backups/algenta-latest.sql
```

## Object storage backup

```bash
mkdir -p backups
docker run --rm \
  -v algenta_minio_data:/from \
  -v "$PWD/backups:/to" \
  alpine:3.20 sh -c 'tar czf /to/minio-data-$(date +%Y%m%d-%H%M%S).tgz -C /from .'
```

## Object storage restore

```bash
docker run --rm \
  -v algenta_minio_data:/to \
  -v "$PWD/backups:/from" \
  alpine:3.20 sh -c 'cd /to && tar xzf /from/minio-data-latest.tgz'
```

## Local source registry backup

```bash
mkdir -p backups
docker run --rm \
  -v algenta_sources_data:/from \
  -v "$PWD/backups:/to" \
  alpine:3.20 sh -c 'tar czf /to/sources-data-$(date +%Y%m%d-%H%M%S).tgz -C /from .'
```

## Local source registry restore

```bash
docker run --rm \
  -v algenta_sources_data:/to \
  -v "$PWD/backups:/from" \
  alpine:3.20 sh -c 'cd /to && tar xzf /from/sources-data-latest.tgz'
```

## Redis persistence

Redis runs with append-only persistence in the default Compose bundle. Treat the `algenta_redis_data` volume as persistent state and snapshot it if Redis durability matters for your deployment.

## Related pages

- [Upgrade & Rollback](/operations/upgrade-and-rollback)
- [Troubleshooting](/operations-advanced/troubleshooting)
