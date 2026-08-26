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

Env: GITHUB_CI_TOKEN (org-admin oauth/PAT: needs org self-hosted-runner registration +
org repo-list scope); GITHUB_REPOS (optional comma-separated override to pin/restrict
the served repo list; unset = every repo in the org, auto-refreshed); AZURE_SP_CLIENT_ID/
AZURE_SP_CLIENT_SECRET (fallback AZURE_CLIENT_ID/AZURE_CLIENT_SECRET), AZURE_TENANT_ID,
AZURE_SUBSCRIPTION_ID.
"""
import base64
import json
import os
import secrets
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
POLL_S = 15
MAX_AGE_S = 90 * 60
# stock-image boot runs apt-get (docker.io) + runner download: 3-6min is normal,
# so a 3min orphan sweep was killing VMs mid-bootstrap (runners never registered).
ORPHAN_AGE_S = 10 * 60
SIZE_CHAIN = [
    "Standard_F8s_v2", "Standard_D8s_v5", "Standard_D8s_v6", "Standard_D8s_v4", "Standard_D8s_v3",
    "Standard_F4s_v2", "Standard_D4s_v5", "Standard_D4s_v4", "Standard_D4s_v3",
]
VM_VCPU = {
    "Standard_F8s_v2": 8, "Standard_D8s_v5": 8, "Standard_D8s_v6": 8, "Standard_D8s_v4": 8, "Standard_D8s_v3": 8,
    "Standard_F4s_v2": 4, "Standard_D4s_v5": 4, "Standard_D4s_v4": 4, "Standard_D4s_v3": 4,
}
MAX_CONCURRENCY = int(os.environ.get("AZ_ORCH_MAX", "20"))
# Blacksmith-style warm capacity: pre-booted registered runners so jobs are picked up
# in seconds; drained to 0 after IDLE_DRAIN_S without queue/busy activity.
WARM_MIN = int(os.environ.get("AZ_ORCH_WARM", "2"))
IDLE_DRAIN_S = int(os.environ.get("AZ_ORCH_IDLE_DRAIN_S", "600"))
WARM_PREFIX = "ci-warm-"
GOLDEN_IMAGE = f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Compute/images/ci-worker-v1"
GOLDEN_REGION = "eastus2"  # managed images are regional; other regions use stock + full cloud-init
SPOT = os.environ.get("AZ_ORCH_SPOT", "0") == "1"
STATE = "/var/lib/az-orch"
os.makedirs(STATE, exist_ok=True)

REGIONS = [
    ("eastus2", "thyn-ci-eastus2", "default"),  # golden image region: fastest boot
    ("eastus", "thyn-gh-runners", "builders"),
    ("centralus", "thyn-ci-centralus", "default"),
    ("westus2", "thyn-ci-westus2", "default"),
    ("westus", "thyn-ci-westus", "default"),
    ("westus3", "thyn-ci-westus3", "default"),
    ("southcentralus", "thyn-ci-southcentralus", "default"),
    ("northcentralus", "thyn-ci-northcentralus", "default"),
]

_lock = threading.Lock()
_inflight = set()
_inflight_names = set()  # VM names currently being provisioned; cleanup must not reap their nic/pip
_absent_once = set()  # net-sweep two-poll guard: base seen without a VM once, swept on second sight
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


def runner_names():
    # Org-level: one shared pool, via RUNNER_GROUP, serves every repo served_repos() finds.
    return {r["name"] for r in gh(f"orgs/{ORG}/actions/runners?per_page=100")["runners"]}


def live_vms():
    d = arm("GET", f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Compute/virtualMachines")
    out = []
    for v in d.get("value", []):
        if v["name"].startswith(("ci-az-", "ci-warm-")):
            out.append((v["name"], v.get("properties", {}).get("timeCreated", "2000-01-01T00:00:00"), v["location"]))
    return out


def free_vcpus(region):
    try:
        d = arm("GET", f"/subscriptions/{SUB}/providers/Microsoft.Compute/locations/{region}/usages")
        free = {}
        for u in d.get("value", []):
            n = u["name"]["value"]
            if n.startswith(("standardDSv3", "standardDSv4", "standardDSv5", "standardDSv6", "standardFSv2")):
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
    if size.startswith("Standard_F"):
        return "standardFSv2Family"
    for f in ("v6", "v5", "v4", "v3"):
        if f in size:
            return f"standardDS{f}Family"
    return "standardDSv4Family"


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
      timeout 420 sh -c 'apt-get update -qq && apt-get install -y -qq docker.io ca-certificates curl git jq libicu70 libssl3 software-properties-common build-essential clang lld' >/dev/null 2>&1
      log "apt rc=$?"
      up
      add-apt-repository -y ppa:deadsnakes/ppa >/dev/null 2>&1
      timeout 240 sh -c 'apt-get update -qq && apt-get install -y -qq python3.14 python3.14-venv libpython3.14' >/dev/null 2>&1
      # deadsnakes ships no pip module; jobs call `python3.14 -m pip` directly.
      python3.14 -m ensurepip --upgrade >/dev/null 2>&1 || true
      log "py314 rc=$?"
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
    # ci-worker-v1 was never captured; probing once avoids a guaranteed 404 per eastus2 attempt.
    global _golden_ok
    if _golden_ok is None:
        try:
            arm("GET", f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Compute/images/ci-worker-v1")
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
    golden = region == GOLDEN_REGION and golden_available()
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


def delete_vm(name, location):
    for kind, path in (
        ("vm", vm_path(name)),
        ("nic", nic_path_for(name, location)),
    ):
        try:
            arm("DELETE", path, api="2022-07-01" if kind != "vm" else "2023-07-01")
        except Exception as e:
            log(f"delete {kind} {name}: {e}")


def nic_path_for(name, region):
    return f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Network/networkInterfaces/{name}-{region}-nic"


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
    now = time.time()
    vms = live_vms()
    for name, created, location in vms:
        try:
            age = now - time.mktime(time.strptime(created[:19], "%Y-%m-%dT%H:%M:%S"))
        except Exception:
            age = MAX_AGE_S
        if (name not in runners and age > ORPHAN_AGE_S) or age > MAX_AGE_S:
            log(f"deleting {name} (age={int(age)}s, runner={'gone' if name not in runners else 'aged'})")
            delete_vm(name, location)
    # leaked nic/pip from failed provisions occupy the per-region PIP quota (limit 20)
    vm_names = {n for n, _, _ in vms}
    with _lock:
        protected = set(_inflight_names)
        for n in protected:
            if n in vm_names:  # VM visible: lag window over, release protection
                _inflight_names.discard(n)
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
        base = None
        for r, _, _ in REGIONS:
            if n.endswith(f"-{r}-nic"):
                base = n[: -len(f"-{r}-nic")]
                break
        if base is None and n.endswith("-nic"):  # legacy pre-region-scoped names
            base = n[: -len("-nic")]
        if base is None or base in vm_names or base in protected:
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


def _read_last_activity():
    try:
        with open(f"{STATE}/last_activity") as f:
            return float(f.read().strip())
    except (OSError, ValueError):
        return 0.0


def manage_warm_pool(vms):
    now = time.time()
    queued = queued_jobs()
    busy = any(
        r["busy"]
        for r in gh(f"orgs/{ORG}/actions/runners?per_page=100")["runners"]
        if r["name"].startswith(("ci-az-", WARM_PREFIX))
    )
    if queued or busy:
        with open(f"{STATE}/last_activity", "w") as f:
            f.write(str(now))
    warm = [v for v in vms if v[0].startswith(WARM_PREFIX)]
    if now - _read_last_activity() > IDLE_DRAIN_S:
        for name, _, loc in warm:  # scale to 0 when idle
            log(f"idle drain: deleting {name}")
            delete_vm(name, loc)
        return queued
    with _lock:
        warm_inflight = sum(1 for n in _inflight_names if n.startswith(WARM_PREFIX))
    if (
        len(warm) + warm_inflight < WARM_MIN
        and len(vms) + len(_inflight) < MAX_CONCURRENCY
    ):
        name = f"{WARM_PREFIX}{int(now)}"
        log(f"warm pool: provisioning {name}")
        threading.Thread(target=provision_worker, args=(name,), daemon=True).start()
    return queued


def main():
    log(f"orchestrator starting (REST mode, warm={WARM_MIN}, max={MAX_CONCURRENCY})")
    while True:
        try:
            cleanup()
            vms = live_vms()
            queued = manage_warm_pool(vms)
            for job in queued:
                with _lock:
                    if job["id"] in _inflight:
                        continue
                    if len(vms) + len(_inflight) >= MAX_CONCURRENCY:
                        break
                    _inflight.add(job["id"])
                threading.Thread(target=provision_job, args=(job,), daemon=True).start()
        except Exception as e:
            log(f"poll error: {e}")
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
