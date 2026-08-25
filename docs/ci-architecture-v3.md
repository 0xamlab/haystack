# CI Architecture v3 — Ephemeral, Intelligence-Driven Build Fleet

Status: design proposal (no workflow changes in this document's accompanying commit).
Scope: `thyn-ai/algenta` CI/CD, org runner fleet, GCP project `eplanev2`.

## 1. Executive summary

CI v3 replaces the persistent-runner-plus-shared-VM topology with two ephemeral
build planes plus a minimal static residue:

| Plane | Technology | Replaces |
|---|---|---|
| Linux (amd64) | Per-job ephemeral GCE VMs, native x86_64, `--ephemeral` GitHub runners | The shared Colima/qemu VM for all `linux/amd64` work |
| macOS (arm64) | Per-job Tart VMs orchestrated by Orchard on the Apple host | 4 of the 5 static launchd runners |
| Residue | 1–2 static bare-metal macOS runners | — (release signing, Metal toolchain legs, break-glass) |

Three properties define the target state:

1. **No shared mutable daemon.** Every job gets its own kernel (Linux plane) or
   its own VM (macOS plane). Docker daemons, port spaces, and disks are
   job-private by construction.
2. **Native execution everywhere.** The emulation-bound legs (linux wheel builds:
   37 min under qemu today; amd64 image builds; CUDA/ROCm compile gates) move to
   native amd64 hardware — an expected 3–5× wall-clock recovery, measured in the
   Phase 1 pilot.
3. **Intelligence gates the work.** The existing codna blast-radius engine
   (`scripts/test_impact.py`, `scripts/adaptive_codeql_scope.py`) is promoted
   from observed to gating on PRs, extended to shard-selective Mojo runtime
   rebuilds, and used to skip CI legs a diff cannot influence. Every ambiguity
   degrades to running more, never less.

## 2. Current state — topology and measured telemetry

Topology (as of 2026-08-24):

- 5 org-level self-hosted runners (`thyn-mac-arm64`, `-2` … `-5`), macOS arm64,
  labels `["self-hosted","thyn-mac"]` (org variable `RUNNER_LABELS`), installed
  as launchd services on one host. All workflow jobs select runners via
  `runs-on: ${{ fromJSON(vars.RUNNER_LABELS) }}`.
- One shared Colima VM (Ubuntu 24.04, 12 vCPU / 32 GB) serves **all**
  `linux/amd64` container work for every runner, via qemu emulation.
- Repo intelligence already in production: codna reverse-import blast radius for
  test selection (observed mode in `ci.yml`) and adaptive CodeQL scoping
  (`#851`/`#862`); kernel-inventory ratchets; `infra/fleet/fleet_reaper.sh`
  watchdog (60 s LaunchAgent: zombie-worker reap, idle-listener restart with
  300 s grace, fail-closed on API errors).

Measured job telemetry (GitHub Actions API, 2026-08-24/25):

| Job | Duration | Notes |
|---|---|---|
| `ci.yml` Test (Python 3.14) | 7–9 min | pytest graph + 3 service containers + Mojo filtered worker |
| `ci.yml` API image Mojo smoke | 2–5 min | amd64 image build under qemu + server-mode proof |
| `ci.yml` Build & Push (3 images) | ~45 min build-minutes | registry-cached buildx, per-run builder |
| `build-runtime` macOS arm64 leg | 16–18 min | native Metal-toolchain shard build |
| `build-runtime` linux x86_64 leg | **37 min** | qemu emulation; shard timeout budget 2700 s vs 900 s hosted-native |
| `build-runtime` CUDA compile gate | 24–33 min | qemu emulation |
| `build-runtime` clean-machine contract | 1–5 min | qemu |
| `sdk-audit` full execution sweep | 17–18 min | native shard build + sweep; postgres in Colima |
| `code-coverage` unit graph | ≤25 min budget | pixi + pytest-cov |
| Queue wait sample | ~9 min | run created → first job started, 5/5 runners busy |

Reliability sample, `ci.yml`, last 30 runs: **2 success / 6 failure / 18
cancelled / 4 in flight** (2026-08-24/25). Observed failure classes attributed
to the shared-VM topology: dockerd instability under parallel container load,
image-store disk pressure, fixed host-port collisions between concurrent runs,
qemu throughput, listener processes that hold jobs without dispatching workers,
and worker processes that survive their run's cancellation.

Shard-build facts (inputs to §9.2):

- Runtime library inventory: **643 executable Mojo modules** → 27 shards at the
  current shard size 24 (`scripts/build_runtime_shards.py`, deterministic sorted
  chunking; shard map `runtime-shards.json`).
- A single 24-module shard compile has been measured at up to ~11 GiB peak
  footprint; the builder enforces per-shard timeout + footprint ceilings and
  emits named diagnostics on kill.

## 3. Job → platform-need map

Every job in `.github/workflows/*` classified by its true requirement.
"docker-needed" = needs a container runtime for services or image builds;
"mac-native" = needs the Apple host itself (release signing, Secure Enclave
helper codesign, Metal toolchain, or bare-metal performance guarantees);
"linux-native" = plain Linux userspace, no containers; "gpu-needed" = none —
both GPU lanes are compile gates (NVPTX/AMDGPU backends ship in the pinned Mojo
toolchain; no GPU hardware or CUDA/ROCm toolkit is required to compile them).

| Workflow | Job | Trigger | Docker today | True need | v3 plane |
|---|---|---|---|---|---|
| ci.yml | Test | PR + push | yes (postgres/dragonfly/minio) | docker-needed | Linux ephemeral |
| ci.yml | SDK artifact install (py) | PR + push | no | linux-compatible (python wheel) | Linux ephemeral |
| ci.yml | TS SDK artifact install ×3 | PR + push | no | linux-compatible (node) | Linux ephemeral |
| ci.yml | API image Mojo smoke | PR | yes (amd64 build+run) | docker-needed, amd64 | Linux ephemeral |
| ci.yml | Build & Push Docker (api/worker/engine) | main push | yes (buildx amd64) | docker-needed, amd64 | Linux ephemeral |
| ci.yml | Deploy to Fly (codna-api) | main push | yes (pull/tag/push mirror) | docker CLI or registry tooling | Linux ephemeral |
| ci.yml | Deploy to Fly (control-plane) | main push | yes (mirror) | docker CLI or registry tooling | Linux ephemeral |
| code-coverage.yml | Python coverage report | PR + push (paths: python surface), weekly | no | linux-native (pixi/pytest) | Linux ephemeral |
| codeql.yml | CodeQL ×3 languages | PR + push + weekly | no | linux-native (analysis DBs) | Linux ephemeral |
| sdk-audit.yml | gap-checks | PR + push | no | linux-native (python) | Linux ephemeral |
| sdk-audit.yml | execution-sweep | main push | yes (postgres only) | mac shard build + docker service | macOS ephemeral, docker baked in (§5.4) |
| sdk-audit.yml | published-artifact-proof | main push | no | linux-compatible | Linux ephemeral |
| build-runtime.yml | macOS arm64 leg | main push (runtime paths) | no | **mac-native** (Metal toolchain, codesign, SE helper) | Static bare-metal residue |
| build-runtime.yml | linux x86_64 leg | main push (runtime paths) | yes (amd64 container) | linux-native, amd64 | Linux ephemeral |
| build-runtime.yml | CUDA compile gate | after linux leg | yes (amd64 container) | linux-native, amd64 | Linux ephemeral |
| build-runtime.yml | clean-machine contract | after builds | yes (amd64 container) | linux-native, amd64 | Linux ephemeral |
| build-runtime.yml | publish-pypi | after contract | no | linux-native (twine) | Linux ephemeral |
| build-runtime-bundle.yml | bundle darwin-arm64 | tag/dispatch | no | **mac-native** | Static residue |
| build-runtime-bundle.yml | bundle linux-x64 | tag/dispatch | yes (amd64 container) | linux-native, amd64 | Linux ephemeral |
| build-runtime-bundle.yml | release | tag | no | linux-native | Linux ephemeral |
| build-mojo.yml | Build & push Mojo image | manual | yes (binfmt + buildx amd64) | docker-needed, amd64 | Linux ephemeral |
| amd-rocm-gate.yml | compile gate | manual | yes (amd64 container) | linux-native, amd64 | Linux ephemeral |
| tpm.yml | swtpm round-trip | PR + push (paths) | yes (amd64 container) | linux-native, amd64 | Linux ephemeral |
| deploy.yml | Deploy to Fly (manual) | manual | yes (mirror) | docker CLI or registry tooling | Linux ephemeral |
| docs-audit.yml | audit | PR + push (docs paths) | no | linux-native (python) | Linux ephemeral |
| release-sdks.yml | guard / build / publish-testpypi / publish-pypi / sdk-release | tag/dispatch | no | linux-compatible (python+node) | Linux ephemeral |
| sync-public-sdk.yml | sync | main push (sdk paths) | no | linux-compatible | Linux ephemeral |
| publish-mcp.yml | publish | release/dispatch | no | linux-compatible (OIDC) | Linux ephemeral |
| windows-availability-probe.yml | probe | daily + manual | no | any (network probes) | macOS ephemeral |

Summary: **2 of 33 jobs are mac-native** (release macOS legs). The remaining 31
are linux-native or docker-needed and run on arm64 macOS today only because no
linux capacity exists (GitHub-hosted runners are unavailable for this org).

Org-level dynamic workflows (Dependabot, Dependency Graph, org CodeQL config,
Code Coverage agent) are managed outside this repo and inherit whatever runner
labels the org assigns; the label scheme in §5 keeps a `code-scanning` label
available for them.

## 4. Target architecture

```
                        GitHub Actions (thyn-ai)
                                   │
        ┌──────────────────────────┼──────────────────────────────┐
        │                          │                              │
  label thyn-mac-static      label gcp-linux-ephemeral     label thyn-mac
  (1–2 bare-metal runners)   (per-job GCE VMs, us-central1)  (per-job Tart VMs,
        │                          │                          Orchard on the host)
   Metal legs, release        docker services, buildx,       pytest graph, sdk legs,
   signing, SE helper,        native amd64 shard builds,     codeql, docs audits,
   break-glass                CodeQL DBs, coverage           probes
        │                          │                              │
        │                     ┌────┴─────┐                   ┌────┴─────┐
        │                     │ VM bakery │                  │ Tart OCI  │
        │                     │ (GCE image│                  │ VM images │
        │                     │ w/ runner)│                  │ (GHCR)    │
        │                     └────┬─────┘                   └────┬─────┘
        │                          │                              │
        └────────────┬─────────────┴──────────────────────────────┘
                     │
            GCS cache buckets (rattler, pip, pnpm, mojo shard objects)
            GHCR buildcache refs (buildx registry cache, unchanged)
```

Selection model: jobs keep using a `runs-on` variable
(`vars.RUNNER_LABELS` for the macOS pool; new `vars.RUNNER_LABELS_LINUX` for
the linux pool), so planes are switched by variable, never by per-job edits,
and a repo-level flag variable gates the rollout per phase (§11).

## 5. Linux plane — ephemeral native-amd64 builders on GCP

### 5.1 Design

- **Golden image**: Ubuntu 24.04 GCE image, baked by a scheduled/CI job,
  containing: Docker CE + buildx, Python 3.14, Node 22 + pnpm, pixi, gcloud,
  the GitHub Actions runner application pre-staged, and warm rattler/pip caches.
  Image versions are pinned and job logs record which image ran.
- **Runner registration**: ephemeral, one job per VM. Registration uses
  GitHub's just-in-time runner REST API (a short-lived, single-use
  registration config), minted by the orchestrator at spawn time — no
  long-lived registration tokens stored on shared hosts. The runner starts with
  `--ephemeral --disableupdate`; runner-application updates are baked into the
  image on schedule (GitHub blocks job dispatch to runners >30 days outdated,
  so the bakery cadence is weekly).
