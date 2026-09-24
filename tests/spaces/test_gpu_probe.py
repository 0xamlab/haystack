"""apps/spaces/gpu-probe — the GPU probe Space, tested without a GPU.

Everything the Space decides on the T4 is a pure helper in `probe_core.py`: the phase machine,
the driver and compute-capability gates, the kernel revision/variant/tier/library gates, the
parity comparison and the timings. Those run here on the build Mac. The orchestrator and the
FastAPI routes run against a fake stage runner that answers with the run-12 artifact's data
(`docs/hf-kernels/evidence/artifacts/gpu-probe-run12-t4-small-qwen3-1p7b.json`), so the page
and `run.json` are checked against the one real run that exists. torch, kernels, transformers
and algenta are never imported.
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
    }


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
    for name in ("kernel", "convert", "decode", "reference", "record"):
        m.start(name)
        m.finish(name, {})
    assert m.status == core.OK and m.phase == "done" and m.finished_utc
    snap = m.snapshot()
    assert list(snap) == list(core.PHASES)
    assert all(rec["status"] == core.OK for rec in snap.values())


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
    for later in ("convert", "decode", "reference", "record"):
        rec = m.records[later]
        assert rec.status == core.SKIPPED and rec.code == "upstream_failed"
        assert "kernel failed with kernel_tier_mismatch" in (rec.message or "")
    with pytest.raises(ValueError, match="cannot start"):
        m.start("convert")
    with pytest.raises(ValueError, match="unknown phase"):
        m.start("nope")
    with pytest.raises(ValueError, match="distinct"):
        core.PhaseMachine(["a", "a"])


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
    assert timings["open_s"] == 41.67 and timings["first_token_ms"] == 0.24
    assert timings["ttft_s"] == round(41.67 + 0.24 / 1000, 2)
    after_first = sum(decode["step_ms"][1:])
    assert timings["tok_per_s"] == round(7 / (after_first / 1000.0), 2)
    assert timings["mean_step_ms"] == round(sum(decode["step_ms"]) / 8, 2)
    assert core.decode_timings(None, []) == {
        "n_tokens": 0,
        "open_s": None,
        "first_token_ms": None,
        "ttft_s": None,
        "tok_per_s": None,
        "mean_step_ms": None,
        "step_ms": [],
    }
    assert core.decode_timings(1.0, [5.0])["tok_per_s"] is None


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
    assert body["kernel"]["selected_library"] == "libalgenta_algenta_llm.sm_75.so"
    assert body["phases"]["record"]["status"] == core.OK and body["run_json"] is True
    record = json.loads(state.run_json.read_text(encoding="utf-8"))
    assert record["decision"] == "ok"
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


def test_page_copy_has_no_banned_words_or_exclamations() -> None:
    for text in (app.TITLE, app.HEADLINE, app.SUBLINE, app.PAGE_TEMPLATE):
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
