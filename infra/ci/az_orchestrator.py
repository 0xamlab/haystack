#!/usr/bin/env python3
"""Azure ephemeral-compute orchestrator for thyn-ai/algenta CI.

Runs on the ci-orch VM (resource group thyn-ci, eastus) as the
az-orchestrator.service systemd unit. Every POLL_SECONDS it polls GitHub
Actions for queued workflow jobs that request the `az-ephemeral` runner label
and, for each one, provisions a dedicated Ubuntu 22.04 worker VM in subnet
`builders`. The worker's cloud-init registers a JIT ephemeral actions runner,
executes exactly one job, and deletes the VM itself (az vm delete via the
RG-scoped thyn-ci-builder service principal). As a safety net this daemon also
reaps any ci-az-* VM older than MAX_VM_AGE_MINUTES.

State (handled job ids, for dedupe) lives in sqlite at STATE_DB.

Configuration is environment-only (see /etc/az-orchestrator.env on ci-orch):

  GITHUB_CI_TOKEN           GitHub oauth token: repo scope (job polling + JIT
                            runner registration tokens). Rotate per docs.
  GITHUB_REPO               default thyn-ai/algenta
  AZURE_SUBSCRIPTION_ID / AZURE_TENANT_ID / AZURE_SP_CLIENT_ID /
  AZURE_SP_CLIENT_SECRET    thyn-ci-builder SP (Contributor on RG thyn-ci ONLY)
  AZURE_RESOURCE_GROUP      default thyn-ci
  AZURE_LOCATION            default eastus
  AZURE_SUBNET_ID           builders subnet resource id (NO delegation; the
                            GitHub-delegated `runners` subnet must never host VMs)
  AZURE_VM_SIZES            space-separated worker sizes tried in order
                            (default "Standard_D8s_v4 Standard_D8s_v3" --
                            one size per family so up to two workers run
                            concurrently under the subscription's per-family
                            caps; D8s_v6 is capacity-restricted in eastus;
                            switch to "Standard_D16s_v5 Standard_D8s_v5" once
                            the subscription's DSv5 quota is granted via a
                            support request)
  POLL_SECONDS              default 15
  MAX_VM_AGE_MINUTES        default 90
  PROVISION_CONCURRENCY     default 4
"""

import json
import logging
import os
import sqlite3
import subprocess
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("az-orchestrator")

# -- environment --------------------------------------------------------------
GITHUB_TOKEN = os.environ["GITHUB_CI_TOKEN"]
GITHUB_REPO = os.environ.get("GITHUB_REPO", "thyn-ai/algenta")
AZ_SUBSCRIPTION = os.environ["AZURE_SUBSCRIPTION_ID"]
AZ_TENANT = os.environ["AZURE_TENANT_ID"]
AZ_CLIENT_ID = os.environ["AZURE_SP_CLIENT_ID"]
AZ_CLIENT_SECRET = os.environ["AZURE_SP_CLIENT_SECRET"]
AZ_RESOURCE_GROUP = os.environ.get("AZURE_RESOURCE_GROUP", "thyn-ci")
AZ_LOCATION = os.environ.get("AZURE_LOCATION", "eastus")
AZ_SUBNET_ID = os.environ["AZURE_SUBNET_ID"]
AZ_VM_SIZES = os.environ.get(
    "AZURE_VM_SIZES", "Standard_D8s_v4 Standard_D8s_v3"
).split()
WORKER_OS_DISK_GB = os.environ.get("WORKER_OS_DISK_GB", "128")
WORKER_IMAGE = os.environ.get(
    "WORKER_IMAGE", "Canonical:0001-com-ubuntu-server-jammy:22_04-lts-gen2:latest"
)
WORKER_SSH_PUBKEY = os.environ.get(
    "WORKER_SSH_PUBKEY", "/root/.ssh/ci_plane_key.pub"
)
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "15"))
MAX_VM_AGE_MINUTES = int(os.environ.get("MAX_VM_AGE_MINUTES", "90"))
PROVISION_CONCURRENCY = int(os.environ.get("PROVISION_CONCURRENCY", "4"))
REAP_EVERY_LOOPS = int(os.environ.get("REAP_EVERY_LOOPS", "4"))
RESOURCE_GC_EVERY_LOOPS = int(os.environ.get("RESOURCE_GC_EVERY_LOOPS", "40"))
MAX_PROVISION_ATTEMPTS = int(os.environ.get("MAX_PROVISION_ATTEMPTS", "3"))
COOLDOWN_SECONDS = int(os.environ.get("COOLDOWN_SECONDS", "90"))
STATE_DB = os.environ.get("STATE_DB", "/var/lib/az-orchestrator/state.db")