- **Orchestrator**: one small always-on VM (e2-small class) in `eplanev2`
  us-central1 running a poll loop:
  1. list `queued` jobs for the org whose label set includes
     `gcp-linux-ephemeral` (GitHub REST),
  2. for each, create one GCE instance from the golden image whose startup
     script registers the ephemeral runner and execs it,
  3. the instance carries a shutdown script: after the runner process exits
     (job done — guaranteed by `--ephemeral`), the VM deletes itself
     (`gcloud compute instances delete --quiet` via attached service account).
  A watchdog sweep deletes any builder VM older than its job timeout + grace,
  and a floor/ceiling caps concurrent VMs (default: 0–16) inside the verified
  quota envelope.
- **GitHub's contract honored**: ephemeral runners are GitHub's recommended
  autoscaling primitive ("GitHub recommends implementing autoscaling with
  ephemeral self-hosted runners"); de-registration after one job is performed
  by GitHub itself; machine wipe is the VM deletion.

### 5.2 Alternative considered — ARC on GKE

Actions Runner Controller (the official Kubernetes operator; autoscaling
runner scale sets, ephemeral container-based runners) is the reference
implementation for organizations with Kubernetes infrastructure. For this org's
scale (single-digit concurrent jobs, one repo consuming the fleet), GKE adds a
cluster, node pools, cert-manager/Helm surface, and pod-level networking to
manage a fleet whose real requirement is "one clean Linux VM per job". The
plain-GCE orchestrator above delivers the same ephemeral contract with one
~200-line service and no cluster. **Decision: plain ephemeral GCE now; ARC is
the documented escalation path if runner demand ever requires cluster-class
scheduling.** The GitHub Runner Scale Set client is the intermediate option if
the poll loop is ever replaced by scale-set API integration.

### 5.3 Why the observed failure classes disappear here

| Failure class (shared-Colima era) | Structural status on ephemeral GCE |
|---|---|
| dockerd crash-loop under parallel load | Impossible: one docker daemon per VM, one job per VM |
| Disk pressure truncating image layers | Impossible: fresh boot disk per job; nothing accumulates |
| Fixed host-port collisions (e.g. two postgres bindings) | Impossible: each VM owns its network namespace; ports are VM-local |
| qemu emulation slowness (37 min linux wheels) | Eliminated: native x86_64 execution |
| Zombie workers holding slots after cancellation | Self-healing: runner exits after one job; VM self-deletes; reaper only watches the residue |
| Listener wedges (online, not dispatching) | No long-lived listener exists to wedge |

New failure modes, and their handling: GCP API outage or quota exhaustion
(orchestrator fails closed, jobs queue — GitHub holds queued jobs 24 h;
quota headroom verified below), golden-image staleness (pinned image + weekly
bakery), spot preemption (builders run **on-demand**, not spot — a preempted
builder mid-job is a reliability regression the pool does not accept; spot is
revisit-able once job retry telemetry exists), runner-log durability (builder
VMs forward runner logs to Cloud Logging before exit, per GitHub's guidance
for ephemeral fleets).

### 5.4 Service containers

`ci.yml`'s Test job currently hand-rolls postgres/dragonfly/minio with
run-unique names and Docker-assigned ports because macOS runners cannot use
GitHub's `services:`. On Linux runners, `services:` (or the same dynamic-port
pattern with native docker) is available; the dynamic-port design already in
`ci.yml` ports over unchanged, and the label-based leak reclaim becomes dead
code (nothing leaks when the VM dies with the job). This is a follow-up
workflow change for Phase 3, not part of this design commit.

