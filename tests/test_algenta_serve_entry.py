"""`algenta serve`'s startup gate and launch path, exercised with NO accelerator.

Every test here runs on CPU on any platform, which is the point: the gate is a
pure function of declared facts, so the whole truth table — no NVIDIA device, an
old driver, an unsupported compute capability, a missing engine binary, an
unsupported model shape — is testable without owning the hardware it refuses on.
The facts are injected (`platform=`, `host=`, `environ=`, `runner=`) rather than
mocked out of existence, so what is under test is the real gate reading real
declarations from `algenta.model_capabilities`.

Two invariants get the most airtime because they are the ones a regression would
hurt most:
* a refusal is TYPED and machine-readable (a stable `code`, the capability
  table's own fact/value/range vocabulary), never a bare non-zero exit;
* an explicit `--backend` NEVER falls back — `resolved_backend` stays the backend
  that was asked for, or the request is refused.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_ALGENTA = ROOT / "packages" / "algenta"
for _path in (str(_ALGENTA), str(ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from algenta.model_capabilities import BACKEND_HOST_REQUIREMENTS  # noqa: E402
from algenta.serve import (  # noqa: E402
    ServeError,
    ServeOutcome,
    ServeRequest,
    plan_serve,
    serve,
)
from algenta.serve import cli as serve_cli  # noqa: E402
from algenta.serve.engine import (  # noqa: E402
    CUDA_ENGINE_BINARY_NAME,
    parse_engine_output,
    resolve_engine,
)
from algenta.serve.gating import (  # noqa: E402
    NvidiaHostFacts,
    detect_backend,
    gate_serve,
    host_refusals,
    model_refusals,
    parse_version_tuple,
    probe_nvidia_host,
    serve_backends,
)

# A supported Qwen3-style d128 shape, declared as a config.json only (so the
# tensor-level facts stay unprobed and no weights are needed on disk).
_SUPPORTED_CONFIG = {
    "hidden_size": 1024,
    "num_hidden_layers": 4,
    "num_attention_heads": 16,
    "num_key_value_heads": 8,
    "head_dim": 128,
    "intermediate_size": 3072,
    "vocab_size": 32000,
    "rope_theta": 10000.0,
    "rms_norm_eps": 1e-5,
    "model_type": "qwen3",
}

_GOOD_HOST = NvidiaHostFacts(
    probed=True,
    probe_source="nvidia-smi",
    driver_version="580.173.02",
    driver_version_tuple=(580, 173, 2),
    device_count=1,
    device_names=("NVIDIA H200",),
    compute_capabilities=((9, 0),),
)


def _checkpoint(tmp_path: Path, **overrides) -> Path:
    directory = tmp_path / "ckpt"
    directory.mkdir(parents=True, exist_ok=True)
    config = {**_SUPPORTED_CONFIG, **overrides}
    (directory / "config.json").write_text(json.dumps(config), encoding="utf-8")
    return directory


def _engine_binary(tmp_path: Path, body: str, *, name: str = CUDA_ENGINE_BINARY_NAME) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    path = bindir / name
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def _converted(tmp_path: Path, *, prompt: tuple[int, ...] = (1, 2)) -> Path:
    """A pre-converted manifest+blob pair, so the launch path is exercisable
    without running the multi-gigabyte converter."""
    directory = tmp_path / "converted"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "config": {"hidden_size": 1024, "n_tokens": len(prompt)},
                "input_ids": list(prompt),
                "tensors": {"token_embd.weight": {"offset": 0, "n_elements": 4}},
            }
        ),
        encoding="utf-8",
    )
    (directory / "weights.blob").write_bytes(b"\0" * 32)
    return directory


def _codes(refusals) -> set[str]:
    return {refusal.code for refusal in refusals}


# ── the declared facts this gate reads ───────────────────────────────────────


def test_published_backends_are_the_contracts_own_and_auto_is_the_only_addition() -> None:
    """No hand-maintained backend list: `--backend`'s choices are the contract's
    published engine-kernel backends plus autodetect."""
    from algenta.runtime_library_contract import engine_kernel_backends

    assert serve_backends() == ("auto",) + tuple(engine_kernel_backends())
    assert "cuda" in serve_backends()


def test_every_published_backend_declares_its_host_requirements() -> None:
    """A backend the contract publishes but this table does not describe would
    gate on nothing at all — which reads as "always allowed"."""
    from algenta.runtime_library_contract import engine_kernel_backends

    for backend in engine_kernel_backends():
        assert backend in BACKEND_HOST_REQUIREMENTS, backend
        requirements = BACKEND_HOST_REQUIREMENTS[backend]
        assert set(requirements) == {"platforms", "min_driver_version", "min_compute_capability"}
        assert requirements["platforms"], f"{backend} declares no platform"


def test_cuda_driver_floor_is_the_published_580() -> None:
    """The floor the gate names in a refusal is the published requirement, not a
    literal that drifted away from it."""
    assert BACKEND_HOST_REQUIREMENTS["cuda"]["min_driver_version"] == (580, 0)
    assert BACKEND_HOST_REQUIREMENTS["cuda"]["min_compute_capability"] == (7, 5)
    assert BACKEND_HOST_REQUIREMENTS["cuda"]["platforms"] == ("linux",)
    assert BACKEND_HOST_REQUIREMENTS["metal"]["min_driver_version"] is None


def test_version_parsing_reports_unknown_rather_than_zero() -> None:
    assert parse_version_tuple("580.173.02") == (580, 173, 2)
    assert parse_version_tuple("595.71.05") == (595, 71, 5)
    assert parse_version_tuple("N/A") is None
    assert parse_version_tuple("") is None
    assert parse_version_tuple(None) is None


# ── host facts ───────────────────────────────────────────────────────────────


def test_no_nvidia_interface_refuses_with_the_driver_floor_named() -> None:
    refusals = host_refusals("cuda", NvidiaHostFacts(probed=False), platform="linux")
    assert _codes(refusals) == {"no_nvidia_gpu"}
    message = refusals[0].message()
    assert "580" in message
    assert refusals[0].stage == "host"


def test_old_driver_refusal_names_the_found_version_and_the_floor() -> None:
    host = NvidiaHostFacts(
        probed=True,
        probe_source="nvidia-smi",
        driver_version="575.57.08",
        driver_version_tuple=(575, 57, 8),
        device_count=1,
        device_names=("NVIDIA L4",),
        compute_capabilities=((8, 9),),
    )
    refusals = host_refusals("cuda", host, platform="linux")
    assert _codes(refusals) == {"nvidia_driver_too_old"}
    message = refusals[0].message()
    assert "575.57.08" in message
    assert "580.0" in message
    assert refusals[0].value == "575.57.08"


def test_bare_major_driver_version_is_not_thereby_too_old() -> None:
    host = NvidiaHostFacts(
        probed=True, driver_version="580", driver_version_tuple=(580,), device_count=1
    )
    assert not host_refusals("cuda", host, platform="linux")


def test_driver_at_exactly_the_floor_is_accepted() -> None:
    host = NvidiaHostFacts(
        probed=True,
        driver_version="580.0",
        driver_version_tuple=(580, 0),
        device_count=1,
        compute_capabilities=((9, 0),),
    )
    assert not host_refusals("cuda", host, platform="linux")


def test_zero_devices_is_no_gpu_even_with_a_current_driver() -> None:
    host = NvidiaHostFacts(
        probed=True,
        driver_version="580.173.02",
        driver_version_tuple=(580, 173, 2),
        device_count=0,
    )
    assert _codes(host_refusals("cuda", host, platform="linux")) == {"no_nvidia_gpu"}


def test_unknown_device_count_never_reads_as_no_device() -> None:
    """A headless driver install knows the driver and nothing about the devices;
    guessing 0 there would refuse a host that has a working GPU."""
    host = NvidiaHostFacts(
        probed=True,
        probe_source="/proc/driver/nvidia/version",
        driver_version="580.173.02",
        driver_version_tuple=(580, 173, 2),
        device_count=None,
    )
    assert not host_refusals("cuda", host, platform="linux")


def test_pre_turing_compute_capability_is_refused() -> None:
    host = NvidiaHostFacts(
        probed=True,
        driver_version="580.173.02",
        driver_version_tuple=(580, 173, 2),
        device_count=1,
        device_names=("NVIDIA V100",),
        compute_capabilities=((7, 0),),
    )
    refusals = host_refusals("cuda", host, platform="linux")
    assert _codes(refusals) == {"nvidia_compute_capability_unsupported"}
    assert "V100" in refusals[0].message()
    assert "7.0" in refusals[0].message()


def test_cuda_is_refused_on_a_non_linux_platform() -> None:
    refusals = host_refusals("cuda", _GOOD_HOST, platform="darwin")
    assert "unsupported_platform" in _codes(refusals)
    assert any("darwin" in refusal.message() for refusal in refusals)


def test_metal_host_gate_is_the_platform_and_never_shells_out_to_nvidia_smi() -> None:
    assert not host_refusals("metal", None, platform="darwin")
    assert "unsupported_platform" in _codes(host_refusals("metal", None, platform="linux"))


def test_an_unknown_backend_is_refused_with_the_accepted_set() -> None:
    refusals = host_refusals("rocm", None, platform="linux")
    assert _codes(refusals) == {"unknown_backend"}
    assert "auto" in refusals[0].supported


# ── the nvidia-smi probe itself ──────────────────────────────────────────────


class _FakeCompleted:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_probe_parses_nvidia_smi_csv_rows() -> None:
    calls: list[list[str]] = []

    def runner(argv, **kwargs):
        calls.append(list(argv))
        return _FakeCompleted(0, "NVIDIA H200, 580.173.02, 9.0\nNVIDIA L4, 580.173.02, 8.9\n")

    facts = probe_nvidia_host(smi_path="/usr/bin/nvidia-smi", runner=runner)
    assert facts.probed is True
    assert facts.driver_version == "580.173.02"
    assert facts.driver_version_tuple == (580, 173, 2)
    assert facts.device_count == 2
    assert facts.device_names == ("NVIDIA H200", "NVIDIA L4")
    assert facts.compute_capabilities == ((9, 0), (8, 9))
    assert calls and "--query-gpu=name,driver_version,compute_cap" in calls[0]


def test_probe_reads_a_driver_with_zero_devices_as_a_fact() -> None:
    facts = probe_nvidia_host(
        smi_path="/usr/bin/nvidia-smi", runner=lambda *a, **k: _FakeCompleted(0, "\n")
    )
    assert facts.probed is True
    assert facts.device_count == 0
    assert _codes(host_refusals("cuda", facts, platform="linux")) == {"no_nvidia_gpu"}


def test_probe_falls_back_to_proc_driver_version_on_a_headless_install(tmp_path: Path) -> None:
    proc_file = tmp_path / "version"
    proc_file.write_text(
        "NVRM version: NVIDIA UNIX Open Kernel Module for x86_64  580.173.02\n"
        "GCC version:  gcc version 11.4.0\n",
        encoding="utf-8",
    )

    def missing(argv, **kwargs):
        raise FileNotFoundError(2, "No such file or directory")

    facts = probe_nvidia_host(
        smi_path="/usr/bin/nvidia-smi", runner=missing, proc_version_path=proc_file
    )
    assert facts.probed is True
    assert facts.driver_version == "580.173.02"
    assert facts.device_count is None
    assert facts.probe_error and "failed" in facts.probe_error


def test_a_failing_probe_is_reported_as_unknown_not_as_no_gpu(tmp_path: Path) -> None:
    facts = probe_nvidia_host(
        smi_path="/usr/bin/nvidia-smi",
        runner=lambda *a, **k: _FakeCompleted(
            6, "", "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver."
        ),
        proc_version_path=tmp_path / "absent",
    )
    assert facts.probed is False
    assert facts.probe_error and "exit 6" in facts.probe_error
    assert _codes(host_refusals("cuda", facts, platform="linux")) == {"no_nvidia_gpu"}


def test_probe_without_any_driver_interface_reports_absent(tmp_path: Path, monkeypatch) -> None:
    """No nvidia-smi on PATH and no /proc entry: the probe reports ABSENT (not a
    crash, and not a fabricated device list)."""
    monkeypatch.delenv("ALGENTA_NVIDIA_SMI", raising=False)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    facts = probe_nvidia_host(proc_version_path=tmp_path / "absent")
    assert facts.probed is False
    assert facts.probe_error
    assert facts.device_count is None


# ── model facts: the capability table's own verdict, un-reworded ─────────────


def test_unsupported_head_dim_refuses_with_the_conformance_wording(tmp_path: Path) -> None:
    checkpoint = _checkpoint(tmp_path, head_dim=96)
    refusals = model_refusals("cuda", checkpoint)
    assert _codes(refusals) == {"unsupported_model"}
    message = refusals[0].message()
    assert "head_dim=96" in message
    assert "{32, 64, 128, 256}" in message


def test_a_family_the_backend_does_not_run_is_refused_by_fact(tmp_path: Path) -> None:
    """Gemma 3 is a CUDA-lane kernel set; on metal it is refused by the declared
    family fact, and the refusal is the table's, not a name match invented here."""
    gemma3 = _checkpoint(
        tmp_path,
        model_type="gemma3_text",
        activation="gelu_pytorch_tanh",
        sliding_window=1024,
        head_dim=256,
        num_attention_heads=8,
        num_key_value_heads=4,
        hidden_size=2048,
        intermediate_size=8192,
    )
    cuda_codes = _codes(model_refusals("cuda", gemma3))
    metal_refusals = model_refusals("metal", gemma3)
    assert "unsupported_model" in _codes(metal_refusals)
    assert any(
        "family" in refusal.fact or "activation" in refusal.fact for refusal in metal_refusals
    )
    assert cuda_codes != _codes(metal_refusals) or metal_refusals


