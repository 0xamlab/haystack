"""`--stage-tier` of the HF-kernel family build (scripts/build_hf_kernel_family.py): argument
validation against the residentk contract, the define reaching the Mojo compile (through the
script's `--print-command` dry run), the container script forwarding it, and the package generator
surfacing the tier (metadata.json backend info, the card sentence, the CUDA merge gate)."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTAINER_SCRIPT = ROOT / "scripts" / "hf_kernels" / "linux_container_build.sh"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


build = _load("hfk_build_family_tier", ROOT / "scripts" / "build_hf_kernel_family.py")
gen = _load("hfk_generate_package_tier", ROOT / "scripts" / "generate_hf_kernel_package.py")


def _defines(cmd: list[str]) -> list[str]:
    return [cmd[i + 1] for i, tok in enumerate(cmd) if tok == "-D"]


def _plan(monkeypatch, capsys, *argv: str) -> dict:
    monkeypatch.setattr(
        sys,
        "argv",
        ["build_hf_kernel_family.py", *argv, "--out", "/nonexistent/hfk-out", "--print-command"],
    )
    assert build.main() == 0
    return json.loads(capsys.readouterr().out)


# --- the tier table (mojo/engine/residentk/contract.mojo) ----------------------------------------


@pytest.mark.parametrize(
    ("backend", "tier", "expected"),
    [
        ("cpu", "default", (None, None)),
        ("metal", "default", (3072, None)),
        ("cuda", "default", (3072, None)),
        ("metal", "6144", (6144, "ALGENTA_STAGE_6144")),
        ("cuda", "6144", (6144, "ALGENTA_STAGE_6144")),
        ("cuda", "8192", (8192, "ALGENTA_STAGE_8192")),
    ],
)
def test_stage_tier_spec_follows_the_contract(backend, tier, expected):
    assert build.stage_tier_spec(backend, tier) == expected


@pytest.mark.parametrize(
    ("backend", "tier", "needle"),
    [
        ("metal", "8192", "CUDA-only"),  # 32 KiB is Apple silicon's whole threadgroup budget
        ("cpu", "6144", "GPU-only"),  # no resident decode on the CPU build
        ("cpu", "8192", "GPU-only"),
        ("cuda", "4096", "unknown --stage-tier"),
    ],
)
def test_stage_tier_spec_refuses_and_names_the_rule(backend, tier, needle):
    with pytest.raises(SystemExit) as exc:
        build.stage_tier_spec(backend, tier)
    assert needle in str(exc.value)


def test_mojo_build_argv_keeps_the_three_recipes():
    src, out = Path("/s/abi.mojo"), Path("/s/out")
    cpu_x86 = build.mojo_build_argv("cpu", src, out, system="linux", plat="x86_64-linux")
    assert (
        cpu_x86[:6] == ["pixi", "run", "mojo", "build", "--mcpu", "x86-64-v3"]
        and "-D" not in cpu_x86
    )
    cpu_arm = build.mojo_build_argv("cpu", src, out, system="linux", plat="aarch64-linux")
    assert "--mcpu" not in cpu_arm and cpu_arm[-4:] == ["--emit", "shared-lib", "-o", "/s/out"]
    cuda = build.mojo_build_argv(
        "cuda",
        src,
        out,
        system="linux",
        plat="x86_64-linux",
        cuda_target="sm_89",
        stage_define="ALGENTA_STAGE_8192",
    )
    assert "--mcpu" not in cuda  # a GPU target sets its own arch
    assert cuda[4:12] == [
        "-D",
        "ALGENTA_GPU",
        "-D",
        "ALGENTA_CUDA",
        "-D",
        "ALGENTA_STAGE_8192",
        "--target-accelerator",
        "sm_89",
    ]
    assert cuda[-4:] == ["--emit", "shared-lib", "-o", "/s/out"]
    metal = build.mojo_build_argv(
        "metal",
        src,
        out,
        system="darwin",
        plat="aarch64-darwin",
        metal_target="apple-m1",
        stage_define="ALGENTA_STAGE_6144",
    )
    assert metal[metal.index("--emit") + 1] == "object" and _defines(metal) == [
        "ALGENTA_GPU",
        "ALGENTA_METAL",
        "ALGENTA_STAGE_6144",
    ]
    plain = build.mojo_build_argv(
        "cuda", src, out, system="linux", plat="x86_64-linux", cuda_target="sm_75"
    )
    assert _defines(plain) == ["ALGENTA_GPU", "ALGENTA_CUDA"]
    with pytest.raises(SystemExit):
        build.mojo_build_argv("cuda", src, out, system="linux", plat="x86_64-linux")
    with pytest.raises(SystemExit):
        build.mojo_build_argv("metal", src, out, system="darwin", plat="aarch64-darwin")


# --- the CLI: the define reaches every library's build command ----------------------------------


def test_cuda_plan_carries_the_define_on_every_target(monkeypatch, capsys):
    plan = _plan(
        monkeypatch,
        capsys,
        "--family",
        "algenta-llm",
        "--backend",
        "cuda",
        "--cuda-targets",
        "sm_75",
        "sm_90",
        "--stage-tier",
        "6144",
    )
    assert (
        plan["resident_stage_tier"] == 6144
        and plan["resident_stage_define"] == "ALGENTA_STAGE_6144"
    )
    ext = Path(plan["libraries"][0]).suffix  # .so on Linux, .dylib on macOS: never a fixed width
    assert ext in {".so", ".dylib"}
    assert plan["libraries"] == [f"libalgenta_algenta_llm.{t}{ext}" for t in ("sm_75", "sm_90")]
    assert len(plan["commands"]) == 2
    for cmd, target in zip(plan["commands"], ("sm_75", "sm_90"), strict=True):
        assert cmd[:4] == ["pixi", "run", "mojo", "build"]
        assert cmd[cmd.index("--target-accelerator") + 1] == target
        assert _defines(cmd) == ["ALGENTA_GPU", "ALGENTA_CUDA", "ALGENTA_STAGE_6144"]
        assert cmd[cmd.index("--emit") + 1] == "shared-lib"
        assert cmd[cmd.index("-o") + 1].endswith(f"libalgenta_algenta_llm.{target}{ext}")


def test_default_gpu_tier_is_3072_with_no_define(monkeypatch, capsys):
    plan = _plan(
        monkeypatch,
        capsys,
        "--family",
        "algenta-llm",
        "--backend",
        "cuda",
        "--cuda-targets",
        "sm_80",
    )
    assert plan["resident_stage_tier"] == 3072 and plan["resident_stage_define"] is None
    assert _defines(plan["commands"][0]) == ["ALGENTA_GPU", "ALGENTA_CUDA"]


def test_metal_plan_puts_the_define_on_the_object_emit(monkeypatch, capsys):
    plan = _plan(
        monkeypatch, capsys, "--family", "algenta-llm", "--backend", "metal", "--stage-tier", "6144"
    )
    assert plan["resident_stage_tier"] == 6144 and len(plan["commands"]) == 1
    cmd = plan["commands"][0]
    assert cmd[cmd.index("--emit") + 1] == "object"
    assert _defines(cmd) == ["ALGENTA_GPU", "ALGENTA_METAL", "ALGENTA_STAGE_6144"]


def test_cpu_plan_has_no_tier_and_no_define(monkeypatch, capsys):
    plan = _plan(monkeypatch, capsys, "--family", "algenta-llm")
    assert plan["resident_stage_tier"] is None and plan["resident_stage_define"] is None
    assert "-D" not in plan["commands"][0]


@pytest.mark.parametrize(
    ("argv", "check"),
    [
        (["--backend", "metal", "--stage-tier", "8192"], lambda exc: "CUDA-only" in str(exc.value)),
        (["--backend", "cpu", "--stage-tier", "6144"], lambda exc: "GPU-only" in str(exc.value)),
        (
            ["--backend", "cuda", "--stage-tier", "4096"],
            lambda exc: exc.value.code == 2,
        ),  # argparse choices
    ],
)
def test_cli_refuses_invalid_tiers_before_touching_the_toolchain(monkeypatch, capsys, argv, check):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_hf_kernel_family.py",
            "--family",
            "algenta-llm",
            *argv,
            "--out",
            "/nonexistent/hfk-out",
            "--print-command",
        ],
    )
    with pytest.raises(SystemExit) as exc:
        build.main()
    assert check(exc)


def test_manifest_records_the_tier_and_the_define():
    """The manifest literal in the build script carries the same two variables the plan prints (the
    build itself needs the pinned toolchain, so the field is checked at the source and on the plan)."""
    src = (ROOT / "scripts" / "build_hf_kernel_family.py").read_text()
    assert (
        '"resident_stage_tier": stage_tier,' in src
        and '"resident_stage_define": stage_define,' in src
    )
    assert src.index(
        "stage_tier, stage_define = stage_tier_spec(a.backend, a.stage_tier)"
    ) < src.index('"resident_stage_tier": stage_tier,')


# --- the container build forwards it -------------------------------------------------------------


def test_container_script_forwards_the_tier_to_the_family_build():
    script = CONTAINER_SCRIPT.read_text()
    assert 'STAGE_TIER="${STAGE_TIER:-default}"' in script
    assert '--stage-tier) STAGE_TIER="$2"; shift 2 ;;' in script
    assert '-e STAGE_TIER="$STAGE_TIER"' in script
    assert (
        'scripts/build_hf_kernel_family.py --family "$fam" --backend "$BACKEND" $extra --stage-tier "$STAGE_TIER"'
        in script
    )
    assert script.index('case "$STAGE_TIER" in default|6144|8192)') < script.index(
        "docker volume create"
    )


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_container_script_rejects_an_unknown_tier_before_docker():
    proc = subprocess.run(
        [
            "bash",
            str(CONTAINER_SCRIPT),
            "--arch",
            "amd64",
            "--out",
            "/Users/nobody/out",
            "--stage-tier",
            "4096",
            "algenta-llm",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2 and "--stage-tier must be default, 6144 or 8192" in proc.stderr


# --- the package generator surfaces it -----------------------------------------------------------


def test_backend_metadata_carries_the_tier_for_gpu_builds_only():
    cuda = {"backend": "cuda", "cuda_targets": ["sm_75", "sm_90"], "resident_stage_tier": 6144}
    assert gen.backend_metadata("cuda", cuda) == {
        "type": "cuda",
        "archs": ["7.5", "9.0"],
        "resident_stage_tier": 6144,
    }
    assert gen.backend_metadata("metal", {"backend": "metal", "resident_stage_tier": 6144}) == {
        "type": "metal",
        "resident_stage_tier": 6144,
    }
    # a GPU manifest written before the field existed is a default build: 3072
    assert gen.backend_metadata("metal", {"backend": "metal"}) == {
        "type": "metal",
        "resident_stage_tier": 3072,
    }
    assert gen.backend_metadata("cpu", {"backend": "cpu", "resident_stage_tier": None}) == {
        "type": "cpu"
    }
    assert (
        gen.stage_tier_of({"backend": "cpu"}) is None
        and gen.stage_tier_of({"backend": "cuda", "resident_stage_tier": True}) == 3072
    )


def test_kernels_loader_tolerates_the_extra_backend_key():
    rust = pytest.importorskip("kernels._rust")
    metadata = {
        "name": "algenta-llm",
        "id": "_algenta_llm_cuda_abcdef0",
        "version": 1,
        "license": "other",
        "python-depends": [],
        "kernel-depends": [],
        "backend": {"type": "cuda", "archs": ["7.5", "9.0"], "resident_stage_tier": 6144},
        "digest": {"algorithm": "sha256", "files": {}},
    }
    parsed = rust.Metadata.from_bytes(json.dumps(metadata).encode())
    assert parsed.id == "_algenta_llm_cuda_abcdef0" and parsed.backend.archs == ["7.5", "9.0"]


def test_card_sentence_names_the_tier_the_formula_and_the_models():
    one = gen.stage_tier_sentence({"metal": 6144, "cuda": 6144})
    assert one.startswith(
        "The GPU builds stage decode for models with `max(d_model, h_q*d_head, d_ff) <= 6144`"
    )
    assert (
        "Qwen3-0.6B and Qwen3-1.7B" in one and 'KernelError("resident_dimension_too_large")' in one
    )
    mixed = gen.stage_tier_sentence({"metal": 3072, "cuda": 6144})
    assert "The Metal build stages decode" in mixed and "<= 3072`, for example Qwen3-0.6B;" in mixed
    assert "The CUDA build stages decode" in mixed and "<= 6144" in mixed


def test_render_card_places_the_sentence_in_the_resident_decode_section():
    contract = {
        "modules": {
            "llmk.generate": {
                "name": "llmk.generate",
                "description": "Autoregressive decode primitives",
                "structs": {},
                "functions": {
                    "greedy_argmax": {
                        "name": "greedy_argmax",
                        "params": [],
                        "return_type": "Int",
                        "count_relations": [],
                        "doc": "",
                        "returns_doc": "",
                    }
                },
            }
        }
    }
    variants = {
        "cpu": ["torch214-cpu-aarch64-darwin"],
        "metal": ["torch214-metal-aarch64-darwin"],
        "cuda": ["torch214-cxx11-cu126-x86_64-linux"],
    }
    card = gen.render_card(
        "algenta-llm",
        "LLM kernels",
        ["llmk.generate"],
        contract,
        variants,
        set(),
        ["cpu", "cuda", "metal"],
        True,
        None,
        False,
        {},
        {"metal": 6144, "cuda": 6144},
    )
    section = card.split("## Resident decode", 1)[1].split("## What's inside", 1)[0]
    assert "`max(d_model, h_q*d_head, d_ff) <= 6144`" in section and "Qwen3-1.7B" in section
    assert max(len(line) for line in section.splitlines()) <= 110  # the package test's prose width
    without = gen.render_card(
        "algenta-llm",
        "LLM kernels",
        ["llmk.generate"],
        contract,
        variants,
        set(),
        ["cpu", "cuda", "metal"],
        True,
        None,
        False,
        {},
    )
    assert "stage decode" not in without and "## Resident decode" in without


def test_cuda_merge_refuses_mixed_tiers(tmp_path):
    pytest.importorskip("huggingface_hub")
    rc = _load("hfk_republish_capped_tier", ROOT / "scripts" / "hf_kernels" / "republish_capped.py")

    def native(name: str, target: str, tier: int) -> Path:
        d = tmp_path / name
        d.mkdir()
        lib = f"libalgenta_algenta_llm.{target}.so"
        (d / lib).write_bytes(b"\x7fELF")
        (d / "manifest.json").write_text(
            json.dumps(
                {
                    "backend": "cuda",
                    "cuda_targets": [target],
                    "cuda_libraries": {target: lib},
                    "library": lib,
                    "load_order": [],
                    "files": {lib: {"sha256": "0", "bytes": 4}},
                    "resident_stage_tier": tier,
                    "resident_stage_define": "ALGENTA_STAGE_6144" if tier == 6144 else None,
                }
            )
        )
        return d

    merged = rc.merge_cuda(
        [native("a", "sm_75", 6144), native("b", "sm_90", 6144)], tmp_path / "same"
    )
    assert (
        merged["resident_stage_tier"] == 6144
        and merged["cuda_targets"] == ["sm_75", "sm_90"]
        and merged["library"] == "libalgenta_algenta_llm.sm_90.so"
    )
    with pytest.raises(SystemExit, match="resident_stage_tier differs"):
        rc.merge_cuda([native("c", "sm_75", 6144), native("d", "sm_80", 3072)], tmp_path / "mixed")