`sdk-audit` execution-sweep is the one hybrid: its shard build needs the
macOS Mojo toolchain (fine on a macOS ephemeral VM), and its postgres is the
job's only container. The v3 placement: the sweep runs on the macOS plane
with docker baked into the Tart base image (one VM, one private daemon, one
private port space — the fixed-port 15433 compatibility code disappears with
the shared Colima daemon).

## 6. macOS plane — ephemeral Tart VMs under Orchard

### 6.1 Design

- **Tart** runs macOS guests via Apple's Virtualization.framework (near-native
  CPU performance). VM images are stored as OCI artifacts in GHCR and
  instantiated by clone (`tart clone ghcr.io/thyn-ai/<base-image> <job-vm>`),
  which on APFS is a copy-on-write clonefile operation; guests boot without
  firmware/UEFI stages. Target: job-VM ready (clone + boot + runner registered)
  inside 60 s, measured in the Phase 2 pilot.
- **Orchard** (controller + worker on the Apple host; REST API
  `POST /v1/vms` with image/cpu/memory/startup script; worker default capacity
  2 VM slots) schedules job-VMs, tracks lifecycle, and deletes them on job
  completion. Client tooling is the `orchard` CLI / API.
- **Base image contents** (built by `packer-plugin-tart`): macOS current,
  Xcode + CLT (≥16.0 for the Metal toolchain), Homebrew python3.14, node/pnpm,
  pixi with warm rattler cache, runner application staged. Image is versioned
  and pushed to GHCR by a scheduled bakery job.