def test_missing_config_is_a_checkpoint_refusal_not_a_crash(tmp_path: Path) -> None:
    refusals = model_refusals("cuda", tmp_path / "does-not-exist")
    assert _codes(refusals) == {"checkpoint_not_found"}


def test_config_only_checkpoint_is_pending_the_probe_until_allowed(tmp_path: Path) -> None:
    checkpoint = _checkpoint(tmp_path)
    gate = gate_serve("cuda", model=checkpoint, platform="linux", host=_GOOD_HOST, engine=None)
    assert _codes(gate.refusals) == {"model_facts_unprobed"}
    allowed = gate_serve(
        "cuda",
        model=checkpoint,
        platform="linux",
        host=_GOOD_HOST,
        engine=None,
        allow_unprobed=True,
    )
    assert allowed.accepted
    assert allowed.resolved_backend == "cuda"


def test_gate_collects_every_refusal_instead_of_only_the_first(tmp_path: Path) -> None:
    checkpoint = _checkpoint(tmp_path, head_dim=96)
    gate = gate_serve(
        "cuda", model=checkpoint, platform="darwin", host=NvidiaHostFacts(probed=False), engine=None
    )
    codes = _codes(gate.refusals)
    assert {"unsupported_platform", "no_nvidia_gpu", "unsupported_model"} <= codes
    assert gate.accepted is False


