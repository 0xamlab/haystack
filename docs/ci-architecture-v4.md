# CI Architecture v4 — GitHub-hosted, no self-hosted fleet, layered local-first security

Status: implemented (this document describes the shipped state as of the PRs listed in §8,
not a proposal). Supersedes `ci-architecture-v3.md` in full — see §1.1 for why.
Scope: `thyn-ai/algenta` CI/CD and its relationship to the org-wide runner and security rollout
tracked in `thyn-ai/security-toolchain`.

## 1. Executive summary

Every job in this repository runs on GitHub-hosted compute: `ubuntu-latest` for everything
except the handful of Mojo-compile jobs, which run on the org's own right-sized larger runner,
`thyn-8c` (8-core/32 GB, capped at 2 concurrent, restricted to this repo and `telys`). There is
no self-hosted fleet, no orchestrator VM, and no Azure resource group in the critical path.
Every PR and every push to `main` also runs a layered, local-first security gate (secrets,
static analysis, dependency and IaC scanning) sourced from one org-wide package,
`thyn-ai/security-toolchain`, in advisory mode.

### 1.1 Why this supersedes v3

`ci-architecture-v3.md` proposed a two-plane design (ephemeral GCP linux builders + Tart/Orchard
macOS VMs) that was itself superseded the same day it was written by an owner addendum moving
the whole plane to Azure (`RG thyn-ci`, `runs-on: [self-hosted, az-ephemeral]` org-wide). Neither
design is what runs today. The Azure plane worked but carried real, measured costs this
architecture removes:

- **Latency.** 2-minute jobs queued 10–81 minutes behind full VM boots — the ephemeral-VM
  provisioning cost dominated the actual job runtime for most of the fleet.
- **Money.** ≈$400+/month list-price Azure spend (compute + 6 attached Premium data disks +
  an idle AKS pilot cluster + assorted orphaned networking) before counting VM job-hours,
  against $0 for standard GitHub-hosted minutes within the org's Enterprise 50,000/month
  included allowance.
- **A hard blocker.** `az-ephemeral-pool.allows_public_repositories=false` — the day
  `algenta-sdk`/`algenta-integrations` (already public) or any future public spin-out needed CI
  on a fork PR, every job on that pool would queue forever. GitHub-hosted `ubuntu-latest` is the
  only runner class that serves fork PRs without additional plumbing.

No replacement local-runner plane was considered this time; §1 of the 2026-08-25 addendum
partially anticipated this ("no local runners at all") without going all the way to "no
self-hosted compute at all" — this document is the completion of that direction, not a reversal
of it.

## 2. Target architecture

| Runner class | Used for | Cost |
|---|---|---|
| `ubuntu-latest` (GitHub-hosted, 2 vCPU/8 GB private-repo standard) | Every job except Mojo compiles: lint/typecheck, unit + integration tests, CodeQL, `cla.yml`, docs-audit, SDK artifact installs, Helm lint/kind-smoke, TPM round-trip, Docker image builds, publish/release/deploy jobs, `security.yml` | Free within the org's 50,000 included Actions minutes/month |
| `thyn-8c` (GitHub larger runner, 8-core/32 GB, `public_ip_enabled: true`, `maximum_runners: 2`, runner group `mojo-heavy` restricted to this repo + `telys` and to named Mojo workflow files) | `build-runtime.yml`, `build-runtime-bundle.yml`, `build-mojo.yml`, `amd-rocm-gate.yml`, `sdk-audit.yml` execution-sweep shard compiles, `ci.yml`'s `test` job only when `workflow_dispatch measure_baseline=true` (otherwise the same job runs on `ubuntu-latest`) | $0.022/min — never free; capped by `maximum_runners: 2` and workflow-file restriction |

There is no third row. `[self-hosted, az-orch]` was listed here until the decommission wave
removed `az-ci-smoke.yml` and `deploy-az-orchestrator.yml` along with the orchestrator VM they
targeted — see §9. **Two runner classes is the complete set**, so any `runs-on:` naming a third
label is a typo, and `.github/actionlint.yaml` no longer allowlists anything that would hide it.