- **Runner model**: identical to §5.1 — JIT-registered ephemeral runner inside
  the VM, one job, VM destroyed after.
- **Licensing**: Tart and Orchard are Fair Source; the free tier covers ≤100
  host CPU cores (Tart) and ≤4 Orchard workers. One host at this core count is
  inside the free tier; growth beyond one host is a paid-tier decision.

### 6.2 Constraints carried into the design

- **Metal device access**: Virtualization.framework does not pass a GPU device
  to guests. Shader *compilation* (the `metal` offline toolchain) works inside
  VMs — GitHub-hosted Apple Silicon runners build Metal stages in VMs — but any
  step requiring Metal device *execution* or release artifact signing stays on
  bare metal (§7). The `build-runtime` macOS leg (release signing + SE helper +
  Metal-enabled wheel validation) therefore remains on the static residue.
- **DHCP lease exhaustion**: the macOS built-in DHCP server leases for 86 400 s;
  beyond ~253 VM creations/day the default lease pool exhausts. Mitigation when
  VM churn grows: shorten the lease TTL on the host. Irrelevant at current
  churn; recorded so scale-out does not rediscover it.
- **Nested virtualization**: available only for Linux guests on M3/M4+ with
  macOS 15+. Not needed: no macOS job requires nested virtualization (docker on
  the mac plane is baked-in or replaced by linux sidecars).

