"""Host-environment EVIDENCE collection — cloud/VM/container/CI signals.

This module answers "what does this host look like?" — it NEVER answers "which license does
this host get?". Per the approved plan (§0b, §4), host evidence is **silent risk signal only**:

  * It can inform mint-time attestation and fraud review on the control plane.
  * It can NEVER move a runtime from personal-device scope into organization-deployment scope,
    block a personal user, or nag a legitimate developer. Deployment scope activates ONLY
    through an explicit artifact (deployment license / ``ALGENTA_DEPLOYMENT_ID`` / Relay lease).
  * Absent or ambiguous evidence ALWAYS resolves to ``workstation`` — never ``server``.

Detect cloud VENDORS, never virtualization: a KVM/QEMU DMI string, ``/.dockerenv``, WSL, or a
CI env var fire on ordinary developer laptops (Docker Desktop, devcontainers, WSL2) and must
never be load-bearing. Only cloud-vendor DMI (Amazon/Google/Azure) is a strong signal, and even
that is documented by the cloud vendors as non-guaranteed — so it stays advisory.

Fully offline + root-less: reads ``/sys/class/dmi`` (world-readable), ``/proc``, and env vars.
No network (IMDS probing, if ever added, belongs behind the egress guard at mint time, not
here). Every read fails soft to ``unknown``.
"""
from __future__ import annotations

import os
import platform
from dataclasses import dataclass, field
from pathlib import Path

_DMI_DIR = "/sys/class/dmi/id"

# Cloud-vendor DMI fingerprints. Matched case-insensitively as substrings against sys_vendor /
# product_name / board/chassis asset tags. Documented as indicative, NOT guaranteed.
_CLOUD_DMI_MARKERS: dict[str, tuple[str, ...]] = {
    "aws": ("amazon ec2", "amazon", "amzn"),
    "gcp": ("google compute engine", "google"),
    "azure": ("microsoft corporation", "7783-7084-3265-9085-8269-3286-77"),  # Azure chassis tag
}

# Generic virtualization markers — these must NEVER gate price/scope (they fire on laptops).
_GENERIC_VM_MARKERS: tuple[str, ...] = ("vmware", "virtualbox", "qemu", "kvm", "xen", "bochs")

# CI providers keyed by the env var that (best-effort) indicates them. Spoofable — advisory only,
# and the real CI lane uses signed workload identity (OIDC), not these vars.
_CI_ENV_MARKERS: dict[str, str] = {
    "github_actions": "GITHUB_ACTIONS",
    "gitlab_ci": "GITLAB_CI",
    "jenkins": "JENKINS_URL",
    "buildkite": "BUILDKITE",
    "circleci": "CIRCLECI",
    "travis": "TRAVIS",
    "codespaces": "CODESPACES",
    "generic_ci": "CI",
}


@dataclass(frozen=True)
class HostEvidence:
    """Structured, offline host signals. All fields fail soft to ``""``/``False``/``unknown``.

    Nothing here decides licensing. ``cloud_vendor`` / ``is_container`` / ``ci_provider`` are
    inputs to control-plane risk review and to the local ``license_status`` display only.
    """

    platform: str = "unknown"  # linux | darwin | windows | unknown
    cloud_vendor: str = "unknown"  # aws | gcp | azure | unknown
    generic_virtualization: str = ""  # vmware/qemu/... or "" — informational, never gating
    is_container: bool = False
    is_kubernetes: bool = False
    is_wsl: bool = False
    ci_provider: str = ""  # "" when not CI
    dmi_sys_vendor: str = ""
    dmi_product_name: str = ""
    dmi_asset_tag: str = ""
    stable_host_uuid: str = ""  # DMI product_uuid (for clone/restore detection at a higher layer)
    logical_cpu_count: int = 0
    raw: dict[str, str] = field(default_factory=dict)

    def is_cloud_datacenter(self) -> bool:
        """True only for a recognized cloud VENDOR (never generic VM/container). Advisory."""
        return self.cloud_vendor in {"aws", "gcp", "azure"}

    def looks_like_personal_dev(self) -> bool:
        """Heuristic: signals consistent with one human on one dev machine. Used only to SUPPRESS
        prompts for legitimate developers, never to grant or deny anything."""
        if self.platform in {"darwin", "windows"}:
            return True
        if self.is_wsl:
            return True
        # A container/CI on a laptop is still personal — only cloud-vendor DMI weighs against it.
        return not self.is_cloud_datacenter()

    def risk_signals(self) -> list[str]:
        """Advisory signals for control-plane fraud review / sales routing. Presence here NEVER
        implies enforcement — it's a list a human or a soft heuristic may weigh."""
        signals: list[str] = []
        if self.is_cloud_datacenter():
            signals.append(f"cloud_vendor:{self.cloud_vendor}")
        if self.is_kubernetes:
            signals.append("kubernetes")
        if self.ci_provider:
            signals.append(f"ci:{self.ci_provider}")
        if self.generic_virtualization:
            signals.append(f"virt:{self.generic_virtualization}")
        return signals


