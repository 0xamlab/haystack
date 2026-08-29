# Algenta Helm chart

Deploys the same two-container topology `infra/docker/docker-compose.selfhosted.yml` ships
for self-hosted Algenta:

- **api** — the FastAPI server. Horizontally scalable, with one documented caveat (below).
- **engine** — the Celery worker + bundled Mojo runtime + agent runtime, built from
  `Dockerfile.engine.prod`. Genuinely single-instance. There is no separate "worker"
  workload in this chart — `Dockerfile.worker.prod` exists in the repo but is not part of
  the shipped self-host topology this chart follows.

Status labels used throughout this document match the rest of this program's discipline:
**Available now** (built and exercised in CI), **Validated** (checked with a real kind
cluster), **Not yet implemented** (documented so, not silently assumed).

## Install

```bash
helm install algenta infra/helm/algenta \
  --set api.image.tag=git-XXXXXXX \
  --set engine.image.tag=git-XXXXXXX \
  --set config.apiPublicBaseUrl=https://algenta.example.com \
  --set externalDatabase.host=postgres.example.internal \
  --set externalDatabase.existingSecret=algenta-external-database \
  --set externalRedis.host=redis.example.internal \
  --set externalObjectStore.endpointUrl=https://s3.example.com \
  --set externalObjectStore.existingSecret=algenta-external-objectstore
```

`api.image.tag` / `engine.image.tag` are **required** (no floating-tag default — mirrors
`ALGENTA_IMAGE_TAG:?` in `docker-compose.selfhosted.yml` and the same
`tests/test_image_pin_guard.py` rule). Pin to a `git-<sha>` tag published by this repo's
`build` CI job, or a digest.

By default this chart is **external-dependency-first**: `externalDatabase.enabled`,
`externalRedis.enabled`, and `externalObjectStore.enabled` all default to `true`, and each
one requires you to point it at something real (a `host`/`url` plus an `existingSecret` for
credentials) — `helm install`/`helm template` fails fast with a clear message if you enable
one without configuring it, rather than silently deploying against nothing. See "External
dependencies" below for the full toggle contract, and "Quick trial" for the fastest path
that skips all of this.

## Quick trial (bundled Postgres/Redis/MinIO)

For a local trial only — see "Why minimal in-chart templates instead of Bitnami subcharts"
below for why these are not production-grade:

```bash
helm install algenta infra/helm/algenta \
  --set api.image.tag=git-XXXXXXX \
  --set engine.image.tag=git-XXXXXXX \
  --set config.apiPublicBaseUrl=http://localhost:8000 \
  --set externalDatabase.enabled=false --set postgresql.enabled=true \
  --set externalRedis.enabled=false --set redis.enabled=true \
  --set externalObjectStore.enabled=false --set minio.enabled=true \
  --set config.resultStorageEnabled=false
```

(`config.resultStorageEnabled=false` sidesteps that the bundled MinIO template does not
auto-create its results bucket — see `templates/bundled/minio.yaml`'s header comment.)

## The `api.replicaCount` / `persistence.sources` tradeoff — read this before scaling the API

`api.replicaCount` defaults to **1**. This is not caution for its own sake; it is because of
one real, currently-unresolved gap confirmed directly in this repo's source:
`apps/api_server/services/source_registry.py` (the dataset-upload registry backing
`ALGENTA_SOURCES_DIR` and the `/v1/data` query surface) does plain, unlocked
`pathlib.Path` file I/O against a shared volume — no S3/object-store awareness, and no
concurrency control. This is unlike Repository Intelligence artifacts, which **have**
migrated to S3 (opt-in via `ALGENTA_RI_OBJECT_STORE=s3`); the dataset registry has not.

This chart mirrors `docker-compose.selfhosted.yml` exactly: **one** PersistentVolumeClaim
(`persistence.sources`) mounted at `/home/app/.algenta` on the engine Pod (always, when
`engine.enabled`) and on every api Pod (when `persistence.sources.enabled`, the default).
That one root holds two logically different things:

- `.../sources` — the dataset registry (the multi-writer hazard described above).
- `.../runtime` — device identity, license, audit, and metering state
  (`apps/runtime/*`), read by **both** api and engine process code paths.

Sharing one volume is deliberate, not incidental: it is what gives every api replica and
the engine the same device identity and the same dataset registry. The tradeoff is that
scaling `api.replicaCount` past 1 means multiple api Pods writing to that same registry
concurrently.

**This chart will not let you set `api.replicaCount > 1` (or `api.autoscaling.maxReplicas >
1`) unless you also set:**

```yaml
persistence:
  sources:
    accessMode: ReadWriteMany
    acknowledgeMultiWriterRisk: true
```

This is enforced twice — once in `values.schema.json` (`allOf`/`if`/`then`), once in
`templates/_helpers.tpl`'s `algenta.validateValues` (a clearer, human-readable `fail`
message) — so it holds even if one enforcement path is ever bypassed.

