#!/usr/bin/env python3
"""Ephemeral Azure self-hosted runner orchestrator (repo-managed, deployed on ci-orch).

Polls GitHub for queued workflow_jobs requesting label `az-ephemeral` across every repo
in the org (auto-discovered, not hardcoded -- any repo that requests the label gets
served, same as GitHub-hosted/Blacksmith runners need no per-repo registration),
provisions one Azure VM per job (parallel, quota-aware, multi-region), and GUARANTEES
cleanup: a VM is deleted when its runner disappears from the org runner list, plus
age-based sweeps. Jobs are never permanently failed here — a provisioning failure leaves
the job queued for the next poll (GitHub's own timeout is the backstop).

Runners register at the ORG level (not per-repo) via RUNNER_GROUP, an org-wide-visible
group -- this replaces the retired thyn-mac fleet, which was also org-shared and had no
repo allowlist. GITHUB_REPOS can still pin an explicit repo list (e.g. for a staged
rollout); unset, it defaults to every repo in the org.

Azure is driven via plain ARM REST (SP client-credentials) — the az CLI on ci-orch proved
unreliable (token-cache concurrency races, empty responses). Scales 0 -> MAX_CONCURRENCY
workers when the queue is deep, back to 0 when idle.

Primary dispatch is a webhook receiver (HTTPS, GITHUB_WEBHOOK_TLS_CERT/_KEY, HMAC-verified
against GITHUB_WEBHOOK_SECRET) subscribed to three event types, each earning its subscription
with real handling -- no event is subscribed speculatively with nothing acting on it:
  - `workflow_job` (queued): the actual dispatch signal -- GitHub pushes this instantly instead
    of the orchestrator polling for new work.
  - `pull_request` (opened/synchronize/reopened): a workflow_job-queued event for it is
    imminent -- pre-warms one extra worker ahead of that reactive signal instead of waiting.
  - `push` (to a branch in PREWARM_PUSH_BRANCHES, i.e. one that actually triggers this repo's
    CI): same pre-warm, for push-triggered runs rather than PR-triggered ones.
Every other event GitHub might deliver (an org's default hook subscribes to more than these
three) is acked 202 and dropped -- see do_POST's early return -- rather than silently ignored
with no trace, which is itself a fix: a correctly-signed-but-unhandled delivery used to leave
zero log line, indistinguishable from a delivery that never arrived (confirmed live: this
made registering the real org webhook impossible to verify from the log alone).

The poll loop in main() still runs, but demoted to a RECONCILE_S-interval backstop
(cleanup/warm-pool/orphan sweep plus a queued_jobs() re-check in case a webhook delivery was
ever lost) rather than the primary trigger -- this also shrinks the historical blast radius of
a hung API call: fewer poll cycles means fewer chances to hit one, even with gh()/arm()'s own
tightened timeouts.

Env: GITHUB_CI_TOKEN (org-admin oauth/PAT: needs org self-hosted-runner registration +
org repo-list + org webhook scope); GITHUB_WEBHOOK_SECRET (HMAC secret for the org-level
`workflow_job` webhook -- independent of the GitHub App's own webhook secret in
apps/api_server/config.py, deliberately: reusing the App's secret would mean registering
through the App's single webhook URL, redirecting ALL its installation events, including
codna's live fix-PR flow, onto this receiver); GITHUB_WEBHOOK_TLS_CERT/_KEY (paths to the
Cloudflare Origin CA cert/key, see infra/cloudflare/webhook.tf); GITHUB_REPOS (optional
comma-separated override to pin/restrict the served repo list; unset = every repo in the
org, auto-refreshed); AZURE_SP_CLIENT_ID/AZURE_SP_CLIENT_SECRET (fallback AZURE_CLIENT_ID/
AZURE_CLIENT_SECRET), AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID.
"""
import base64
import hashlib
import hmac
import http.server
import json
import os
import re
import secrets
import ssl
import threading
import time
import urllib.request

import yaml  # gate on rendered cloud-init: see render_userdata(). Present on ci-orch's python3.

RG = os.environ.get("AZURE_RESOURCE_GROUP", os.environ.get("AZURE_RG", "thyn-ci"))
SUB = os.environ["AZURE_SUBSCRIPTION_ID"]
TENANT = os.environ["AZURE_TENANT_ID"]
ORG = os.environ.get("GITHUB_ORG", "thyn-ai")
_PINNED_REPOS = [r.strip() for r in os.environ.get("GITHUB_REPOS", "").split(",") if r.strip()]
_repo_cache = {"value": [], "exp": 0}
REPO_CACHE_S = 300  # org repo list changes rarely; avoid a full org/repos scan every 15s poll
# Org-wide-visible: any repo in the org can be served, matching GitHub-hosted/Blacksmith
# behavior (no per-repo registration step). Narrow this via a runner-group repository
# allowlist instead of code if per-repo access control is ever needed.
RUNNER_GROUP = os.environ.get("AZ_ORCH_RUNNER_GROUP", "az-ephemeral-pool")
LABEL = "az-ephemeral"
# The poll loop is now a RECONCILE backstop, not the primary trigger (see module docstring) --
# 90s, not 15s: fewer cycles means fewer chances to hit a hung call, and the webhook path
# handles the actual "a job just queued" latency.
RECONCILE_S = int(os.environ.get("AZ_ORCH_RECONCILE_S", "90"))
WEBHOOK_PORT = int(os.environ.get("AZ_ORCH_WEBHOOK_PORT", "443"))
WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
WEBHOOK_CERT = os.environ.get("GITHUB_WEBHOOK_TLS_CERT", "")
WEBHOOK_KEY = os.environ.get("GITHUB_WEBHOOK_TLS_KEY", "")
# Branches whose push triggers this repo's own CI-triggering workflow (ci.yml's own
# `on: push: branches:`) -- pre-warming on push to any OTHER branch would just provision
# workers for pushes that never queue a job. "main" alone is the portable default; a
# deployment with a different convention (this repo's own ci.yml also triggers on "develop")
# sets AZ_ORCH_PREWARM_BRANCHES explicitly.
PREWARM_PUSH_BRANCHES = {
    b.strip() for b in os.environ.get("AZ_ORCH_PREWARM_BRANCHES", "main").split(",") if b.strip()
}
MAX_AGE_S = 90 * 60
# ONE boot window for every reap rule. A worker is presumed to be booting -- and therefore
# untouched by the sweep -- until it is this old, whatever its power state reads as.
#
# Sized against the slowest first boot, not a round number. Golden-image path measured live
# 2026-09-16 on a Standard_D8s_v5 in centralus: tier0 apt repair 23s, runner re-download ~7s,
# config.sh ~14s -- ~55s of bootstrap after cloud-init. The stock-image path runs apt-get
# (docker-ce) + deadsnakes + NodeSource + the runner download and needs 3-6min, so 720s covers
# it with margin and stays well inside MAX_AGE_S.
#
# Why it also governs STOPPED workers, reversing the earlier "reap a stopped VM at once" rule:
# that rule assumed stopped-means-finished, and during the 2026-09-16 outage the assumption
# became a churn engine. Every worker self-powered-off ~55s into its own bootstrap (see
# RUNNER_UPGRADE_SH), so the sweep reaped it, the reconcile loop provisioned a replacement,
# that one died the same way, and the plane spun at roughly one VM per queued job per 90s --
# 7 dead workers plus their leaked NICs inside an hour, every ARM delete racing the next
# create (NicInUse). Holding a corpse for 720s costs 8 vCPU of quota; recreating one every 90s
# costs the whole plane. A stopped-but-never-registered VM is now left alone inside the window
# and reaped at its far edge, which bounds churn at one generation of workers per boot window
# no matter what is broken underneath.
BOOT_GRACE_S = 720
# Kept as a name because the reap rules below and their tests read better with it. DERIVED so
# the two windows cannot drift apart again: a 720s stopped-grace is a silent no-op while the
# unregistered rule still fires at 600s, which is what the hot-patch this replaced did.
ORPHAN_AGE_S = BOOT_GRACE_S
# Minimum spacing between the TWO power-state observations that condemn a STOPPED-BUT-REGISTERED
# worker (see _stopped_twice). RECONCILE_S is 90s, so two consecutive polls are already further
# apart than this; the floor exists because cleanup() is not contractually reconcile-only -- a
# second caller (or a test driving two passes back to back) must not be able to convert "one
# observation" into "two" by being invoked twice inside the same minute. A single instanceView
# read that returns a stale power state is a real ARM behaviour, and one stale read must never
# be enough to delete a VM GitHub still lists as a runner.
STOPPED_CONFIRM_S = 60
# How long delete_vm() waits for the compute resource to disappear before it touches the NIC.
# See delete_vm(): ARM deletes are async and a NIC delete issued too early fails NicInUse and
# leaks the NIC. Measured 2026-08-26: 21s from virtualMachines/delete Started to Succeeded.
VM_DELETE_WAIT_S = 60
# Ordered by REALIZED capacity, not nominal preference. Two live facts drive this
# (measured 2026-08-25 across eastus/eastus2/centralus/westus2):
#   1. The F-series is quota-clean but CAPACITY-RESTRICTED in every region we use --
#      Azure has no physical stock, so every attempt fails with "not available in
#      location". free_vcpus() cannot see this (quota says 0/10 used, i.e. free), so
#      F-first burned ~6s of guaranteed failures on EVERY provision. It stays in the
#      chain as a genuine last resort, but never leads.
#   2. Per-FAMILY vCPU limits are the real ceiling (mostly 10 = one 8-vCPU VM per
#      family per region), so total concurrency comes from spreading across families.
#      Dsv6/Dsv5 carry the largest limits (40 in centralus vs 10 for Dsv3/Dsv4), so
#      leading with them yields materially more simultaneous workers.
# Dsv6 is DELIBERATELY ABSENT. It requires an NVMe disk controller, and this fleet's
# golden image is Ubuntu Jammy Gen2 with a SCSI controller, so every Dsv6 attempt fails
# with "disk controller types supported by the OS image ... for the VM size
# 'Standard_D8s_v6'" (confirmed live 2026-08-26). Quota for it is therefore useless until
# the image is rebuilt NVMe-capable -- listing it only burned a failed ARM round-trip per
# provision. Dsv5 leads because it is the largest family PROVEN to boot this image here.
SIZE_CHAIN = [
    "Standard_D8s_v5", "Standard_D8s_v4", "Standard_D8s_v3",
    "Standard_D4s_v5", "Standard_D4s_v4", "Standard_D4s_v3",
    "Standard_F8s_v2", "Standard_F4s_v2",
]
VM_VCPU = {
    "Standard_F8s_v2": 8, "Standard_D8s_v5": 8, "Standard_D8s_v6": 8, "Standard_D8s_v4": 8, "Standard_D8s_v3": 8,
    "Standard_F4s_v2": 4, "Standard_D4s_v5": 4, "Standard_D4s_v4": 4, "Standard_D4s_v3": 4,
}
MAX_CONCURRENCY = int(os.environ.get("AZ_ORCH_MAX", "20"))
# Blacksmith-style warm capacity: pre-booted registered runners so jobs are picked up
# in seconds instead of paying a full cold boot; drained to WARM_FLOOR after IDLE_DRAIN_S
# without queue/busy activity. A non-zero floor buys dispatch speed at the cost of paying
# full on-demand Standard_D8s_v5 price ($0.434/hr each, AZ_ORCH_SPOT is off by default and
# not enabled here) for idle capacity around the clock, whether or not any job ever arrives
# to use it.
#
# DEFAULTS TO ZERO, DELIBERATELY (owner decision, 2026-09-09): cold start on the first job
# after a quiet period is an accepted tradeoff here -- standing idle capacity billed 24/7 for
# bursty, intermittent CI usage is not. This previously defaulted to WARM_MIN=6/WARM_FLOOR=3
# (48 vCPU held steady around the clock) with no cost figure attached to justify that size;
# the live deployment had already been hand-tuned down to WARM_MIN=1/WARM_FLOOR=1 via the
# AZ_ORCH_WARM/AZ_ORCH_WARM_FLOOR env overrides on ci-orch's own /etc/az-orchestrator.env
# before this change, which still meant one Standard_D8s_v5 running continuously. If warm
# capacity is wanted again later, set AZ_ORCH_WARM/AZ_ORCH_WARM_FLOOR explicitly with the
# real dollar cost of the chosen floor stated alongside, not folded silently into "the point
# of a floor."
WARM_MIN = int(os.environ.get("AZ_ORCH_WARM", "0"))
WARM_FLOOR = min(WARM_MIN, int(os.environ.get("AZ_ORCH_WARM_FLOOR", "0")))
IDLE_DRAIN_S = int(os.environ.get("AZ_ORCH_IDLE_DRAIN_S", "600"))
WARM_PREFIX = "ci-warm-"
# Azure Compute Gallery image version, REPLICATED to every region in REGIONS. This replaces
# the classic managed image (ci-worker-v1/v2), which was single-region by construction:
# only centralus got the fast path, so the other 7 regions ran the full CLOUD_INIT bootstrap
# (apt + docker repo + deadsnakes + Node + runner download) on every boot -- 3-6min before a
# runner could register. Measured live 2026-08-25: 15 VMs up, 9 of them outside centralus and
# therefore all still bootstrapping, which is why VM count and usable-runner count diverged so
# badly. A gallery version is the supported way to get one image into many regions.
#
# Contents: docker-ce + buildx plugin (Docker's own apt repo, not Ubuntu's), python3.14,
# clang/lld, and Node.js. Node is not optional: without a real system npm, pnpm's installer
# falls through to the runner's own externals npm stub and dies deterministically (see
# CLOUD_INIT's nodejs comment).
GOLDEN_IMAGE = (
    f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Compute"
    "/galleries/thynci/images/ci-worker/versions/1.0.0"
)
# Retained only as the fallback probe region. With the gallery replicated everywhere, the
# fast path is no longer region-gated -- see _create_vm.
GOLDEN_REGION = "centralus"
SPOT = os.environ.get("AZ_ORCH_SPOT", "0") == "1"
STATE = "/var/lib/az-orch"
os.makedirs(STATE, exist_ok=True)

