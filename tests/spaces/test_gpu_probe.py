"""apps/spaces/gpu-probe — the GPU probe Space, tested without a GPU.

Everything the Space decides on the T4 is a pure helper in `probe_core.py`: the phase machine,
the driver and compute-capability gates, the kernel revision/variant/tier/library gates, the
parity comparison, the timings and the side-by-side lanes. Those run here on the build Mac.
The orchestrator and the FastAPI routes run against a fake stage runner that answers with the
run-12 artifact's data (`docs/hf-kernels/evidence/artifacts/gpu-probe-run12-t4-small-qwen3-1p7b.json`)
and replay the run-13 record (`gpu-probe-run13-*.json`, the health-body shape), so the page and
`run.json` are checked against the real runs that exist. The baseline stage (transformers on the
GPU) has no real run yet: its report is a shape-only fixture here, and no figure from it is
asserted as a measurement. torch, kernels, transformers and algenta are never imported.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path
from types import ModuleType

import copy_lint
import pytest
from _rules import _assert_clean_copy
from manifest import load_manifest

REPO = Path(__file__).resolve().parents[2]
PROBE_DIR = REPO / "apps" / "spaces" / "gpu-probe"
ARTIFACT = REPO / "docs/hf-kernels/evidence/artifacts/gpu-probe-run12-t4-small-qwen3-1p7b.json"
ARTIFACT_RUN13 = (
    REPO / "docs/hf-kernels/evidence/artifacts/gpu-probe-run13-t4-small-qwen3-1p7b.json"
)
#: The step times of the run-13 rerun (2026-09-24 18:19Z, Tesla T4), as the page printed them.
RUN13_STEP_MS = [0.1, 194.7, 26.7, 26.8, 26.9, 26.9, 27.0, 27.0]
RUN13_OPEN_S = 42.64
FLAGSHIP_DIR = REPO / "apps" / "spaces" / "algenta"

# Appended, not inserted: the flagship's tests import their own `app` and `hf_ua_shim` from
# apps/spaces/algenta at sys.path[0]; the probe's modules with unique names (probe, probe_core,
# probe_config) resolve from the end of the path, and its `app` is loaded by file under an alias.
if str(PROBE_DIR) not in sys.path:
    sys.path.append(str(PROBE_DIR))

cfg = importlib.import_module("probe_config")
core = importlib.import_module("probe_core")
probe = importlib.import_module("probe")


def _load_by_file(alias: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(alias, PROBE_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


app = _load_by_file("gpu_probe_app", "app.py")


@pytest.fixture(scope="module")
def artifact() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def artifact13() -> dict:
    return json.loads(ARTIFACT_RUN13.read_text(encoding="utf-8"))


def _fixture_baseline(tokens: list[int], *, float16_code: str | None = None) -> dict:
    """The baseline stage's report in shape only. Every figure here is invented so the
    orchestrator, the `baseline` block and the page can be exercised without a GPU; none is a
    measurement and none is asserted as one. `float16_code` makes that lane fail closed."""

    def lane(dtype: str, load_s: float, ttft_s: float, step: float, taken: int) -> dict:
        steps = [ttft_s * 1000.0, *([step] * 7)]
        return {
            "ok": True,
            "dtype": dtype,
            "torch_dtype": f"torch.{dtype}",
            "model_dtype": f"torch.{dtype}",
            "load_s": load_s,
            "ttft_s": ttft_s,
            "step_ms": steps,
            "generate_s": round(sum(steps) / 1000.0, 3),
            "tokens": list(tokens),
            "decoded": cfg.RUN12_DECODED,
            "stopped_on_eos": False,
            "eos_token_id": [151645, 151643],
            "gpu_free_bytes_before": 15_000_000_000,
            "gpu_free_bytes_after_load": 15_000_000_000 - taken,
            "device_taken_bytes": taken,
            "weights_allocated_bytes": taken,
            "peak_allocated_bytes": taken + 300_000_000,
            "peak_reserved_bytes": taken + 500_000_000,
            "same_tokens_as_warmup": True,
            "warmup": {
                "excluded": True,
                "tokens": list(tokens),
                "step_ms": [ttft_s * 3000.0, *([step * 2] * 7)],
                "ttft_s": ttft_s * 3,
                "generate_s": 1.0,
            },
        }

    lanes = {
        "float32": lane("float32", 9.0, 0.09, 40.0, 7_000_000_000),
        "float16": lane("float16", 6.0, 0.05, 30.0, 3_500_000_000),
    }
    if float16_code:
        lanes["float16"] = {
            "ok": False,
            "dtype": "float16",
            "code": float16_code,
            "message": "OutOfMemoryError: CUDA out of memory",
        }
    return {
        "method": "transformers generate on CUDA (fixture)",
        "device_name": "Tesla T4",
        "compute_capability": [7, 5],
        "torch": "2.9.1+cu128",
        "cuda": "12.8",
        "transformers": "5.17.0",
        "prompt": cfg.PROMPT,
        "prompt_ids": list(cfg.RUN12_PROMPT_IDS),
        "n_prompt": len(cfg.RUN12_PROMPT_IDS),
        "max_new_tokens": cfg.MAX_NEW_TOKENS,
        "dtypes": list(cfg.BASELINE_DTYPES),
        "gpu_total_bytes": 15_828_320_256,
        "gpu_free_bytes_start": 15_000_000_000,
        "gpu_free_bytes_end": 15_000_000_000,
        "lanes": lanes,
        "max_rss_mib": 1.0,
    }


def _run12_stage_data(artifact: dict) -> dict[str, dict]:
    """The run-12 artifact's stage outputs in the shape `probe.py` reports today."""
    driver = artifact["steps"]["driver"]["data"]
    gpu = artifact["steps"]["gpu"]["data"]
    convert = artifact["steps"]["convert"]["data"]
    reference = artifact["steps"]["reference"]["data"]
    build_kernel = artifact["image"]["build_facts"]["kernel"]
    kernel = {
        "repo": build_kernel["repo"],
        "revision": build_kernel["v1_sha"],
        "variant": gpu["kernel"]["variant"],
        "resident_stage_tier": build_kernel["resident_stage_tier"],
        "cuda_targets": build_kernel["cuda_targets"],
        "cuda_libraries": build_kernel["cuda_libraries"],
        "selected_library": gpu["kernel"]["selected_library"],
        "mojo_version": build_kernel["mojo_version"],
        "get_kernel_s": gpu["kernel"]["get_kernel_s"],
        "native_init_s": gpu["kernel"]["native_init_s"],
        "compute_capability": gpu["torch"]["compute_capability"],
    }
    return {
        "driver": {
            **core.driver_gate(driver["nvidia_smi"]["driver_version"]),
            "nvidia_smi": driver["nvidia_smi"],
            "device_name": driver["libcuda"]["device_name"],
            "compute_capability": driver["libcuda"]["compute_capability"],
            "cu_driver_get_version": driver["libcuda"]["cu_driver_get_version"],
            "cuda_driver_api": driver["libcuda"]["cuda_driver_api"],
            "libcuda_mapped_paths": driver["libcuda"]["mapped_paths"],
            "torch": gpu["torch"],
        },
        "kernel": kernel,
        "convert": {
            "reused": convert["reused"],
            "wall_s": convert["wall_s"],
            "blob_bytes": convert["blob_bytes"],
            "weights_dtype": convert["weights_dtype"],
            "prompt_ids": artifact["prompt"]["token_ids"],
        },
        "decode": {
            **kernel,
            "prompt_ids": artifact["prompt"]["token_ids"],
            "tokens": gpu["decode"]["tokens"],
            "step_ms": gpu["decode"]["step_ms"],
            "open_s": gpu["decode"]["open_s"],
            "decoded": artifact["parity"]["native"]["decoded"],
        },
        "reference": {
            "reference": reference["reference"],
            "transformers": reference["transformers"],
            "threads": reference["threads"],
            "tokens": reference["tokens"],
            "decoded": reference["decoded"],
            "load_s": reference["load_s"],
            "generate_s": reference["generate_s"],
            "prompt_ids_agree_with_algenta_tokenizer": reference[
                "prompt_ids_agree_with_algenta_tokenizer"
            ],
        },
        "baseline": _fixture_baseline(reference["tokens"]),
    }