### 6.3 Failure-mode profile

Same structural eliminations as §5.3 (no shared daemon across jobs, no shared
port space, no persistent disk). Orchard-specific modes: single controller
instance (acceptable for one host; controller state is small and restartable —
a controller restart does not kill running VMs), VM boot failure on a bad base
image (bakery publishes only validated images; last-known-good tag pinned),
slot exhaustion (jobs queue at GitHub; capacity is observable via Orchard's
worker resource fields).

## 7. Static residue pool

Two bare-metal macOS runners (from the existing five; labels
`thyn-mac-static` + retain `code-scanning` for org dynamic workflows):

- `build-runtime` / `build-runtime-bundle` macOS legs (release signing key,
  Secure Enclave helper codesign identity, Metal-toolchain wheel validation).
- Break-glass capacity: if either ephemeral plane is down, the flag variables
  (§11) route jobs back to static runners at variable granularity — no
  workflow edits required.

The other three static runner registrations are retired in Phase 3.
`infra/fleet_reaper.sh` continues to watch only the residue pool (its
zombie-reap + idle-listener restart logic remains correct for persistent
runners and is unnecessary for ephemeral planes by construction).

## 8. Caching layer — GCS-backed, so ephemeral builders stay warm

Ephemeral VMs have cold local disks; the cache layer externalizes everything
expensive to reproduce. GCS bucket `gs://algenta-ci-cache` (us-central1,
lifecycle-rule eviction), addressed by content hash, restored with
`rclone`/`gsutil` in job pre-steps and saved in post-steps:

| Cache | Key | Contents | Consumers |
|---|---|---|---|
| rattler/pixi | `sha256(mojo_env/pixi.lock)` | `RATTLER_CACHE_DIR` | every mojo/pixi job |
| pip | `sha256(requirements/pyproject set)` | pip wheel cache | python-only jobs |
| pnpm | `sha256(pnpm-lock.yaml)` | pnpm store | node jobs |
| **mojo shard objects** | `sha256(sorted shard module list + source-hash of the module closure + mojo toolchain version + build flags)` | compiled `algenta-runtime-worker*` binaries + per-shard build metadata | build-runtime legs, sdk-audit sweep |
| buildx layers | GHCR registry cache refs `buildcache:{api,worker,engine}-v2` | unchanged from today (registry cache already proven superior to GHA cache for these images) | image build jobs |

Shard-object cache semantics (§9.2 is the consumer): the key is
content-addressed per shard's *module set and source closure*, not per shard
index — when module additions shift chunk boundaries, affected shards miss and
rebuild, untouched shards hit. Toolchain version and build flags
(`ALGENTA_GPU`, `BUILD_VARIANT`) are part of the key, so a pixi.lock bump or a
flag change invalidates globally, as it must.

Eviction: GCS object lifecycle (e.g. 30-day no-access expiry) plus
generation-keyed overwrites; no custom GC process.

## 9. Codna-intelligence deepening — ultra-fast and adaptive

The repo already owns a proven reverse-import blast-radius engine
(`scripts/test_impact.py`, with the productized `codna.impact` engine when the
codna wheel is present). v3 promotes it from advisory to load-bearing across
three axes.

### 9.1 Test selection: observed → gating

Today `ci.yml` runs `scripts/test_impact.py --json` as an observed-only report
step (never fails). Promotion path:

1. **Record** (immediate): publish the selection JSON as a run artifact so
   subset-vs-full decisions accumulate an auditable history.
2. **Gate PR runs**: `mode == "subset"` runs the selected tests **plus** a
   fixed anchor set (Mojo dispatch server smoke, OpenAPI drift, kernel
   inventory) that guards the cross-cutting contracts; `mode == "all"` runs the
   full suite. Any tool error exits to the full suite with a warning — the
   gate never fails because the selector failed.
3. **Main stays exhaustive**: pushes to `main` (the gate of record) and the
   scheduled legs always run the full suite regardless of selection.