# Ordered by REAL available quota, highest first. provision_worker() walks this list in
# order and takes the first region/size that fits, so a nearly-full region at the head
# burns a failed ARM round-trip (~2s each) on EVERY provision before anything can succeed.
# centralus leads because it carries by far the most headroom (190 total cores, 120 Dsv6
# after the 2026-08-26 increase) vs 40 total cores in the others. The golden image is a
# gallery version replicated to all 8 regions, so leading with centralus costs no boot speed.
REGIONS = [
    ("centralus", "thyn-ci-centralus", "default"),
    ("eastus2", "thyn-ci-eastus2", "default"),
    ("eastus", "thyn-gh-runners", "builders"),
    ("westus2", "thyn-ci-westus2", "default"),
    ("westus", "thyn-ci-westus", "default"),
    ("westus3", "thyn-ci-westus3", "default"),
    ("southcentralus", "thyn-ci-southcentralus", "default"),
    ("northcentralus", "thyn-ci-northcentralus", "default"),
]

_lock = threading.Lock()
_delivery_lock = threading.Lock()
_delivery_seen = {}  # X-GitHub-Delivery -> received_at; GitHub retries a delivery verbatim on
# a non-2xx/timeout response, so dedup is required for correctness, not just efficiency.
_DELIVERY_TTL_S = 3600
_inflight = set()
_inflight_names = set()  # VM names currently being provisioned; cleanup must not reap their nic/pip
_absent_once = set()  # net-sweep two-poll guard: base seen without a VM once, swept on second sight
# Stopped-worker two-poll guard, same shape as _absent_once: VM name -> wall time of the FIRST
# stopped/deallocated sighting of the current streak. A sighting of anything else clears the
# entry, so only two CONSECUTIVE polls agree can condemn a registered worker (see _stopped_twice).
# Touched only from cleanup(), which runs on the single reconcile thread -- deliberately no lock,
# matching _absent_once/_unswept_nics. Pruned each cycle against the live VM set so a name can
# never accumulate forever.
_stopped_seen = {}
# NIC names the sweep could not parse. Log-once set, so an unhandled naming form is reported the
# first time rather than every 90s poll -- but IS reported, which is what 31 leaked NICs cost.
_unswept_nics = set()
# Boot-log gist index: VM name -> html_url, plus when it was listed. The worker bootstrap creates
# its gist with THIS orchestrator's own token, so the gists are listable from here -- see
# _gist_index() for why the pointer has to be resolved on this side of the delete.
_gist_cache = {"at": 0.0, "map": {}}
GIST_CACHE_S = 60      # one listing per reconcile cycle at most, however many VMs it reaps
# TWO pages, not three, and the reason is a rate limit rather than a guess. Measured live
# 2026-09-16 on a worker: the boot-log gist PATCH returned
# `403 API rate limit exceeded for user ID 79715912` -- GITHUB_CI_TOKEN had exhausted its
# 5000/hr core budget, because ONE token is shared by the orchestrator's whole poll surface
# (org repo list, then runs+jobs for each of 25 repos, plus paginated runner listings, every
# cycle) AND by every worker (gist create, a handful of gist flushes, registration-token
# fetches). Every call this file adds comes out of that same exhausted budget, so the index is
# capped at the smallest window that still covers a reapable corpse: 200 gists spans ~2.5h at
# the observed burst rate of ~80 workers/hr, well past MAX_AGE_S (90min).
GIST_MAX_PAGES = 2
# Deletion ledger: VM name -> {at, reason, was_busy}. Consulted when a workflow_job `completed`
# webhook reports a non-success, so an infra kill is attributed the moment GitHub notices it
# instead of being reconstructed afterwards from three separate logs.
_deleted = {}
_deleted_lock = threading.Lock()
_DELETED_TTL_S = 3 * 3600  # >> the ~9min runner-heartbeat timeout measured on 2026-08-26
_token = {"value": None, "exp": 0}
_token_lock = threading.Lock()


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(f"{STATE}/orch.log", "a") as f:
        f.write(line + "\n")


def az_token():
    with _token_lock:
        if _token["value"] and time.time() < _token["exp"] - 60:
            return _token["value"]
        cid = os.environ.get("AZURE_SP_CLIENT_ID") or os.environ.get("AZURE_CLIENT_ID")
        csec = os.environ.get("AZURE_SP_CLIENT_SECRET") or os.environ.get("AZURE_CLIENT_SECRET")
        if not cid or not csec:
            raise RuntimeError("no SP credentials in env (AZURE_SP_CLIENT_ID/AZURE_CLIENT_ID)")
        body = (
            f"grant_type=client_credentials&client_id={cid}"
            f"&client_secret={csec}"
            "&scope=https%3A%2F%2Fmanagement.azure.com%2F.default"
        ).encode()
        req = urllib.request.Request(
            f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        _token["value"] = d["access_token"]
        _token["exp"] = time.time() + int(d.get("expires_in", 3500))
        return _token["value"]


def arm(method, path, body=None, api="2023-07-01"):
    url = f"https://management.azure.com{path}{'&' if '?' in path else '?'}api-version={api}"
    for attempt in (1, 2, 3):
        req = urllib.request.Request(
            url,
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {az_token()}", "Content-Type": "application/json"},
        )
        try:
            # 20s, not 120s: a healthy ARM call completes in low single-digit seconds. A
            # genuinely hung TCP/TLS read (observed live via py-spy: MainThread stuck in
            # ssl.py's socket read, no error, no data) at 120s can block the entire poll
            # loop -- with zero log output -- for up to two full minutes on ONE call.
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read()
            return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:  # ARM throttle: back off, retry
                time.sleep(5 * attempt)
                continue
            body = e.read().decode(errors="replace")[:300].replace("\r", "").replace("\n", " ")
            raise urllib.error.HTTPError(e.url, e.code, f"{e.reason} body={body}", e.hdrs, None)
        except (TimeoutError, OSError) as e:
            # A hung/dropped connection, not an HTTP error -- urlopen raises these instead
            # of HTTPError. Retry like a 429 rather than propagating a bare socket error.
            if attempt < 3:
                time.sleep(3 * attempt)
                continue
            raise
    raise RuntimeError("unreachable")


_usage_cache = {}


def gh(path, method="GET", body=None):
    req = urllib.request.Request(
        f"https://api.github.com/{path}",
        method=method,
        data=json.dumps(body).encode() if body else None,
        headers={
            "Authorization": f"Bearer {os.environ['GITHUB_CI_TOKEN']}",
            "Accept": "application/vnd.github+json",
        },
    )
    for attempt in (1, 2, 3):
        try:
            # 15s, not 60s -- see arm()'s comment; same live-observed hang applies here.
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read() or b"{}")
        except (TimeoutError, OSError) as e:
            if attempt < 3:
                time.sleep(2 * attempt)
                continue
            raise
    raise RuntimeError("unreachable")


def served_repos():
    if _PINNED_REPOS:
        return _PINNED_REPOS
    now = time.time()
    if _repo_cache["value"] and now < _repo_cache["exp"]:
        return _repo_cache["value"]
    repos = []
    page = 1
    try:
        while True:
            batch = gh(f"orgs/{ORG}/repos?per_page=100&page={page}&type=all")
            if not batch:
                break
            repos.extend(r["full_name"] for r in batch if not r.get("archived"))
            if len(batch) < 100:
                break
            page += 1
    except Exception as e:
        log(f"served_repos() org scan failed: {e} (keeping previous list of {len(_repo_cache['value'])})")
        return _repo_cache["value"]  # stale-but-known beats an empty served set on a transient error
    _repo_cache["value"] = repos
    _repo_cache["exp"] = now + REPO_CACHE_S
    log(f"served_repos() refreshed: {len(repos)} repos in {ORG}")
    return repos


def _queued_jobs_for_repo(repo):
    jobs = []
    try:
        runs = gh(f"repos/{repo}/actions/runs?status=queued&per_page=30")["workflow_runs"]
        for run in runs:
            for j in gh(f"repos/{repo}/actions/runs/{run['id']}/jobs?per_page=50")["jobs"]:
                if j["status"] == "queued" and any(LABEL in (l or "") for l in j.get("labels", [])):
                    jobs.append(j)
    except Exception as e:
        # One slow/erroring repo must not block the others or silently eat the whole poll
        # cycle -- this call ran serially pre-org-wide (one repo); with N served repos a
        # single hung request could stall the entire loop with zero log output for minutes.
        log(f"queued_jobs({repo}) failed: {e}")
    return jobs