def _run13_stage_data(artifact13: dict, *, baseline: dict | None = None) -> dict[str, dict]:
    """The run-13 record's blocks as the stages reported them (the orchestrator's own keys
    stripped), plus a baseline report when given: run 13 predates that stage."""
    added = {"started_utc", "finished_utc", "stage_wall_s", "timings"}
    data = {
        name: {k: v for k, v in artifact13[block].items() if k not in added}
        for name, block in (
            ("driver", "driver"),
            ("kernel", "kernel"),
            ("convert", "model"),
            ("decode", "decode"),
            ("reference", "reference"),
        )
    }
    if baseline is not None:
        data["baseline"] = baseline
    return data


def _fake_runner(stage_data: dict[str, dict], failures: dict[str, dict] | None = None):
    """A stage runner that answers from data instead of a subprocess; `failures` override."""
    calls: list[str] = []

    def runner(name: str, timeout_s: float) -> app.StageOutcome:
        calls.append(name)
        assert timeout_s > 0
        if failures and name in failures:
            spec = failures[name]
            return app.StageOutcome(
                stdout=spec.get("stdout", ""),
                stderr=spec.get("stderr", ""),
                returncode=spec.get("returncode", 1),
                timed_out=spec.get("timed_out", False),
                wall_s=0.5,
            )
        payload = {"ok": True, "stage": name, **stage_data[name]}
        return app.StageOutcome(
            stdout="INFO noise line\n" + json.dumps(payload) + "\n",
            stderr="log line\n",
            returncode=0,
            timed_out=False,
            wall_s=1.5,
        )

    runner.calls = calls  # type: ignore[attr-defined]
    return runner


# --- the pins are the artifact's facts ------------------------------------------------------


def test_pins_match_the_run12_artifact(artifact: dict) -> None:
    plan = artifact["plan"]
    build_kernel = artifact["image"]["build_facts"]["kernel"]
    assert cfg.PROMPT == artifact["prompt"]["text"]
    assert list(cfg.RUN12_PROMPT_IDS) == artifact["prompt"]["token_ids"]
    assert list(cfg.RUN12_TOKENS) == artifact["parity"]["reference_tokens"]
    assert cfg.RUN12_DECODED == artifact["parity"]["reference_decoded"]
    assert cfg.MAX_NEW_TOKENS == plan["max_ctx"]["max_new_tokens"] == 8
    assert cfg.MODEL_REPO == plan["model"]["repo"]
    assert cfg.MODEL_REVISION == plan["model"]["revision"]
    assert cfg.KERNEL_REPO == plan["kernel"]["repo"]
    assert cfg.EXPECTED_VARIANT == plan["kernel"]["expected_variant"]
    assert cfg.EXPECTED_STAGE_TIER == build_kernel["resident_stage_tier"] == 6144
    assert cfg.DRIVER_FLOOR_MAJOR == plan["driver_floor"] == 580
    assert [list(c) for c in cfg.SUPPORTED_COMPUTE_CAPABILITIES] == plan[
        "supported_compute_capabilities"
    ]
    assert str(ARTIFACT.relative_to(REPO)) == cfg.RUN12_ARTIFACT
    # the revision moved past run 12's 92ef06d7 with REPUBLISH-006; the pin is today's v1
    assert cfg.KERNEL_REVISION != build_kernel["v1_sha"]
    assert core.is_sha(cfg.KERNEL_REVISION)


def test_kernel_revision_pin_is_the_flagships_frozen_sha() -> None:
    hubkernel = importlib.import_module("algenta_spaces.hubkernel")
    assert cfg.KERNEL_REVISION == hubkernel.FROZEN_CAPPED_V1_SHAS[cfg.KERNEL_REPO]


# --- phase machine ---------------------------------------------------------------------------


def test_phase_machine_runs_in_order_and_reports_status() -> None:
    m = core.PhaseMachine()
    assert m.status == core.PENDING and m.phase == "driver"
    with pytest.raises(ValueError, match="predecessors"):
        m.start("kernel")
    m.start("driver")
    assert m.status == core.RUNNING and m.phase == "driver"
    with pytest.raises(ValueError, match="only start once"):
        m.start("driver")
    m.finish("driver", {"device_name": "Tesla T4"}, wall_s=0.5234)
    assert m.records["driver"].wall_s == 0.52 and m.data("driver") == {"device_name": "Tesla T4"}
    assert m.phase == "kernel"
    for name in ("kernel", "convert", "decode", "baseline", "reference", "record"):
        m.start(name)
        m.finish(name, {})
    assert m.status == core.OK and m.phase == "done" and m.finished_utc
    snap = m.snapshot()
    assert list(snap) == list(core.PHASES)
    assert list(core.PHASES) == [
        "driver",
        "kernel",
        "convert",
        "decode",
        "baseline",
        "reference",
        "record",
    ]
    assert all(rec["status"] == core.OK for rec in snap.values())
    assert set(cfg.STAGE_TIMEOUTS_S) == set(app.STAGE_PHASES)


def test_phase_machine_failure_skips_the_rest() -> None:
    m = core.PhaseMachine()
    m.start("driver")
    m.finish("driver", {})
    m.start("kernel")
    with pytest.raises(ValueError, match="not running"):
        m.fail("driver", "x", "y")
    m.fail("kernel", "kernel_tier_mismatch", "tier 3072", wall_s=1.0)
    assert m.status == core.ERROR and m.phase == "kernel"
    assert m.failure is not None and m.failure.code == "kernel_tier_mismatch"
    for later in ("convert", "decode", "baseline", "reference", "record"):
        rec = m.records[later]
        assert rec.status == core.SKIPPED and rec.code == "upstream_failed"
        assert "kernel failed with kernel_tier_mismatch" in (rec.message or "")
    with pytest.raises(ValueError, match="cannot start"):
        m.start("convert")
    with pytest.raises(ValueError, match="unknown phase"):
        m.start("nope")
    with pytest.raises(ValueError, match="distinct"):
        core.PhaseMachine(["a", "a"])