**Do not set `acknowledgeMultiWriterRisk: true` unless one of these is actually true for
your deployment:**

1. Your StorageClass is genuinely ReadWriteMany-capable (e.g. NFS-backed, or a CSI driver
   with real RWX support) **and** you accept that concurrent writers to the dataset
   registry are unlocked — a real (if narrow) data-race risk until upstream fixes
   `source_registry.py`, or
2. You never use the dataset-upload / `/v1/data` feature at all, in which case the shared
   directory only ever holds the runtime/device-identity files, which are effectively
   read-heavy and far lower risk under concurrent access.

**A subtler point Kubernetes' own docs make but is easy to miss:** `ReadWriteOnce` is a
**single-node**, not a single-Pod, constraint — multiple Pods on the *same* node can mount
an RWO volume concurrently. That means even with the default `api.replicaCount: 1`, this
chart still puts **two** Pods (the one api Pod and the one engine Pod) on the same shared
RWO volume. On a genuinely single-node cluster (common for a "Single VM"-tier self-hosted
install, e.g. k3s) this is automatically safe. On a multi-node cluster it is only safe if
the scheduler happens to place both Pods on the same node — not guaranteed. If you run a
multi-node cluster and stay at the default `api.replicaCount: 1`, either add node affinity
pinning the api and engine Pods together, or switch to an RWX-capable StorageClass anyway.
This chart does not attempt to auto-pin them for you (a wrong guess at your topology is
worse than no guess), so treat it as an explicit, "your call" step.

**This is not claimed as an unconditional "the API is horizontally available" — it is
horizontally available *conditionally*, exactly as described above.**

## The engine's single-instance constraint

`engine.replicaCount` is pinned to the literal value `1` — not a default, a ceiling.
Confirmed multiple independent ways in this repo, unrelated to anything else that has
changed recently:

- `Dockerfile.engine.prod`'s own header: the Celery worker and the bundled agent runtime
  share one filesystem contract and "must run in one container".
- `fly.engine.toml`: "keep count at 1 (no scale-to-zero) ... Do NOT scale >1 (one volume,
  one Machine)".
- `.github/workflows/deploy.yml` enforces `flyctl scale count 1` at deploy time.
- `gitbook/self-hosting.md` has an explicit danger callout about this.