# ── engine facts ─────────────────────────────────────────────────────────────


def test_an_unresolved_engine_binary_refuses_and_prints_the_whole_chain(tmp_path: Path) -> None:
    resolution = resolve_engine("cuda", environ={})
    assert resolution.path is None
    from algenta.serve.engine import engine_refusals

    refusals = engine_refusals("cuda", resolution=resolution)
    assert _codes(refusals) == {"cuda_engine_binary_unresolved"}
    message = refusals[0].message()
    for expected in ("ALGENTA_CUDA_ENGINE", "ALGENTA_CONFORM_CUDA_DRIVER", "BENCH_BIN_DIR"):
        assert expected in message


def test_engine_resolution_honours_the_explicit_override(tmp_path: Path) -> None:
    binary = _engine_binary(tmp_path, "#!/bin/sh\nexit 0\n")
    resolution = resolve_engine("cuda", override=binary, environ={})
    assert resolution.path == binary
    assert resolution.source == "--engine-binary"


def test_engine_resolution_honours_the_legacy_conform_env_name(tmp_path: Path) -> None:
    binary = _engine_binary(tmp_path, "#!/bin/sh\nexit 0\n")
    resolution = resolve_engine("cuda", environ={"ALGENTA_CONFORM_CUDA_DRIVER": str(binary)})
    assert resolution.path == binary
    assert resolution.source == "$ALGENTA_CONFORM_CUDA_DRIVER"


