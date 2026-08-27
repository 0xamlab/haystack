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
import secrets
import ssl
import threading
import time
import urllib.request

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
# stock-image boot runs apt-get (docker.io) + runner download: 3-6min is normal,
# so a 3min orphan sweep was killing VMs mid-bootstrap (runners never registered).
ORPHAN_AGE_S = 10 * 60
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
# in seconds; drained to WARM_FLOOR (never 0) after IDLE_DRAIN_S without queue/busy activity.
# The floor exists so the FIRST job after any quiet period still gets warm-pool pickup speed
# instead of paying a full cold boot -- a burst-only pool (drain to 0) makes every post-idle
# job slow, not just excess capacity beyond real demand.
# Sized against real demand, not a round number. ONE pull request fires 3-4 jobs here
# (CI/CD + sdk-audit + codeql), so a pool of 2 guaranteed that most of every PR paid a full
# cold boot -- measured 2026-08-27T01:33Z: 7 jobs queued, 3 runners online, 5 VMs created in
# the same minute and none registered for ~3 minutes. That IS the flakiness; nothing was
# stuck, everything was waiting for Ubuntu to boot.
#
# 6 warm x 8 vCPU (Standard_D8s_v5) = 48 vCPU held steady. Live quota at the time of this
# change: 108 of 350 regional vCPUs used, so this fits with room for MAX_CONCURRENCY bursts
# on top. The floor rises with it: after a quiet period the first PR should still find a
# warm runner, which is the whole point of a floor.
WARM_MIN = int(os.environ.get("AZ_ORCH_WARM", "6"))
WARM_FLOOR = min(WARM_MIN, int(os.environ.get("AZ_ORCH_WARM_FLOOR", "3")))
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
# NIC names the sweep could not parse. Log-once set, so an unhandled naming form is reported the
# first time rather than every 90s poll -- but IS reported, which is what 31 leaked NICs cost.
_unswept_nics = set()
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
      import json,urllib.request
      try:
          gid=open("/root/gist.id").read().strip()
          content=open("/root/boot.log").read()[-3000:]
          req=urllib.request.Request("https://api.github.com/gists/"+gid,method="PATCH",
           data=json.dumps({"files":{"boot.log":{"content":content}}}).encode(),
           headers={"Authorization":"Bearer $TOK","Accept":"application/vnd.github+json"})
          urllib.request.urlopen(req,timeout=30)
      except Exception:
          pass
      PY
      }
      log start
      GIST=$(python3 - <<PY
      import json,urllib.request
      try:
          req=urllib.request.Request("https://api.github.com/gists",method="POST",
           data=json.dumps({"public":False,"files":{"boot.log":{"content":"init"}}}).encode(),
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
      curl -m 120 -o /tmp/runner.tar.gz -LsS https://github.com/actions/runner/releases/download/v2.327.1/actions-runner-linux-x64-2.327.1.tar.gz
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
      su - runner -c "/opt/runner/config.sh --url https://github.com/__ORG__ --token '$TOKEN' --name __VMNAME__ --runnergroup '__RUNNERGROUP__' --labels az-ephemeral,self-hosted --ephemeral --unattended" >> /root/boot.log 2>&1
      log "config rc=$?"
      up
      su - runner -c "/opt/runner/run.sh" || true
      log "run-exited"
      up
      shutdown -h now || true
runcmd:
  - bash /root/bootstrap.sh
"""


def write_ci_file(name):
    with open(f"{STATE}/{name}.yml", "w") as f:
        f.write(
            CLOUD_INIT.replace("__SSH_PUB__", SSH_PUB)
            .replace("__GH_TOKEN__", os.environ["GITHUB_CI_TOKEN"])
            .replace("__ORG__", ORG)
            .replace("__RUNNERGROUP__", RUNNER_GROUP)
            .replace("__VMNAME__", name)
        )


def subnet_id(region, vnet, subnet):
    return (
        f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Network/"
        f"virtualNetworks/{vnet}/subnets/{subnet}"
    )


CLOUD_INIT_FAST = """#cloud-config
ssh_authorized_keys:
  - __SSH_PUB__
write_files:
  - path: /root/bootstrap.sh
    permissions: "0755"
    content: |
      #!/bin/bash
      TOK="__GH_TOKEN__"
      RT=$(curl -s -m 30 -X POST -H "Authorization: Bearer $TOK" -H "Accept: application/vnd.github+json" https://api.github.com/orgs/__ORG__/actions/runners/registration-token)
      TOKEN=$(echo "$RT" | python3 -c "import json,sys;print(json.load(sys.stdin)['token'])" 2>/dev/null)
      # The GOLDEN IMAGE predates two things the retired Mac fleet provided and that repos moved
      # here by the org-wide RUNNER_LABELS still expect. Reasserted per boot because patching
      # CLOUD_INIT alone would never reach a golden-image VM -- and that IS the normal path now.
      # Both are guarded, so each becomes a no-op the moment the image is recaptured:
      #   python : codna runs `python -m pip` / `python -m pytest` -> exit 127 without it
      #   unzip  : actions/setup-bun shells out to it -> "Unable to locate executable file: unzip"
      command -v python >/dev/null 2>&1 || ln -sf "$(command -v python3.14 || command -v python3)" /usr/local/bin/python 2>/dev/null || true
      # BACKGROUNDED on purpose. Blocking here put up to 120s of apt in front of runner
      # registration on EVERY boot, which is the opposite of what this pool needs -- and boot
      # latency is exactly what makes the fleet feel flaky. Registration starts immediately;
      # unzip lands seconds later, long before any job reaches a step that shells out to it.
      # Delete this line entirely once the golden image is recaptured with unzip baked in.
      ( command -v unzip >/dev/null 2>&1 || timeout 120 sh -c 'apt-get update -qq && apt-get install -y -qq unzip' >/dev/null 2>&1 ) &
      useradd -m -s /bin/bash runner 2>/dev/null || true
      usermod -aG docker runner 2>/dev/null || true
      chown -R runner:runner /opt/runner
      su - runner -c "/opt/runner/config.sh --url https://github.com/__ORG__ --token '$TOKEN' --name __VMNAME__ --runnergroup '__RUNNERGROUP__' --labels az-ephemeral,self-hosted --ephemeral --unattended"
      su - runner -c "/opt/runner/run.sh" || true
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
        with open(f"{STATE}/{name}.fast.yml", "w") as f:
            f.write(
                CLOUD_INIT_FAST.replace("__SSH_PUB__", SSH_PUB)
                .replace("__GH_TOKEN__", os.environ["GITHUB_CI_TOKEN"])
                .replace("__ORG__", ORG)
                .replace("__RUNNERGROUP__", RUNNER_GROUP)
                .replace("__VMNAME__", name)
            )
        ci_file = f"{STATE}/{name}.fast.yml"
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
        "networkProfile": {"networkInterfaces": [{"id": nic}]},
    }
    if SPOT:
        props["priority"] = "Spot"
        props["evictionPolicy"] = "Deallocate"
        props["billingProfile"] = {"maxPrice": -1}
    def put_vm():
        arm("PUT", vm_path(name), {"location": region, "properties": props})

    try:
        props["storageProfile"]["osDisk"] = {
            "createOption": "FromImage",
            "diffDiskSettings": {"option": "Local"},  # ephemeral OS disk: zero storage cost, fast
        }
        put_vm()
    except urllib.error.HTTPError as e:
        if e.code == 409:  # stale VM from an earlier attempt: delete VM only (nic/pip stay), wait, retry
            try:
                arm("DELETE", vm_path(name))
            except Exception:
                pass
            _wait_gone(vm_path(name), "2023-07-01")
            props["storageProfile"].pop("osDisk", None)
            put_vm()
        else:
            props["storageProfile"].pop("osDisk", None)  # sizes without local disk fall back
            put_vm()
    except Exception:
        props["storageProfile"].pop("osDisk", None)  # sizes without local disk fall back
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
    for kind, path in (
        ("vm", vm_path(name)),
        ("nic", nic_path_for(name, location)),
    ):
        try:
            arm("DELETE", path, api="2022-07-01" if kind != "vm" else "2023-07-01")
        except Exception as e:
            # NicInUse/BadRequest is EXPECTED (the NIC delete races the still-attached VM) and
            # is itself diagnostic, so the reason travels with it instead of reading as noise.
            log(f"delete {kind} {name} (reason={reason}): {e}")


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
        # A worker that has ALREADY POWERED OFF is finished or dead -- it can never register, so
        # ORPHAN_AGE_S buys nothing and costs a lot. That grace window exists purely for a VM
        # still BOOTING (see ORPHAN_AGE_S's own comment: stock-image boot runs apt-get + the
        # runner download, 3-6min, and a 3min sweep was killing workers mid-bootstrap). A booting
        # VM is powerState=running-but-unregistered; a STOPPED one is neither.
        #
        # Why it matters: a "stopped" (not deallocated) Azure VM still holds its full vCPU quota.
        # Measured live 2026-08-26 -- 13 VMs, only 3 registered, 10 stopped; centralus DSv5 at
        # 96/140 cores with 80 of them held by those 10 corpses, leaving room for 5 workers while
        # 6 checks sat QUEUED. Deleting them by hand took quota to 8/140 and the orchestrator
        # provisioned 8 workers within 3 seconds. This is the mechanism behind the recurring
        # "only 1-3 runners are working" reports, and the earlier warm-pool failures logging
        # "exceeding approved standardDSv5Family Cores quota".
        stopped = False
        if unregistered and age <= ORPHAN_AGE_S:
            # Ask ONLY inside the window where the answer changes the verdict: past ORPHAN_AGE_S
            # the rule below already deletes, and a registered VM is by definition alive. Power
            # state costs one call per VM (see vm_power_state), so it must stay this narrow.
            stopped = vm_power_state(name) in ("stopped", "deallocated")
        if stopped or (unregistered and age > ORPHAN_AGE_S) or age > MAX_AGE_S:
            if stopped:
                why = "stopped-no-runner"
            elif unregistered:
                why = "orphan-no-runner"
            else:
                why = "max-age"
            log(f"deleting {name} (age={int(age)}s, reason={why})")
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
    _sweep_stale_registrations(vm_names | protected)


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