Fallback matrix (all already implemented in `test_impact.py`, restated as the
gating contract):

| Condition | Decision |
|---|---|
| codna wheel absent | conservative local import graph (same bias) |
| broad/config change (`.github/**`, `scripts/**`, `pixi.toml`, `conftest.py`, …) | full suite |
| non-Python change, or unmappable file | full suite |
| closure reaches ≥34 % of tests (shared-core) | full suite |
| empty/undeterminable diff | full suite |

Bias is invariant: when in doubt, run more tests, never fewer.

### 9.2 Shard-selective runtime rebuilds

`build-runtime.yml` compiles 643 modules as 27 deterministic shards on every
qualifying push. v3 rebuilds only the shards whose module closure intersects
the diff:

1. **Full-rebuild tripwires** (any hit → build everything, cache included):
   toolchain change (`mojo_env/pixi.lock`), shard builder or dispatch generator
   change (`scripts/build_runtime_shards.py`,
   `scripts/generate_runtime_library_dispatch.py`,
   `scripts/stage_runtime_worker_package.py`), container bootstrap scripts,
   the shared worker entrypoint (`mojo/engine/main.mojo`), or CI pipeline files.
2. **Mojo import closure**: parse the diff's changed `.mojo` files; walk
   `import x.y` / `from x.y import …` edges across `mojo/` to the transitive
   set of affected modules (the Mojo-level analogue of the existing Python
   reverse-import walk).
3. **Shard intersection**: map affected modules to shards through the same
   deterministic chunking `build_runtime_shards.py` uses (sorted module list,
   shard size 24) — or read the previous `runtime-shards.json` when the module
   set is unchanged.
4. **Selective compile**: compile only intersecting shards; restore all other
   workers from the shard-object cache (§8). Staging
   (`stage_runtime_worker_package.py`) and manifest signing then run over the
   merged worker set exactly as today — downstream jobs are unaware selection
   happened.
5. **Verification unaffected**: the clean-machine contract and the sdk-audit
   execution sweep still execute against the complete staged artifact set, so
   a selection bug can at worst waste compute, never ship an untested shard.

Expected effect: a single-kernel PR rebuilds 1 shard (~minutes) instead of 27
(16–18 min native; 37 min emulated today), and the linux leg's cache-hit shards
skip compilation entirely.

### 9.3 Adaptive skip — inventory and extensions

Already adaptive (path- or blast-radius-gated today):

| Workflow | Mechanism |
|---|---|
| build-runtime.yml | `paths:` filter on the runtime surface |
| docs-audit.yml | `paths:` filter on docs + generator surfaces |
| tpm.yml | `paths:` filter on the TPM backend + test |
| sync-public-sdk.yml | `paths:` filter on the two SDK packages |
| code-coverage.yml | `paths:` filter on the Python surface |
| codeql.yml | blast-radius skip/differential/full per language leg |

Not adaptive today, with the v3 extension for each:

| Job/step | v3 gate |
|---|---|
| `ci.yml` docs steps (`docs-gitbook-verify`, `docs-check`) | run only when the blast radius touches `gitbook/**` or the doc generators |
| `ci.yml` `openapi-check` | run when the closure touches the API surface (`apps/api_server/**`, `apps/mcp_server/**`, `schemas/openapi/**`) — this gate imports the app, so its trigger set stays app-broad |
| `ci.yml` `inventory-check` | run when the closure touches `mojo/**` or the inventory generators |
| `api-image-mojo-smoke` (every PR today) | run when the closure can change the image inputs (Dockerfiles, app code, mojo engine); skip for docs-only PRs |
| SDK/TS artifact-install legs (every PR today) | run when the closure touches the SDK packages |

All gates share the §9.1 fallback contract: ambiguity runs the leg.

## 10. Mojo in CI — honest assessment

**What Mojo accelerates in CI.** Compute-bound, pure-CPU verification steps:
kernel-inventory checks, contract-diff and JSON sweep steps, blast-radius graph
computation itself, and engine self-tests (the CI Mojo smoke already executes a
compiled worker). Any CI step that is today "python over large JSON" is a
candidate for a compiled Mojo worker behind the same runtime the product ships.

**What Mojo does not accelerate.** The pytest graph's cost is test count and
service bring-up, not interpreter arithmetic — selection (§9.1) is its lever.
Docker image costs are layer builds and registry I/O — native hardware (§5) and
registry cache (§8) are its levers. Neither is a Mojo problem.