def test_engine_resolution_finds_the_binary_in_bench_bin_dir(tmp_path: Path) -> None:
    binary = _engine_binary(tmp_path, "#!/bin/sh\nexit 0\n")
    resolution = resolve_engine("cuda", environ={"BENCH_BIN_DIR": str(binary.parent)})
    assert resolution.path == binary


def test_a_non_executable_override_is_refused_by_name(tmp_path: Path) -> None:
    path = tmp_path / CUDA_ENGINE_BINARY_NAME
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o644)
    from algenta.serve.engine import engine_refusals

    resolution = resolve_engine("cuda", override=path, environ={})
    assert resolution.path is None
    assert _codes(engine_refusals("cuda", resolution=resolution)) == {
        "cuda_engine_binary_unresolved"
    }


# ── the no-silent-fallback invariant ─────────────────────────────────────────


def test_explicit_cuda_never_resolves_to_metal(tmp_path: Path) -> None:
    checkpoint = _checkpoint(tmp_path)
    gate = gate_serve(
        "cuda",
        model=checkpoint,
        platform="darwin",
        host=NvidiaHostFacts(probed=False),
        engine=None,
        allow_unprobed=True,
    )
    assert gate.accepted is False
    assert gate.resolved_backend == "cuda"
    assert gate.backend == "cuda"