def test_baseline_phase_failure_is_soft_and_the_run_goes_on() -> None:
    """The comparison beside the verdict is not the verdict: its failure is on its own record,
    `reference` and `record` still run, and the machine ends `ok` with no top-level failure."""
    assert core.SOFT_PHASES == frozenset({"baseline"})
    m = core.PhaseMachine()
    for name in ("driver", "kernel", "convert", "decode"):
        m.start(name)
        m.finish(name, {})
    m.start("baseline")
    m.fail("baseline", "stage_crashed", "signal 11", wall_s=2.0)
    assert m.records["baseline"].status == core.ERROR
    assert m.records["reference"].status == core.PENDING, "nothing was skipped"
    assert m.status == core.RUNNING and m.phase == "reference" and m.failure is None
    assert m.finished_utc is None
    for name in ("reference", "record"):
        m.start(name)
        m.finish(name, {})
    assert m.status == core.OK and m.phase == "done" and m.failure is None
    # a phase that stops the run still does, whatever the soft one did
    n = core.PhaseMachine()
    for name in ("driver", "kernel", "convert", "decode", "baseline"):
        n.start(name)
        n.finish(name, {})
    n.start("reference")
    n.fail("reference", "RuntimeError", "boom")
    assert n.status == core.ERROR and n.failure is not None and n.failure.name == "reference"
    assert n.records["record"].status == core.SKIPPED


# --- gates -----------------------------------------------------------------------------------


def test_driver_gate_accepts_580_and_refuses_below() -> None:
    ok = core.driver_gate("580.178.04")
    assert ok == {
        "driver_version": "580.178.4",
        "base_driver_major": 580,
        "driver_floor": 580,
        "meets_driver_floor": True,
    }
    assert core.parse_driver_version(
        "NVRM version: NVIDIA UNIX x86_64 Kernel Module  580.178.04"
    ) == (
        580,
        178,
        4,
    )
    with pytest.raises(core.ProbeError) as exc:
        core.driver_gate("570.124.06")
    assert exc.value.code == "driver_below_floor"
    assert exc.value.details == {"driver_version": "570.124.06", "driver_floor": 580}
    with pytest.raises(core.ProbeError) as exc:
        core.driver_gate("")
    assert exc.value.code == "driver_version_unreadable"
    assert exc.value.as_dict()["code"] == "driver_version_unreadable"


def test_compute_capability_gate() -> None:
    assert core.compute_capability_gate([7, 5]) == (7, 5)
    assert core.compute_capability_gate((8, 9)) == (8, 9)
    assert core.compute_capability_gate((8, 6)) == (8, 6)  # PTX forward compatibility
    with pytest.raises(core.ProbeError) as exc:
        core.compute_capability_gate((6, 1))
    assert exc.value.code == "compute_capability_unsupported"
    with pytest.raises(core.ProbeError) as exc:
        core.compute_capability_gate(("x",))
    assert exc.value.code == "compute_capability_unreadable"


def test_parse_nvidia_smi_row() -> None:
    fields = probe.NVIDIA_SMI_FIELDS
    row = "Tesla T4, 580.178.04, 7.5, 15360 MiB"
    assert core.parse_nvidia_smi(row, fields) == {
        "name": "Tesla T4",
        "driver_version": "580.178.04",
        "compute_cap": "7.5",
        "memory.total": "15360 MiB",
    }
    with pytest.raises(core.ProbeError) as exc:
        core.parse_nvidia_smi("No devices were found", fields)
    assert exc.value.code == "nvidia_smi_unreadable"


def test_revision_and_variant_gates_read_the_snapshot_path() -> None:
    path = (
        f"/home/user/hf/hub/kernels--thyn-ai--algenta-llm/snapshots/{cfg.KERNEL_REVISION}"
        f"/build/{cfg.EXPECTED_VARIANT}/__init__.py"
    )
    assert core.revision_gate(path) == cfg.KERNEL_REVISION
    assert core.variant_gate(path) == cfg.EXPECTED_VARIANT
    other = path.replace(cfg.KERNEL_REVISION, "92ef06d7b01116a70d8a8a6179c492aac5462146")
    with pytest.raises(core.ProbeError) as exc:
        core.revision_gate(other)
    assert exc.value.code == "kernel_revision_mismatch"
    assert exc.value.details["loaded"].startswith("92ef06d7")
    with pytest.raises(core.ProbeError) as exc:
        core.variant_gate(path.replace("cu128", "cpu"))
    assert exc.value.code == "kernel_variant_mismatch"
    assert core.snapshot_sha_of("/nowhere") == "" and core.variant_of(None) == ""


def test_tier_gate_is_the_run11_negative_control() -> None:
    assert core.tier_gate({"resident_stage_tier": 6144}) == 6144
    with pytest.raises(core.ProbeError) as exc:
        core.tier_gate({"resident_stage_tier": 3072})
    assert exc.value.code == "kernel_tier_mismatch"
    assert "resident_dimension_too_large" in exc.value.message
    with pytest.raises(core.ProbeError) as exc:
        core.tier_gate({})
    assert exc.value.code == "kernel_tier_missing"
    with pytest.raises(core.ProbeError) as exc:
        core.tier_gate({"resident_stage_tier": True})
    assert exc.value.code == "kernel_tier_mismatch"


def test_expected_library_mirrors_the_published_loader(artifact: dict) -> None:
    manifest = {"cuda_libraries": artifact["image"]["build_facts"]["kernel"]["cuda_libraries"]}
    assert core.expected_library(manifest, (7, 5)) == "libalgenta_algenta_llm.sm_75.so"
    assert (
        core.expected_library(manifest, (7, 5))
        == artifact["steps"]["gpu"]["data"]["kernel"]["selected_library"]
    )
    assert core.expected_library(manifest, (8, 9)) == "libalgenta_algenta_llm.sm_89.so"
    assert core.expected_library(manifest, (8, 6)) == "libalgenta_algenta_llm.sm_80.so"
    assert core.expected_library(manifest, (9, 0)) == "libalgenta_algenta_llm.sm_90.so"
    assert core.expected_library(manifest, (12, 0)) == "libalgenta_algenta_llm.sm_90.so"
    with pytest.raises(core.ProbeError) as exc:
        core.expected_library(manifest, (7, 0))
    assert exc.value.code == "gpu_unsupported"
    with pytest.raises(core.ProbeError) as exc:
        core.expected_library({}, (7, 5))
    assert exc.value.code == "kernel_manifest_invalid"
    assert core.library_gate("libalgenta_algenta_llm.sm_75.so", manifest, [7, 5])
    with pytest.raises(core.ProbeError) as exc:
        core.library_gate("libalgenta_algenta_llm.sm_90.so", manifest, [7, 5])
    assert exc.value.code == "kernel_library_mismatch"
    assert core.cuda_targets_of(manifest) == ["sm_75", "sm_80", "sm_89", "sm_90"]


# --- parity and timings ----------------------------------------------------------------------


def test_parity_full_match_is_eight_of_eight(artifact: dict) -> None:
    native = artifact["parity"]["native"]["tokens"]
    reference = artifact["parity"]["reference_tokens"]
    report = core.parity_report(native, reference, reference_margins=[1.0] * 8)
    assert report["verdict"] == "8/8" and report["full_match"] is True
    assert report["prefix_match"] == 8 and report["first_divergence"] is None
    assert report["reference_top2_margin_at_divergence"] is None