**The compile cost is Mojo compilation, full stop.** The single largest CI cost
center is compiling 643 engine modules; no kernel makes that cheaper — sharding
(done), shard-level caching (§8), blast-radius selectivity (§9.2), and native
hardware (§5) do. That is the complete lever set; v3 applies all four.

## 11. Phased migration

Rollout switches are repo/org **variables**, so every phase flips without a
workflow edit and rolls back the same way:

- `vars.CI_LINUX_POOL`: `colima` (default) | `gcp` — which label set linux jobs use.
- `vars.CI_MAC_POOL`: `static` (default) | `tart` — which label set mac jobs use.

### Phase 1 — linux jobs to ephemeral GCP native builders (this week)

1. **Days 1–2, infra**: golden-image bake script + registry of image versions;
   orchestrator VM with JIT runner registration, self-delete, watchdog sweep,
   Cloud Logging forwarding; concurrency floor/ceiling. Dry-run against the
   org's runner API with zero real jobs.
2. **Days 2–3, first migrations (flag-gated)**: `tpm.yml` (path-gated,
   container-bound, re-runnable) and `ci.yml` API-image smoke (PR-bound,
   amd64-build-heavy). Both are re-runnable and outside release critical paths.
3. **Days 3–5, image pipeline (flag-gated)**: `ci.yml` Build & Push, both
   auto-deploy jobs, `deploy.yml`, `build-mojo.yml`.
4. **Deferred to Phase 2** (release-critical): `build-runtime` linux/cuda/
   clean-machine legs, `sdk-audit` sweep, `ci.yml` Test job.

**Green criteria**: ≥10 consecutive green runs of every migrated job; ≥2×
wall-clock improvement on the amd64 image builds vs the Colima baseline; zero
lost/orphaned jobs (orchestrator sweep logs empty); runner logs visible in
Cloud Logging for every run.

**Rollback**: set `vars.CI_LINUX_POOL=colima`. Jobs return to the existing
fleet immediately; no state migrates because the builders are stateless.

### Phase 2 — Tart/Orchard macOS runners (weeks 2–3)

1. Bake the Tart base image (packer), push to GHCR, version-pin.
2. Orchard controller + worker on the Apple host; pilot the PR-tier legs first:
   TS SDK installs (3 legs), SDK artifact install, CodeQL (3 legs), docs-audit,
   code-coverage, sdk-audit gap-checks.
3. Release-critical and Metal legs stay on bare metal by design (§7).
4. Migrate the `ci.yml` Test job to the linux plane behind the flag (its
   service containers become native docker), and the `build-runtime`
   linux/cuda/clean-machine legs + sdk-audit sweep once §9.2's selectivity is
   live (their shard builds are the biggest remaining emulation cost).

**Green criteria**: measured VM clone+boot+runner-ready ≤60 s; one full week of
green PR pipelines on the tart legs; zero wedge events on either plane.

**Rollback**: set `vars.CI_MAC_POOL=static`; static runners were never
deregistered until Phase 3 completes.

### Phase 3 — retire Colima and the static surplus (week 4+)

1. Two weeks of dual-plane green required before entry.
2. Deregister 3 static runners; keep the 2-runner residue (§7).
3. Remove Colima and its disk; delete the fixed-port compatibility code paths
   in workflows where native `services:` replaces them (the one workflow-edit
   batch of the migration, reviewed separately).
4. `fleet_reaper.sh` re-scoped to the residue pool.

**Rollback**: re-register runners from the existing `svc.sh` installs
(restoration is a config operation, not a rebuild); flip pool variables back.

## 12. Cost model

Verified inputs (2026-08-24): `eplanev2` us-central1 quota — N2: 3 000 vCPU,
C3: 300 vCPU, PREEMPTIBLE: 5 000 vCPU, all at usage ≈0. Public pricing
(us-central1): n2-standard-8 (8 vCPU / 32 GB) **$0.3885/h** on-demand;
c3-standard-8 **$0.4032/h** on-demand, ~**$0.09/h** spot; n2 spot ≈50 %
below on-demand (~$0.20/h per public pricing mirrors). Self-hosted Actions
minutes carry no GitHub billing; cost is infrastructure only.

Estimated linux-plane demand: 30–60 builder-hours/day at current run volume
(≈45 min image pipeline, 10–40 min legs, multiple concurrent runs).

| Scenario | Monthly infra cost |
|---|---|
| GCP builders, on-demand, 45 h/day avg | ≈ $525 |
| GCP builders, spot-tolerant retries (future) | ≈ $250 |
| Orchestrator + bakery VMs (e2-small class) | ≈ $10 |
| Current fleet electricity (5 runners, 1 host, ~3–7 kWh/day) | ≈ $15–35 |