Compare against §12 of v3's cost model (GCP $525–785/mo projected, Azure addendum unpriced but
measured in practice at $400+/mo): the GitHub-hosted-only model's expected steady state is
~9–12k standard minutes/month (≈20% of the included quota, $0) plus incidental `thyn-8c`
minutes for Mojo compiles, against an org Actions spending limit set at $150/month as a hard
backstop.

## 3. Job → runner placement (verified, not proposed)

This repo's `ci.yml` alone carries 12 distinct `runs-on:` sites; the table below is the shape,
not an exhaustive per-line listing (see the workflow files themselves for that).

| Job family | Runner | Rationale |
|---|---|---|
| `Test (Python 3.14)` canary, SDK artifact installs (×4), TS SDK artifact installs (×3), gap checks, TPM round-trip, docs interaction-contract audit, Helm lint | `ubuntu-latest` | No native compile step; proven green on first hosted run (see §8) |
| Helm kind-install smoke, OpenResponses protocol conformance | `ubuntu-latest` | Container-only, no Mojo toolchain |
| `build-runtime`, `build-runtime-bundle`, `build-mojo`, `amd-rocm-gate` | `thyn-8c` | Native Mojo/MAX compile; the 2 vCPU/8 GB standard runner is undersized for a 24-module shard (measured up to ~11 GiB peak footprint per shard in the v3-era telemetry, still the right order of magnitude here) |
| `sdk-audit` execution-sweep (compiled-worker shards) | `thyn-8c` | Same compile cost as above |
| Docker image builds, Fly deploys, Helm chart OCI push, published-artifact install/execute proof | `ubuntu-latest` | Only run on `main`/tags/release, never on fork PRs; no compile step of their own (consume prebuilt artifacts) |

The `az-ci-smoke` / `deploy-az-orchestrator` row this table used to carry is gone with the
workflows themselves; §9 records what they were and when they went.

## 4. Security gate

Every PR and every push to `main` runs `security.yml`, a ~30-line caller into the reusable
`thyn-ai/security-toolchain` workflows (private repo; the toolchain is not yet public — see
§7). Layered by execution point, same policy at every layer:

| Layer | Runs | Tools |
|---|---|---|
| `pre-commit` (<5s, developer machine) | Gitleaks on the staged diff; Opengrep on changed files; `actionlint`; `verify-toolchain` (pin ⇔ hook ⇔ caller consistency) | gitleaks, opengrep, actionlint |
| `pre-push` (≤2 min, developer machine) | Gitleaks on the push range; full-repo Opengrep vs. baseline; OSV-Scanner over lockfiles; Trivy `config` mode over IaC | + osv-scanner, trivy |
| CI `security.yml` → `security-full.yml` (hosted `ubuntu-latest`, ≤20 min) | The same policy on a clean checkout — the authoritative merge gate; changed-file scoped on PRs (via the toolchain's own PR-files-API-first, fail-closed-to-full changed-file resolver, independent of `ci.yml`'s own `id: impact` blast-radius step — SAST findings are per-file, not per-import-graph), full scan on `main` push and a weekly `cron` | reusable workflow, `overlay: engine` |

Mode is `advisory` (annotates + uploads SARIF, never fails a check) until a `security/baseline/*.txt`
file exists for a given tool, measured via `workflow_dispatch measure_baseline=true` on a clean
`main` run and committed — only then does that tool's gate ratchet (new findings block; existing
ones may only shrink). **No baseline has been measured yet as of this document** — that is the
literal next step once this PR and the toolchain-onboarding PR both land on `main`, not a gap in
the design.

Two engine-specific pieces beyond the templated per-repo rollout:

- **Gitleaks unification.** `sync-public-sdk.yml` and `release-sdks.yml` each ran their own
  ad hoc `curl | tar` gitleaks install (no checksum) and a bare `gitleaks detect` with no config
  file and no `.gitleaksignore` awareness despite a comment promising one. Both now install via
  the toolchain's own sha256-verified fetch (`security/toolchain.lock` is the one version source
  for laptop, this repo's CI, and these two mirror/release gates) and run `thyn-sec gitleaks-dir`,
  which honors a `.gitleaks.toml`/`.gitleaksignore` committed at the scanned root the same way
  every other gate in the org does.