def test_parity_divergence_names_the_index_and_the_margin() -> None:
    reference = [9856, 13, 15920, 315, 279, 2701, 374, 830]
    native = [9856, 13, 15920, 315, 100, 2701, 374, 830]
    margins = [5.0, 4.0, 3.0, 2.0, 0.031251, 1.0, 1.0, 1.0]
    report = core.parity_report(native, reference, reference_margins=margins)
    assert report["verdict"] == "4/8" and report["full_match"] is False
    assert report["first_divergence"] == {"index": 4, "native": 100, "reference": 279}
    assert report["reference_top2_margin_at_divergence"] == 0.031251
    short = core.compare_tokens(reference[:5], reference)
    assert short["prefix_match"] == 5 and short["full_match"] is False
    assert short["first_divergence"]["length_only"] is True
    assert core.compare_tokens([], [])["full_match"] is False


def test_decode_timings_from_the_run12_steps(artifact: dict) -> None:
    decode = artifact["steps"]["gpu"]["data"]["decode"]
    timings = core.decode_timings(decode["open_s"], decode["step_ms"])
    assert timings["n_tokens"] == 8
    assert timings["open_s"] == 41.67 and timings["first_step_ms"] == 0.24
    assert timings["ttft_s"] == round(41.67 + 0.24 / 1000, 2)
    assert timings["ttft_is_session_open"] is True
    after_first = sum(decode["step_ms"][1:])
    assert timings["tok_per_s"] == round(7 / (after_first / 1000.0), 2)
    assert timings["mean_step_ms"] == round(sum(decode["step_ms"]) / 8, 2)
    assert core.decode_timings(None, []) == {
        "n_tokens": 0,
        "step_ms": [],
        "first_step_ms": None,
        "mean_step_ms": None,
        "steady_steps": None,
        "steady_step_ms": None,
        "steady_tok_per_s": None,
        "all_steps_tok_per_s": None,
        "open_s": None,
        "ttft_s": None,
        "ttft_is_session_open": True,
        "tok_per_s": None,
    }
    assert core.decode_timings(1.0, [5.0])["tok_per_s"] is None


def test_steady_tokens_per_second_is_steps_three_to_eight() -> None:
    """The run-13 step times: the 0.1 ms first step (prefill at session open) and the 194.7 ms
    warm-up are outside the steady figure; the older `tok_per_s` (7 tokens over steps 2 to 8,
    the 19.67 the page used to headline) is kept under its own name."""
    steady = RUN13_STEP_MS[2:]
    steady_mean = sum(steady) / len(steady)
    t = core.step_timings(RUN13_STEP_MS)
    assert t["steady_steps"] == "3-8" and cfg.STEADY_FROM_STEP == 3
    assert t["steady_step_ms"] == round(steady_mean, 2) == 26.88
    assert t["steady_tok_per_s"] == round(1000.0 / steady_mean, 2) == 37.2
    assert t["all_steps_tok_per_s"] == round(8 / (sum(RUN13_STEP_MS) / 1000.0), 2) == 22.47
    assert t["first_step_ms"] == 0.1 and t["mean_step_ms"] == round(sum(RUN13_STEP_MS) / 8, 2)
    d = core.decode_timings(RUN13_OPEN_S, RUN13_STEP_MS)
    assert d["tok_per_s"] == round(7 / (sum(RUN13_STEP_MS[1:]) / 1000.0), 2) == 19.66
    assert d["ttft_s"] == 42.64 == d["open_s"], "the prefill ran at session open"
    assert {k: d[k] for k in t} == t, "the steady figures are the shared definition"
    # the same definition for a transformers lane: step 1 is its prefill
    b = core.baseline_timings(9.0, [90.0, 40.0, 40.0, 40.0, 40.0, 40.0, 40.0, 40.0])
    assert b["load_s"] == 9.0 and b["ttft_s"] == 0.09 and b["ttft_is_session_open"] is False
    assert b["steady_step_ms"] == 40.0 and b["steady_tok_per_s"] == 25.0
    assert b["all_steps_tok_per_s"] == round(8 / 0.37, 2)
    short = core.step_timings([50.0, 40.0])
    assert short["steady_steps"] is None and short["steady_tok_per_s"] is None
    assert short["all_steps_tok_per_s"] == round(2 / 0.09, 2)


# --- the stage protocol ----------------------------------------------------------------------


def test_stage_result_reads_the_last_json_line() -> None:
    out = 'INFO something\n{"ok": true, "stage": "driver", "x": 1}\n'
    assert core.stage_result_from_output(out, 0) == {"ok": True, "stage": "driver", "x": 1}
    failed = core.stage_result_from_output('{"ok": false, "code": "no_gpu", "message": "m"}', 1)
    assert failed["code"] == "no_gpu" and failed["message"] == "m"
    bare = core.stage_result_from_output('{"ok": false}', 1)
    assert bare["code"] == "stage_failed"
    crashed = core.stage_result_from_output("Fatal Python error\n", -11)
    assert crashed["code"] == "stage_crashed" and "signal 11" in crashed["message"]
    inconsistent = core.stage_result_from_output('{"ok": true}', 1)
    assert inconsistent["code"] == "stage_crashed"
    assert core.stage_result_from_output("", 0, timed_out=True)["code"] == "stage_timeout"
    assert core.log_tail("a\n\nb\nc\n", 2) == ["b", "c"]


def test_public_error_keeps_a_typed_code() -> None:
    class KernelError(RuntimeError):
        def __init__(self, code: str, message: str) -> None:
            super().__init__(message)
            self.code = code

    err = core.public_error(KernelError("resident_dimension_too_large", "d_ff 6144 > 3072"))
    assert err.code == "resident_dimension_too_large" and "6144" in err.message
    plain = core.public_error(ValueError("bad\nsecond line"))
    assert plain.code == "ValueError" and plain.message == "bad"
    assert core.public_error(core.ProbeError("x", "y")).code == "x"


@pytest.mark.skipif(shutil.which("nvidia-smi") is not None, reason="a GPU host runs the stage")
def test_driver_stage_fails_closed_without_a_gpu() -> None:
    report = probe.run_stage("driver")
    assert report["ok"] is False and report["code"] == "nvidia_smi_missing"
    assert "Traceback" not in json.dumps(report)
    unknown = probe.run_stage("nope")
    assert unknown["ok"] is False and unknown["code"] == "unknown_stage"
    assert set(probe.STAGES) == set(app.STAGE_PHASES)


def test_environment_facts_are_stdlib_only() -> None:
    facts = probe.environment_facts({"CUDA_VERSION": "12.8.1", "NVIDIA_DISABLE_REQUIRE": "1"})
    assert facts["cuda_version_env"] == "12.8.1" and facts["nvidia_disable_require"] == "1"
    assert set(facts["packages"]) == set(probe.PACKAGES)
    space = probe.space_facts({"SPACE_ID": cfg.SPACE_REPO_ID})
    assert space["SPACE_ID"] == cfg.SPACE_REPO_ID and space["hardware_requested"] == "t4-small"
    assert probe.work_dir({"PROBE_WORK_DIR": "/w"}) == Path("/w")
    assert probe.build_facts_path({"PROBE_BUILD_FACTS": "/b.json"}) == Path("/b.json")
    assert probe.read_build_facts(Path("/nonexistent/build_facts.json")) == {}


# --- health, run.json and the page against the run-12 data ----------------------------------