# ── readers (all offline, root-less, fail-soft) ──────────────────────────────────


def _read_dmi(name: str) -> str:
    try:
        return Path(f"{_DMI_DIR}/{name}").read_text().strip()
    except OSError:
        return ""


def _classify_cloud(*dmi_values: str) -> str:
    blob = " ".join(v.lower() for v in dmi_values if v)
    if not blob:
        return "unknown"
    for vendor, markers in _CLOUD_DMI_MARKERS.items():
        if any(m in blob for m in markers):
            return vendor
    return "unknown"


def _classify_generic_virt(*dmi_values: str) -> str:
    blob = " ".join(v.lower() for v in dmi_values if v)
    for marker in _GENERIC_VM_MARKERS:
        if marker in blob:
            return marker
    return ""


def _detect_container() -> bool:
    if Path("/.dockerenv").exists():
        return True
    try:
        cgroup = Path("/proc/1/cgroup").read_text()
    except OSError:
        return False
    return any(tok in cgroup for tok in ("docker", "containerd", "kubepods", "crio", "podman"))


def _detect_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def _detect_ci() -> str:
    for name, env in _CI_ENV_MARKERS.items():
        val = os.environ.get(env, "").strip().lower()
        if val and val not in {"0", "false", "no"}:
            return name
    return ""


# ── public API ───────────────────────────────────────────────────────────────


def collect_host_evidence() -> HostEvidence:
    """Collect all offline host signals. Deterministic, safe at boot and on heartbeat.

    Never raises: any failed read degrades to the field default (which biases toward
    ``workstation`` / ``unknown``)."""
    system = platform.system().lower()  # 'linux' | 'darwin' | 'windows' | ''
    plat = system if system in {"linux", "darwin", "windows"} else "unknown"

    sys_vendor = _read_dmi("sys_vendor")
    product_name = _read_dmi("product_name")
    board_asset = _read_dmi("board_asset_tag")
    chassis_asset = _read_dmi("chassis_asset_tag")
    product_uuid = _read_dmi("product_uuid")

    cloud = _classify_cloud(sys_vendor, product_name, board_asset, chassis_asset)
    virt = _classify_generic_virt(sys_vendor, product_name)

    return HostEvidence(
        platform=plat,
        cloud_vendor=cloud,
        generic_virtualization=virt,
        is_container=_detect_container(),
        is_kubernetes=bool(os.environ.get("KUBERNETES_SERVICE_HOST", "").strip()),
        is_wsl=_detect_wsl(),
        ci_provider=_detect_ci(),
        dmi_sys_vendor=sys_vendor,
        dmi_product_name=product_name,
        dmi_asset_tag=board_asset or chassis_asset,
        stable_host_uuid=product_uuid,
        logical_cpu_count=os.cpu_count() or 0,
        raw={
            "sys_vendor": sys_vendor,
            "product_name": product_name,
            "board_asset_tag": board_asset,
            "chassis_asset_tag": chassis_asset,
        },
    )
