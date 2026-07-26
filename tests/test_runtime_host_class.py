"""Host-environment evidence collection (apps/runtime/host_class.py).

Covers plan §9 detection gates: cloud VENDOR classification (EC2/GCE/Azure), the critical
false-positive rule (Docker/WSL/CI/generic-VM on a personal laptop must NOT read as
datacenter), and fail-to-unknown/workstation on absent evidence. Evidence is advisory only —
these tests assert classification, never enforcement (there is none here).
"""
from __future__ import annotations

from apps.runtime import host_class as hc


# ── cloud-vendor DMI classification ──────────────────────────────────────────────


def test_classify_cloud_aws() -> None:
    assert hc._classify_cloud("Amazon EC2", "t3.large") == "aws"


def test_classify_cloud_gcp() -> None:
    assert hc._classify_cloud("Google", "Google Compute Engine") == "gcp"


def test_classify_cloud_azure_chassis_tag() -> None:
    assert hc._classify_cloud("", "", "", "7783-7084-3265-9085-8269-3286-77") == "azure"


def test_classify_cloud_azure_vendor_string() -> None:
    assert hc._classify_cloud("Microsoft Corporation", "Virtual Machine") == "azure"


def test_classify_cloud_unknown_when_empty() -> None:
    assert hc._classify_cloud("", "", "") == "unknown"


def test_generic_qemu_is_not_a_cloud_vendor() -> None:
    # A KVM/QEMU laptop VM must classify as generic virt, NOT a cloud datacenter.
    assert hc._classify_cloud("QEMU", "Standard PC (Q35)") == "unknown"
    assert hc._classify_generic_virt("QEMU", "Standard PC (Q35)") == "qemu"


def test_vmware_is_generic_virt_only() -> None:
    assert hc._classify_cloud("VMware, Inc.", "VMware Virtual Platform") == "unknown"
    assert hc._classify_generic_virt("VMware, Inc.", "VMware Virtual Platform") == "vmware"


# ── false-positive protection (the SDK-GTM-critical cases) ───────────────────────


def test_docker_on_laptop_is_personal_not_datacenter() -> None:
    ev = hc.HostEvidence(platform="linux", cloud_vendor="unknown", is_container=True)
    assert not ev.is_cloud_datacenter()
    assert ev.looks_like_personal_dev()
    assert "cloud_vendor" not in " ".join(ev.risk_signals())


def test_wsl_is_personal_dev() -> None:
    ev = hc.HostEvidence(platform="linux", is_wsl=True)
    assert ev.looks_like_personal_dev()


def test_macos_and_windows_are_personal_dev() -> None:
    assert hc.HostEvidence(platform="darwin").looks_like_personal_dev()
    assert hc.HostEvidence(platform="windows").looks_like_personal_dev()


def test_ci_on_laptop_container_not_datacenter() -> None:
    ev = hc.HostEvidence(platform="linux", is_container=True, ci_provider="github_actions")
    assert not ev.is_cloud_datacenter()
    # CI shows as a risk signal but never as cloud datacenter.
    assert ev.risk_signals() == ["ci:github_actions"]


def test_ec2_is_cloud_datacenter() -> None:
    ev = hc.HostEvidence(platform="linux", cloud_vendor="aws")
    assert ev.is_cloud_datacenter()
    assert not ev.looks_like_personal_dev()
    assert "cloud_vendor:aws" in ev.risk_signals()


def test_kubernetes_and_cloud_stack_signals() -> None:
    ev = hc.HostEvidence(
        platform="linux", cloud_vendor="gcp", is_kubernetes=True, is_container=True
    )
    sigs = ev.risk_signals()
    assert "cloud_vendor:gcp" in sigs and "kubernetes" in sigs


# ── CI env detection (spoofable → advisory only) ─────────────────────────────────


def test_detect_ci_github(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert hc._detect_ci() == "github_actions"


def test_detect_ci_generic(monkeypatch) -> None:
    for var in hc._CI_ENV_MARKERS.values():
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CI", "true")
    assert hc._detect_ci() == "generic_ci"


def test_detect_ci_false_values_ignored(monkeypatch) -> None:
    for var in hc._CI_ENV_MARKERS.values():
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CI", "false")
    assert hc._detect_ci() == ""


def test_detect_ci_none(monkeypatch) -> None:
    for var in hc._CI_ENV_MARKERS.values():
        monkeypatch.delenv(var, raising=False)
    assert hc._detect_ci() == ""


# ── collect_host_evidence is total (never raises) ────────────────────────────────


def test_collect_host_evidence_never_raises(monkeypatch) -> None:
    for var in hc._CI_ENV_MARKERS.values():
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
    ev = hc.collect_host_evidence()
    assert ev.platform in {"linux", "darwin", "windows", "unknown"}
    assert ev.cloud_vendor in {"aws", "gcp", "azure", "unknown"}
    assert ev.logical_cpu_count >= 0
    # On this dev machine (macOS/Linux laptop) the default must be personal-dev-friendly:
    # ambiguous/no cloud DMI → not a datacenter.
    if ev.cloud_vendor == "unknown":
        assert not ev.is_cloud_datacenter()


def test_ambiguous_evidence_defaults_to_workstation() -> None:
    # The core invariant: no signal → workstation-friendly, never server.
    ev = hc.HostEvidence()
    assert not ev.is_cloud_datacenter()
    assert ev.looks_like_personal_dev()
    assert ev.risk_signals() == []