def queued_jobs():
    repos = served_repos()
    threads = []
    results = [None] * len(repos)

    def _run(i, repo):
        results[i] = _queued_jobs_for_repo(repo)

    for i, repo in enumerate(repos):
        t = threading.Thread(target=_run, args=(i, repo), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join(timeout=60)  # gh()'s own retries cap at ~45s worst case; 60s is headroom, not the bound
    jobs = []
    for r in results:
        jobs.extend(r or [])
    return jobs


def all_runners():
    """Every org runner registration, following pagination.

    `?per_page=100` alone SILENTLY TRUNCATES at 100. That is not hypothetical here: ephemeral
    workers leave their registration behind when the VM is deleted, so the org list grows well
    past the live fleet (measured 2026-08-26: 32 registrations for 6 online runners -- 21 stale
    az-ephemeral plus 5 retired blacksmith entries). Past 100, a truncated page silently drops
    runners from the `busy` sets built by cleanup() and manage_warm_pool(), and a busy runner
    missing from those sets is a runner eligible for reaping MID-JOB -- exactly the failure #898
    fixed by a different route (age cap killing sdk-audit's execution-sweep 20 minutes into a
    build, reported as a build failure). Truncation would reintroduce it silently, so paginate.

    100 per page is the API maximum. Stop on a short page; the 20-page cap is a runaway guard
    (2000 registrations is far past anything real) so a pathological response can never spin
    the poll loop forever -- the same defensive shape as gh()'s bounded retry.
    """
    out = []
    for page in range(1, 21):
        batch = gh(f"orgs/{ORG}/actions/runners?per_page=100&page={page}").get("runners") or []
        out.extend(batch)
        if len(batch) < 100:
            break
    return out


def runner_names():
    # Org-level: one shared pool, via RUNNER_GROUP, serves every repo served_repos() finds.
    return {r["name"] for r in all_runners()}


def busy_runner_names():
    """Names of runners GitHub reports as mid-job. NEVER derive this from a truncated listing:
    a busy runner absent from this set is one the reapers will happily delete under a live job."""
    return {r["name"] for r in all_runners() if r.get("busy")}


def delete_runner_registration(name):
    """Delete this worker's org runner registration BY NAME, ahead of deleting its VM.

    Why the reaper needs this and cannot leave it to _sweep_stale_registrations: that sweep is
    deliberately conservative -- it only prunes a registration that is offline, not busy, AND has
    no live VM. A worker being reaped for being stopped-but-registered fails the third condition
    at the moment of the reap (its VM is still listed), so its registration survives the cycle in
    which the VM dies and is only collected on some later pass. In the window between, the org
    runner list still asserts a runner that has no machine behind it. That assertion is what the
    reaper gap lived on: cleanup() reads `name in runners` as "this worker is alive", so a stale
    registration kept a corpse out of the unregistered rule for the whole MAX_AGE_S window. The
    registration goes FIRST so the two facts can never disagree -- the VM is deleted only after
    GitHub has been told the runner is gone.

    Matched by exact name (the runner registers with --name __VMNAME__, so name is the identity
    here, not the numeric id, which the caller does not have). Listed through all_runners() rather
    than a fresh `?per_page=100` call for the reason documented there: a truncated listing is how
    a busy runner went missing from the busy set once already.

    Returns True when the registration is gone or never existed, False when the delete failed.
    A False does NOT abort the VM delete -- freeing the quota is the point of the reap, and the
    failed registration is collected by _sweep_stale_registrations on a later pass once the VM is
    gone. It is logged loudly either way, because a registration this orchestrator cannot delete
    is one it also cannot account for."""
    try:
        runners = all_runners()
    except Exception as e:  # noqa: BLE001 -- listing failure must not wedge the reap
        log(f"registration delete for {name}: listing org runners failed: {e}")
        return False
    hits = [r for r in runners if (r.get("name") or "") == name]
    if not hits:
        log(f"registration delete for {name}: no org runner by that name, nothing to delete")
        return True
    ok = True
    for r in hits:
        rid = r.get("id")
        if rid is None:
            log(f"registration delete for {name}: runner entry carries no id ({r!r}) -- cannot "
                f"delete it; _sweep_stale_registrations will retry once the VM is gone")
            ok = False
            continue
        try:
            gh(f"orgs/{ORG}/actions/runners/{rid}", method="DELETE")
            log(f"deleted runner registration {name} (id={rid}) BEFORE deleting its VM")
        except Exception as e:  # noqa: BLE001 -- same reasoning as the listing above
            ok = False
            log(f"registration delete for {name} (id={rid}) FAILED: {e} -- the VM is still being "
                f"reaped, so the registration is left to _sweep_stale_registrations")
    return ok


# The `vm=<name>` stamp the bootstrap writes into its gist description. Anchored on the fleet's
# own name prefixes so a gist whose description merely mentions some other VM cannot be matched.
_GIST_VM_RE = re.compile(r"\bvm=(?P<vm>ci-(?:az|warm)-[0-9A-Za-z-]+)")


def _gist_index():
    """VM name -> boot-log gist URL, listed at most once per GIST_CACHE_S.

    WHY THIS EXISTS. /root/boot.log on a worker is the only record of why it failed to register,
    and the VM is deleted within minutes of that failure. #997 made the bootstrap PATCH boot.log
    to a private per-worker gist, so the evidence survives the delete -- but nothing ever said
    WHERE it went: the gist id lived in /root/gist.id on a machine that no longer exists. So
    "this worker never registered" was diagnosable only by guessing, and the 2026-09-16 runner
    -version outage cost nine hours partly for that reason.

    Resolved from THIS side of the delete instead. The bootstrap creates its gist with the same
    token the orchestrator holds, so those gists are this token owner's own and `GET /gists`
    lists them, description included. Matching is on the description the bootstrap stamps
    (`az-ci-worker vm=<name>`), which is why that stamp is part of this change: without it the
    only match key is inside the gist CONTENT, and the listing endpoint truncates content, so
    every match would cost an extra fetch per gist per reap.

    Bounded: GIST_MAX_PAGES pages of 100, most-recent-first (the API's own default ordering),
    cached so a cycle reaping a dozen workers pays ONE listing rather than twelve. A worker
    older than that window, or one booted before the description stamp shipped, simply reports
    no pointer -- a missing pointer is logged as missing, never guessed at.

    NEVER raises. This annotates a reap; annotating must not be able to prevent one."""
    now = time.time()
    if now - _gist_cache["at"] < GIST_CACHE_S:
        return _gist_cache["map"]
    _gist_cache["at"] = now  # set BEFORE the call: a failure must not cause a refetch per reap
    found = {}
    try:
        for page in range(1, GIST_MAX_PAGES + 1):
            batch = gh(f"gists?per_page=100&page={page}")
            if not isinstance(batch, list):
                break  # not a gist listing (an error body, or a stub in tests): stop, do not guess
            for g in batch:
                if not isinstance(g, dict):
                    continue
                m = _GIST_VM_RE.search(g.get("description") or "")
                if m and g.get("html_url"):
                    found.setdefault(m.group("vm"), g["html_url"])  # most recent wins
            if len(batch) < 100:
                break
    except Exception as e:  # noqa: BLE001 -- annotation is best-effort by construction
        log(f"gist index: listing failed ({e}); reaps this cycle will report no boot-log pointer")
        return _gist_cache["map"]
    _gist_cache["map"] = found
    return found


def gist_url_for(name):
    """The boot-log gist URL for this worker, or None if it cannot be resolved."""
    return _gist_index().get(name)


def live_vms():
    d = arm("GET", f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Compute/virtualMachines")
    out = []
    for v in d.get("value", []):
        if v["name"].startswith(("ci-az-", "ci-warm-")):
            out.append((v["name"], v.get("properties", {}).get("timeCreated", "2000-01-01T00:00:00"), v["location"]))
    return out


def vm_power_state(name):
    """This VM's power state ("running" / "stopped" / "deallocated" / ...), or None if unknown.

    PER-VM deliberately, not a collection call, because neither collection form works here
    (both verified live 2026-08-26 against this subscription):
      * `virtualMachines?$expand=instanceView` fails CONSISTENTLY -- 2/2 attempts returned
        502 ProviderError "Resource provider 'Microsoft.Compute' failed to return collection
        response for type 'virtualMachines'". Not a transient blip; do not "just retry" it.
      * `virtualMachines?statusOnly=true` returns 200 but carries no instanceView at all, so
        there is no power state in the payload to read.
    One call per VM is therefore the only shape that works, which is exactly why callers must
    ask only about VMs where the answer changes a decision -- never the whole fleet per poll.

    Returns None on any failure (unknown != stopped): the caller must fall back to the
    age-based rule rather than delete a VM it could not inspect."""
    try:
        d = arm("GET", f"{vm_path(name)}/instanceView")
    except Exception:  # noqa: BLE001 -- an uninspectable VM must not be deleted on that basis
        return None
    for s in d.get("statuses") or []:
        code = s.get("code") or ""
        if code.startswith("PowerState/"):
            return code.split("/", 1)[1]
    return None


def _stopped_twice(name, now):
    """The power state if this VM has been stopped/deallocated on TWO CONSECUTIVE polls at least
    STOPPED_CONFIRM_S apart; None otherwise (including "unknown", which must never read as
    stopped -- see vm_power_state).

    Returns the state string rather than a bool so the caller can label the deletion without
    paying a SECOND instanceView round-trip for the same answer.

    The two-poll shape is the same guard the leaked-nic and leaked-disk sweeps already use
    (_absent_once), for the same reason: one ARM read is allowed to be wrong, two agreeing reads
    spaced a minute apart are not. A worker that reboots itself (the bootstrap's
    `shutdown -h now` is a normal success path, and a job VM can be restarting Docker) can be
    caught mid-transition by a single sample; deleting a registered runner on one sample is how
    a healthy worker would get killed between two jobs.

    Streak bookkeeping: any non-stopped sighting CLEARS the entry, so the two observations have
    to be consecutive rather than merely both-happened-sometime. Nothing is logged on the first
    sighting beyond that one line, so a candidate costs at most one log line per streak and one
    per cycle thereafter -- never more than one line per VM per cycle."""
    state = vm_power_state(name)
    if state not in ("stopped", "deallocated"):
        _stopped_seen.pop(name, None)
        return None
    first = _stopped_seen.get(name)
    if first is None:
        _stopped_seen[name] = now
        log(f"stopped-but-registered: {name} is {state} (sighting 1/2, confirm on a later poll)")
        return None
    if now - first < STOPPED_CONFIRM_S:
        return None  # too soon to call this a second, independent observation
    _stopped_seen.pop(name, None)
    return state


def free_vcpus(region):
    try:
        d = arm("GET", f"/subscriptions/{SUB}/providers/Microsoft.Compute/locations/{region}/usages")
        free = {}
        for u in d.get("value", []):
            # Keys are LOWERCASED before matching: Azure is not self-consistent about family
            # casing. Live values include both `standardDSv3Family` and `StandardDsv6Family`
            # (capital S, lowercase "sv6"). A case-SENSITIVE startswith silently missed every
            # Dsv6/Dsv7-era family, so free.get(family(size)) returned 0 and those sizes were
            # never provisionable -- invisible, because "no quota" and "quota not matched" look
            # identical here. That made a 120-vCPU Dsv6 grant in centralus completely unusable
            # while the fleet fell through to nearly-full eastus2 (found live 2026-08-26).
            n = u["name"]["value"].lower()
            if n.startswith(("standarddsv", "standardfsv2")):
                free[n] = max(0, int(u["limit"]) - int(u["currentValue"]))
            elif n == "cores":  # total regional vCPU cap; family quota alone is not enough
                free["cores"] = max(0, int(u["limit"]) - int(u["currentValue"]))
        return free
    except Exception as e:
        log(f"usage {region} failed: {e}")
        return {}


def free_vcpus_cached(region):
    now = time.time()
    if region in _usage_cache and now - _usage_cache[region][0] < 120:
        return _usage_cache[region][1]
    free = free_vcpus(region)
    _usage_cache[region] = (now, free)
    return free


def family(size):
    # Returns a LOWERCASED key to match free_vcpus()'s lowercased map -- see the casing
    # note there. Never return mixed case from here.
    if size.startswith("Standard_F"):
        return "standardfsv2family"
    for f in ("v6", "v5", "v4", "v3"):
        if f in size:
            return f"standardds{f}family"
    return "standarddsv4family"


# Fallback actions/runner version for the stock-image bootstrap when the boot-time
# releases/latest lookup fails. This is the version PROVEN to register against the live org on
# 2026-09-16 (config.sh rc=0, "Runner successfully added"), and it is a floor, not a target:
# both bootstrap paths resolve the current release at boot and only fall back to this.
RUNNER_PIN = "2.337.0"

SSH_PUB = ""
for _p in ("/opt/ci/worker_key.pub", os.path.expanduser("~/.ssh/id_ed25519.pub")):
    try:
        with open(_p) as f:
            SSH_PUB = f.read().strip()
        break
    except OSError:
        pass

# Bootstrap lives in a write_files block scalar: plain runcmd lines containing
# "Header: value" are INVALID YAML (colon+space) and silently aborted cloud-init.
CLOUD_INIT = """#cloud-config
ssh_authorized_keys:
  - __SSH_PUB__
write_files:
  - path: /root/bootstrap.sh
    permissions: "0755"
    content: |
      #!/bin/bash
      TOK="__GH_TOKEN__"
      log(){ echo "T=$(date +%s) $*" | tee -a /root/boot.log; }
      up(){ python3 - <<PY
      import json,urllib.error,urllib.request
      gid="unknown"
      try:
          gid=open("/root/gist.id").read().strip()
          content=open("/root/boot.log").read()[-3000:]
          req=urllib.request.Request("https://api.github.com/gists/"+gid,method="PATCH",
           data=json.dumps({"files":{"boot.log":{"content":content}}}).encode(),
           headers={"Authorization":"Bearer $TOK","Accept":"application/vnd.github+json"})
          urllib.request.urlopen(req,timeout=30)
      except urllib.error.HTTPError as e:
          print("telemetry-flush-FAILED http=%s gist=%s" % (e.code,gid), file=open("/root/boot.log","a"))
      except Exception as e:
          print("telemetry-flush-FAILED %s gist=%s" % (type(e).__name__,gid), file=open("/root/boot.log","a"))
      PY
      }
      log start
      GIST=$(python3 - <<PY
      import json,urllib.request
      try:
          req=urllib.request.Request("https://api.github.com/gists",method="POST",
           data=json.dumps({"public":False,"description":"az-ci-worker vm=__VMNAME__","files":{"boot.log":{"content":"init"}}}).encode(),
           headers={"Authorization":"Bearer $TOK","Accept":"application/vnd.github+json"})
          print(json.load(urllib.request.urlopen(req,timeout=30))["id"])
      except Exception as e:
          print("ERR-%s"%e)
      PY
      )
      echo "$GIST" > /root/gist.id
      log "gist=$GIST"
      up
      # package set mirrors main's worker image: python3.14 (Test job + bundled-runtime
      # doctor gate) and clang/lld (Mojo shard builds link with clang).
      #
      # Docker: NOT Ubuntu's docker.io/docker-buildx universe packages -- those produced a
      # broken/absent buildx CLI plugin live on this fleet (root-caused 2026-08-25 against
      # actions/runner-images' own install-docker.sh, which never uses the distro packages
      # either). Docker's own apt repo + docker-buildx-plugin is the same method GitHub's
      # own hosted-runner images use.
      timeout 60 sh -c 'install -m 0755 -d /etc/apt/keyrings && curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc && chmod a+r /etc/apt/keyrings/docker.asc' >/dev/null 2>&1
      log "docker-repo-key rc=$?"
      echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
      timeout 420 sh -c 'apt-get update -qq && apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin ca-certificates curl git jq unzip rsync libicu70 libssl3 software-properties-common build-essential clang lld' >/dev/null 2>&1
      log "apt rc=$?"
      up
      # GitHub CLI is not in jammy main. It sits on RELEASE and SYNC paths (release-sdks.yml,
      # codna auto-release-cli.yml) that had not run since the fleet went org-wide -- so the
      # first real release would have been the discovery event, not a test.
      timeout 120 sh -c 'curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        -o /usr/share/keyrings/githubcli-archive-keyring.gpg && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
        && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list && apt-get update -qq && apt-get install -y -qq gh' >/dev/null 2>&1 || true
      log "gh rc=$?"
      add-apt-repository -y ppa:deadsnakes/ppa >/dev/null 2>&1
      timeout 240 sh -c 'apt-get update -qq && apt-get install -y -qq python3.14 python3.14-venv libpython3.14' >/dev/null 2>&1
      # deadsnakes ships no pip module; jobs call `python3.14 -m pip` directly.
      python3.14 -m ensurepip --upgrade >/dev/null 2>&1 || true
      # Provide a bare `python` as well. The Mac fleet this pool replaced had one, and the repos
      # that landed here when RUNNER_LABELS went org-wide still call it -- codna's CI runs
      # `python -m pip install -e ".[dev]"` and `python -m pytest`, both of which died with
      # `python: command not found` (exit 127) on this image. Point it at 3.14, not the distro
      # python3: ensurepip above gives 3.14 a working pip and the distro interpreter has none.
      ln -sf "$(command -v python3.14)" /usr/local/bin/python 2>/dev/null || true
      log "py314 rc=$?"
      up
      # Node.js: GitHub's own hosted-runner images ship it preinstalled; this hand-rolled
      # image never did, and the gap is NOT cosmetic. pnpm/action-setup's self-installer
      # shells out to `npm`, and with no system Node the only `npm` on PATH is the runner's
      # own bundled stub (/opt/runner/externals.*/node*/bin/npm) -- a 2-line shim that
      # requires ../lib/cli.js, which the runner's Node bundle does not ship. That fails
      # 100% of the time with "Cannot find module '../lib/cli.js'", which reads like a flaky
      # network install but is fully deterministic (root-caused 2026-08-25). NodeSource, not
      # Ubuntu's ancient distro nodejs.
      timeout 120 sh -c 'curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y -qq nodejs' >/dev/null 2>&1
      log "nodejs rc=$? version=$(node --version 2>/dev/null) npm=$(npm --version 2>/dev/null)"
      up
      systemctl enable --now docker
      # Pre-pull CI service images: cold workers otherwise race the ci.yml service-step
      # wait timeout on first pull (observed flake: 'Start Postgres + Dragonfly + MinIO').
      docker pull postgres:16-alpine >/dev/null 2>&1 || true
      docker pull docker.dragonflydb.io/dragonflydb/dragonfly:v1.39.0 >/dev/null 2>&1 || true
      docker pull quay.io/minio/minio:RELEASE.2025-04-22T22-12-26Z >/dev/null 2>&1 || true
      # Resolve the runner version at BOOT, with the pin below only as a fallback. A version
      # hardcoded in this template is the same time bomb as one baked into the image: GitHub
      # enforces a registration floor and moves it without notice, and a runner below it cannot
      # register at all -- which is what took the whole plane dark on 2026-09-16 when the floor
      # moved to 2.329.0 over an image baking 2.327.1. See CLOUD_INIT_FAST's runner-upgrade
      # block for the post-mortem. The fallback stays so a GitHub API outage cannot make the
      # stock path undownloadable; it is the floor we last PROVED registers, not a preference.
      RUNNER_VERSION=$(curl -s -m 20 https://api.github.com/repos/actions/runner/releases/latest | python3 -c "import json,sys;print(json.load(sys.stdin)['tag_name'].lstrip('v'))" 2>/dev/null)
      [ -n "$RUNNER_VERSION" ] || RUNNER_VERSION=__RUNNER_PIN__
      log "runner-version=$RUNNER_VERSION"
      curl -m 180 -o /tmp/runner.tar.gz -LsS "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
      log "runner-dl rc=$?"
      mkdir -p /opt/runner && tar -xzf /tmp/runner.tar.gz -C /opt/runner
      RT=$(curl -s -m 30 -X POST -H "Authorization: Bearer $TOK" -H "Accept: application/vnd.github+json" https://api.github.com/orgs/__ORG__/actions/runners/registration-token)
      log "token rc=$?"
      up
      TOKEN=$(echo "$RT" | python3 -c "import json,sys;print(json.load(sys.stdin)['token'])" 2>/dev/null)
      # runner config.sh refuses to run as root ("Must not run with sudo"); cloud-init is root.
      useradd -m -s /bin/bash runner 2>/dev/null || true
      usermod -aG docker runner 2>/dev/null || true
      chown -R runner:runner /opt/runner
      # Bounded like the fast path's, for the same reason: this was an unbounded step, and a
      # hung registration leaves a VM running-but-unregistered with nothing on it to explain
      # why. 124 is timeout(1)'s "never returned"; `-k 30` escalates because timeout signals
      # `su` and a dotnet child can ignore SIGTERM.
      timeout -k 30 240 su - runner -c "/opt/runner/config.sh --url https://github.com/__ORG__ --token '$TOKEN' --name __VMNAME__ --runnergroup '__RUNNERGROUP__' --labels az-ephemeral,self-hosted --ephemeral --unattended" >> /root/boot.log 2>&1
      log "config rc=$? (124 means config.sh timed out at 240s and was killed)"
      up
      su - runner -c "/opt/runner/run.sh" || true
      log "run-exited"
      up
      shutdown -h now || true
runcmd:
  - bash /root/bootstrap.sh
"""


def render_userdata(template, name, path):
    """Render one worker's cloud-init document and GATE it before ARM ever sees it.

    Two failure modes, both of which have already cost this plane:

    1. INVALID YAML. A bare runcmd line containing `-H "Authorization: Bearer ..."` carries a
       `: ` (colon+space), which is illegal in a YAML plain scalar. cloud-init parse-aborts and
       runcmd NEVER runs, so every worker provisions as a no-op VM: it boots, does nothing, gets
       swept ten minutes later, and nothing anywhere says why. The bootstrap lives in a
       write_files block scalar (block scalars permit colons) behind a single runcmd line, and
       this gate is what proves the document still parses AFTER substitution -- the template
       parsing is not enough, because the substituted values are what carry the colons.
    2. NON-ASCII. customData is latin-1 transported, so one em-dash in the payload fails the
       ARM PUT mid-deploy. Checked here rather than only in deploy_orchestrator.sh because the
       payload is assembled per worker and the token/name/group values are not static.

    Parsing alone is not sufficient: a document can be perfectly valid YAML and still have lost
    the bootstrap, which is failure mode 1 wearing a different hat. Hence the structural checks.
    """
    doc = (
        template.replace("__SSH_PUB__", SSH_PUB)
        .replace("__GH_TOKEN__", os.environ["GITHUB_CI_TOKEN"])
        .replace("__ORG__", ORG)
        .replace("__RUNNERGROUP__", RUNNER_GROUP)
        .replace("__VMNAME__", name)
        .replace("__RUNNER_PIN__", RUNNER_PIN)
    )
    non_ascii = sorted({c for c in doc if ord(c) > 127})
    if non_ascii:
        raise ValueError(
            f"userdata for {name} is not ASCII ({non_ascii[:5]!r}): cloud-init customData is "
            f"latin-1 transported, so the ARM PUT would fail mid-deploy"
        )
    parsed = yaml.safe_load(doc) or {}  # raises on the colon-in-a-plain-scalar class of breakage
    written = {f.get("path"): f.get("content", "") for f in parsed.get("write_files", [])}
    runcmd = parsed.get("runcmd") or []
    if not any("/root/bootstrap.sh" in str(c) for c in runcmd):
        raise ValueError(
            f"userdata for {name} parses but runcmd={runcmd!r} never invokes /root/bootstrap.sh "
            f"-- the worker would boot, do nothing, and be swept as an orphan"
        )
    if not written.get("/root/bootstrap.sh", "").strip():
        raise ValueError(f"userdata for {name} parses but /root/bootstrap.sh came out empty")
    with open(path, "w") as f:
        f.write(doc)
    return path


def write_ci_file(name):
    return render_userdata(CLOUD_INIT, name, f"{STATE}/{name}.yml")


def subnet_id(region, vnet, subnet):
    return (
        f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Network/"
        f"virtualNetworks/{vnet}/subnets/{subnet}"
    )


# ── tier0 repair budget (2026-09-16) ──────────────────────────────────────────────────────────
# The dpkg-lock wait and the single retry that CLOUD_INIT_FAST's repair block now performs are
# bounded by these two numbers, and the bound is the whole point: the repair BLOCKS registration
# (see [notes].repair_blocks_registration in infra/ci/image/manifest.toml), so every second added
# here is a second of boot latency paid on every cold provision and every warm-pool refill.
#
# They are mirrored as LITERALS in the shell rather than substituted into it. CLOUD_INIT_FAST has
# to stay a plain string constant -- tests/test_az_orchestrator_runner_version_floor.py lifts the
# two templates straight out of the module AST and asserts both are constants, because that is
# what proves a worker receives the raw text rather than a reconstruction of it -- and adding a
# placeholder would break render_userdata's own "no unsubstituted placeholder" gate. So the
# arithmetic lives here, the numbers live there, and a test pins the two together.
TIER0_LOCK_WAIT_S = 30      # flock -w on the dpkg frontend lock; once per attempt, two attempts
TIER0_RETRY_BUDGET_S = 30   # hard ceiling for the whole retry pass, not per package
TIER0_ADDED_BUDGET_S = 90   # the promise: worst case this hardening ADDS to a boot


def tier0_repair_added_s(lock_wait=TIER0_LOCK_WAIT_S, retry=TIER0_RETRY_BUDGET_S):
    """Worst-case seconds the lock-wait + one-retry hardening ADDS to a worker boot.

    Two bounded lock waits (one before the first install attempt, one before the retry) plus one
    bounded retry pass. The retry is capped as a PASS, not per package, so a boot missing all
    three tier0 tools pays the retry budget once and not three times.

    The pre-existing install timeouts (120s for the distro packages, 150s for the gh chain) are
    deliberately NOT counted: they were already the repair block's worst case before this
    hardening, so they are not added by it. That is the number to compare against
    TIER0_ADDED_BUDGET_S, and it is why the promise is expressed as an addition rather than as a
    total -- a total would have to move every time an install timeout is retuned, and would say
    nothing about what THIS change cost."""
    return 2 * lock_wait + retry


CLOUD_INIT_FAST = """#cloud-config
ssh_authorized_keys:
  - __SSH_PUB__
write_files:
  - path: /root/bootstrap.sh
    permissions: "0755"
    content: |
      #!/bin/bash
      # NO `set -e`, deliberately. Every step below is either a best-effort repair or the
      # registration attempt itself, and the two things that must always happen are that
      # config.sh is reached and that whatever happened on the way is reported. Aborting early
      # is how a 54-second config.sh failure became a nine-hour undiagnosable outage on
      # 2026-09-16: the VM powered itself off, wrote nothing anywhere, and the only observable
      # was an Azure power state.
      TOK="__GH_TOKEN__"
      BOOT_T0=$(date +%s)
      log(){ echo "T=$(date +%s) +$(( $(date +%s) - BOOT_T0 ))s $*" | tee -a /root/boot.log; }
      up(){ python3 - <<PY
      import json,urllib.error,urllib.request
      gid="unknown"
      try:
          gid=open("/root/gist.id").read().strip()
          content=open("/root/boot.log").read()[-4000:]
          req=urllib.request.Request("https://api.github.com/gists/"+gid,method="PATCH",
           data=json.dumps({"files":{"boot.log":{"content":content}}}).encode(),
           headers={"Authorization":"Bearer $TOK","Accept":"application/vnd.github+json"})
          urllib.request.urlopen(req,timeout=30)
      except urllib.error.HTTPError as e:
          print("telemetry-flush-FAILED http=%s gist=%s" % (e.code,gid), file=open("/root/boot.log","a"))
      except Exception as e:
          print("telemetry-flush-FAILED %s gist=%s" % (type(e).__name__,gid), file=open("/root/boot.log","a"))
      PY
      }
      # The fast path had NO telemetry at all until 2026-09-16 -- that is the whole reason the
      # outage below took hours. CLOUD_INIT (the stock-image path) has always PATCHed
      # /root/boot.log to a per-worker private gist; the golden path, which is the path every
      # real worker takes, wrote nothing, so /root/boot.log was empty on every corpse and read
      # as "bootstrap never ran" when in fact it ran to completion and failed at config.sh.
      log "fast-bootstrap-start vm=__VMNAME__"
      GIST=$(python3 - <<PY
      import json,urllib.request
      try:
          req=urllib.request.Request("https://api.github.com/gists",method="POST",
           data=json.dumps({"public":False,"description":"az-ci-worker vm=__VMNAME__","files":{"boot.log":{"content":"init"}}}).encode(),
           headers={"Authorization":"Bearer $TOK","Accept":"application/vnd.github+json"})
          print(json.load(urllib.request.urlopen(req,timeout=30))["id"])
      except Exception as e:
          print("ERR-%s"%e)
      PY
      )
      echo "$GIST" > /root/gist.id
      log "gist=$GIST"
      up
      # ---- stage: token-fetch ----
      get_token(){ curl -s -m 30 -X POST -H "Authorization: Bearer $TOK" -H "Accept: application/vnd.github+json" https://api.github.com/orgs/__ORG__/actions/runners/registration-token | python3 -c "import json,sys;print(json.load(sys.stdin)['token'])" 2>/dev/null; }
      TOKEN=$(get_token)
      TOK_RC=$?
      # The LENGTH, never the value: this file is PATCHed to a gist. len=0 is the distinction
      # that matters (fetch failed vs parse failed vs succeeded) and the one the old bootstrap
      # threw away by writing nothing.
      log "token-fetch rc=$TOK_RC len=${#TOKEN}"
      up
      # The GOLDEN IMAGE predates two things the retired Mac fleet provided and that repos moved
      # here by the org-wide RUNNER_LABELS still expect. Reasserted per boot because patching
      # CLOUD_INIT alone would never reach a golden-image VM -- and that IS the normal path now.
      # Both are guarded, so each becomes a no-op the moment the image is recaptured:
      #   python : codna runs `python -m pip` / `python -m pytest` -> exit 127 without it
      #   unzip  : actions/setup-bun shells out to it -> "Unable to locate executable file: unzip"
      command -v python >/dev/null 2>&1 || ln -sf "$(command -v python3.14 || command -v python3)" /usr/local/bin/python 2>/dev/null || true
      # BLOCKING, and it has to be. This was backgrounded to protect boot latency, and the race
      # that choice accepted fired on its FIRST real test rather than as a rare tail:
      #
      #   orchestrator deployed  03:52Z
      #   ci-warm-1787804191 booted  04:16:31Z   <- carried this repair
      #   its job started        04:17:25Z   <- 54s later
      #   result                 gh: command not found, exit 127
      #
      # Adding the cli.github.com repo and apt-installing gh does not finish in 54 seconds, so
      # codna's release failed on a VM that HAD the fix. Registering a runner while its
      # guaranteed tier0 tools are still installing advertises a guarantee the machine cannot
      # keep -- the same class of untruth the image contract exists to stop. A runner that is
      # not ready must not claim to be ready.
      #
      # The cost is real and bounded: ~20-40s before a new VM joins the pool, which affects cold
      # provisions and warm-pool refill, not warm hits (those VMs are already registered).
      # Recapturing the golden image deletes this whole block and the cost with it.
      log "repair-start"
      # ---- the dpkg lock, and why this stage now waits for it ----
      # Two workers booting in the same minute on 2026-09-16 reported OPPOSITE verdicts for the
      # SAME gallery image: one had unzip and gh, the other had neither. Both were built from
      # version 1.0.0, so the image is not the variable -- the boot is. The suspected cause is
      # contention on /var/lib/dpkg/lock-frontend early in boot: cloud-init runs its own package
      # work (unattended-upgrades, package-update-before-boot) concurrently with this block, and
      # an `apt-get install` that loses the lock race exits non-zero in milliseconds. SUSPECTED,
      # NOT PROVEN -- and that is itself the finding worth recording: the old shape redirected
      # every attempt to >/dev/null, tried once, and never re-probed, so it could not distinguish
      # "somebody else held the lock" from "this package does not exist" and reported neither.
      #
      # So: wait for the lock, retry once, re-verify every tier0 tool, and NAME anything still
      # missing. All of it bounded -- see tier0_repair_added_s(), whose arithmetic a test pins to
      # the literals below: worst case 90s added to a boot, on a stage that already blocks
      # registration by design.
      #
      # `flock -w N <lockfile> true` IS the wait: block until the lock is granted or N seconds
      # pass, run `true`, release. Best-effort in both directions -- an absent lockfile or a
      # timed-out wait falls through to the install anyway, because a boot is never gated on a
      # lock and a tool that is still missing afterwards is named in the verdict below.
      wait_dpkg_lock(){ flock -w 30 /var/lib/dpkg/lock-frontend true 2>/dev/null || true; }
      # Seconds left until a deadline, floored at 1. The floor is not decoration: `timeout 0`
      # means NO timeout in coreutils, so an exhausted budget echoed as 0 would silently unbound
      # the very step it was capping -- the exact inverse of what this block is for.
      secs_left(){ d=$(( $1 - $(date +%s) )); [ "$d" -gt 1 ] && echo "$d" || echo 1; }
      (
        # One `command -v <tool>` per tool, deliberately not a loop over "$t": the contract test
        # greps for exactly that literal per tier0 entry, so a loop would satisfy the shell while
        # leaving the gate blind -- which is the class of hole that let `gh` ship missing. Kept as
        # a function so the probe, the re-verification and the retry all decide from the SAME
        # per-tool list instead of from three hand-maintained copies of it.
        tier0_missing(){
          m=""
          command -v unzip >/dev/null 2>&1 || m="$m unzip"
          command -v rsync >/dev/null 2>&1 || m="$m rsync"
          command -v gh >/dev/null 2>&1 || m="$m gh"
          echo "$m"
        }
        NEED=$(tier0_missing)
        log "repair-probe missing=${NEED:-none}"
        # The apt-installable subset. `gh` ships from cli.github.com, not jammy main, so it gets
        # its own chain below rather than being handed to this install line.
        PKGS=""
        case "$NEED" in *unzip*) PKGS="$PKGS unzip" ;; esac
        case "$NEED" in *rsync*) PKGS="$PKGS rsync" ;; esac
        # ONE lock wait per attempt, not one per install command. That is a budget constraint,
        # not a style choice: tier0_repair_added_s() accounts for exactly two waits plus the
        # retry, and a test counts the call sites in this rendered shell so a third one cannot
        # be added without the promise being re-stated. Gated on something actually being
        # missing, because flock on a lock that unattended-upgrades happens to hold would
        # otherwise cost a boot 30s to repair nothing.
        if [ -n "$NEED" ]; then
          wait_dpkg_lock
        fi
        if [ -n "$PKGS" ]; then
          timeout 120 sh -c "apt-get update -qq && apt-get install -y -qq $PKGS" >/dev/null 2>&1
        fi
        # `gh` is NOT in jammy main -- it ships from cli.github.com, the same third-party-repo
        # pattern the full bootstrap already uses for docker-ce. This one is not hypothetical:
        # codna's auto-release-cli died with `gh: command not found` (exit 127) on the FIRST real
        # release after the fleet went org-wide, which is exactly the event infra/ci/image/
        # manifest.toml predicted when it declared gh tier0. It was declared and apt-installed in
        # CLOUD_INIT, but never repaired HERE -- and CLOUD_INIT never runs on a golden-image VM.
        case "$NEED" in *gh*)
          timeout 150 sh -c 'curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list && apt-get update -qq && apt-get install -y -qq gh' >/dev/null 2>&1 ;;
        esac
        # ---- re-verify, then ONE retry under its own hard ceiling ----
        # Driven by a re-probe and never by an exit code, because an install can exit 0 and still
        # leave the binary absent, and can exit non-zero merely because the lock was held. Only
        # looking at the filesystem again tells those apart.
        STILL=$(tier0_missing)
        if [ -n "$STILL" ]; then
          log "repair-retry still-missing=$STILL lock-wait=done attempt=2of2"
          RETRY_BY=$(( $(date +%s) + 30 ))
          wait_dpkg_lock
          PKGS=""
          case "$STILL" in *unzip*) PKGS="$PKGS unzip" ;; esac
          case "$STILL" in *rsync*) PKGS="$PKGS rsync" ;; esac
          # No `apt-get update` on the retry: the lists are already warm from the first attempt,
          # and dropping it is what makes a 30s ceiling realistic rather than aspirational.
          if [ -n "$PKGS" ]; then
            timeout "$(secs_left "$RETRY_BY")" sh -c "apt-get install -y -qq $PKGS" >/dev/null 2>&1
          fi
          # The gh chain keeps its own repo setup, because a first attempt that died at the
          # keyring curl left no sources.list.d entry for a bare install to succeed against.
          case "$STILL" in *gh*)
            timeout "$(secs_left "$RETRY_BY")" sh -c 'curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list && apt-get update -qq && apt-get install -y -qq gh' >/dev/null 2>&1 ;;
          esac
        fi
        touch /var/run/ci-image-repair-done 2>/dev/null || true
      )
      # ---- per-tool verdicts, uploaded with the rest of boot.log ----
      # The PATHS, not the exit codes, are what get reported. Every timeout above is bounded, so a
      # network failure degrades to "tool still missing" rather than wedging the boot -- and a
      # missing tool is then named here, in the one channel that outlives the VM. A job that needs
      # it still fails; what it must never do is fail silently, or fail looking like a build bug.
      V_unzip=OK; command -v unzip >/dev/null 2>&1 || V_unzip=MISSING
      V_rsync=OK; command -v rsync >/dev/null 2>&1 || V_rsync=MISSING
      V_gh=OK; command -v gh >/dev/null 2>&1 || V_gh=MISSING
      V_python=OK; command -v python >/dev/null 2>&1 || V_python=MISSING
      log "repair-done unzip=$V_unzip rsync=$V_rsync gh=$V_gh python=$V_python"
      GONE=""
      [ "$V_unzip" = "MISSING" ] && GONE="$GONE unzip"
      [ "$V_rsync" = "MISSING" ] && GONE="$GONE rsync"
      [ "$V_gh" = "MISSING" ] && GONE="$GONE gh"
      [ "$V_python" = "MISSING" ] && GONE="$GONE python"
      # A tier0 tool that survived a lock wait AND a retry is a broken guarantee, so it is said
      # outright and named -- not left for a job to discover as an exit 127 fifty seconds in.
      [ -n "$GONE" ] && log "repair-incomplete TIER0-STILL-MISSING:$GONE after lock-wait and one retry"
      up
      # ---- stage: runner-upgrade ----
      # GitHub enforces a MINIMUM self-hosted-runner version at REGISTRATION time. Below the
      # floor, POST /actions/runner-registration answers 404 with a "RUNNER UPDATE REQUIRED"
      # box, config.sh exits non-zero, run.sh reports "Not configured" and exits, and this
      # script falls through to `shutdown -h now`. The VM then powers itself off looking
      # exactly like a worker that finished its job, so the only fleet-visible symptom is
      # "workers never register" -- with nothing on the worker saying why.
      #
      # THAT IS WHAT TOOK THE WHOLE PLANE DOWN ON 2026-09-16. The gallery image bakes
      # actions/runner 2.327.1 (captured 2026-08-26) and GitHub moved the floor to 2.329.0;
      # from ~07:00Z every worker died the same way, ~55s into its own bootstrap. Reproduced
      # verbatim on a live Standard_D8s_v5 created from gallery version 1.0.0 in centralus:
      #   18:20:52 su - runner -c "/opt/runner/config.sh ..."
      #   18:21:06 Http response code: NotFound from 'POST .../actions/runner-registration'
      #   18:21:06 ERROR: Your runner version is out of date and can no longer register.
      #   18:21:06 The minimum runner version required to register is now 2.329.0.
      #   18:21:06 An error occurred: Not configured. Run config.(sh/cmd) to configure.
      #   18:21:06 + shutdown -h now
      # Upgrading the same VM to 2.337.0 and re-running config.sh registered it immediately
      # ("Runner successfully added", rc=0), which is the whole of the causal proof.
      #
      # A runner version pinned inside a FROZEN image is a time bomb whose fuse GitHub holds,
      # and recapturing the image only resets the fuse -- today's 2.329.0 is tomorrow's 2.340.
      # So resolve releases/latest at boot and upgrade in place. Measured on that same worker:
      # the lookup costs 0.17s and the 226 MB tarball downloads in 1.8s, so the stage is ~8s
      # against a ~55s bootstrap -- cheap insurance against the fleet going dark again.
      #
      # Nothing here can abort the boot. If the lookup or the download fails, the baked runner
      # stays and config.sh is still attempted, so a GitHub API outage degrades to the previous
      # behaviour instead of becoming a new failure mode.
      runner_version(){ ( cd /opt/runner && ./bin/Runner.Listener --version 2>/dev/null | tail -1 ); }
      HAVE=$(runner_version)
      # dpkg calls amd64 what the release asset calls x64; arm64 is spelled the same in both.
      case "$(dpkg --print-architecture 2>/dev/null)" in
        arm64) RARCH=arm64 ;;
        *) RARCH=x64 ;;
      esac
      # ---- resolve WHAT to install, and how to PROVE the download ----
      # The org downloads endpoint is tried first because it is the only source that gives both
      # halves in one call: the asset URL GitHub itself serves for this org, and its
      # `sha256_checksum`. releases/latest below stays as the fallback, and stays a real fallback
      # rather than being deleted, because losing version resolution ENTIRELY is the 2026-09-16
      # outage -- a boot that cannot verify its tarball but can still upgrade beats a fleet that
      # cannot register at all.
      #
      # The one-liner form is deliberate, not golf. This is a plain (non-raw) Python
      # triple-quoted string inside a YAML block scalar, so a multi-line python3 -c body would
      # have to survive two independent indentation regimes and one backslash-interpretation
      # pass; render_userdata() gates the result, but a gate that fires is an outage, not a
      # save. One physical line has no indentation to get wrong.
      #
      # The version is read from TWO places, url path first and filename second. Only the url
      # form (`.../download/v2.337.0/...`) was parsed at first, and a test fixture using a
      # plainer url exposed the consequence: the version came back empty, `WANT` was empty, and
      # the block silently took the releases/latest fallback -- losing the checksum, which is
      # the entire reason this endpoint is consulted. One url-shape change at GitHub's end would
      # have downgraded every boot to unverifiable without anything failing loudly.
      DL=$(curl -s -m 20 -H "Authorization: Bearer $TOK" -H "Accept: application/vnd.github+json" "https://api.github.com/orgs/__ORG__/actions/runners/downloads" 2>/dev/null)
      DLINFO=$(DL_JSON="$DL" RARCH="$RARCH" python3 -c 'import json,os,re; d=json.loads(os.environ.get("DL_JSON") or "[]"); a=[x for x in d if isinstance(x,dict) and x.get("os")=="linux" and x.get("architecture")==os.environ.get("RARCH")]; e=a[0] if a else {}; u=e.get("download_url") or ""; m=re.search(r"/v([0-9][0-9.]*)/",u) or re.search(r"([0-9]+[.][0-9]+[.][0-9]+)",e.get("filename") or ""); print(u,(e.get("sha256_checksum") or ""),(m.group(1) if m else ""))' 2>/dev/null)
      URL=$(printf '%s' "$DLINFO" | awk '{print $1}')
      SUM=$(printf '%s' "$DLINFO" | awk '{print $2}')
      WANT=$(printf '%s' "$DLINFO" | awk '{print $3}')
      if [ -z "$WANT" ]; then
        WANT=$(curl -s -m 20 https://api.github.com/repos/actions/runner/releases/latest | python3 -c "import json,sys;print(json.load(sys.stdin)['tag_name'].lstrip('v'))" 2>/dev/null)
        URL="https://github.com/actions/runner/releases/download/v${WANT}/actions-runner-linux-${RARCH}-${WANT}.tar.gz"
        SUM=""
        log "runner-upgrade downloads-endpoint gave no linux/$RARCH asset; fell back to releases/latest, so this boot CANNOT checksum-verify the tarball and will fall back to a gzip integrity test"
      fi
      UPGRADE_NEEDED=0
      if [ -n "$WANT" ]; then
        if [ -z "$HAVE" ]; then
          UPGRADE_NEEDED=1
        elif [ "$HAVE" != "$WANT" ]; then
          # sort -V orders the two versions; if the older of the pair is HAVE, an upgrade is
          # due. Written with two echos rather than a printf format string on purpose: this
          # template is a plain (non-raw) Python triple-quoted string, so a literal backslash-n
          # here would be interpreted by PYTHON as a real newline and split the shell line --
          # which ends the YAML block scalar and is exactly what render_userdata() gates on.
          if [ "$( { echo "$HAVE"; echo "$WANT"; } | sort -V | head -1 )" = "$HAVE" ]; then
            UPGRADE_NEEDED=1
          fi
        fi
      fi
      if [ "$UPGRADE_NEEDED" = "1" ]; then
        if [ -n "$SUM" ]; then SUMSTATE=present; else SUMSTATE=UNAVAILABLE; fi
        log "runner-upgrade-start have=${HAVE:-unknown} want=$WANT arch=$RARCH checksum=$SUMSTATE"
        # WHY VERIFY BEFORE EXTRACTING. The old guard was `[ -s /tmp/runner-new.tar.gz ]` --
        # non-empty. A CDN or redirect failure that returns an HTML error page satisfies
        # "non-empty" perfectly, and the next line then ran `tar -xzf` over the LIVE /opt/runner
        # tree: the extraction fails partway, leaving a runner that is neither the baked version
        # nor the new one. That is strictly worse than not upgrading, and it is invisible -- the
        # only symptom is config.sh behaving oddly on a half-overwritten tree. So: verify, and
        # only then touch /opt/runner.
        #
        # TWO attempts, and the retry covers download+verify+extract as a unit rather than the
        # curl alone, because a corrupt tarball is as much a failure as a missing one and
        # re-extracting bytes we already know are bad cannot help.
        UPGRADE_OK=0
        for uattempt in 1 2; do
          HTTP=$(timeout 300 curl -sL -o /tmp/runner-new.tar.gz -w "%{http_code}" "$URL" 2>/dev/null)
          BYTES=$(wc -c < /tmp/runner-new.tar.gz 2>/dev/null || echo 0)
          VERIFIED=0
          if [ -n "$SUM" ]; then
            GOT=$(sha256sum /tmp/runner-new.tar.gz 2>/dev/null | awk '{print $1}')
            if [ "$GOT" = "$SUM" ]; then
              VERIFIED=1
              log "runner-upgrade-download attempt=$uattempt http=$HTTP bytes=$BYTES sha256=MATCH"
            else
              log "runner-upgrade-download attempt=$uattempt http=$HTTP bytes=$BYTES sha256=MISMATCH got=${GOT:-none} want=$SUM -- refusing to extract over /opt/runner"
            fi
          elif gzip -t /tmp/runner-new.tar.gz >/dev/null 2>&1; then
            # No checksum to compare against, so the next best proof that this is a tarball and
            # not an error page. Weaker -- it cannot detect a valid gzip of the WRONG version --
            # and said so in the log line above rather than passing silently.
            VERIFIED=1
            log "runner-upgrade-download attempt=$uattempt http=$HTTP bytes=$BYTES sha256=UNAVAILABLE gzip=VALID"
          else
            log "runner-upgrade-download attempt=$uattempt http=$HTTP bytes=$BYTES sha256=UNAVAILABLE gzip=INVALID -- refusing to extract over /opt/runner"
          fi
          if [ "$VERIFIED" = "1" ]; then
            if tar -xzf /tmp/runner-new.tar.gz -C /opt/runner 2>>/root/boot.log; then
              UPGRADE_OK=1
              log "runner-upgrade-extract attempt=$uattempt ok"
            else
              log "runner-upgrade-extract attempt=$uattempt FAILED rc=$?"
            fi
          fi
          rm -f /tmp/runner-new.tar.gz
          [ "$UPGRADE_OK" = "1" ] && break
        done
        if [ "$UPGRADE_OK" = "1" ]; then
          # Clear any half-written config state so config.sh starts clean. Safe because this
          # stage always runs BEFORE config.sh.
          rm -f /opt/runner/.runner /opt/runner/.credentials /opt/runner/.credentials_rsaparams /opt/runner/.service 2>/dev/null || true
        else
          # Degrade, do not gate: the baked runner stays and config.sh is still attempted, so a
          # GitHub or CDN outage costs the previous behaviour instead of becoming a new failure
          # mode. But say so LOUDLY and name the version being kept, because "the fleet will not
          # register" and "the fleet will not register because the upgrade was abandoned and the
          # baked runner is below the floor" are the same symptom with very different causes.
          log "runner-upgrade ABANDONED after 2 attempts; keeping baked runner ${HAVE:-unknown}. If that is below the registration floor, config.sh will report it below and this VM will power off."
        fi
      else
        log "runner-upgrade-skip have=${HAVE:-unknown} want=${WANT:-unresolved}"
      fi
      log "runner-upgrade-done now=$(runner_version)"
      up
      # ---- stage: config ----
      useradd -m -s /bin/bash runner 2>/dev/null || true
      usermod -aG docker runner 2>/dev/null || true
      chown -R runner:runner /opt/runner
      # config.sh output goes to boot.log, and therefore to the gist. That redirect is the
      # difference between "the fleet is dark" and "the fleet is dark because GitHub says
      # RUNNER UPDATE REQUIRED" -- the message above was invisible for nine hours purely
      # because it landed in a cloud-init log nobody reads on a VM that no longer exists.
      #
      # Two attempts, and the retry re-fetches the token rather than replaying it: a
      # registration token is short-lived and may already be spent. Not a loop -- if GitHub is
      # refusing registration a third attempt will not change the answer, and burning boot
      # time here only delays the report that says so.
      #
      # BOUNDED, at 240s, and this was the last unbounded step in the bootstrap. Every other
      # network call here carries a -m/--timeout except this one, so a config.sh that stalled
      # (registration endpoint accepting the connection and never answering) blocked the script
      # forever: the VM stayed RUNNING and unregistered, which reads to cleanup() as neither
      # stopped nor registered, so it survived to BOOT_GRACE_S and was then reaped as
      # orphan-no-runner with nothing on the machine explaining why. `-k 30` escalates to
      # SIGKILL, because timeout(1) signals `su` and a dotnet child can ignore SIGTERM.
      CFG_RC=1
      for attempt in 1 2; do
        [ -n "$TOKEN" ] || TOKEN=$(get_token)
        timeout -k 30 240 su - runner -c "/opt/runner/config.sh --url https://github.com/__ORG__ --token '$TOKEN' --name __VMNAME__ --runnergroup '__RUNNERGROUP__' --labels az-ephemeral,self-hosted --ephemeral --unattended" >>/root/boot.log 2>&1
        CFG_RC=$?
        if [ "$CFG_RC" = "124" ]; then
          log "config-TIMEOUT attempt=$attempt: config.sh did not return within 240s and was killed. A hung registration, not a refused one -- the distinction matters, because a refusal names a cause and a hang does not."
        fi
        log "config-rc=$CFG_RC attempt=$attempt runner-version=$(runner_version)"
        up
        [ "$CFG_RC" = "0" ] && break
        TOKEN=""
      done
      if [ "$CFG_RC" != "0" ]; then
        # Say what is about to happen and why, THEN let the machine go. A worker that cannot
        # register will never become useful, and holding it only spends quota -- but powering
        # off silently is exactly the failure that made this outage undiagnosable. The state
        # that led here is named on the same line, so a reader of the journal or the gist does
        # not have to reconstruct it from four earlier stages: which rc, which runner version
        # ended up installed, and whether the upgrade that was supposed to produce it succeeded.
        if [ "$CFG_RC" = "124" ]; then HOW="config.sh TIMED OUT after 240s and was killed"; else HOW="config.sh returned rc=$CFG_RC"; fi
        log "config-failed: runner did not register -- $HOW; runner-version=$(runner_version), wanted=${WANT:-unresolved}, upgrade-ok=${UPGRADE_OK:-not-attempted}. Powering off so the reaper can free this VM's quota. The config.sh output above is the reason and is in this VM's boot-log gist."
        up
        shutdown -h now || true
        exit 0
      fi
      # ---- stage: run ----
      # An ephemeral runner exits by itself after its one job, so reaching the shutdown below
      # with rc=0 is the SUCCESS path, not an error.
      log "run-started"
      up
      su - runner -c "/opt/runner/run.sh"
      RUN_RC=$?
      log "run-exited rc=$RUN_RC"
      up
      shutdown -h now || true
runcmd:
  - bash /root/bootstrap.sh
"""


_golden_ok = None


def golden_available():
    # Probe GOLDEN_IMAGE once: a missing/not-yet-replicated image would otherwise 404 on every
    # single provision attempt, in every region. (v1 was referenced here for a long stretch
    # while never actually having been captured -- the probe is what kept that cheap.)
    global _golden_ok
    if _golden_ok is None:
        try:
            arm("GET", GOLDEN_IMAGE, api="2023-07-03")
            _golden_ok = True
        except urllib.error.HTTPError as e:
            _golden_ok = e.code != 404
        except Exception:
            _golden_ok = False
        log(f"golden image ci-worker-v1 available: {_golden_ok}")
    return _golden_ok


def _exists(path, api):
    try:
        arm("GET", path, api=api)
        return True
    except urllib.error.HTTPError as e:
        return e.code != 404


def _wait_gone(path, api, timeout=90):
    # ARM deletes are async; re-PUTting while the old resource is still Deleting 409s/404s.
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _exists(path, api):
            return True
        time.sleep(5)
    return False


def create_vm(name, size, region, vnet, subnet):
    # No public IP: workers only need outbound (Azure default SNAT), and the 20-PIP
    # per-region quota was a recurring wall. Inbound debug access goes through the
    # gist log sink in cloud-init instead of SSH.
    nic = nic_path_for(name, region)
    for p, api in ((vm_path(name), "2023-07-01"), (nic, "2022-07-01")):
        if _exists(p, api):  # same-region leftovers from an earlier failed attempt (409 otherwise)
            try:
                arm("DELETE", p, api=api)
            except Exception:
                pass
            _wait_gone(p, api)
    try:
        _create_vm(name, size, region, vnet, subnet, nic)
    except Exception:
        clear_net(name, region)
        raise


# An ephemeral os disk needs a local temp disk at least as large as the image, and MOST OF
# SIZE_CHAIN HAS NONE. Measured in centralus: D8s_v5 / D8s_v6 / D8s_v4 / D4s_v5 / D4s_v4 all report
# 0 MB of resource disk; F8s_v2 and D8s_v3 (65536), F4s_v2 and D4s_v3 (32768) can do it. SIZE_CHAIN
# prefers D8s_v5, so the "zero storage cost" path was failing on the COMMON case and every fallback
# created a managed 30 GB Premium P4 disk that delete_vm() never removed. The fallback still needs a
# managed disk -- no choice on those sizes -- but now one ARM deletes with the VM.
_MANAGED_OS_DISK = {"createOption": "FromImage", "deleteOption": "Delete"}


def _create_vm(name, size, region, vnet, subnet, nic):
    arm(
        "PUT",
        nic,
        {
            "location": region,
            "properties": {
                "ipConfigurations": [
                    {"name": "ip", "properties": {"subnet": {"id": subnet_id(region, vnet, subnet)}}}
                ]
            },
        },
        api="2022-07-01",
    )
    pwd = "Ci-" + secrets.token_urlsafe(16)
    # No region gate: GOLDEN_IMAGE is a gallery version replicated to every region in
    # REGIONS, so the fast path applies fleet-wide. This was `region == GOLDEN_REGION`
    # while the golden image was a single-region managed image -- which meant 7 of 8
    # regions always paid the full 3-6min bootstrap and were the reason usable runner
    # count lagged VM count so badly under load.
    golden = golden_available()
    if golden:
        # Gated. render_userdata() refuses to hand back a document that does not parse, is not
        # ASCII, or lost the bootstrap -- all three of which have shipped on this plane and all
        # three of which present identically from the outside: a VM that never registers.
        ci_file = render_userdata(CLOUD_INIT_FAST, name, f"{STATE}/{name}.fast.yml")
        image_ref = {"id": GOLDEN_IMAGE}
    else:
        ci_file = f"{STATE}/{name}.yml"
        image_ref = {
            "publisher": "Canonical",
            "offer": "0001-com-ubuntu-server-jammy",
            "sku": "22_04-lts-gen2",
            "version": "latest",
        }
    props = {
        "hardwareProfile": {"vmSize": size},
        "storageProfile": {"imageReference": image_ref},
        "osProfile": {
            "computerName": name[:64],
            "adminUsername": "azureuser",
            "adminPassword": pwd,
            "customData": base64.b64encode(open(ci_file, "rb").read()).decode(),
            "linuxConfiguration": {"disablePasswordAuthentication": False},
        },
        # deleteOption=Delete makes ARM cascade the nic AND the os disk (below) with the VM, in one
        # operation. Strictly better than sweeping after: a sweep has an orphan window and both
        # had been leaking through it. Measured 2026-08-28: 1411 unattached disks / 41.6 TiB, and
        # Storage was $378.65 of a $582.64 month-to-date bill -- the largest line, ahead of VMs
        # at $189.38, for a CI plane whose entire job is running VMs.
        "networkProfile": {"networkInterfaces": [{"id": nic, "properties": {"deleteOption": "Delete"}}]},
    }
    if SPOT:
        props["priority"] = "Spot"
        props["evictionPolicy"] = "Deallocate"
        props["billingProfile"] = {"maxPrice": -1}
    def put_vm():
        arm("PUT", vm_path(name), {"location": region, "properties": props})

    try:
        props["storageProfile"]["osDisk"] = dict(
            _MANAGED_OS_DISK, diffDiskSettings={"option": "Local"}  # ephemeral: no disk resource at all
        )
        put_vm()
    except urllib.error.HTTPError as e:
        if e.code == 409:  # stale VM from an earlier attempt: delete VM only (nic/pip stay), wait, retry
            try:
                arm("DELETE", vm_path(name))
            except Exception:
                pass
            _wait_gone(vm_path(name), "2023-07-01")
            props["storageProfile"]["osDisk"] = dict(_MANAGED_OS_DISK)
            put_vm()
        else:
            props["storageProfile"]["osDisk"] = dict(_MANAGED_OS_DISK)  # sizes without local disk fall back
            put_vm()
    except Exception:
        props["storageProfile"]["osDisk"] = dict(_MANAGED_OS_DISK)  # sizes without local disk fall back
        put_vm()


def vm_path(name):
    return f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Compute/virtualMachines/{name}"


def delete_vm(name, location, reason="unspecified", was_busy=False):
    """Delete a worker VM, recording it so a later job failure on this runner self-attributes.

    Autopsy of the 2026-08-26 execution-sweep kill (Azure activity log + orchestrator log):
      13:23:18.166  virtualMachines/delete Started    caller=<orchestrator SP>
      13:23:18.509  networkInterfaces/delete FAILED   BadRequest (NicInUse -- VM still attached)
      13:23:39.853  virtualMachines/delete Succeeded
      13:32:42      GitHub reports the job FAILED     <- 9 MINUTES after the VM died
    The job log contained no error of its own, so the red check pointed at the build. Attribution
    has to be automatic; hand-correlating three logs is not a diagnosis path."""
    with _deleted_lock:
        now = time.time()
        for k in [k for k, v in _deleted.items() if now - v["at"] > _DELETED_TTL_S]:
            del _deleted[k]
        _deleted[name] = {"at": now, "reason": reason, "was_busy": bool(was_busy)}
    if was_busy:
        # Unreachable now that both reaper paths skip busy runners -- but if a third path ever
        # appears, this must be loud at the moment of the kill, not inferred 9 minutes later.
        log(f"INFRA-KILL: deleting {name} while BUSY (reason={reason}) -- a job is running on "
            f"it and will fail with an unrelated-looking error in ~9min")
    # SEQUENTIAL, not a loop over both: the NIC delete must not be issued until the compute
    # resource is actually gone. ARM deletes are ASYNC, so firing them back to back fails the
    # NIC with NicInUse/BadRequest and LEAKS IT -- nothing retries the call, and a leaked NIC
    # occupies per-region quota indefinitely. That is the 13:23:18.509 line in the autopsy
    # above, and it is what left seven orphaned NICs behind during the 2026-09-16 churn: every
    # self-powered-off worker was deleted VM-and-NIC in the same breath, so every one leaked.
    vm = vm_path(name)
    try:
        arm("DELETE", vm, api="2023-07-01")
    except Exception as e:
        log(f"delete vm {name} (reason={reason}): {e}")
    # Bounded, because cleanup() runs on the reconcile thread and a wait per VM would stall the
    # backstop (webhook dispatch is unaffected -- it runs on its own thread). 60s is generous
    # against the 21s the 2026-08-26 delete actually took. On timeout the NIC delete is SKIPPED
    # rather than attempted-and-doomed: the leaked-nic sweep at the end of cleanup() is the
    # backstop for exactly this, complete with the two-poll _absent_once guard, so skipping
    # loses nothing but one cycle of latency and avoids an error that reads like a new failure.
    if not _wait_gone(vm, "2023-07-01", timeout=VM_DELETE_WAIT_S):
        log(f"delete vm {name} (reason={reason}): still Deleting after {VM_DELETE_WAIT_S}s, "
            f"leaving the nic to the leaked-nic sweep")
        return
    # deleteOption=Delete on the networkProfile means ARM usually cascaded the NIC away with the
    # VM, so this is normally a no-op that logs nothing rather than a 404 on every teardown.
    nic = nic_path_for(name, location)
    if not _exists(nic, "2022-07-01"):
        return
    try:
        arm("DELETE", nic, api="2022-07-01")
    except Exception as e:
        log(f"delete nic {name} (reason={reason}): {e}")


def nic_path_for(name, region):
    return f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Network/networkInterfaces/{name}-{region}-nic"


def _nic_base(nic_name):
    """The worker VM name a NIC belongs to, or None if the name is in no known form.

    Three forms exist in this resource group, and only the first two were ever handled:
      1. `<vm>-<region>-nic`  -- what nic_path_for() creates today.
      2. `<vm>-nic`           -- legacy, pre-region-scoped.
      3. `<vm>VMNic`          -- AZURE'S OWN default name, used when a VM is created without an
                                 explicit NIC (the `az vm create` path this orchestrator used
                                 before the ARM REST rewrite). No hyphen before "nic", so it
                                 matched neither form above and leaked forever.
    Measured 2026-08-26 in thyn-ci: 53 NICs for 14 VMs, 34 orphaned (virtualMachine == null), of
    which 31 were form 3 -- e.g. ci-az-32854312574-97822446727VMNic, from runs long since gone.

    Longest-suffix-first, so a hypothetical `<vm>-eastus2-nic` can never be mis-parsed as the
    legacy form with `-eastus2` swallowed into the VM name."""
    for r, _, _ in REGIONS:
        suffix = f"-{r}-nic"
        if nic_name.endswith(suffix):
            return nic_name[: -len(suffix)]
    for suffix in ("VMNic", "-nic"):
        if nic_name.endswith(suffix):
            return nic_name[: -len(suffix)]
    return None


def clear_net(name, region):
    p = nic_path_for(name, region)
    if _exists(p, "2022-07-01"):
        try:
            arm("DELETE", p, api="2022-07-01")
        except Exception as e:
            log(f"clear_net {name}: {e}")


def provision_worker(name):
    with _lock:
        _inflight_names.add(name)
    write_ci_file(name)
    for region, vnet, subnet in REGIONS:
        free = free_vcpus_cached(region)
        if not free:
            continue
        for size in SIZE_CHAIN:
            if free.get(family(size), 0) < VM_VCPU[size] or free.get("cores", 10**9) < VM_VCPU[size]:
                continue
            try:
                create_vm(name, size, region, vnet, subnet)
                log(f"provisioned {name} ({size} in {region})")
                return True  # name stays protected until cleanup() sees the VM in live_vms()
            except Exception as e:
                log(f"{size}@{region} failed for {name}: {str(e)[-200:]}")
    log(f"all regions/sizes failed for {name}")
    with _lock:
        _inflight_names.discard(name)
    return False


def provision_job(job):
    if not provision_worker(f"ci-az-{job['run_id']}-{job['id']}"):
        log(f"leaving job {job['id']} queued for next poll")
        with _lock:
            _inflight.discard(job["id"])


def cleanup():
    runners = runner_names()
    # BUSY runners are never reaped by age. The age cap exists to stop leaked/hung VMs
    # accumulating, but it used to fire unconditionally -- `or age > MAX_AGE_S` deleted a VM
    # even while it was actively executing a job. That specifically punished LONG jobs on
    # WARM VMs: a warm worker's age clock starts when it is pre-booted, not when it picks up
    # work, so the longer it waited in the pool the less budget remained for whatever job it
    # accepted. Killed live 2026-08-26: ci-warm-1787745129 was pre-booted 11:52:13, took
    # sdk-audit's `execution-sweep` at 13:03:41, and was deleted at 13:23:18 with
    # "age=5465s, runner=aged" -- 20 minutes into a real build, reported as a build failure.
    # The repo's longest job is also main-only, so it was the likeliest victim and the least
    # likely to be caught before merge.
    busy = busy_runner_names()
    now = time.time()
    vms = live_vms()
    for name, created, location in vms:
        try:
            age = now - time.mktime(time.strptime(created[:19], "%Y-%m-%dT%H:%M:%S"))
        except Exception:
            age = MAX_AGE_S
        if name in busy:
            continue  # mid-job: let it finish; MAX_AGE_S is a leak guard, not a job timeout
        unregistered = name not in runners
        # ONE boot window, BOOT_GRACE_S, for a worker in ANY power state. Read that constant's
        # comment for the 2026-09-16 churn that made a stopped-but-young VM protected rather
        # than an immediate kill; the short version is that "stopped means finished" is only
        # true when bootstraps succeed, and when they do not, reaping on sight turns a fleet
        # outage into a provision/delete storm that also leaks a NIC per cycle.
        #
        # The quota cost this accepts is real and bounded: a "stopped" (not deallocated) VM
        # still holds its full vCPU allocation, so a corpse now pins 8 cores for up to
        # BOOT_GRACE_S instead of being freed at once. Measured live 2026-08-26 -- 13 VMs, only
        # 3 registered, 10 stopped; centralus DSv5 at 96/140 cores with 80 of them held by
        # those 10 corpses, leaving room for 5 workers while 6 checks sat QUEUED. That is the
        # failure mode being traded against, and it is the cheaper of the two: centralus now
        # carries 190 total cores, so one generation of corpses inside a 720s window fits,
        # whereas a delete/create cycle every 90s does not leave the plane standing at all.
        condemned = (unregistered and age > BOOT_GRACE_S) or age > MAX_AGE_S
        power = None
        if not condemned and not unregistered and age > BOOT_GRACE_S:
            # ── THE STOPPED-BUT-REGISTERED GAP (2026-09-16, the second half of that day) ──
            # `unregistered` above is the ONLY thing that lets the BOOT_GRACE_S rule fire early,
            # so a worker that powered itself off AFTER registering was invisible to it: not
            # unregistered, not yet MAX_AGE_S, therefore `continue` -- and its 8 vCPU stayed
            # pinned for the full 90 minutes. That is not a corner case, it is the common case
            # whenever a job ends and the runner exits: the bootstrap's success path IS
            # `shutdown -h now` on a VM whose registration GitHub still lists. After the
            # restart burst on 2026-09-16, 15 of 19 VMs were in exactly this state, i.e. 120 of
            # the subscription's vCPU quota held by corpses with 90 minutes left on the clock
            # and checks queued behind them.
            #
            # The registration is therefore NOT evidence of life, only of a life that started.
            # Two consecutive stopped sightings past the boot grace are the evidence of death,
            # and they are what this asks for. Bounded the same way the unregistered rule is:
            # the grace still applies, so a worker self-powering-off 55s into a broken bootstrap
            # is held for the whole window and the 2026-09-16 churn storm cannot come back --
            # this reaps at BOOT_GRACE_S + one poll, not on sight.
            #
            # Cost, stated plainly: one instanceView call per REGISTERED worker older than the
            # boot grace per reconcile cycle, capped by MAX_CONCURRENCY (20). It is asked only
            # where the answer can change a verdict, which is the rule vm_power_state's own
            # docstring sets.
            power = _stopped_twice(name, now)
            condemned = power is not None
        if not condemned:
            continue
        if power is None:
            # Power state is asked ONLY for a VM already condemned, and only to LABEL the reason.
            # It used to be asked for every young unregistered VM each cycle so a stopped one could
            # be reaped early, which made it one ARM round-trip per young worker per 90s poll for a
            # verdict that no longer changes anything. Asking here costs one call per deletion.
            power = vm_power_state(name)
        stopped = power in ("stopped", "deallocated")
        if stopped and not unregistered:
            why = "stopped-registered"
        elif stopped:
            why = "stopped-no-runner"
        elif unregistered:
            why = "orphan-no-runner"
        else:
            why = "max-age"
        if not unregistered:
            # REGISTRATION FIRST, VM SECOND, and both logged. A VM deleted under a live
            # registration leaves the org asserting a runner that no longer exists, which is the
            # exact stale fact this rule was blind to; deleting the registration first means the
            # two can never disagree, and GitHub cannot dispatch to it in the gap. Never reached
            # for a busy runner -- the busy check above is absolute and stays that way, because
            # GitHub cancels a job whose runner registration disappears.
            delete_runner_registration(name)
        # The boot-log pointer goes ON the reap line, not on a separate one: an operator reading
        # the journal needs the evidence link in the same breath as the verdict, and one line per
        # VM per cycle is the noise ceiling this sweep is held to. "none" is printed rather than
        # omitted, so "this worker has no boot log" is distinguishable from "the annotator broke".
        log(f"deleting {name} (age={int(age)}s, reason={why}, "
            f"boot-log={gist_url_for(name) or 'none'})")
        delete_vm(name, location, reason=f"{why} age={int(age)}s", was_busy=name in busy)
    # leaked nic/pip from failed provisions occupy the per-region PIP quota (limit 20)
    vm_names = {n for n, _, _ in vms}
    with _lock:
        protected = set(_inflight_names)
        for n in protected:
            if n in vm_names:  # VM visible: lag window over, release protection
                _inflight_names.discard(n)

    # ── Release finished job claims (fixes a permanent capacity wedge) ────────────────
    # _inflight holds claimed job IDs so two dispatch paths can't double-provision the same
    # job. It was only ever discarded from on provisioning FAILURE (provision_job), so every
    # SUCCESSFUL dispatch leaked its ID forever. Since _dispatch_job/_prewarm/manage_warm_pool
    # all gate on `len(vms) + len(_inflight) >= MAX_CONCURRENCY`, the set grew monotonically
    # until it alone hit the cap -- after which EVERY new job was refused with
    # `dispatched=False` and the fleet drained to zero while jobs queued. Observed live
    # 2026-08-26: 0 VMs, 0 runners, 5 jobs pending, every dispatch refused.
    #
    # A claim is dead once its worker no longer exists: the VM name encodes the job id
    # (ci-az-<run_id>-<job_id>), so a claim is kept only while its VM is live OR still inside
    # the provisioning window (_inflight_names) -- otherwise the job has been picked up,
    # finished, or failed, and holding the slot serves no purpose.
    live_job_ids = set()
    for n in vm_names | protected:
        if n.startswith("ci-az-"):
            tail = n.rsplit("-", 1)[-1]
            if tail.isdigit():
                live_job_ids.add(int(tail))
    with _lock:
        for jid in [j for j in _inflight if j not in live_job_ids]:
            _inflight.discard(jid)
            log(f"released stale job claim {jid} (no live worker)")
    for b in list(_absent_once):
        if b in vm_names or b in protected:
            _absent_once.discard(b)
    # Same hygiene for the stopped-worker streaks: a name whose VM is gone (reaped this cycle, or
    # deleted by something else) must not keep an entry, or the dict grows one key per worker
    # forever and a recycled name would inherit a dead worker's sighting 1/2.
    for n in list(_stopped_seen):
        if n not in vm_names and n not in protected:
            _stopped_seen.pop(n, None)
    d = arm(
        "GET",
        f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Network/networkInterfaces",
        api="2022-07-01",
    )
    for p in d.get("value", []):
        n = p["name"]
        if not n.startswith(("ci-az-", "ci-warm-")):
            continue
        base = _nic_base(n)
        if base is None:
            # An unrecognized ci-* NIC name must never fall through SILENTLY. It did, and it cost
            # 31 leaked NICs: Azure's own auto-generated name is `<vm>VMNic` (no hyphen before
            # "nic"), so it matched neither the `-{region}-nic` form this orchestrator creates nor
            # the legacy `-nic` fallback, and every one was skipped on every pass forever. Leaked
            # NICs occupy per-region quota, so this throttles provisioning -- the sweep reporting
            # nothing was the reason it went unnoticed for weeks.
            if n not in _unswept_nics:
                _unswept_nics.add(n)
                log(f"WARNING: leaked-nic sweep cannot parse NIC name {n!r} -- not swept. "
                    f"Add its suffix to _nic_base() or it will occupy quota indefinitely.")
            continue
        if base in vm_names or base in protected:
            continue
        if base not in _absent_once:
            # ARM read-after-write lag: a VM just PUT may not list for ~15-30s; sweeping
            # its nic in that window fails the VM with NotFound (killed wave-2 workers).
            _absent_once.add(base)
            continue
        _absent_once.discard(base)
        log(f"sweeping leaked nic for {base}")
        try:
            arm("DELETE", p["id"], api="2022-07-01")
        except Exception:
            pass
    sweep_leaked_disks(vm_names, protected)
    _sweep_stale_registrations(vm_names | protected)


_DISK_OWNER_RE = re.compile(r"^(?P<base>.+?)_(?:disk1|OsDisk_1)_[0-9a-f]{8,}$")


def sweep_leaked_disks(vm_names, protected):
    """Delete Unattached disks whose owning VM is gone.

    Belt-and-braces behind deleteOption=Delete: that covers every VM created from now on, but
    cannot adopt disks left by VMs deleted earlier, and an operator deletion can still strand one.
    Uses the SAME two-pass _absent_once guard as the nic sweep, for the same reason -- a VM just PUT
    may not list for 15-30s, and deleting its disk in that window kills the VM.
    """
    try:
        d = arm("GET", f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Compute/disks",
                api="2023-04-02")
    except Exception as e:
        log(f"disk sweep list failed: {e}")
        return
    for disk in d.get("value", []):
        name = disk.get("name", "")
        m = _DISK_OWNER_RE.match(name)
        if not m:
            continue  # not a VM-derived name; never touch it
        base = m.group("base")
        if not base.startswith(("ci-az-", "ci-warm-")):
            continue  # ci-golden-build / probe / cidebug disks are not ours to delete
        if disk.get("properties", {}).get("diskState") != "Unattached":
            continue
        if base in vm_names or base in protected:
            continue
        key = f"disk:{base}"
        if key not in _absent_once:
            _absent_once.add(key)
            continue
        _absent_once.discard(key)
        log(f"sweeping leaked disk {name} (owner {base} gone)")
        try:
            arm("DELETE", disk["id"], api="2023-04-02")
        except Exception as e:
            log(f"delete disk {name}: {e}")


def _sweep_stale_registrations(live_names):
    """Delete runner registrations whose VM is gone.

    An ephemeral worker's registration outlives its VM, so the org list drifts far above the real
    fleet: measured 2026-08-26, 32 registrations for 6 online runners (21 stale ci-az-/ci-warm-
    plus 5 retired blacksmith entries). Nothing removed them, so the count only grew.

    That matters because the runner listing is paginated at 100 per page. all_runners() now
    follows pages so a large list is no longer *unsafe*, but letting it grow unbounded still means
    every reaper pass pays extra API round-trips forever, and it was one truncation bug away from
    reaping busy runners mid-job. Prune instead of merely tolerating.

    THREE conditions, all required, because deleting the wrong registration is worse than keeping
    a stale one -- GitHub cancels a job whose runner registration disappears:
      * offline   -- an online runner may be about to accept work.
      * not busy  -- a busy runner is mid-job by definition.
      * no live VM -- the decisive one. A VM mid-bootstrap has no registration yet (nothing to
        delete), so "no VM" genuinely means the worker is gone, not merely not-yet-arrived.
    Plus a name-prefix guard: only this fleet's own workers. ci-orch itself is a runner (a
    repo-level one, which is why an org-only listing does not even show it) and must never be
    touched; neither must any runner some other system registered."""
    try:
        runners = all_runners()
    except Exception as e:  # noqa: BLE001 -- reconciliation is best-effort, never fatal
        log(f"registration sweep: listing failed, skipping this pass: {e}")
        return
    for r in runners:
        name = r.get("name") or ""
        if not name.startswith(("ci-az-", "ci-warm-")):
            continue
        if r.get("status") != "offline" or r.get("busy") or name in live_names:
            continue
        rid = r.get("id")
        if rid is None:
            continue
        try:
            gh(f"orgs/{ORG}/actions/runners/{rid}", method="DELETE")
            log(f"pruned stale runner registration {name} (id={rid}, offline, no live VM)")
        except Exception as e:  # noqa: BLE001 -- a failed prune is harmless; retry next pass
            log(f"registration sweep: could not delete {name} (id={rid}): {e}")


def _read_last_activity():
    try:
        with open(f"{STATE}/last_activity") as f:
            return float(f.read().strip())
    except (OSError, ValueError):
        return 0.0


def _prewarm(reason):
    """Provision one extra warm worker ahead of an imminent CI run (a PR just opened/updated, or
    a push to a CI-triggering branch) instead of waiting for the reactive workflow_job-queued
    path. Bounded by MAX_CONCURRENCY like every other provisioning path; a no-op once at
    capacity, never queues or blocks."""
    vms = live_vms()
    with _lock:
        warm_inflight = sum(1 for n in _inflight_names if n.startswith(WARM_PREFIX))
        if len(vms) + len(_inflight) + warm_inflight >= MAX_CONCURRENCY:
            return False
    name = f"{WARM_PREFIX}{int(time.time())}"
    log(f"webhook: pre-warming {name} ({reason})")
    threading.Thread(target=provision_worker, args=(name,), daemon=True).start()
    return True


def manage_warm_pool(vms):
    now = time.time()
    queued = queued_jobs()
    busy_names = {
        n for n in busy_runner_names() if n.startswith(("ci-az-", WARM_PREFIX))
    }
    busy = bool(busy_names)
    if queued or busy:
        with open(f"{STATE}/last_activity", "w") as f:
            f.write(str(now))
    warm = [v for v in vms if v[0].startswith(WARM_PREFIX)]
    idle = now - _read_last_activity() > IDLE_DRAIN_S
    if idle and len(warm) > WARM_FLOOR:
        # Scale down to the permanent floor, never to 0: the floor absorbs the very next job
        # at warm-pool speed instead of every post-idle job paying a full cold boot.
        #
        # BUSY warm workers are excluded from the drain. This used to slice purely by position
        # (`warm[WARM_FLOOR:]`), so a warm VM actively running a job could be deleted just for
        # sorting past the floor -- the same class of bug as cleanup()'s unconditional age reap
        # (see there). `idle` can legitimately be true while one long job still runs: it is
        # derived from a last_activity timestamp that a single quiet poll can age out.
        drainable = [v for v in warm if v[0] not in busy_names]
        keep = len(warm) - len(drainable)  # busy workers already count toward the floor
        for name, _, loc in drainable[max(0, WARM_FLOOR - keep):]:
            log(f"idle drain: deleting {name} (keeping floor={WARM_FLOOR}, busy={len(busy_names)})")
            delete_vm(name, loc, reason="idle-drain", was_busy=name in busy_names)
        warm = [v for v in warm if v[0] in busy_names] + drainable[: max(0, WARM_FLOOR - keep)]
    target = WARM_FLOOR if idle else WARM_MIN
    with _lock:
        warm_inflight = sum(1 for n in _inflight_names if n.startswith(WARM_PREFIX))
    if (
        len(warm) + warm_inflight < target
        and len(vms) + len(_inflight) < MAX_CONCURRENCY
    ):
        name = f"{WARM_PREFIX}{int(now)}"
        log(f"warm pool: provisioning {name} (target={target}, idle={idle})")
        threading.Thread(target=provision_worker, args=(name,), daemon=True).start()
    return queued


def _dispatch_job(job, vms):
    """Claim + spawn a provisioning thread for one queued job, or no-op if already claimed /
    at capacity. Shared by the poll-loop backstop and the webhook handler so both paths use the
    exact same admission logic."""
    with _lock:
        if job["id"] in _inflight:
            return False
        if len(vms) + len(_inflight) >= MAX_CONCURRENCY:
            return False
        _inflight.add(job["id"])
    threading.Thread(target=provision_job, args=(job,), daemon=True).start()
    return True


def _verify_signature(secret, body, header_value):
    """Constant-time HMAC-SHA256 check of a GitHub webhook's X-Hub-Signature-256 header. An
    unset secret always fails closed (never accept unsigned/unverifiable webhooks)."""
    if not secret:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header_value or "", expected)


def _delivery_dedup(delivery_id):
    """True if this X-GitHub-Delivery was already handled. GitHub retries a delivery verbatim
    (same id) on a non-2xx response or timeout, so acting on a duplicate would double-provision."""
    now = time.time()
    with _delivery_lock:
        for k in [k for k, t in _delivery_seen.items() if now - t > _DELIVERY_TTL_S]:
            del _delivery_seen[k]
        if delivery_id in _delivery_seen:
            return True
        _delivery_seen[delivery_id] = now
        return False


def _note_completed_job(job, repo):
    """Attribute a non-success job to an infra kill, at the instant GitHub reports it.

    GitHub's workflow_job `completed` event already carries `runner_name` AND `conclusion`, and
    this receiver already gets it -- only `queued` was ever handled. One cross-reference against
    the deletion ledger converts the hardest-to-diagnose failure class here into a single
    self-explanatory line."""
    conclusion = job.get("conclusion")
    runner = job.get("runner_name") or ""
    jid = job.get("id")
    if conclusion == "success" or not runner:
        return
    with _deleted_lock:
        rec = _deleted.get(runner)
    if rec is None:
        return
    delta = int(time.time() - rec["at"])
    log(
        f"INFRA-KILL ATTRIBUTION: job {jid} ({repo}) reported '{conclusion}' on runner {runner}, "
        f"which THIS ORCHESTRATOR deleted {delta}s earlier (reason={rec['reason']}, "
        f"was_busy={rec['was_busy']}). The job did not fail on its own -- its runner was removed. "
        f"Re-run it; do not debug the build."
    )


class _WebhookHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # noqa: A003 -- stdlib hook name; route through log()
        pass  # BaseHTTPRequestHandler's default writes to stderr, bypassing orch.log entirely

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length else b""
            sig = self.headers.get("X-Hub-Signature-256", "")
            if not _verify_signature(WEBHOOK_SECRET, body, sig):
                log(f"webhook: bad signature from {self.client_address[0]}")
                self.send_response(401)
                self.end_headers()
                return
            delivery_id = self.headers.get("X-GitHub-Delivery", "")
            event = self.headers.get("X-GitHub-Event", "")
            # WHICH webhook sent this. Without these, the delivery source is unauditable, and that
            # is not theoretical: on 2026-08-26 an org owner holding admin:org_hook found
            # GET /orgs/thyn-ai/hooks -> 200 [] , zero hooks on all 25 repos, no enterprise hooks,
            # and no installed App subscribed to workflow_job -- while 1819 HMAC-VALID deliveries
            # per day were arriving here. A correctly-signed delivery whose registration cannot be
            # located through any GitHub API is a secret nobody can rotate or revoke.
            # GitHub stamps every delivery with the hook's identity; log it so the origin is
            # answerable from this log alone:
            #   target_type = organization | repository | integration (integration == GitHub App)
            #   target_id   = the org / repo / app id that owns the hook
            #   hook_id     = the specific hook, usable directly against the REST API
            hook_id = self.headers.get("X-GitHub-Hook-ID", "?")
            tgt_type = self.headers.get("X-GitHub-Hook-Installation-Target-Type", "?")
            tgt_id = self.headers.get("X-GitHub-Hook-Installation-Target-ID", "?")
            log(f"webhook: accepted {event} delivery={delivery_id} from {self.client_address[0]} "
                f"hook={hook_id} origin={tgt_type}:{tgt_id}")
            self.send_response(202)  # ack fast; GitHub's own delivery timeout is short
            self.end_headers()
            if event not in ("workflow_job", "pull_request", "push"):
                return  # subscribed-but-unhandled (e.g. the org default's "push"): ack, no-op
            if not delivery_id or _delivery_dedup(delivery_id):
                return
            payload = json.loads(body) if body else {}
            repo = (payload.get("repository") or {}).get("full_name", "")

            if event == "workflow_job":
                action = payload.get("action")
                if action == "completed":
                    _note_completed_job(payload.get("workflow_job") or {}, repo)
                    return
                if action != "queued":
                    return
                job = payload.get("workflow_job") or {}
                if not any(LABEL in (l or "") for l in job.get("labels", [])):
                    return
                if repo and repo not in served_repos():  # defense in depth; label match is primary
                    log(f"webhook: {repo} not in served_repos(), skipping job {job.get('id')}")
                    return
                dispatched = _dispatch_job(job, live_vms())
                log(f"webhook: queued job {job.get('id')} ({repo}) dispatched={dispatched}")
            elif event == "pull_request":
                # A PR just opened or got a new commit -- a workflow_job-queued event for it is
                # imminent. Pre-warm now instead of waiting for that reactive signal.
                if payload.get("action") not in ("opened", "synchronize", "reopened"):
                    return
                if not repo or repo not in served_repos():
                    return
                _prewarm(f"pull_request {payload.get('action')} on {repo}")
            elif event == "push":
                ref = payload.get("ref", "")
                branch = ref.removeprefix("refs/heads/")
                if branch not in PREWARM_PUSH_BRANCHES:
                    return  # push to a branch that doesn't trigger this repo's CI -- no-op
                if not repo or repo not in served_repos():
                    return
                _prewarm(f"push to {branch} on {repo}")
        except Exception as e:  # noqa: BLE001 -- a webhook handler must never crash the server thread
            log(f"webhook error: {e}")
            try:
                self.send_response(500)
                self.end_headers()
            except Exception:
                pass


def run_webhook_server():
    if not (WEBHOOK_SECRET and WEBHOOK_CERT and WEBHOOK_KEY):
        log("webhook server disabled: GITHUB_WEBHOOK_SECRET/_TLS_CERT/_TLS_KEY not fully set")
        return
    server = http.server.ThreadingHTTPServer(("0.0.0.0", WEBHOOK_PORT), _WebhookHandler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=WEBHOOK_CERT, keyfile=WEBHOOK_KEY)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    log(f"webhook server listening on :{WEBHOOK_PORT}")
    try:
        server.serve_forever()
    except Exception as e:
        log(f"webhook server crashed: {e}")


def main():
    log(f"orchestrator starting (webhook + {RECONCILE_S}s reconcile backstop, warm={WARM_MIN}, floor={WARM_FLOOR}, max={MAX_CONCURRENCY})")
    threading.Thread(target=run_webhook_server, daemon=True).start()
    while True:
        try:
            cleanup()
            vms = live_vms()
            queued = manage_warm_pool(vms)
            for job in queued:
                if len(vms) + len(_inflight) >= MAX_CONCURRENCY:
                    break
                _dispatch_job(job, vms)
        except Exception as e:
            log(f"poll error: {e}")
        time.sleep(RECONCILE_S)


if __name__ == "__main__":
    main()