# Errors that mean "no capacity RIGHT NOW" (quota/capacity exhaustion) or that
# hide the ARM error entirely (az CLI crashes while formatting some ARM error
# responses: "content for this response was already consumed"). Both are
# transient: free capacity returns when a worker self-deletes, so the job is
# retried after a cooldown instead of being failed permanently.
TRANSIENT_MARKERS = (
    "quotaexceeded",
    "exceeding approved",
    "allocationfailed",
    "skunotavailable",
    "capacity restrictions",
    "operationnotallowed",
    "no available capacity",
    # az CLI crash signatures that swallow the underlying ARM error:
    "the command failed with an unexpected error",
    "the content for this response was already consumed",
)

_cooldown_lock = threading.Lock()
_cooldown_until = 0.0


def is_transient_error(err: str) -> bool:
    e = err.lower()
    return any(marker in e for marker in TRANSIENT_MARKERS)


def enter_cooldown():
    global _cooldown_until
    with _cooldown_lock:
        _cooldown_until = time.time() + COOLDOWN_SECONDS


def cooling_down() -> bool:
    with _cooldown_lock:
        return time.time() < _cooldown_until

GH_API = "https://api.github.com"
VM_PREFIX = "ci-az-"

WORKER_CLOUD_INIT = """#cloud-config
# Ephemeral GitHub Actions worker for thyn-ai/algenta -- one VM per job.
# Registers a JIT ephemeral runner (labels az-ephemeral,self-hosted), runs
# exactly one job, then deletes itself via the RG-scoped thyn-ci-builder SP.
# If the self-delete fails, the orchestrator's 90-minute reaper deletes the VM.
package_update: true
package_upgrade: false
packages:
  - ca-certificates
  - curl
  - git
  - jq
  - docker.io
  - python3
  - python3-pip
  - software-properties-common
write_files:
  - path: /opt/ci/secrets.env
    permissions: '0600'
    content: |
      AZURE_TENANT_ID=__AZURE_TENANT_ID__
      AZURE_SP_CLIENT_ID=__AZURE_SP_CLIENT_ID__
      AZURE_SP_CLIENT_SECRET=__AZURE_SP_CLIENT_SECRET__
      AZURE_SUBSCRIPTION_ID=__AZURE_SUBSCRIPTION_ID__
      AZURE_RESOURCE_GROUP=__AZURE_RESOURCE_GROUP__
  - path: /opt/ci/self-delete.sh
    permissions: '0700'
    content: |
      #!/usr/bin/env bash
      # Runs as root (invoked via sudo by run-worker.sh) so the SP secrets stay
      # root-only; deletes this VM once the runner has finished its one job.
      set -eu
      . /opt/ci/secrets.env
      az login --service-principal -u "$AZURE_SP_CLIENT_ID" \\
        -p "$AZURE_SP_CLIENT_SECRET" --tenant "$AZURE_TENANT_ID" --output none
      az account set --subscription "$AZURE_SUBSCRIPTION_ID"
      az vm delete --resource-group "$AZURE_RESOURCE_GROUP" \\
        --name "$(hostname)" --yes --no-wait
  - path: /opt/ci/run-worker.sh
    permissions: '0755'
    content: |
      #!/usr/bin/env bash
      # Run the ephemeral agent (blocks until the one job finishes), then
      # delete this VM so no compute outlives the job it was provisioned for.
      set -u
      cd /opt/actions-runner
      ./run.sh
      rc=$?
      echo "runner exited rc=$rc; self-deleting VM $(hostname)"
      sudo /opt/ci/self-delete.sh \\
        || echo "self-delete FAILED; orchestrator reaper will reclaim this VM" >&2
      exit 0
runcmd:
  - systemctl enable --now docker
  - usermod -aG docker azureuser
  # python3.14: several jobs (docs-audit) call it directly from PATH and the
  # workflows deliberately avoid actions/setup-python; Ubuntu 22.04 ships 3.10.
  - add-apt-repository -y ppa:deadsnakes/ppa
  - apt-get update
  - apt-get install -y python3.14 python3.14-venv
  # Azure CLI (needed only for the post-job self-delete; installed before the
  # runner starts so workflow steps never race the apt lock).
  - curl -sL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-archive-keyring.gpg
  - echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-archive-keyring.gpg] https://packages.microsoft.com/repos/azure-cli/ jammy main" > /etc/apt/sources.list.d/azure-cli.list
  - apt-get update
  - apt-get install -y azure-cli
  - mkdir -p /opt/actions-runner
  - bash -c 'RUNNER_VERSION=$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest | jq -r .tag_name | tr -d v) && cd /opt/actions-runner && curl -fsSL -o runner.tar.gz "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" && tar xzf runner.tar.gz && rm -f runner.tar.gz'
  - chown -R azureuser:azureuser /opt/actions-runner
  - cd /opt/actions-runner && sudo -u azureuser ./config.sh --url https://github.com/__GITHUB_REPO__ --token __REGISTRATION_TOKEN__ --name __VM_NAME__ --labels az-ephemeral,self-hosted --ephemeral --unattended
  - cd /opt/actions-runner && sudo -u azureuser nohup /opt/ci/run-worker.sh >/var/log/runner-exec.log 2>&1 &
"""


