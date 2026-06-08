---
sidebar_position: 4
slug: /operations/upgrade-and-rollback
---

# Upgrade & Rollback

Pin image tags for every release. Validate the stack after every change.

## Upgrade

1. Update `ALGENTA_IMAGE_TAG` in `.env`.
2. Pull and restart the stack.
3. Run migrations.
4. Verify health and the self-host gates.

```bash
docker compose -f infra/docker/docker-compose.selfhosted.yml pull
docker compose -f infra/docker/docker-compose.selfhosted.yml up -d
docker compose -f infra/docker/docker-compose.selfhosted.yml exec -T api \
  python -m alembic -c apps/api_server/alembic.ini upgrade head
curl http://localhost:8000/v1/health
make self-host-status
make self-host-verify
```

## Rollback

1. Set `ALGENTA_IMAGE_TAG` back to the previous known-good release.
2. Restart the stack.
3. Verify health.

```bash
docker compose -f infra/docker/docker-compose.selfhosted.yml up -d
curl http://localhost:8000/v1/health
```

If the failed release changed persisted data in a way that must be reverted, restore the matching PostgreSQL and MinIO backups.

## Related pages

- [Operations](/operations)
- [Backup & Recovery](/operations-advanced/backup-and-recovery)
- [Logs & Metrics](/operations/logs-and-metrics)