def test_health_body_before_the_run_shows_pins_and_no_facts() -> None:
    body = core.health_body(core.PhaseMachine(), versions={"python": "3.14.7"}, space={})
    assert body["schema"] == core.SCHEMA
    assert body["status"] == core.PENDING and body["phase"] == "driver"
    assert body["pins"]["kernel_revision"] == cfg.KERNEL_REVISION
    assert body["pins"]["expected_stage_tier"] == 6144
    for key in ("driver", "kernel", "model", "decode", "reference", "parity", "failure"):
        assert body[key] is None, key
    assert body["run12_recorded"]["matches_this_run"] is None
    assert body["versions"] == {"python": "3.14.7"}
    with pytest.raises(core.ProbeError) as exc:
        core.run_record(body)
    assert exc.value.code == "run_incomplete"


def test_full_run_reproduces_the_run12_record(tmp_path: Path, artifact: dict) -> None:
    state = app.ProbeState(work=tmp_path, versions={"python": "3.14.7"}, space={}, build={})
    runner = _fake_runner(_run12_stage_data(artifact))
    app.run_probe(state, runner)
    assert runner.calls == list(app.STAGE_PHASES)
    body = state.health()
    assert body["status"] == core.OK and body["phase"] == "done"
    assert body["parity"]["verdict"] == "8/8" and body["parity"]["full_match"] is True
    assert body["parity"]["native_tokens"] == artifact["parity"]["native"]["tokens"]
    assert body["run12_recorded"]["matches_this_run"] is True
    assert body["decode"]["timings"]["open_s"] == 41.67
    assert body["decode"]["timings"]["steady_steps"] == "3-8"
    assert body["kernel"]["selected_library"] == "libalgenta_algenta_llm.sm_75.so"
    assert body["phases"]["record"]["status"] == core.OK and body["run_json"] is True
    assert body["schema"] == core.SCHEMA == "algenta-gpu-probe/3"
    record = json.loads(state.run_json.read_text(encoding="utf-8"))
    assert record["decision"] == "ok"
    assert record["baseline"]["status"] == core.OK and set(record["baseline"]["lanes"]) == {
        "float32",
        "float16",
    }
    row = record["evidence"]["GPU-SPACE-PARITY-001"]
    expected = artifact["evidence"]["GPU-SPACE-PARITY-001"]
    for key in ("native_tokens", "reference_tokens", "step_ms", "open_s", "blob_bytes"):
        assert row[key] == expected[key], key
    assert row["prompt_token_ids"] == expected["prompt_token_ids"]
    assert row["conversion_wall_s"] == expected["conversion_wall_s"] == 81.73
    driver_row = record["evidence"]["GPU-SPACE-DRIVER-001"]
    assert driver_row["gpu"] == "Tesla T4" and driver_row["cuDriverGetVersion"] == 13000
    assert driver_row["meets_driver_floor"] is True and driver_row["compute_capability"] == [7, 5]


def test_failed_stage_stops_the_run_with_its_code(tmp_path: Path, artifact: dict) -> None:
    state = app.ProbeState(work=tmp_path, versions={}, space={}, build={})
    failure = {
        "kernel": {
            "stdout": json.dumps(
                {"ok": False, "code": "kernel_tier_mismatch", "message": "tier 3072, expected 6144"}
            ),
            "returncode": 1,
            "stderr": "ERROR gpu_probe: tier\n",
        }
    }
    runner = _fake_runner(_run12_stage_data(artifact), failure)
    app.run_probe(state, runner)
    assert runner.calls == ["driver", "kernel"]
    body = state.health()
    assert body["status"] == core.ERROR and body["phase"] == "kernel"
    assert body["failure"]["code"] == "kernel_tier_mismatch"
    assert body["phases"]["kernel"]["log_tail"] == ["ERROR gpu_probe: tier"]
    assert body["phases"]["decode"]["status"] == core.SKIPPED
    assert body["kernel"] is None and body["driver"]["device_name"] == "Tesla T4"
    assert not state.run_json.exists()


def test_crash_and_timeout_are_phase_codes(tmp_path: Path, artifact: dict) -> None:
    data = _run12_stage_data(artifact)
    crashed = app.ProbeState(work=tmp_path / "a", versions={}, space={}, build={})
    app.run_probe(crashed, _fake_runner(data, {"decode": {"stdout": "", "returncode": -11}}))
    failure = crashed.health()["failure"]
    assert failure["phase"] == "decode" and failure["code"] == "stage_crashed"
    assert "signal 11" in failure["message"]
    slow = app.ProbeState(work=tmp_path / "b", versions={}, space={}, build={})
    app.run_probe(slow, _fake_runner(data, {"convert": {"timed_out": True}}))
    assert slow.health()["failure"]["code"] == "stage_timeout"

    def exploding(name: str, timeout_s: float) -> app.StageOutcome:
        raise OSError("no interpreter")

    broken = app.ProbeState(work=tmp_path / "c", versions={}, space={}, build={})
    app.run_probe(broken, exploding)
    assert broken.health()["failure"]["code"] == "stage_crashed"


def test_routes_and_page(tmp_path: Path, artifact: dict) -> None:
    testclient = pytest.importorskip("starlette.testclient")
    state = app.ProbeState(work=tmp_path, versions={"python": "3.14.7"}, space={}, build={})
    client = testclient.TestClient(app.build_app(state))
    health = client.get("/health")
    assert health.status_code == 200 and health.json()["status"] == core.PENDING
    missing = client.get("/run.json")
    assert missing.status_code == 404 and missing.json()["error"] == "run_not_recorded"
    page = client.get("/")
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    assert app.TITLE in page.text and "Waiting to start." in page.text
    _assert_clean_copy(page.text)

    app.run_probe(state, _fake_runner(_run12_stage_data(artifact)))
    run = client.get("/run.json")
    assert run.status_code == 200 and run.json()["decision"] == "ok"
    page = client.get("/")
    assert "Parity 8/8" in page.text and "Germany. Which of the following is true" in page.text
    assert "libalgenta_algenta_llm.sm_75.so" in page.text and "Tesla T4" in page.text
    assert "Traceback" not in page.text
    _assert_clean_copy(page.text)
    for url in (cfg.PRICING_URL, cfg.DISCORD_URL, cfg.DOCS_URL):
        assert url in page.text

    failed = app.ProbeState(work=tmp_path / "f", versions={}, space={}, build={})
    app.run_probe(
        failed,
        _fake_runner(
            _run12_stage_data(artifact),
            {"driver": {"stdout": json.dumps({"ok": False, "code": "no_gpu", "message": "none"})}},
        ),
    )
    client = testclient.TestClient(app.build_app(failed))
    assert client.get("/health").status_code == 503
    text = client.get("/").text
    assert "Stopped at driver: no_gpu" in text and "Traceback" not in text
    _assert_clean_copy(text)


def _page_text(page: str) -> str:
    """The page's rendered words: tags and the stylesheet stripped, whitespace collapsed."""
    import html as _html

    without_css = re.sub(r"<style>.*?</style>", " ", page, flags=re.DOTALL)
    return _html.unescape(" ".join(re.sub(r"<[^>]+>", " ", without_css).split()))