@dataclass
class Job:
    id: int
    run_id: int
    name: str
    html_url: str


# -- GitHub API (stdlib only) -------------------------------------------------
def gh_api(method: str, path: str, body=None):
    req = urllib.request.Request(
        f"{GH_API}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "algenta-az-orchestrator",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_queued_az_jobs():
    """Queued jobs requesting the az-ephemeral label, across queued AND
    in-progress runs (matrix legs can be queued while their run is running)."""
    jobs = []
    seen_jobs = set()
    for status in ("queued", "in_progress"):
        try:
            runs = gh_api(
                "GET", f"/repos/{GITHUB_REPO}/actions/runs?status={status}&per_page=50"
            ).get("workflow_runs", [])
        except (urllib.error.URLError, TimeoutError) as exc:
            log.warning("listing %s runs failed: %s", status, exc)
            continue
        for run in runs:
            try:
                page = gh_api(
                    "GET",
                    f"/repos/{GITHUB_REPO}/actions/runs/{run['id']}/jobs?per_page=100",
                ).get("jobs", [])
            except (urllib.error.URLError, TimeoutError) as exc:
                log.warning("listing jobs for run %s failed: %s", run["id"], exc)
                continue
            for j in page:
                if (
                    j.get("status") == "queued"
                    and "az-ephemeral" in j.get("labels", [])
                    and j["id"] not in seen_jobs
                ):
                    seen_jobs.add(j["id"])
                    jobs.append(
                        Job(
                            id=j["id"],
                            run_id=run["id"],
                            name=j.get("name", "?"),
                            html_url=j.get("html_url", ""),
                        )
                    )
    return jobs


def fetch_registration_token() -> str:
    return gh_api(
        "POST", f"/repos/{GITHUB_REPO}/actions/runners/registration-token", body={}
    )["token"]


# -- state (dedupe by job id) -------------------------------------------------
_db_lock = threading.Lock()


def _db():
    conn = sqlite3.connect(STATE_DB, timeout=10)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS handled ("
        " job_id INTEGER PRIMARY KEY,"
        " run_id INTEGER,"
        " vm_name TEXT,"
        " status TEXT,"
        " ts TEXT)"
    )
    return conn


def is_handled(job_id: int) -> bool:
    with _db_lock:
        conn = _db()
        try:
            row = conn.execute(
                "SELECT 1 FROM handled WHERE job_id = ?", (job_id,)
            ).fetchone()
            return row is not None
        finally:
            conn.close()


def mark_handled(job: Job, vm_name: str, status: str = "provisioning"):
    with _db_lock:
        conn = _db()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO handled (job_id, run_id, vm_name, status, ts)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    job.id,
                    job.run_id,
                    vm_name,
                    status,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()


def unmark(job_id: int):
    with _db_lock:
        conn = _db()
        try:
            conn.execute("DELETE FROM handled WHERE job_id = ?", (job_id,))
            conn.commit()
        finally:
            conn.close()


def _set_status(job_id: int, status: str):
    with _db_lock:
        conn = _db()
        try:
            conn.execute(
                "UPDATE handled SET status = ? WHERE job_id = ?", (status, job_id)
            )
            conn.commit()
        finally:
            conn.close()


def _provisioning_rows():
    with _db_lock:
        conn = _db()
        try:
            return conn.execute(
                "SELECT job_id, vm_name FROM handled WHERE status = 'provisioning'"
            ).fetchall()
        finally:
            conn.close()


# -- Azure --------------------------------------------------------------------
def _az_error_detail(stderr: str) -> str:
    """Extract the real error from az CLI stderr.

    The az CLI sometimes crashes while FORMATTING an ARM error response
    ("The content for this response was already consumed"), emitting a long
    Python traceback that buries/truncates the actual reason. Surface the real
    `ERROR:`/`Code:`/`Message:` lines when present, else fall back to the tail
    of stderr, and keep enough text for transient (quota/capacity) matching.
    """
    lines = [ln for ln in stderr.splitlines() if ln.strip()]
    useful = [
        ln
        for ln in lines
        if ln.strip().startswith(("ERROR:", "Code:", "Message:"))
        or "quota" in ln.lower()
        or "The command failed with an unexpected error" in ln
        or "content for this response was already consumed" in ln
    ]
    if useful:
        return " | ".join(ln.strip() for ln in useful)[:1500]
    return stderr.strip()[-1500:]


def run_az(args, check=True, timeout=600):
    cmd = ["az"] + args + ["--output", "json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if check and proc.returncode != 0:
        detail = _az_error_detail(proc.stderr or "")
        raise RuntimeError(f"az {' '.join(args[:3])} failed: {detail}")
    return proc


def ensure_az_login():
    probe = subprocess.run(
        ["az", "account", "show"], capture_output=True, text=True
    )
    if probe.returncode != 0:
        run_az(
            [
                "login",
                "--service-principal",
                "-u",
                AZ_CLIENT_ID,
                "-p",
                AZ_CLIENT_SECRET,
                "--tenant",
                AZ_TENANT,
            ]
        )
    run_az(["account", "set", "--subscription", AZ_SUBSCRIPTION])
    log.info("az CLI authenticated as SP %s (subscription %s)", AZ_CLIENT_ID, AZ_SUBSCRIPTION)


def render_worker_cloud_init(reg_token: str, vm_name: str) -> str:
    rendered = (
        WORKER_CLOUD_INIT
        .replace("__AZURE_TENANT_ID__", AZ_TENANT)
        .replace("__AZURE_SP_CLIENT_ID__", AZ_CLIENT_ID)
        .replace("__AZURE_SP_CLIENT_SECRET__", AZ_CLIENT_SECRET)
        .replace("__AZURE_SUBSCRIPTION_ID__", AZ_SUBSCRIPTION)
        .replace("__AZURE_RESOURCE_GROUP__", AZ_RESOURCE_GROUP)
        .replace("__GITHUB_REPO__", GITHUB_REPO)
        .replace("__REGISTRATION_TOKEN__", reg_token)
        .replace("__VM_NAME__", vm_name)
    )
    # Azure custom-data must survive latin-1 transport; fail loud, not mid-deploy.
    rendered.encode("ascii")
    return rendered


def create_worker_vm(job: Job, vm_name: str, cloud_init: str):
    """Try each configured size in order; first successful allocation wins."""
    last_error = "no sizes configured"
    for size in AZ_VM_SIZES:
        init_file = f"/tmp/{vm_name}.cloud-init"
        with open(init_file, "w", encoding="utf-8") as fh:
            fh.write(cloud_init)
        os.chmod(init_file, 0o600)
        try:
            run_az(
                [
                    "vm",
                    "create",
                    "--resource-group",
                    AZ_RESOURCE_GROUP,
                    "--name",
                    vm_name,
                    "--location",
                    AZ_LOCATION,
                    "--image",
                    WORKER_IMAGE,
                    "--size",
                    size,
                    "--admin-username",
                    "azureuser",
                    "--ssh-key-value",
                    WORKER_SSH_PUBKEY,
                    "--subnet",
                    AZ_SUBNET_ID,
                    "--public-ip-sku",
                    "Standard",
                    "--os-disk-size-gb",
                    WORKER_OS_DISK_GB,
                    "--storage-sku",
                    "Premium_LRS",
                    "--custom-data",
                    init_file,
                    "--tags",
                    "plane=az-ci",
                    f"github-run={job.run_id}",
                    f"github-job={job.id}",
                ],
                timeout=900,
            )
            log.info("provisioned %s (%s) for job %s", vm_name, size, job.id)
            return
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            last_error = str(exc)
            log.warning("size %s failed for %s: %s", size, vm_name, last_error)
        finally:
            try:
                os.unlink(init_file)
            except OSError:
                pass
    raise RuntimeError(f"all sizes failed for {vm_name}: {last_error}")


_attempts = {}  # job_id -> failed provision attempts (in-memory)
_attempts_lock = threading.Lock()


def provision(job: Job):
    vm_name = f"{VM_PREFIX}{job.run_id}-{job.id}"[:64]
    try:
        reg_token = fetch_registration_token()
        cloud_init = render_worker_cloud_init(reg_token, vm_name)
        create_worker_vm(job, vm_name, cloud_init)
        mark_handled(job, vm_name, status="running")
        log.info(
            "job %s (%s) handled by %s -- %s", job.id, job.name, vm_name, job.html_url
        )
    except Exception as exc:  # noqa: BLE001 -- never let one job kill the loop
        # Capacity/quota exhaustion (and az CLI crashes that hide ARM errors)
        # is TRANSIENT: capacity frees up when a worker self-deletes. Reset the
        # job and pause new provisioning for a cooldown instead of counting it
        # toward the permanent-failure budget.
        if is_transient_error(str(exc)):
            unmark(job.id)
            enter_cooldown()
            log.warning(
                "job %s provision hit transient capacity error; cooldown %ds: %s",
                job.id,
                COOLDOWN_SECONDS,
                str(exc)[:400],
            )
            return
        with _attempts_lock:
            _attempts[job.id] = _attempts.get(job.id, 0) + 1
            attempts = _attempts[job.id]
        if attempts >= MAX_PROVISION_ATTEMPTS:
            mark_handled(job, vm_name, status="failed")
            log.error(
                "job %s permanently failed after %d attempts: %s",
                job.id,
                attempts,
                str(exc)[:400],
            )
        else:
            unmark(job.id)
            log.warning(
                "job %s provision attempt %d/%d failed (will retry): %s",
                job.id,
                attempts,
                MAX_PROVISION_ATTEMPTS,
                str(exc)[:400],
            )


def reap_stale_vms():
    proc = run_az(
        ["vm", "list", "--resource-group", AZ_RESOURCE_GROUP], check=False
    )
    if proc.returncode != 0:
        log.warning("reaper: vm list failed: %s", proc.stderr.strip()[:300])
        return
    now = datetime.now(timezone.utc)
    for vm in json.loads(proc.stdout or "[]"):
        name = vm.get("name", "")
        created_raw = vm.get("timeCreated")
        if not name.startswith(VM_PREFIX) or not created_raw:
            continue
        try:
            created = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        age_min = (now - created).total_seconds() / 60
        if age_min > MAX_VM_AGE_MINUTES:
            log.warning(
                "reaping stale VM %s (age %.0f min > %d min)",
                name,
                age_min,
                MAX_VM_AGE_MINUTES,
            )
            run_az(
                ["vm", "delete", "--resource-group", AZ_RESOURCE_GROUP,
                 "--name", name, "--yes", "--no-wait"],
                check=False,
            )


def _protected_vm_names():
    """VM names currently being provisioned (must not GC their NIC/PIP/NSG/disk,
    which transiently exist before the VM shows up in `az vm list`)."""
    with _db_lock:
        conn = _db()
        try:
            rows = conn.execute(
                "SELECT vm_name FROM handled WHERE status = 'provisioning'"
            ).fetchall()
        finally:
            conn.close()
    return {r[0] for r in rows if r[0]}


def reap_orphaned_resources():
    """GC the NIC/PIP/NSG/OS-disk that `az vm delete` leaves behind when a
    worker self-deletes (vm delete removes only the compute resource). Only
    touched are ci-az-* resources whose VM no longer exists and is not
    mid-provision, so a live or in-flight worker is never dismembered."""
    proc = run_az(["vm", "list", "--resource-group", AZ_RESOURCE_GROUP], check=False)
    if proc.returncode != 0:
        return
    live_vms = {vm.get("name") for vm in json.loads(proc.stdout or "[]")}
    protected = _protected_vm_names()

    def gcable(base_vm: str) -> bool:
        return bool(base_vm) and base_vm not in live_vms and base_vm not in protected

    # Orphaned NICs (virtualMachine == null)
    proc = run_az(["network", "nic", "list", "--resource-group", AZ_RESOURCE_GROUP], check=False)
    if proc.returncode == 0:
        for nic in json.loads(proc.stdout or "[]"):
            name = nic.get("name", "")
            if name.startswith(VM_PREFIX) and name.endswith("VMNic") and nic.get("virtualMachine") is None:
                base = name[: -len("VMNic")]
                if gcable(base):
                    run_az(["network", "nic", "delete", "--resource-group", AZ_RESOURCE_GROUP, "--name", name], check=False)
                    log.info("gc: deleted orphaned NIC %s", name)

    # Orphaned public IPs (detached)
    proc = run_az(["network", "public-ip", "list", "--resource-group", AZ_RESOURCE_GROUP], check=False)
    if proc.returncode == 0:
        for pip in json.loads(proc.stdout or "[]"):
            name = pip.get("name", "")
            if name.startswith(VM_PREFIX) and name.endswith("PublicIP") and not pip.get("ipConfiguration"):
                base = name[: -len("PublicIP")]
                if gcable(base):
                    run_az(["network", "public-ip", "delete", "--resource-group", AZ_RESOURCE_GROUP, "--name", name], check=False)
                    log.info("gc: deleted orphaned PIP %s", name)

    # Orphaned NSGs (named <vm>NSG, VM gone)
    proc = run_az(["network", "nsg", "list", "--resource-group", AZ_RESOURCE_GROUP], check=False)
    if proc.returncode == 0:
        for nsg in json.loads(proc.stdout or "[]"):
            name = nsg.get("name", "")
            if name.startswith(VM_PREFIX) and name.endswith("NSG"):
                base = name[: -len("NSG")]
                if gcable(base):
                    run_az(["network", "nsg", "delete", "--resource-group", AZ_RESOURCE_GROUP, "--name", name], check=False)
                    log.info("gc: deleted orphaned NSG %s", name)

    # Orphaned OS disks (managedBy == null, older than 10 min for safety)
    proc = run_az(["disk", "list", "--resource-group", AZ_RESOURCE_GROUP], check=False)
    if proc.returncode == 0:
        now = datetime.now(timezone.utc)
        for disk in json.loads(proc.stdout or "[]"):
            name = disk.get("name", "")
            if not (name.startswith(VM_PREFIX) and disk.get("managedBy") is None):
                continue
            base = name.split("_OsDisk")[0]
            created_raw = disk.get("timeCreated")
            if created_raw:
                try:
                    created = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
                    if (now - created).total_seconds() < 600:
                        continue
                except ValueError:
                    pass
            if gcable(base):
                run_az(["disk", "delete", "--resource-group", AZ_RESOURCE_GROUP, "--name", name, "--yes"], check=False)
                log.info("gc: deleted orphaned disk %s", name)


def recover_stale_provisioning():
    """Recover jobs wedged in 'provisioning' after a daemon restart.

    A restart kills the in-flight provision threads (and their az children),
    but their dedupe rows survive; the fresh daemon would then skip those jobs
    forever. A row whose VM never materialized is reset so the job is retried;
    a row whose VM DOES exist (the ARM deployment outlived the process) is kept
    and promoted to 'running'.
    """
    # Clear rows marked 'failed' by a previous daemon lifetime: they were most
    # often transient capacity errors mis-bucketed before a restart picked up
    # fixes. GitHub still has the job queued, so retry it; a genuine repeat
    # failure re-fails it within this lifetime.
    with _db_lock:
        conn = _db()
        try:
            n = conn.execute("DELETE FROM handled WHERE status = 'failed'").rowcount
            conn.commit()
        finally:
            conn.close()
    if n:
        log.info("recovery: reset %d previously failed job(s) for retry", n)

    rows = _provisioning_rows()
    if not rows:
        return
    existing = set()
    proc = run_az(
        ["vm", "list", "--resource-group", AZ_RESOURCE_GROUP], check=False
    )
    if proc.returncode == 0:
        existing = {vm.get("name") for vm in json.loads(proc.stdout or "[]")}
    for job_id, vm_name in rows:
        if vm_name in existing:
            _set_status(job_id, "running")
            log.info("recovery: job %s kept (VM %s exists)", job_id, vm_name)
        else:
            unmark(job_id)
            log.info("recovery: job %s reset for retry (VM %s absent)", job_id, vm_name)


# -- main loop ----------------------------------------------------------------
def main():
    os.makedirs(os.path.dirname(STATE_DB), exist_ok=True)
    ensure_az_login()
    try:
        recover_stale_provisioning()
    except Exception as exc:  # noqa: BLE001
        log.warning("recovery failed: %s", exc)
    log.info(
        "watching %s for az-ephemeral jobs (sizes: %s, poll %ds, reap >%d min)",
        GITHUB_REPO,
        ",".join(AZ_VM_SIZES),
        POLL_SECONDS,
        MAX_VM_AGE_MINUTES,
    )
    loop = 0
    cooldown_logged = False
    with ThreadPoolExecutor(max_workers=PROVISION_CONCURRENCY) as pool:
        while True:
            loop += 1
            try:
                jobs = fetch_queued_az_jobs()
            except Exception as exc:  # noqa: BLE001
                log.warning("poll failed: %s", exc)
                jobs = []
            if cooling_down():
                if not cooldown_logged:
                    log.info("provisioning paused for %ds (capacity cooldown)", COOLDOWN_SECONDS)
                    cooldown_logged = True
            else:
                cooldown_logged = False
                for job in jobs:
                    if is_handled(job.id):
                        continue
                    # Reserve the slot BEFORE the slow provision so the next
                    # poll cannot double-provision; on failure the row is
                    # removed.
                    mark_handled(job, f"{VM_PREFIX}{job.run_id}-{job.id}"[:64])
                    pool.submit(provision, job)
            if loop % REAP_EVERY_LOOPS == 0:
                try:
                    reap_stale_vms()
                except Exception as exc:  # noqa: BLE001
                    log.warning("reap failed: %s", exc)
            if loop % RESOURCE_GC_EVERY_LOOPS == 0:
                try:
                    reap_orphaned_resources()
                except Exception as exc:  # noqa: BLE001
                    log.warning("resource gc failed: %s", exc)
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
