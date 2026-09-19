# CI Architecture v4 — GitHub-hosted, no self-hosted fleet, layered local-first security

Status: implemented (this document describes the shipped state as of the PRs listed in §8,
not a proposal). Supersedes the former `ci-architecture-v3.md` in full — that document has since
been **deleted** together with the Azure fleet code it described, so §1.1 below is now the only
record of what it proposed and why it was abandoned.
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

The deleted `ci-architecture-v3.md` proposed a two-plane design (ephemeral GCP linux builders +
Tart/Orchard macOS VMs) that was itself superseded the same day it was written by an owner
addendum moving the whole plane to Azure (`RG thyn-ci`, `runs-on: [self-hosted, az-ephemeral]`
org-wide). Neither design is what runs today, and neither document survives in the tree — this
section is the record. The Azure plane worked but carried real, measured costs this
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

Compare against the cost model v3 carried in its own §12 — GCP $525–785/mo projected, and the
Azure addendum unpriced but measured in practice at $400+/mo. Those figures are quoted here in
full because v3 is deleted: the comparison has to survive the document it came from, or the
number this architecture is judged against becomes unrecoverable. The GitHub-hosted-only model's
expected steady state is ~9–12k standard minutes/month (≈20% of the included quota, $0) plus
incidental `thyn-8c` minutes for Mojo compiles, against an org Actions spending limit set at
$150/month as a hard backstop.

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

## 9. Azure decommission (complete — code, cloud and DNS)

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

### 9.2 Azure and org side — DONE, re-verified 2026-09-19T03:17–03:21Z

**This section replaces an earlier one that said the opposite.** §9.2 originally carried a residue
inventory (orphaned NIC, public IP, NSG, VNet, disk, the Compute Gallery with the `ci-worker`
image, the idle `ci-arc-pilot` AKS cluster and its `MC_*` managed RG, the DevCenter project, a
`GitHub.Network/networkSettings`) and gated deletion on 7 consecutive days of hosted-only CI green.
The owner executed the destructive steps instead — `thyn-ci` was deleted 2026-09-18 01:09Z, per
#1025 — so that inventory described resources that no longer existed and the gate had nothing left
to guard. Both are recorded as superseded rather than quietly dropped, because a reader who finds
the old text in git history should be able to see that it was overtaken by events, not wrong when
written.

Re-measured rather than assumed, 2026-09-19T03:17–03:21Z:

| Check | Result |
|---|---|
| `az group list` filtered on `thyn` | **no resource group at all** — `thyn-ci` and the `MC_thyn-ci_ci-arc-pilot_centralus` managed RG are both gone |
| `az resource list` for DevCenter / galleries | **none** — the DevCenter project and devcenter, and the Compute Gallery holding `ci-worker`, are gone |
| `gh api orgs/thyn-ai/actions/runner-groups` | only `Default` and `mojo-heavy`; **`az-ephemeral-pool` is gone** |
| `gh api orgs/thyn-ai/actions/variables` | **empty**; `RUNNER_LABELS` is gone |
| `gh api orgs/thyn-ai/actions/runners` | `total_count: 0` |
| `dig +short ci-webhook.codna.ai` | **no answer** — the DNS record that fronted the orchestrator's webhook receiver has been removed (`docs.algenta.ai` resolved in the same check, so this is an absent record, not a broken resolver) |

The Cloudflare row matters and is easy to miss: `infra/cloudflare/webhook.tf` was deleted from this
repo by #1025, but that module was never applied from a checkout, so no Terraform state ever
tracked the record — deleting the file could not have removed it. It was still resolving after
#1025 merged. It does not resolve now, which means somebody removed it in the dashboard; the repo
gives no way to tell who or when, so the measurement is the only evidence available.

**The 7-day window still has a purpose, but not the one it was written for.** It is no longer a
precondition for deleting anything, because there is nothing left to delete. It remains a sensible
observation period for one thing only: confirming that hosted-only CI is stable now that no
fallback plane exists to absorb a bad week. That is tracked in the PR history, not here.

**Not verified, and not verifiable from this repo:** whether any *other* repository in the org
still expected the Azure fleet. This tree can only speak for itself. The gallery image and VNet are
gone, so any such repo is already broken rather than at risk — which is worth knowing if one
surfaces later, because the fix is a migration, not a restoration.

## 10. Verification

- `thyn-sec verify-toolchain --root .` — pin (`.pre-commit-config.yaml` rev) ⇔ caller SHA ⇔
  installed-package version all agree; run in CI via `security.yml`'s own toolchain setup step
  implicitly, and locally via the pre-commit `verify-toolchain` hook.
- `thyn-sec actionlint .github/workflows/*.yml` — workflow lint, run standalone in this repo's
  own `.github/actionlint.yaml`-configured step and as part of every toolchain pre-commit/CI run.
- `grep -rlE "RUNNER_LABELS|az-ephemeral|az-orch" .github/workflows` — expect **zero hits**, with
  no exceptions. Scoped to `workflows/` deliberately: `.github/actionlint.yaml` names both labels
  in a comment recording their removal, so the unscoped form of this check matches its own
  explanation and can never return zero. A verification command that always fails gets ignored,
  and then it is not a verification command. Before the decommission wave this allowed two named
  orchestrator-management workflows; there are none now, so any hit in a workflow is a regression.
- `git grep -n "runs-on:" .github/workflows | grep -vE "ubuntu-latest|thyn-8c"` — expect zero
  hits: every job is GitHub-hosted, and `.github/actionlint.yaml` allows `thyn-8c` as the only
  custom label, so any other label fails `actionlint`.
- `test -e infra/ci -o -e infra/fleet -o -e infra/cloudflare/webhook.tf -o -e docs/ci-architecture-v3.md`
  — expect non-zero. None of the four should exist; this is the one command that proves the whole
  wave landed rather than part of it.
- `gh api organizations/thyn-ai/settings/billing/usage` — `Actions Linux` minutes should stay
  under the included quota; larger-runner line items should show only `thyn-8c` job names.