def test_auto_detection_picks_the_host_backend_and_reports_the_loser() -> None:
    resolved, report = detect_backend(platform="linux", host=_GOOD_HOST)
    assert resolved == "cuda"
    assert "metal" in report and _codes(report["metal"]) == {"unsupported_platform"}

    resolved, report = detect_backend(platform="darwin", host=NvidiaHostFacts(probed=False))
    assert resolved == "metal"
    assert "cuda" in report and report["cuda"]


def test_auto_with_no_viable_backend_refuses_and_names_every_candidate() -> None:
    gate = gate_serve("auto", platform="plan9", host=NvidiaHostFacts(probed=False), engine=None)
    assert gate.accepted is False
    assert gate.resolved_backend is None
    assert "no_supported_backend" in _codes(gate.refusals)
    message = gate.refusals[0].message()
    assert "cuda" in message and "metal" in message


def test_an_unknown_backend_value_is_refused_with_the_accepted_set() -> None:
    gate = gate_serve("tpu", platform="linux", host=_GOOD_HOST, engine=None)
    assert _codes(gate.refusals) == {"unknown_backend"}
    assert gate.resolved_backend is None


# ── the launch plan and the engine's output contract ─────────────────────────


def test_dry_run_declares_the_argv_and_touches_nothing(tmp_path: Path) -> None:
    checkpoint = _checkpoint(tmp_path)
    binary = _engine_binary(tmp_path, "#!/bin/sh\nexit 0\n")
    request = ServeRequest(
        model=checkpoint,
        backend="cuda",
        prompt_token_ids=(1, 2, 3),
        max_new_tokens=7,
        converted_dir=tmp_path / "converted",
        allow_unprobed=True,
    )
    plan = plan_serve(
        request,
        platform="linux",
        host=_GOOD_HOST,
        environ={"ALGENTA_CUDA_ENGINE": str(binary)},
    )
    assert plan.accepted
    assert plan.launch is not None
    assert plan.launch.kind == "subprocess"
    assert plan.launch.argv == (str(binary), str(tmp_path / "converted"), "--max-new", "7")
    assert plan.prompt_token_count == 3
    # A plan is a declaration: nothing was converted and nothing was spawned.
    assert not (tmp_path / "converted").exists()

    outcome = serve(
        request,
        platform="linux",
        host=_GOOD_HOST,
        environ={"ALGENTA_CUDA_ENGINE": str(binary)},
        dry_run=True,
    )
    assert outcome.plan.accepted
    assert not (tmp_path / "converted").exists()


def test_engine_output_contract_is_parsed_from_the_declared_lines() -> None:
    result = parse_engine_output(
        0,
        "conform_generate_cuda: d_model=1024 n_layers=4\n"
        "CONFORM_TOKENS: 785 6722 315\n"
        "CONFORM_TIMING: n_prompt=2 n_gen=3 prefill_ms=12.5 decode_tok_s=640.2\n",
        "",
    )
    assert result.ok
    assert result.token_ids == (785, 6722, 315)
    assert result.timing == {
        "n_prompt": 2.0,
        "n_gen": 3.0,
        "prefill_ms": 12.5,
        "decode_tok_s": 640.2,
    }


def test_engine_timing_tolerates_a_space_around_the_equals() -> None:
    result = parse_engine_output(
        0, "CONFORM_TOKENS: 1\nCONFORM_TIMING: prefill_ms= 12.5  decode_tok_s= 640.2\n", ""
    )
    assert result.timing == {"prefill_ms": 12.5, "decode_tok_s": 640.2}


@pytest.mark.parametrize(
    ("stdout", "code", "status"),
    [
        (
            "conform_generate_cuda: built without -D ALGENTA_GPU -D ALGENTA_CUDA\n",
            "engine_binary_not_cuda_build",
            None,
        ),
        (
            "conform_generate_cuda: no accelerator on this host\n",
            "no_nvidia_gpu",
            None,
        ),
        (
            "conform_generate_cuda: REFUSED by preflight: resident_err_context\n"
            "CONFORM_REFUSED: resident_err_context\n",
            "engine_refused_model",
            "resident_err_context",
        ),
    ],
)
def test_the_engine_own_refusals_become_typed_refusals(stdout: str, code: str, status) -> None:
    result = parse_engine_output(4 if status is None else 3, stdout, "")
    assert result.ok is False
    assert result.refusal is not None
    assert result.refusal.code == code
    assert result.refused_status == status