def test_baseline_block_shape_and_lane_failure_codes(tmp_path: Path, artifact: dict) -> None:
    """`/health.baseline`: the stage's facts, each lane with its timings (the shared steady
    definition) and its parity against the CPU reference; a failed lane is its code alone."""
    data = _run12_stage_data(artifact)
    tokens = artifact["parity"]["reference_tokens"]
    data["baseline"] = _fixture_baseline(tokens, float16_code="baseline_oom")
    state = app.ProbeState(work=tmp_path, versions={}, space={}, build={})
    app.run_probe(state, _fake_runner(data))
    body = state.health()
    assert body["status"] == core.OK and body["phases"]["baseline"]["status"] == core.OK
    block = body["baseline"]
    assert block["status"] == core.OK and block["code"] is None
    for key in ("device_name", "torch", "cuda", "transformers", "n_prompt", "dtypes", "method"):
        assert key in block, key
    f32 = block["lanes"]["float32"]
    assert f32["ok"] is True and f32["dtype"] == "float32"
    assert f32["timings"] == core.baseline_timings(f32["load_s"], f32["step_ms"])
    assert f32["timings"]["steady_step_ms"] == 40.0 and f32["timings"]["ttft_s"] == 0.09
    assert f32["warmup_timings"]["n_tokens"] == 8 and f32["warmup"]["excluded"] is True
    assert f32["parity"]["verdict"] == "8/8" and f32["parity"]["full_match"] is True
    f16 = block["lanes"]["float16"]
    assert f16 == {
        "ok": False,
        "dtype": "float16",
        "code": "baseline_oom",
        "message": "OutOfMemoryError: CUDA out of memory",
    }
    assert "timings" not in f16 and "step_ms" not in f16, "a failed lane carries no number"
    record = json.loads(state.run_json.read_text(encoding="utf-8"))
    assert record["baseline"]["lanes"]["float16"]["code"] == "baseline_oom"
    assert record["baseline"]["lanes"]["float32"]["parity"]["verdict"] == "8/8"
    # a lane the stage did not report at all is unavailable with its own code
    data["baseline"] = {**_fixture_baseline(tokens), "lanes": {}}
    other = app.ProbeState(work=tmp_path / "b", versions={}, space={}, build={})
    app.run_probe(other, _fake_runner(data))
    lanes = other.health()["baseline"]["lanes"]
    assert lanes["float32"]["code"] == lanes["float16"]["code"] == "baseline_lane_missing"


def test_side_by_side_lanes_and_the_unavailable_state(tmp_path: Path, artifact: dict) -> None:
    data = _run12_stage_data(artifact)
    tokens = artifact["parity"]["reference_tokens"]
    data["baseline"] = _fixture_baseline(tokens, float16_code="baseline_oom")
    state = app.ProbeState(work=tmp_path, versions={}, space={}, build={})
    app.run_probe(state, _fake_runner(data))
    body = state.health()
    view = core.side_by_side(body)
    assert view["gpu"] == "Tesla T4" and view["predates"] is False
    assert [lane["id"] for lane in view["lanes"]] == ["algenta", "float32", "float16"]
    algenta, f32, f16 = view["lanes"]
    assert algenta["status"] == core.OK_LANE and algenta["ttft_s"] == algenta["load_s"] == 41.67
    assert algenta["steady_step_ms"] == body["decode"]["timings"]["steady_step_ms"]
    assert algenta["first_step_note"].startswith("prefill done at session open; step 2 (")
    assert algenta["device_taken_bytes"] is None, "run 12 did not record device memory"
    assert f32["status"] == core.OK_LANE and f32["tokens"] == tokens
    assert f32["parity"]["verdict"] == "8/8" and f32["load_s"] == 9.0 and f32["ttft_s"] == 0.09
    assert f32["steady_step_ms"] == 40.0 and f32["steady_tok_per_s"] == 25.0
    assert f32["device_taken_bytes"] == 7_000_000_000
    assert f32["peak_allocated_bytes"] == 7_300_000_000
    assert "warm-up generate excluded" in f32["first_step_note"]
    assert f16["status"] == core.UNAVAILABLE and f16["code"] == "baseline_oom"
    assert "steady_step_ms" not in f16
    ratio_f32, ratio_f16 = view["ratios"]
    assert ratio_f32["same_tokens"] is True
    assert ratio_f32["steady_step_ratio"] == round(40.0 / algenta["steady_step_ms"], 2)
    assert ratio_f16 == {"lane": "float16", "same_tokens": None, "steady_step_ratio": None}

    page = app.render_page(body)
    text = _page_text(page)
    _assert_clean_copy(page)
    verdict = text.index("Run complete. Parity 8/8")
    section = text.index("Side by side on the same Tesla T4")
    assert verdict < section < text.index("Phases driver ok"), "right under the verdict"
    assert "Algenta CUDA kernels · f32 resident" in text
    assert "transformers CUDA · float32" in text and "transformers CUDA · float16" in text
    assert "unavailable (baseline_oom)" in text
    assert text.count("Germany. Which of the following is true (the same 8 tokens)") == 1
    assert "9.00 s (model load: from_pretrained, then moved to the device)" in text
    assert "0.090 s (timed generate: the prefill of the 12 prompt tokens)" in text
    assert app._s(0.0654, fine=True) == "0.065 s" and app._s(42.64, fine=True) == "42.64 s"
    assert "41.67 s (= session open; the prefill runs there)" in text
    assert "Ratio of steady per-token times, transformers CUDA float32 over Algenta:" in text
    assert "7.00 GB (7,000,000,000 bytes) taken on the device; peak allocated 7.30 GB" in text
    for needle in (
        "Steady per-token (steps 3 to 8)",
        "Tokens per second (steady)",
        "Tokens per second (over all 8 steps)",
        "First step and warm-up",
        "Device memory",
        "Precision",
        "transformers 5.17.0 · torch 2.9.1+cu128 · CUDA 12.8",
        "same eight greedy tokens requested, same GPU",
        "one warm-up generate first, excluded from every timed figure",
    ):
        assert needle in text, needle
    assert "differs from the Algenta lane" not in text

    # tokens that differ: marked on the page, and no ratio
    other = [*tokens[:4], 100, *tokens[5:]]
    data["baseline"] = _fixture_baseline(other)
    diverged = app.ProbeState(work=tmp_path / "d", versions={}, space={}, build={})
    app.run_probe(diverged, _fake_runner(data))
    text = _page_text(app.render_page(diverged.health()))
    assert "(differs from the Algenta lane at index 4)" in text
    assert "4/8, first divergence at index 4" in text
    assert "No ratio for transformers CUDA float32: its tokens differ" in text
    assert "Ratio of steady" not in text