Enforced three ways here: `values.schema.json` pins `engine.replicaCount` to `const: 1`;
`algenta.validateValues` fails the render if it is ever anything else; and
`templates/engine-deployment.yaml` **hardcodes** `replicas: 1` and
`strategy.type: Recreate` regardless of the values file, so even an edited/forced values
file cannot produce a rolling update that briefly runs two engine Pods against the same RWO
volume. There is deliberately no PodDisruptionBudget for the engine (see
`templates/api-pdb.yaml`'s header comment) and no HPA — neither concept helps a
single-replica-by-construction workload.

## Mojo / CPU architecture requirement

Every Mojo build in this repo is pinned to **x86-64-v3** (AVX2/FMA/BMI2) and
`platforms: linux/amd64` — ARM64 is explicitly, unambiguously unsupported. This chart sets
`engine.nodeSelector: {kubernetes.io/arch: amd64}` by default, which guarantees the ISA
**family** but not the microarchitecture **level** — a `linux/amd64` node could still lack
AVX2/FMA/BMI2 on older hardware.

**Recommended production hardening (not a default):** if your cluster runs
[Node Feature Discovery](https://kubernetes-sigs.github.io/node-feature-discovery/), add a
stronger node selector/affinity on `feature.node.kubernetes.io/cpu-cpuid.AVX2` (and
`...BMI2`/`...FMA3` if you want to be exhaustive) to `engine.nodeSelector` or
`engine.affinity`. This is not the chart default because NFD is not installed on every
cluster, and defaulting to a label that does not exist would make the engine unschedulable
everywhere NFD is absent.

## Mojo worker pool sizing (`config.mojoPoolSize`) — set this before deploying to a real cluster

Found live while validating this chart against a real `kind` cluster, not a theoretical
concern: `apps/api_server/compute/mojo_pool.py` sizes its Mojo subprocess worker pool as
`max(1, os.cpu_count() - 1)` **unless** `MOJO_POOL_SIZE` is set. `os.cpu_count()` reads the
**node's** total CPU count, not this container's `resources.limits.cpu` / cgroup quota — on
an 8-vCPU node this spawns 7 Mojo subprocess workers **per** uvicorn worker
(`Dockerfile.api.prod` runs `--workers 2`, so 14 Mojo subprocesses total) regardless of how
small a CPU limit you set on the Pod. Left unset on a CPU-limited Pod, this oversubscribes
badly enough that the api Pod can fail its own readiness probe (the DB check inside
`/v1/health/ready` starves for CPU and never completes) — this is exactly what happened
during this chart's own `kind`-cluster validation before `config.mojoPoolSize` was added.

`config.mojoMaxConcurrent` (`MOJO_MAX_CONCURRENT`) is **not** the same knob — it is a
`apps/api_server/config.py` field kept only for parity with
`docker-compose.selfhosted.yml`, and as of this chart's writing is not read anywhere else in
the codebase. **Set `config.mojoPoolSize` explicitly**, sized to fit
`api.resources.limits.cpu` (e.g. `limits.cpu - 1`, floor `1`) — this chart intentionally does
not compute a default for you: Helm renders manifests before the container ever sees its own
cgroup, so any default this chart guessed would work for some node/limit combinations and
silently misbehave for others.

## External dependencies

External-first by default, per this program's stated preference. The app layer already
takes these as plain env vars with no hardcoded compose-network hostnames
(`apps/api_server/config.py`: `database_url`, `database_url_sync`, `redis_url`,
`s3_endpoint_url`, `s3_bucket_name`, `s3_access_key_id`, `s3_secret_access_key`,
`s3_region`) — what this chart adds is the deployment-artifact-level toggle between
"bring your own managed instance" and "bundle a minimal one for a trial", Bitnami-subchart
style:

| Toggle | Default | Bundled alternative |
| --- | --- | --- |
| `externalDatabase.enabled` | `true` | `postgresql.enabled` |
| `externalRedis.enabled` | `true` | `redis.enabled` |
| `externalObjectStore.enabled` | `true` | `minio.enabled` |

Exactly one of each pair must be `true` — both or neither fails the render
(`algenta.validateValues`). Passwords/access keys for the external path are always taken
from an `existingSecret` you manage (never a plaintext value in `values.yaml`), except when
you pass a full connection URL with embedded credentials (`externalDatabase.url` /
`externalRedis.url`), which bypasses the discrete host/port/existingSecret fields entirely.

### Why minimal in-chart templates instead of Bitnami subcharts

`postgresql.enabled` / `redis.enabled` / `minio.enabled` render this chart's **own** tiny
templates (`templates/bundled/*.yaml`), not `dependencies:` entries pulling in the Bitnami
postgresql/redis charts. Tradeoff, stated plainly:

- **What you lose**: replication, connection pooling (pgbouncer), automated backups, Redis
  Sentinel/cluster modes, MinIO distributed/erasure-coded mode — everything a real Bitnami
  subchart gives you for production use.
- **What you gain**: `helm dependency build` needs no network access to a chart
  repository, which keeps the PR-triggered `helm-lint` CI job (and any air-gapped install)
  fully offline; the chart's own supply chain stays self-contained (no upstream chart
  version to track/audit); and the bundled path is explicitly documented and positioned as
  **trial-only**, so there is no risk of an operator mistaking it for a production-grade
  managed database.

If you need a bundled dependency for anything beyond a quick trial or CI smoke test, run
your own Postgres/Redis/MinIO Helm release alongside this one (or use the Bitnami charts
directly) and point `externalDatabase`/`externalRedis`/`externalObjectStore` at it.

## Prometheus scraping

`/metrics` exists (`apps/api_server/main.py`) but is **not** an open Prometheus endpoint: it
403s any request that is neither loopback nor carrying a matching `X-Metrics-Secret` header
(see that route's own code). Setting `api.metrics.enabled=true` adds
`prometheus.io/scrape`/`port`/`path` annotations to the api Pods, but a scrape from a
**different** Pod (any real Prometheus) still needs:

1. `api.metrics.existingSecret` set (a Secret with your chosen key holding the
   `METRICS_SECRET` value), and
2. your scrape config sending that **same** value back as the `X-Metrics-Secret` header —
   plain `prometheus.io/scrape` annotation-based discovery does not support custom headers.
   With prometheus-operator (>= v0.68), configure a `ServiceMonitor` with
   `spec.endpoints[].headers` set to `X-Metrics-Secret: <value>` (or the equivalent
   `metricRelabelings`/scrape-config mechanism for your Prometheus setup).

Leaving `api.metrics.existingSecret` unset leaves `METRICS_SECRET` unset at the app layer,
which means `/metrics` is loopback-only — safe, but not scrapeable from outside the Pod.

## Structured logging

No new logging mode was invented for this chart. The app already emits structured JSON
logs whenever `API_ENV` is not `development` (`apps/api_server/app_support.py`'s
`configure_logging`, using `structlog.processors.JSONRenderer`) — this chart's
`config.apiEnv` defaults to `production`, so JSON logs are the out-of-the-box behavior with
no extra configuration.

## Security defaults

- Every workload's Pod runs as non-root (`runAsNonRoot: true`, fixed non-root UID/GID),
  `seccompProfile: RuntimeDefault`, `allowPrivilegeEscalation: false`, and every Linux
  capability dropped.
- `readOnlyRootFilesystem` is **not** enabled by default on api/engine — the app was not
  audited for every incidental write path outside `/home/app/.algenta` and `/tmp` (both of
  which already have their own volumes/mounts here), so this chart does not claim a
  guarantee it has not verified. Override `api.securityContext.readOnlyRootFilesystem` /
  `engine.securityContext.readOnlyRootFilesystem` yourself if you have verified it works
  for your image build.
- `automountServiceAccountToken: false` on every ServiceAccount this chart creates — neither
  workload talks to the Kubernetes API.
- NetworkPolicies (`api.networkPolicy.enabled` / `engine.networkPolicy.enabled`, both off by
  default) restrict engine ingress to api Pods only, and leave external egress open (their
  own header comments explain why — external datastore addresses are not known to the
  chart ahead of time).
- No Secret this chart renders is ever committed or baked into the chart itself — see
  `templates/secret.yaml`'s header, and prefer `secrets.existingSecret` /
  `external*.existingSecret` for anything beyond a quick trial.

## Supply chain — what this PR does NOT do

**Cosign-signing the packaged chart is explicitly out of scope for this PR.** No
supply-chain signing infrastructure exists anywhere in this repository yet — verified
directly: `scripts/supply_chain/` does not exist, and the only cosign-related artifact
anywhere is one deferred-signing comment in
`.github/actions/image-sbom-scan/action.yml`. Signing the chart is blocked on that
image-signing infrastructure being built first, which is a separate, larger initiative.
The chart **is** pushed as an OCI artifact to the same registry the container images use
(see `.github/workflows/ci.yml`'s `helm-oci-push` job) — it is simply not signed yet.

## What was and was not verified with a real `kind` cluster

**Validated** with a real `kind` cluster (see `.github/workflows/ci.yml`'s
`helm-kind-smoke` job, PR-triggered):

- `helm install` of this chart with `engine.enabled=false` and the bundled
  Postgres/Redis/MinIO templates all enabled.
- The real API image (built the same way `api-image-mojo-smoke` already does — locally,
  from `Dockerfile.api.prod`, no registry push) reaches `Running`/`Ready`.
- `GET /v1/health` (liveness) and `GET /v1/health/ready` (readiness, which genuinely pings
  the bundled Postgres) both return `200` through the api Service.
- The `helm test` hooks (`templates/tests/test-api-health.yaml`) pass against the live
  release.

This is also exactly how the `MOJO_POOL_SIZE`/CPU-oversubscription issue described above was
found: the first two attempts at this smoke test both timed out with the api Pod never
reaching `Ready`, and `kubectl describe`/logs against a *real* cluster (not `helm template`
output, which cannot see runtime behavior) showed the actual cause — a schema/lint-only
validation approach would never have caught this.

**Not validated** in CI, documented rather than silently assumed:

- **The engine workload end-to-end**, including an actual `/v1/simulate` or repository
  "engine simulate" call processed by the Celery worker. Building a real engine image
  requires `infra/docker/Dockerfile.engine.prod`'s private
  `ghcr.io/thyn-ai/codna/sidecar` base image and `CODNA_GHCR_READ_TOKEN` — neither
  available to a PR-triggered, no-registry-credential validation job. This mirrors the
  exact same boundary the pre-existing `api-image-mojo-smoke` CI job already respects (it
  also only builds the API image, never the engine image, on a PR). The
  `templates/tests/test-engine-health.yaml` helm-test hook exists and is exercised whenever
  `engine.enabled=true` against a *real* engine image outside of CI (e.g. a developer
  running `helm test` after a manual `helm install` with real credentials) — it is simply
  not part of the automated, credential-free CI path.
- Multi-node RWX behavior for `persistence.sources` when `api.replicaCount > 1` — `kind`
  in this CI job runs a single-node cluster, so the RWX-vs-same-node-RWO distinction
  described above is documented, not exercised by an automated test.
- A ReadWriteMany StorageClass in general — `kind`'s default `local-path` StorageClass is
  RWO-only, so the `api.replicaCount > 1` path is schema/template-validated (via the
  `helm-lint` job's `ci/values-lint.yaml` overlay, which sets `accessMode: ReadWriteMany`
  purely at the manifest level) but not proven against a real RWX volume.
- Cosign chart signing (see above — out of scope for this PR, not merely untested).