def test_a_non_zero_exit_with_no_tokens_is_still_a_typed_refusal() -> None:
    result = parse_engine_output(139, "", "segmentation fault")
    assert result.refusal is not None
    assert result.refusal.code == "engine_launch_failed"
    assert "139" in result.refusal.message()


def test_exit_zero_without_tokens_is_refused_not_reported_as_an_empty_completion() -> None:
    result = parse_engine_output(0, "conform_generate_cuda: d_model=1024\n", "")
    assert result.ok is False
    assert result.refusal is not None
    assert result.refusal.code == "engine_produced_no_tokens"


def test_a_serve_launches_the_engine_and_returns_its_tokens(tmp_path: Path) -> None:
    checkpoint = _checkpoint(tmp_path)
    converted = _converted(tmp_path)
    binary = _engine_binary(
        tmp_path,
        "#!/bin/sh\n"
        'echo "CONFORM_TOKENS: 785 6722 315"\n'
        'echo "CONFORM_TIMING: n_prompt=2 n_gen=3 prefill_ms=12.5 decode_tok_s=640.2"\n',
    )
    request = ServeRequest(
        model=checkpoint,
        backend="cuda",
        prompt_token_ids=(11, 22, 33),
        max_new_tokens=3,
        converted_dir=converted,
        allow_unprobed=True,
    )
    outcome = serve(
        request,
        platform="linux",
        host=_GOOD_HOST,
        environ={"ALGENTA_CUDA_ENGINE": str(binary)},
    )
    assert outcome.ok, outcome.as_dict()
    assert outcome.token_ids == (785, 6722, 315)
    assert outcome.timing["decode_tok_s"] == 640.2
    assert outcome.text is None  # no tokenizer was loaded: ids are the contract