- **`.semgrepignore`** mirrors `[tool.ruff] extend-exclude` in `pyproject.toml` (`.codex/`,
  `apps/api-server/`, `apps/runtime/proto/`, `benchmarks/python_libs/`, `hello-world/`,
  `mojo_env/`) plus `vendor/` and `*.mojo` — the ~495-module frozen Mojo kernel tree is a
  language Opengrep does not parse; `mojo/bindings/*.py` (real Python) stays in scope.

## 5. Cost control (structural, not aspirational)

- Org Actions spending limit: $150/month hard stop.
- `thyn-8c`: `maximum_runners: 2`, runner group restricted to algenta + telys and to the
  specific Mojo workflow files (`restricted_to_workflows`) — a scanner job or an accidental
  `runs-on: thyn-8c` on an unrelated workflow cannot land there.
- `security-full.yml`'s first step validates its `runner_json` input against `^ubuntu-` and
  fails on any `-core`/`thyn-`/`self-hosted`/`blacksmith` label, so a security job can never be
  pointed at billed compute even by a future caller mistake. `security-smoke.yml` does the same.
- The 32-core `thyn` larger runner (max 50, referenced by zero workflows, last active
  2026-08-25 — the runner class behind the August hosted-compute overrun) has been deleted.

## 6. What is NOT covered here

- Image CVE scanning stays on `syft` + `grype` (`image-sbom-scan`, publicly documented in
  `gitbook/trust/supply-chain.md`) — untouched by this migration. Trivy in this repo's gate is
  IaC `config` mode only, never image scanning; the two tools are not redundant.
- CodeQL stays a separate, per-PR workflow wherever it already existed. This repo removed
  CodeQL entirely in #870 — Opengrep is not backfilling a SAST tool that used to run here, it is
  the first one.
- `docker-compose*.yml`/`fly.*.toml` are not covered by the Trivy `config` overlay (stated here,
  not silently dropped) — IaC scanning targets Terraform/Bicep/Dockerfile/Helm/K8s manifests.

## 7. The toolchain itself

`thyn-ai/security-toolchain` is currently a **private** repository. Every workflow in this repo
that calls it can do so today because private-repo GitHub Actions billing extends to a private
reusable workflow/action called from another repo in the same organization. It must be flipped
public before any *public* repository (`algenta-sdk`, `algenta-integrations`) can consume it —
a fork PR against a public caller cannot resolve a private reusable workflow and the job fails
at startup with zero jobs run. That flip is an owner action (repository visibility change),
tracked as outstanding in the toolchain rollout, not something this repo's CI depends on.

## 8. Migration status (as of this document)