The GCP spend is real money where electricity was nearly free; what it purchases:
3–5× throughput on the emulation-bound legs, burst capacity to the quota ceiling
(375 concurrent n2-standard-8 VMs) instead of 5 wedged slots, and the
structural deletion of the shared-daemon failure classes rather than their
watchdog-managed mitigation. The macOS plane adds no cloud spend (same host,
VMs instead of static listeners).

## 13. Appendix — verified facts and references

- Runners: org-level, `thyn-mac-arm64[-2..-5]`, labels
  `self-hosted,macOS,ARM64,macos-arm64,thyn-mac,code-scanning`;
  `vars.RUNNER_LABELS = ["self-hosted","thyn-mac"]` (org variable).
- Quotas and pricing: `gcloud compute regions describe us-central1`
  (project `eplanev2`, 2026-08-24); public pricing mirrors for
  n2/c3-standard-8 us-central1 on-demand and spot.
- Tart: Apple Virtualization.framework, OCI-registry VM images, clone-based
  instantiation; Fair Source License (free ≤100 cores / ≤4 Orchard workers);
  DHCP lease caveat (~253 VMs/day at default 86 400 s lease); nested
  virtualization M3/M4 + macOS 15, Linux guests only.
- Orchard: controller + workers + clients; REST API (`POST /v1/vms`,
  events/logs, delete); default 2 VM slots per worker; single controller
  instance; workers may sit behind NAT.
- GitHub autoscaling contract: ephemeral runners recommended; `--ephemeral`
  de-registers after one job; JIT runner REST API available; ARC is the
  reference Kubernetes implementation; Runner Scale Set client for custom
  non-K8s autoscaling; `workflow_job` webhook payloads expose
  queued/in_progress/completed; runners >30 days outdated stop receiving jobs;
  ephemeral-fleet runner logs must be forwarded externally.
- Repo telemetry and shard facts: GitHub Actions API (2026-08-24/25);
  `scripts/build_runtime_shards.py` (643 modules, shard size 24);
  `scripts/test_impact.py` and `scripts/adaptive_codeql_scope.py` (bias
  contracts); `infra/fleet/fleet_reaper.sh` (watchdog semantics).

## 12. Owner decision addendum (2026-08-25): ALL-AZURE, ZERO LOCAL RUNNERS

Owner directive supersedes the two-plane design above: **no local runners at
all**; the CI compute plane is Azure. Consequences and resolutions:

1. **Linux plane = Azure** (as already provisioned: RG `thyn-ci` eastus, SP
   `thyn-ci-builder` scoped Contributor, repo secrets `AZURE_CREDENTIALS` /
   `AZURE_CI_RG` / `AZURE_CI_LOCATION`). The GCE option in §5 remains the
   validated fallback (quotas verified, pricing sourced) but is NOT the
   decision. Phase order unchanged; the orchestrator pattern
   (provision → JIT `--ephemeral` runner → self/teardown delete → reaper
   leak-sweep) is provider-identical.
2. **macOS plane: retire, don't replace, for 31 of 33 jobs.** §2 shows only
   two jobs are genuinely Apple-hardware-bound (release signing with the
   Secure-Enclave helper; Metal-toolchain wheel validation). Everything else
   moves to Azure linux (arm64 linux legs where the mac was arbitrary; the
   x86-64-v3 wheels and amd64 images were always linux-targeted).
3. **The two Apple-bound legs** run on GitHub-hosted `macos-15` ONLY at
   release time (they fire on release tags, not per-PR — the historical
   $1.8k/20d burn was the per-PR matrix on hosted, which this architecture
   eliminates; release-only hosted mac usage is hundreds of minutes/month,
   negligible). Alternative if zero-GitHub-hosted is ever required: one
   MacStadium on-demand Mac mini as a dedicated signer (~$100/mo), still not
   "local". Metal validation may additionally be demoted to a release-gate
   manual step if hosted mac proves flaky.
4. **This Mac exits CI entirely** — dev box + GPU-race orchestration only.
   The 5 static listeners retire with no Tart/Orchard replacement (Tart plan
   cancelled same day). `fleet_reaper.sh` re-scopes to Azure VM leak-sweep
   only.
5. Rollback contract unchanged: builders are stateless; the pool choice is a
   repo var, and every job's artifacts come from caches (GCS/Azure Blob per
   §7), never from a persistent machine.