def test_baseline_stage_failure_is_unavailable_not_a_stop(tmp_path: Path, artifact: dict) -> None:
    """The baseline subprocess crashing (or timing out) keeps the parity record: the run is ok,
    `run.json` is written, and both transformers columns say unavailable with the code."""
    data = _run12_stage_data(artifact)
    crashed = app.ProbeState(work=tmp_path, versions={}, space={}, build={})
    runner = _fake_runner(data, {"baseline": {"stdout": "", "returncode": -11}})
    app.run_probe(crashed, runner)
    assert runner.calls == list(app.STAGE_PHASES)
    body = crashed.health()
    assert body["status"] == core.OK and body["phase"] == "done" and body["failure"] is None
    assert body["phases"]["baseline"]["status"] == core.ERROR
    assert body["phases"]["baseline"]["code"] == "stage_crashed"
    assert body["baseline"]["status"] == core.ERROR and body["baseline"]["lanes"] == {}
    assert body["parity"]["verdict"] == "8/8" and body["run_json"] is True
    record = json.loads(crashed.run_json.read_text(encoding="utf-8"))
    assert record["decision"] == "ok" and record["baseline"]["code"] == "stage_crashed"
    text = _page_text(app.render_page(body))
    assert "Run complete. Parity 8/8" in text
    assert text.count("unavailable (stage_crashed)") == 2
    assert "baseline error in 0.5 s (stage_crashed)" in text
    slow = app.ProbeState(work=tmp_path / "t", versions={}, space={}, build={})
    app.run_probe(slow, _fake_runner(data, {"baseline": {"timed_out": True}}))
    assert slow.health()["baseline"]["code"] == "stage_timeout"
    assert slow.health()["status"] == core.OK
    # while it runs, the columns say so
    machine = core.PhaseMachine()
    for name in ("driver", "kernel", "convert", "decode"):
        machine.start(name)
        machine.finish(name, data[name])
    machine.start("baseline")
    live = core.health_body(machine, versions={}, space={})
    assert live["baseline"]["status"] == core.RUNNING
    assert _page_text(app.render_page(live)).count("not measured yet") == 2


def test_run13_record_replays_and_predates_the_baseline(tmp_path: Path, artifact13: dict) -> None:
    """The run-13 record (schema 2, no `baseline` block) renders as it was measured: the section
    says the run predates the stage, in words, and nothing reads as a failure. Its stage data
    replays through today's orchestrator with a baseline report beside it."""
    assert artifact13["schema"] == "algenta-gpu-probe/2" and "baseline" not in artifact13
    view = core.side_by_side(artifact13)
    assert view["predates"] is True and view["gpu"] == "Tesla T4"
    algenta, f32, f16 = view["lanes"]
    assert algenta["status"] == core.OK_LANE and algenta["parity"]["verdict"] == "8/8"
    assert algenta["load_s"] == algenta["ttft_s"] == artifact13["decode"]["open_s"] == 42.81
    assert algenta["device_taken_bytes"] == (
        artifact13["decode"]["gpu_free_bytes_start"]
        - artifact13["decode"]["gpu_free_bytes_after_open"]
    )
    assert f32["status"] == f16["status"] == core.ABSENT_LANE and f32["code"] is None
    page = app.render_page(artifact13)
    text = _page_text(page)
    _assert_clean_copy(page)
    assert app.SIDE_BY_SIDE_PREDATES in text
    assert text.count("not measured in this run") == 2
    assert "unavailable" not in text and "Stopped at" not in text and " error" not in text
    assert "Tokens 9856, 13, 15920, 315, 279, 2701, 374, 830" in text
    assert "First step 0.12 ms (prefill done at session open)" in text
    assert "Time to first token 42.81 s (= session open)" in text
    assert "First token" not in text
    steady = core.step_timings(artifact13["decode"]["step_ms"])
    assert f"Tokens per second (steady) {steady['steady_tok_per_s']:.2f}" in text
    assert f"Tokens per second (over all 8 steps) {steady['all_steps_tok_per_s']:.2f}" in text

    state = app.ProbeState(work=tmp_path, versions={}, space={}, build={})
    tokens = artifact13["reference"]["tokens"]
    data = _run13_stage_data(artifact13, baseline=_fixture_baseline(tokens))
    app.run_probe(state, _fake_runner(data))
    body = state.health()
    assert body["status"] == core.OK and body["parity"]["verdict"] == "8/8"
    assert body["decode"]["timings"]["open_s"] == 42.81
    assert body["baseline"]["lanes"]["float32"]["parity"]["full_match"] is True
    record = json.loads(state.run_json.read_text(encoding="utf-8"))
    row = record["evidence"]["GPU-SPACE-PARITY-001"]
    for key in ("native_tokens", "reference_tokens", "step_ms", "open_s", "blob_bytes"):
        assert row[key] == artifact13["evidence"]["GPU-SPACE-PARITY-001"][key], key
    text = _page_text(app.render_page(body))
    assert app.SIDE_BY_SIDE_PREDATES not in text
    assert "(the same 8 tokens)" in text and "Side by side on the same Tesla T4" in text


def test_identifiers_render_plain_and_quantities_with_separators(artifact13: dict) -> None:
    text = _page_text(app.render_page(artifact13))
    assert "59604, 374, 279, 6722" in text and "59,604" not in text
    assert "9856, 13, 15920" in text and "9,856" not in text and "15,920" not in text
    assert "Staging tier 6144" in text and "6,144" not in text
    assert "Memory 15,360 MiB (15,828,320,256 bytes)" in text
    assert "12.82 GiB (13,764,599,808 bytes)" in text
    assert app._fmt([59604, 374], plain=True) == "59604, 374"
    assert app._fmt(13764599808) == "13,764,599,808"
    assert app._memory("15360 MiB", 15828320256) == "15,360 MiB (15,828,320,256 bytes)"
    assert app._memory("n/a", None) == "n/a" and app._memory(None, None) == app.ABSENT


def test_step_clock_times_tokens_as_they_reach_the_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """The streamer skips the prompt echo and times each single-token put from the previous
    one; step 1 counts from `start()`, the timed call's start."""

    class Tensor:
        def __init__(self, values: list[int]) -> None:
            self.values = values

        def reshape(self, _shape: int) -> Tensor:
            return self

        def tolist(self) -> list[int]:
            return list(self.values)

    ticks = iter([100.0, 100.0, 100.09, 100.13, 100.17, 100.21])
    monkeypatch.setattr(probe.time, "perf_counter", lambda: next(ticks))
    clock = probe.StepClock()  # 100.0
    clock.start()  # 100.0
    clock.put(Tensor([59604, 374, 279]))  # 100.09: the prompt echo, before the prefill
    clock.put(Tensor([9856]))  # 100.13
    clock.put(Tensor([13]))  # 100.17
    clock.put(Tensor([15920]))  # 100.21
    assert clock.prompt_echoed(3) and not clock.prompt_echoed(4)
    tokens, step_ms = clock.token_times()
    assert tokens == [9856, 13, 15920]
    assert [round(ms, 3) for ms in step_ms] == [130.0, 40.0, 40.0]
    assert probe.STAGES["baseline"] is probe.stage_baseline
    assert "baseline" in app.STAGE_PHASES and cfg.BASELINE_DTYPES == ("float32", "float16")


def test_page_copy_has_no_banned_words_or_exclamations() -> None:
    for text in (
        app.TITLE,
        app.HEADLINE,
        app.SUBLINE,
        app.PAGE_TEMPLATE,
        app.SIDE_BY_SIDE_CAPTION,
        app.SIDE_BY_SIDE_PREDATES,
    ):
        _assert_clean_copy(text)
    assert copy_lint.word_count(app.HEADLINE) <= copy_lint.HEADLINE_MAX_WORDS
    assert copy_lint.word_count(app.SUBLINE) <= copy_lint.SUBLINE_MAX_WORDS
    assert "!important" not in app.PAGE_CSS


# --- the Space directory: README, Dockerfile, requirements, manifest decision ---------------


