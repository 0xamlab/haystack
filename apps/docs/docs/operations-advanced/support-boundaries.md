---
sidebar_position: 4
slug: /operations-advanced/support-boundaries
---

# Support Boundaries

| Area | Status |
| --- | --- |
| Single VM + Compose | ✅ Supported |
| API + Bundled Engine | ✅ Supported |
| Backup/Restore | ✅ Supported |
| SDK usage | ⚠️ Best effort / secondary |
| Kubernetes | ✅ Supported (Helm chart — see below) |
| UI/Portal | ❌ Not included |

## Kubernetes

A Helm chart is available at `infra/helm/algenta` in this repository, and is published as
an OCI artifact by this repository's CI on every merge to `main`. It charts the same
api + engine topology as the Compose install, with these conditions stated plainly rather
than glossed over:

- **api** is horizontally scalable by default, with one documented condition: scaling past
  1 replica requires explicitly acknowledging a real multi-writer caveat on the
  dataset-upload registry's shared volume. The chart will not let you scale past 1 replica
  without that acknowledgement — see the chart's own README for the exact toggle and why it
  exists.
- **engine** (the Celery worker + bundled Mojo runtime + agent runtime) is single-instance
  by design, matching the same constraint that already applies to this project's own
  hosted deployment. The chart enforces this at the schema and template level, not just by
  convention.
- Nodes running the engine must be `linux/amd64` with an x86-64-v3-capable CPU
  (AVX2/FMA/BMI2) — ARM64 is not supported.
- Chart signing (cosign) is not yet implemented. This is a known, tracked gap, not a
  silent omission — it is blocked on image-signing infrastructure that does not exist in
  this repository yet.