def test_the_prompt_is_stamped_into_the_manifest_and_the_blob_is_left_alone(tmp_path: Path) -> None:
    """One conversion per checkpoint, one manifest re-stamp per request: the blob
    is prompt-independent, so re-converting a 27B checkpoint per prompt would be
    unusable — and serving the FIRST prompt's ids for the second request would be
    silently wrong."""
    checkpoint = _checkpoint(tmp_path)
    converted = _converted(tmp_path, prompt=(1, 2))
    blob_before = (converted / "weights.blob").read_bytes()
    binary = _engine_binary(tmp_path, "#!/bin/sh\necho 'CONFORM_TOKENS: 9'\n")
    request = ServeRequest(
        model=checkpoint,
        backend="cuda",
        prompt_token_ids=(11, 22, 33),
        max_new_tokens=1,
        converted_dir=converted,
        allow_unprobed=True,
    )
    outcome = serve(
        request,
        platform="linux",
        host=_GOOD_HOST,
        environ={"ALGENTA_CUDA_ENGINE": str(binary)},
    )
    assert outcome.ok, outcome.as_dict()
    manifest = json.loads((converted / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["input_ids"] == [11, 22, 33]
    assert manifest["config"]["n_tokens"] == 3
    # Every non-prompt fact survives the re-stamp verbatim.
    assert manifest["config"]["hidden_size"] == 1024
    assert manifest["tensors"] == {"token_embd.weight": {"offset": 0, "n_elements": 4}}
    assert (converted / "weights.blob").read_bytes() == blob_before


def test_a_refused_request_never_spawns_the_engine(tmp_path: Path) -> None:
    checkpoint = _checkpoint(tmp_path, head_dim=96)
    spawned: list[list[str]] = []
    binary = _engine_binary(tmp_path, "#!/bin/sh\necho 'CONFORM_TOKENS: 1'\n")

    def runner(argv, **kwargs):
        spawned.append(list(argv))
        return _FakeCompleted(0, "CONFORM_TOKENS: 1\n")

    outcome = serve(
        ServeRequest(
            model=checkpoint,
            backend="cuda",
            prompt_token_ids=(1,),
            converted_dir=_converted(tmp_path),
            allow_unprobed=True,
        ),
        platform="linux",
        host=_GOOD_HOST,
        environ={"ALGENTA_CUDA_ENGINE": str(binary)},
        runner=runner,
    )
    assert outcome.ok is False
    assert "unsupported_model" in _codes(outcome.plan.gate.refusals)
    assert spawned == []


def test_request_validation_rejects_an_ambiguous_prompt(tmp_path: Path) -> None:
    checkpoint = _checkpoint(tmp_path)
    with pytest.raises(ServeError) as both:
        plan_serve(
            ServeRequest(
                model=checkpoint, prompt_text="hi", prompt_token_ids=(1,), allow_unprobed=True
            ),
            platform="linux",
            host=_GOOD_HOST,
        )
    assert both.value.code == "invalid_arguments"
    with pytest.raises(ServeError) as neither:
        plan_serve(
            ServeRequest(model=checkpoint, allow_unprobed=True),
            platform="linux",
            host=_GOOD_HOST,
        )
    assert neither.value.code == "invalid_arguments"


def test_request_validation_rejects_a_non_positive_token_budget(tmp_path: Path) -> None:
    checkpoint = _checkpoint(tmp_path)
    with pytest.raises(ServeError) as excinfo:
        plan_serve(
            ServeRequest(
                model=checkpoint,
                prompt_token_ids=(1,),
                max_new_tokens=0,
                allow_unprobed=True,
            ),
            platform="linux",
            host=_GOOD_HOST,
        )
    assert excinfo.value.code == "invalid_arguments"


# ── the CLI: grammar, exit codes, machine-readable output ────────────────────


def test_cli_backends_prints_the_declared_requirements() -> None:
    assert serve_cli.main(["--backends"]) == serve_cli.EXIT_OK


def test_cli_rejects_an_unknown_backend_value_at_the_grammar_level() -> None:
    with pytest.raises(SystemExit) as excinfo:
        serve_cli.main(["--backend", "tpu", "--model", "/tmp/x", "--prompt", "hi"])
    assert excinfo.value.code == 2  # argparse's own usage-error exit


def test_cli_requires_exactly_one_prompt_source(tmp_path: Path, capsys) -> None:
    checkpoint = _checkpoint(tmp_path)
    code = serve_cli.main(["--model", str(checkpoint), "--prompt", "a", "--prompt-file", "b"])
    assert code == serve_cli.EXIT_ERROR
    assert "exactly one of --prompt" in capsys.readouterr().err


def test_cli_requires_a_model(tmp_path: Path, capsys) -> None:
    assert serve_cli.main(["--prompt", "hi"]) == serve_cli.EXIT_ERROR
    assert "--model is required" in capsys.readouterr().err


def test_cli_reads_the_prompt_from_a_file(tmp_path: Path) -> None:
    prompt_file = tmp_path / "p.txt"
    prompt_file.write_text("The capital of France is", encoding="utf-8")
    request = serve_cli._build_request(
        serve_cli.build_parser().parse_args(
            ["--model", "/tmp/x", "--prompt-file", str(prompt_file)]
        )
    )
    assert request.prompt_text == "The capital of France is"


def test_cli_parses_token_ids_and_rejects_junk(tmp_path: Path) -> None:
    args = serve_cli.build_parser().parse_args(
        ["--model", "/tmp/x", "--prompt-token-ids", "1, 2,3"]
    )
    request = serve_cli._build_request(args)
    assert request.prompt_token_ids == (1, 2, 3)
    with pytest.raises(ServeError):
        serve_cli._build_request(
            serve_cli.build_parser().parse_args(
                ["--model", "/tmp/x", "--prompt-token-ids", "1,two"]
            )
        )


def test_cli_refusal_exits_two_and_is_machine_readable(tmp_path: Path, capsys) -> None:
    """Deterministic on ANY host: a checkpoint that does not exist is refused by
    the model gate whatever the platform, and the refusal is carried in --json."""
    missing = tmp_path / "no-such-checkpoint"
    code = serve_cli.main(
        ["--backend", "cuda", "--model", str(missing), "--prompt", "hi", "--json"]
    )
    assert code == serve_cli.EXIT_REFUSED
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    codes = {refusal["code"] for refusal in payload["plan"]["gate"]["refusals"]}
    assert "checkpoint_not_found" in codes
    # An explicit backend is never quietly re-pointed at another one.
    assert payload["plan"]["gate"]["resolved_backend"] == "cuda"
    assert payload["plan"]["gate"]["backend"] == "cuda"
    # --json is the machine-readable channel: the report is on stdout, not prose
    # on stderr for a caller to scrape.
    assert payload["refusal"]["code"] in codes


def test_cli_refusal_is_loud_on_stderr_without_json(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "no-such-checkpoint"
    code = serve_cli.main(["--backend", "cuda", "--model", str(missing), "--prompt", "hi"])
    assert code == serve_cli.EXIT_REFUSED
    captured = capsys.readouterr()
    assert "REFUSED:" in captured.err
    assert "checkpoint_not_found" in captured.err
    assert "backend: cuda (explicit)" in captured.out


def test_cli_dry_run_does_not_launch_and_says_so(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "no-such-checkpoint"
    code = serve_cli.main(
        ["--backend", "cuda", "--model", str(missing), "--prompt", "hi", "--dry-run"]
    )
    assert code == serve_cli.EXIT_REFUSED
    captured = capsys.readouterr()
    assert "REFUSED:" in captured.err
    assert "dry-run" not in captured.out  # a refused plan never reaches the dry-run line


def test_cli_serves_the_cuda_engine_when_the_host_facts_are_met(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """The accepted path, end to end through the CLI, with the host facts stated
    instead of owned: `sys.platform` and the NVIDIA probe are the only two things
    standing between a CPU test box and a real H200."""
    checkpoint = _checkpoint(tmp_path)
    converted = _converted(tmp_path)
    binary = _engine_binary(
        tmp_path,
        "#!/bin/sh\necho 'CONFORM_TOKENS: 785 6722'\n"
        "echo 'CONFORM_TIMING: prefill_ms=12.5 decode_tok_s=640.2'\n",
    )
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("ALGENTA_CUDA_ENGINE", str(binary))
    import algenta.serve.gating as gating

    monkeypatch.setattr(gating, "probe_nvidia_host", lambda **kwargs: _GOOD_HOST)

    code = serve_cli.main(
        [
            "--backend",
            "cuda",
            "--model",
            str(checkpoint),
            "--prompt-token-ids",
            "1,2",
            "--max-new-tokens",
            "2",
            "--converted-dir",
            str(converted),
            "--allow-unprobed",
        ]
    )
    assert code == serve_cli.EXIT_OK, capsys.readouterr()
    out = capsys.readouterr().out
    assert "backend: cuda (explicit)" in out
    assert "tokens:  2 generated" in out
    assert "decode_tok_s=640.2" in out


def test_cli_exit_three_is_reserved_for_the_unprobed_verdict_alone(
    tmp_path: Path, monkeypatch
) -> None:
    """3 means exactly what the conformance CLI's 3 means: supported, but the
    tensor-level facts were never probed. Any other refusal present makes it a 2."""
    checkpoint = _checkpoint(tmp_path)
    binary = _engine_binary(tmp_path, "#!/bin/sh\necho 'CONFORM_TOKENS: 1'\n")
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("ALGENTA_CUDA_ENGINE", str(binary))
    import algenta.serve.gating as gating

    monkeypatch.setattr(gating, "probe_nvidia_host", lambda **kwargs: _GOOD_HOST)

    argv = [
        "--backend",
        "cuda",
        "--model",
        str(checkpoint),
        "--prompt-token-ids",
        "1",
        "--converted-dir",
        str(_converted(tmp_path)),
    ]
    assert serve_cli.main(argv) == serve_cli.EXIT_PENDING
    assert serve_cli.main([*argv, "--allow-unprobed"]) == serve_cli.EXIT_OK


def test_cli_help_names_the_gating_contract() -> None:
    parser = serve_cli.build_parser()
    text = parser.format_help()
    for expected in ("--backend", "--dry-run", "--json", "--engine-binary", "--allow-unprobed"):
        assert expected in text
    assert "never fall back" in text.lower() or "refuses" in text.lower()


def test_serve_command_is_wired_into_the_algenta_cli() -> None:
    """The entry point has to be reachable from the shipped console script, not
    only from `python -m algenta.serve.cli`."""
    from algenta import cli as algenta_cli

    assert hasattr(algenta_cli, "cmd_serve")
    source = (Path(algenta_cli.__file__)).read_text(encoding="utf-8")
    assert 'elif cmd == "serve":' in source


def test_serve_is_reachable_as_a_subprocess_through_the_console_entry() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(_ALGENTA), str(ROOT)])
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "algenta.cli", "serve", "--backends"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "published backends" in proc.stdout
    assert "cuda" in proc.stdout


def test_outcome_as_dict_is_json_serialisable_and_carries_the_gate(tmp_path: Path) -> None:
    checkpoint = _checkpoint(tmp_path, head_dim=96)
    plan = plan_serve(
        ServeRequest(model=checkpoint, backend="cuda", prompt_token_ids=(1,), allow_unprobed=True),
        platform="linux",
        host=_GOOD_HOST,
    )
    outcome = ServeOutcome(plan=plan)
    payload = json.loads(json.dumps(outcome.as_dict(), default=str))
    assert payload["ok"] is False
    codes = {refusal["code"] for refusal in payload["plan"]["gate"]["refusals"]}
    assert "unsupported_model" in codes