def _frontmatter(readme: Path) -> dict[str, str]:
    lines = readme.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---"
    end = lines.index("---", 1)
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if line.startswith((" ", "\t", "-")):
            continue
        key, _, raw = line.partition(":")
        fields[key.strip()] = raw.strip().strip("\"'")
    return fields


def test_readme_card_and_copy_lint() -> None:
    front = _frontmatter(PROBE_DIR / "README.md")
    assert front["title"] == "Algenta GPU probe"
    assert front["sdk"] == "docker" and front["hardware"] == cfg.HARDWARE == "t4-small"
    assert front["pinned"] == "false" and front["app_port"] == str(cfg.APP_PORT)
    assert front["short_description"] == "Qwen3-1.7B on Algenta CUDA kernels — parity probe"
    body = (PROBE_DIR / "README.md").read_text(encoding="utf-8")
    for url in (cfg.DOCS_URL, cfg.PRICING_URL, cfg.DISCORD_URL, cfg.MODEL_HUB_URL):
        assert url in body, url
    assert "licensing@" not in body and "decision engine" not in body.lower()
    assert "Apache-2.0" in body and "private" in body and "paused" in body
    assert (
        "The same decode without Algenta — transformers on the same GPU, float32 and float16 — "
        "sits beside it." in " ".join(body.split())
    )
    assert copy_lint.lint_space(PROBE_DIR) == []


def test_dockerfile_pins_and_conventions() -> None:
    text = (PROBE_DIR / "Dockerfile").read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
    froms = [line for line in lines if line.startswith("FROM ")]
    assert froms == [
        "FROM nvidia/cuda:12.8.1-runtime-ubuntu24.04@sha256:"
        "ebef3c171eeef0298e4eb2e4be843105edf3b8b0ac45e0b43acee358e8046867"
    ]
    copies = [line for line in lines if line.startswith("COPY --from=")]
    assert len(copies) == 1 and re.search(r"uv:\d+\.\d+\.\d+@sha256:[0-9a-f]{64} ", copies[0])
    assert not re.search(r"(?<=[\w}./-]):-?latest\b", "\n".join(lines), re.IGNORECASE)
    assert "NVIDIA_DISABLE_REQUIRE=1" in text
    assert re.findall(r"^EXPOSE\s+(\d+)", text, re.M) == [str(cfg.APP_PORT)]
    assert "useradd --create-home --uid 1000" in text
    bake = text.index("python fetch_assets.py --bake")
    assert text.index("USER user") < bake, "the bake runs as the runtime user"
    assert "HF_HUB_OFFLINE=1 python fetch_assets.py --verify" in text
    assert text.index("ENV HF_HUB_OFFLINE=1") > bake, "offline is set after the bake"
    assert "uv python install 3.14" in text and "--index-strategy unsafe-best-match" in text
    assert text.rstrip().endswith('CMD ["python", "app.py"]')


def _pins(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        name, _, version = line.partition("==")
        pins[name.strip().split("[", 1)[0].lower().replace("-", "_")] = version.strip()
    return pins


def test_requirements_are_exact_and_agree_with_the_flagship() -> None:
    text = (PROBE_DIR / "requirements.txt").read_text(encoding="utf-8")
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line and not line.startswith("-"):
            assert re.fullmatch(r"[A-Za-z0-9_.\-\[\]]+==[A-Za-z0-9_.+\-]+", line), line
    assert "--extra-index-url https://download.pytorch.org/whl/cu128" in text
    pins = _pins(PROBE_DIR / "requirements.txt")
    assert pins["torch"] == "2.9.1+cu128"
    assert pins["kernels"] == "0.17.1" and pins["huggingface_hub"] == "1.26.1"
    assert pins["transformers"] == "5.17.0" and pins["safetensors"] == "0.8.0"
    assert pins["algenta"] == "1.0.28"
    flagship = _pins(FLAGSHIP_DIR / "requirements.txt")
    for name in ("kernels", "huggingface_hub", "algenta", "numpy", "fastapi", "uvicorn"):
        if name in flagship:
            assert pins[name] == flagship[name], f"{name} disagrees with the flagship"
    assert probe.PACKAGES[0] == "torch"


def test_probe_is_not_in_the_fleet_manifest_and_deploys_by_hand() -> None:
    """A `[spaces.gpu-probe]` table would put a paid GPU on `deploy.py --all` and the
    `spaces=all` dispatch, and the manifest schema has no `private` and requires `api_names`;
    the Space is deployed by the steps in DEPLOY.md instead."""
    manifest = load_manifest()
    assert "gpu-probe" not in manifest.spaces
    assert all(s.repo_id != cfg.SPACE_REPO_ID for s in manifest.spaces.values())
    deploy_md = (PROBE_DIR / "DEPLOY.md").read_text(encoding="utf-8")
    for needle in (
        "private=True",
        "upload_folder",
        "request_space_hardware",
        '"t4-small"',
        "pause_space",
        "restart_space",
        "get_space_runtime",
        cfg.SPACE_REPO_ID,
    ):
        assert needle in deploy_md, needle
    assert "licensing@" not in deploy_md
    doc = (REPO / "docs/spaces/GPU-PROBE.md").read_text(encoding="utf-8")
    assert "t4-small" in doc and "M3.1" in doc and cfg.RUN12_ARTIFACT in doc
    for needle in ("`baseline`", "float16", "steady", "baseline_oom", "same prompt"):
        assert needle in doc, needle


def test_stage_ignore_patterns_keep_tests_and_caches_out_of_the_upload() -> None:
    stage = importlib.import_module("stage")
    files = sorted(p.name for p in PROBE_DIR.iterdir() if p.is_file())
    assert {
        "README.md",
        "Dockerfile",
        "requirements.txt",
        "app.py",
        "probe.py",
        "probe_core.py",
        "probe_config.py",
        "fetch_assets.py",
        "hf_ua_shim.py",
        "DEPLOY.md",
        "ruff.toml",
    } <= set(files)
    for rel in stage.iter_files(PROBE_DIR):
        assert not stage.is_ignored(rel)
        assert (PROBE_DIR / rel).stat().st_size <= stage.MAX_FILE_BYTES
    assert stage.frontmatter_sdk((PROBE_DIR / "README.md").read_text(encoding="utf-8")) == "docker"


def test_user_agent_shim_removes_every_trailing_separator_and_space() -> None:
    """The header is refused by h11 for trailing whitespace, whatever produced it: one `"; "`
    (kernels' empty user_agent), a doubled separator, or a bare trailing space all come back
    legal. `rstrip("; ")` is the intended semantics — a token that legitimately ended in `;` or a
    space would itself be the illegal form (Codna review on #1169)."""
    import importlib.util
    from pathlib import Path as _Path

    shim = _Path(__file__).resolve().parents[2] / "apps" / "spaces" / "gpu-probe" / "hf_ua_shim.py"
    spec = importlib.util.spec_from_file_location("hf_ua_shim_probe", shim)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for raw in ("kernels/0.17.1; ", "kernels/0.17.1;; ", "foo/1.0 ", "kernels/0.17.1"):
        cleaned = mod.clean_user_agent(raw)
        assert cleaned == cleaned.rstrip(), raw
        assert not cleaned.endswith(";"), raw
    assert mod.clean_user_agent("kernels/0.17.1; torch/2.9.1; ") == "kernels/0.17.1; torch/2.9.1"