| PR | Scope | State |
|---|---|---|
| #1007 `chore/hosted-runners-security-toolchain` | Every `runs-on:` in every workflow off `[self-hosted, az-ephemeral]` onto `ubuntu-latest`/`thyn-8c`; `.github/actionlint.yaml` added | All 12 non-release/deploy checks green on the **first ever hosted run** of every engine job (SDK artifact installs ×4, TS SDK installs ×3, gap checks, TPM round-trip on swtpm, docs interaction-contract audit, Helm lint, Helm kind-install smoke, OpenResponses conformance, `Test (Python 3.14)` canary — no `thyn-8c` fallback needed). Blocked only on required review. |
| #1008 `chore/pre-commit-reconcile` | `.pre-commit-config.yaml` reconciled with the actual pixi/Makefile toolchain (`ruff-pre-commit` v0.3.0 → v0.12.0, matching `mojo_env/pixi.toml`'s own pin exactly; dropped a dead `black` hook; added `mirrors-mypy` scoped to the four packages `make typecheck` covers, `stages: [manual]` until its measured 3,409 pre-existing errors are worked down; `default_install_hook_types: [pre-commit, pre-push]`) plus a dynamic pin-drift test | Open, review-gated |
| This PR | `security.yml` caller, `.github/dependabot.yml`, `.semgrepignore`, gitleaks unification in `sync-public-sdk.yml`/`release-sdks.yml` | Open, stacked on #1007 |
| Follow-up (small, stacked on #1008) | The `thyn-ai/security-toolchain` pre-commit block itself, appended to #1008's reconciled config | Pending #1008 merge |
| Baseline measurement | `workflow_dispatch measure_baseline=true` on `main`, for gitleaks/opengrep/osv/trivy | Pending — needs #1007+#1008+this PR merged first; a baseline measured from a laptop is refused by convention (`security/baseline/<tool>.txt` headers require a CI run + commit SHA) |
| Ratchet flip | `mode: advisory` → `mode: ratchet` in `security.yml` | Pending one clean baseline-measured week |

## 9. Azure decommission

### 9.1 Code level — DONE

This repository is at **zero** Azure CI dependency, and that is now a property of the tree rather
than of a comment. The decommission wave deleted:

- `.github/workflows/az-ci-smoke.yml` and `.github/workflows/deploy-az-orchestrator.yml` — the last
  two jobs with `runs-on: [self-hosted, az-orch]`. Both were already unrunnable: they target a
  runner registration that no longer exists, so a trigger would have queued forever rather than
  failed.
- `infra/ci/**` — `az_orchestrator.py`, `deploy_orchestrator.sh`, `orchestrator-cloud-init.yaml`,
  `az_quota_raise.py`, and `image/{build_image.py,manifest.toml}`.
- `infra/fleet/**` — the retired persistent-fleet daemons (`fleet_reaper.sh`, `fleet_watchdog.sh`,
  `algenta_dns_proxy.py`, both launchd plists, `install_fleet_daemons.sh`, README).
- Their 18 test modules (`tests/test_az_orchestrator_*.py`, `tests/test_ci_image_{build,contract}.py`).
- The `az-ephemeral` / `az-orch` entries in `.github/actionlint.yaml`.

Measured at the time of the wave, so this is a state and not an intention:
`gh api orgs/thyn-ai/actions/runners` returned `total_count: 0` — no `az-ephemeral` and no `az-orch`
registration anywhere in the org — and `az vm list -g thyn-ci` returned **0 VMs**: the `ci-orch`
orchestrator box was deleted during the same hour. There is therefore no running consumer of
anything removed here, and no runner able to execute the two deleted workflows.

### 9.2 Azure resources — NOT done by this wave, still owner-gated

The resource group `thyn-ci` **still exists** and still holds residue, inventoried at the same
moment: 1 orphaned NIC, 1 public IP, 1 NSG, 1 VNet, 1 disk, the Compute Gallery with the
`ci-worker` image and version, the idle `ci-arc-pilot` AKS managed cluster (plus its `MC_*`
managed RG), the DevCenter project and devcenter, and a `GitHub.Network/networkSettings`.

Deleting any of it is **out of scope for the code wave by design** and remains a separate,
explicitly owner-confirmed step, gated on 7 consecutive days of hosted-only CI green. Two of the
original preconditions have changed since this section was first written and are recorded rather
than silently dropped:

1. *"no `az-ephemeral` registrations for 7 consecutive days"* — the count is now 0, but the clock
   starts from the wave, not from this document; the 7 days still have to elapse.
2. *"every fleet consumer has merged its hosted-runner migration"* — this repo has. **Other repos
   in the org are not verified here**, and the gallery image, VNet and NSGs may still be referenced
   by them. Confirm org-wide before touching the resource group; this repo's tree cannot answer
   that question.

Every step in that teardown is destructive (disk/cluster/gallery/resource-group deletion) and is
confirmed with the owner individually at execution time; this document records the precondition,
not a standing authorization to proceed once it is met.

## 10. Verification

- `thyn-sec verify-toolchain --root .` — pin (`.pre-commit-config.yaml` rev) ⇔ caller SHA ⇔
  installed-package version all agree; run in CI via `security.yml`'s own toolchain setup step
  implicitly, and locally via the pre-commit `verify-toolchain` hook.
- `thyn-sec actionlint .github/workflows/*.yml` — workflow lint, run standalone in this repo's
  own `.github/actionlint.yaml`-configured step and as part of every toolchain pre-commit/CI run.
- `grep -rlE "RUNNER_LABELS|az-ephemeral|az-orch" .github` — expect **zero hits**, with no
  exceptions. Before the decommission wave this allowed two named orchestrator-management
  workflows; there are none now, so any hit is a regression.
- `test -e infra/ci -o -e infra/fleet` — expect non-zero. Neither directory should exist.
- `gh api organizations/thyn-ai/settings/billing/usage` — `Actions Linux` minutes should stay
  under the included quota; larger-runner line items should show only `thyn-8c` job names.
