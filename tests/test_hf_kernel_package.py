"""Generated Hugging Face kernel packages: layout, import discipline, digests, validation, copy.

Runs against a generated repo directory when HF_KERNEL_REPO_DIR points at one (CI/local builds);
the filter-table checks run from the contract alone. The native library is exercised in-process
where a check needs it (defaults, in-place updates, engine status codes).
"""
from __future__ import annotations

import ast
import base64
import hashlib
import importlib.util
import inspect
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "packages" / "algenta" / "algenta" / "runtime_library_contract.json").read_text())
FILTERS = json.loads((ROOT / "scripts" / "hf_kernel_filters.json").read_text())
STDLIB = set(sys.stdlib_module_names)
REPO_DIR = os.environ.get("HF_KERNEL_REPO_DIR")
PILOTS = ("algenta-stats", "algenta-llm")


def test_every_executable_module_lands_in_exactly_one_filter():
    from apps.runtime.mojo_inventory import discover_runtime_library_modules  # noqa: PLC0415

    modules = sorted(m.import_path for m in discover_runtime_library_modules(executable_only=True))
    placed = [m for f in FILTERS["filters"].values() for m in f["modules"]]
    assert sorted(placed) == modules
    assert len(placed) == len(set(placed))
    assert FILTERS["module_count"] == len(modules)


def test_every_exclusion_is_a_known_safe_category():
    """A function is excluded from the manifest only for a documented reason: the Python-bridge
    interop function (datetime.now_epoch / the env module), or a crash-gate finding whose reason is
    recorded in the filter table. No function is excluded silently."""
    import importlib.util as _ilu  # noqa: PLC0415
    _spec = _ilu.spec_from_file_location("_gen_filters", ROOT / "scripts" / "hf_kernels" / "generate_filters.py")
    _gf = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_gf)
    UNSAFE_IN_PROCESS = _gf.UNSAFE_IN_PROCESS

    interop = {"datetime.now_epoch"}
    for slug, f in FILTERS["filters"].items():
        reasons = f.get("exclusion_reasons", {})
        for e in f.get("excluded_functions", []):
            assert e in interop or e in UNSAFE_IN_PROCESS, (slug, e)
            if e not in interop:
                assert e in reasons and reasons[e], (slug, e, "crash-gate exclusion has no recorded reason")
    # the crash-gate set is real, not empty, and each entry lands in exactly the family that owns its module
    assert len(UNSAFE_IN_PROCESS) >= 10
    for full in UNSAFE_IN_PROCESS:
        mod = full[:-2] if full.endswith(".*") else full.rsplit(".", 1)[0]
        homes = [slug for slug, f in FILTERS["filters"].items() if any(m == mod or m.startswith(mod + ".") for m in f["modules"])]
        assert len(homes) == 1 and full in FILTERS["filters"][homes[0]].get("excluded_functions", []), (full, homes)
    assert FILTERS["filters"]["algenta-host-interop"]["modules"] == ["env"]
    assert FILTERS["filters"]["algenta-host-interop"]["status"] == "excluded-v1"


def test_gpu_bearing_packages_live_in_the_llm_family():
    llm = set(FILTERS["filters"]["algenta-llm"]["modules"])
    for prefix in ("residentk.", "metaldispatch.", "accel.", "attnk.", "gemm.", "llmk.", "normk.", "lossk.", "mlpk.", "tensorx."):
        for f in FILTERS["filters"].values():
            for m in f["modules"]:
                if m.startswith(prefix):
                    assert m in llm, m


def test_statistics_family_holds_only_statistics():
    """'stat' used to match 'state', 'estate' and 'electrostatics' in the category rules."""
    stats = FILTERS["filters"]["algenta-stats"]["modules"]
    for stray in ("electrostatics", "real_estate", "degradation_state", "stateful_runtime"):
        assert stray not in stats


def test_pilot_families_carry_card_copy():
    for fam in PILOTS:
        f = FILTERS["filters"][fam]
        assert f.get("card_example"), fam
        descriptions = f.get("module_descriptions", {})
        for m in f["modules"]:
            text = descriptions.get(m, "")
            assert text and len(text) <= 100 and "`" not in text and "Zero Python" not in text, (fam, m, text)


# --- generated repository -----------------------------------------------------------------------

def _variants(repo: Path) -> list[Path]:
    return sorted(v for v in (repo / "build").iterdir() if (v / "metadata.json").exists())


def _cpu_variant(repo: Path) -> Path:
    return next(v for v in _variants(repo) if "-cpu-" in v.name)


def _load_package(variant_dir: Path):
    pkg = next(p for p in variant_dir.iterdir() if p.is_dir() and p.name.startswith("algenta_"))
    name = f"_hf_{pkg.name}_{variant_dir.name.replace('-', '_')}"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, pkg / "__init__.py", submodule_search_locations=[str(pkg)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not REPO_DIR, reason="HF_KERNEL_REPO_DIR not set")
def test_generated_python_imports_only_stdlib_or_itself():
    for py in Path(REPO_DIR).rglob("*.py"):
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] in STDLIB, (py, alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    assert node.module.split(".")[0] in STDLIB, (py, node.module)


@pytest.mark.skipif(not REPO_DIR, reason="HF_KERNEL_REPO_DIR not set")
def test_metadata_digest_matches_files():
    for variant in _variants(Path(REPO_DIR)):
        meta = json.loads((variant / "metadata.json").read_text())
        assert meta["version"] >= 1 and meta["license"] == "other" and meta["backend"]["type"] in {"cpu", "metal", "cuda", "rocm"}
        expected = {}
        for p in variant.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(variant).as_posix()
            if rel in ("metadata.json", "metadata.json.sigstore") or "__pycache__" in rel or rel.endswith(".pyc"):
                continue
            expected[rel] = base64.b64encode(hashlib.sha256(p.read_bytes()).digest()).decode()
        assert meta["digest"]["files"] == expected, variant.name


@pytest.mark.skipif(not REPO_DIR, reason="HF_KERNEL_REPO_DIR not set")
def test_build_tree_ships_no_private_paths_or_build_narrative():
    for p in Path(REPO_DIR).rglob("*"):
        if p.is_file() and p.suffix in {".py", ".json", ".md", ".txt"}:
            text = p.read_text(errors="replace")
            for needle in ("/private/tmp", "/Users/", "source_dirty", "stub_guard", "inclusion_method"):
                assert needle not in text, (p, needle)
    for variant in _variants(Path(REPO_DIR)):
        pkg = next(d for d in variant.iterdir() if d.is_dir() and d.name.startswith("algenta_"))
        manifest = json.loads((pkg / "_native" / "manifest.json").read_text())
        # resident_stage_tier: the GPU build's decode staging ceiling (a public fact of the variant, also in
        # metadata.json and the card); absent from CPU closures, which have no resident decode.
        assert set(manifest) <= {"schema", "family", "backend", "abi_version", "library", "cuda_targets", "cuda_libraries", "platform", "minos", "load_order", "files", "runtime_tag", "mojo_version", "source_commit", "resident_stage_tier"}
        if manifest["backend"] in ("metal", "cuda"):
            assert isinstance(manifest.get("resident_stage_tier"), int) and manifest["resident_stage_tier"] >= 3072
        else:
            assert "resident_stage_tier" not in manifest
        for name in manifest["load_order"] + [manifest["library"]] + list((manifest.get("cuda_libraries") or {}).values()):
            assert name in manifest["files"] and os.path.basename(name) == name
        meta = json.loads((variant / "metadata.json").read_text())
        assert meta["id"].endswith(manifest["source_commit"][:7])


@pytest.mark.skipif(not REPO_DIR, reason="HF_KERNEL_REPO_DIR not set")
def test_modules_are_real_packages_with_documented_defaults():
    pkg = _load_package(_cpu_variant(Path(REPO_DIR)))
    for name in pkg.modules:
        obj = pkg
        for part in name.split("."):
            obj = getattr(obj, part)
        assert inspect.ismodule(obj), name
        assert obj.__name__.endswith("." + name), obj.__name__
        for fname in pkg.CONTRACT["modules"][name]["functions"]:
            fn = getattr(obj, fname)
            assert fn.__doc__ and "Args:" in fn.__doc__ or not pkg.CONTRACT["modules"][name]["functions"][fname]["params"], (name, fname)
            for param in inspect.signature(fn).parameters.values():
                assert "object at 0x" not in repr(param.default)
    assert callable(pkg.execute) and "dict of parameter names" in pkg.execute.__doc__
    assert "excluded_functions" in pkg.__all__
    if "ab_testing" in pkg.modules:
        assert inspect.signature(pkg.ab_testing.mde).parameters["alpha"].default == 0.05
        assert pkg.ab_testing.mde(1000, 0.1, power=0.9) == pkg.ab_testing.mde(1000, 0.1, 0.05, 0.9)


@pytest.mark.skipif(not REPO_DIR, reason="HF_KERNEL_REPO_DIR not set")
def test_transport_rejects_what_the_encoder_or_native_side_would_not():
    pkg = _load_package(_cpu_variant(Path(REPO_DIR)))
    transport = sys.modules[pkg.__name__ + "._transport"]
    module = next(m for m in pkg.modules if pkg.CONTRACT["modules"][m]["functions"])
    fname, spec = next((f, s) for f, s in pkg.CONTRACT["modules"][module]["functions"].items() if s["params"])
    structs = pkg.CONTRACT["modules"][module]["structs"]
    p0 = spec["params"][0]
    bad = {"Int": [float("nan"), 2**70, "@x", "$1", True], "Float64": [float("inf"), 2**1030, "@x", True], "List[Float64]": ["@x", "$1", [float("nan")], [2**1030]], "String": ["\ud800", 1], "Bool": [1, "@x"]}.get(p0["type"], ["@x", "$1"])
    for value in bad:
        with pytest.raises(pkg.KernelError) as exc:
            transport.normalize_value(value, p0["type"], structs, p0["name"])
        assert exc.value.code == "invalid_arguments"
        assert "args." not in exc.value.message
    assert transport.to_plain({"a": (1, 2), "b": [b"\x01"]}) == {"a": [1, 2], "b": [[1]]}
    with pytest.raises(pkg.KernelError) as exc:
        transport.normalize_arguments({spec["params"][-1]["name"]: 1} if len(spec["params"]) > 1 and spec["params"][-1]["has_default"] and spec["params"][-2]["has_default"] else {"nope": 1}, spec, structs)
    assert exc.value.code == "invalid_arguments"


@pytest.mark.skipif(not REPO_DIR, reason="HF_KERNEL_REPO_DIR not set")
def test_in_place_updates_and_engine_status_codes():
    pkg = _load_package(_cpu_variant(Path(REPO_DIR)))
    if "stats" in pkg.modules:
        a = [3.0, 1.0, 2.0]
        assert pkg.stats.fast_sort(a, 3) is None and a == [1.0, 2.0, 3.0]
        assert pkg.execute("stats", "fast_sort", [[3.0, 1.0], 2]) == {"result": None, "mutated_args": {"a": [1.0, 3.0]}}
        with pytest.raises(pkg.KernelError) as exc:
            pkg.stats.fast_sort((3.0, 1.0), 2)
        assert exc.value.code == "invalid_arguments"
    if "token_bucket" in pkg.modules:
        bucket = {"capacity": 10.0, "tokens": 5.0, "refill_rate": 1.0, "last_refill": 0.0}
        assert pkg.token_bucket.tb_consume(bucket, 1.0, 0.0) is True and bucket["tokens"] == 4.0
    if "gemm.blocked" in pkg.modules:
        with pytest.raises(pkg.KernelError) as exc:
            pkg.gemm.blocked.gemm_reference_delta_flat([1.0], [1.0] * 4, 2, 2, 2)
        assert exc.value.code == "a_length_mismatch" and exc.value.details["status"] == 322
        assert pkg.gemm.blocked.sgemm_flat([1.0, 2.0, 3.0, 4.0], [1.0, 0.0, 0.0, 1.0], 2, 2, 2, 1.0, 0.0, False, False)["c"] == [1.0, 2.0, 3.0, 4.0]
    if "normk.rmsnorm" in pkg.modules:  # ran the parallel runtime without a Mojo main: used to SIGSEGV
        out = pkg.normk.rmsnorm.rmsnorm_fwd_flat([float(i) for i in range(1, 9)], [1.0] * 4, 2, 4, 1e-6)
        assert out["n_rows"] == 2 and len(out["y"]) == 8


@pytest.mark.skipif(not REPO_DIR, reason="HF_KERNEL_REPO_DIR not set")
def test_decode_session_is_an_iterator_and_gated_on_metal(monkeypatch):
    pkg = _load_package(_cpu_variant(Path(REPO_DIR)))
    if not hasattr(pkg, "DecodeSession"):
        pytest.skip("family has no decode session")
    session_mod = sys.modules[pkg.__name__ + ".session"]
    with pytest.raises(pkg.KernelError) as exc:
        pkg.DecodeSession("/tmp/x", [1, 2], max_new_tokens=2)
    assert exc.value.code == "gpu_build_required"
    script = iter([{"session": "qd_1", "n_prompt": 2}, {"token_id": 5, "position": 3, "done": False}, {"token_id": 7, "position": 4, "done": True, "stopped_on_eos": True}, {"closed": True}])
    monkeypatch.setattr(session_mod, "_BACKEND", "metal")
    monkeypatch.setattr(session_mod, "execute", lambda request: next(script))
    with pkg.DecodeSession("/ckpt", [1, 2], max_new_tokens=2) as s:
        assert next(s) == 5
        assert s.step() == {"token_id": 7, "position": 4, "done": True, "stopped_on_eos": True}
        assert list(s) == [] and s.done
        with pytest.raises(pkg.KernelError):
            s.step()
    s.close()
    with pytest.raises(pkg.KernelError) as exc:
        s.step()
    assert exc.value.code == "session_closed"
    for bad in (("", [1], 1), ("/c", [], 1), ("/c", [1, -1], 1), ("/c", [1.5], 1), ("/c", [1], 0)):
        with pytest.raises(pkg.KernelError) as exc:
            pkg.DecodeSession(bad[0], bad[1], max_new_tokens=bad[2])
        assert exc.value.code == "invalid_arguments"


@pytest.mark.skipif(not REPO_DIR, reason="HF_KERNEL_REPO_DIR not set")
def test_vendored_count_guard_agrees_with_the_sdk_guard():
    from algenta.runtime_count_guard import enforce_count_relations as sdk_guard  # noqa: PLC0415
    from algenta.runtime_library_contract import find_runtime_function  # noqa: PLC0415
    from algenta.runtime_library_contract import RuntimeLibraryContractError  # noqa: PLC0415

    pkg = _load_package(_cpu_variant(Path(REPO_DIR)))
    transport = sys.modules[pkg.__name__ + "._transport"]
    if "stats" not in transport.CONTRACT["modules"]:
        pytest.skip("stats family not in this repo")
    cases = [("stats", "compute_mean", [[1.0, 2.0], 5]), ("stats", "compute_mean", [[1.0, 2.0], 2]), ("stats", "compute_mean", ["@u8:AQID", 4]), ("stats", "compute_mean", ["@handle", 2]), ("stats", "pctile", [[1.0, 2.0, 3.0], 9, 50])]
    for module, fn, args in cases:
        spec = transport.CONTRACT["modules"][module]["functions"][fn]
        _, sdk_fn = find_runtime_function(module, fn)
        try:
            sdk_guard(module, sdk_fn, args)
            sdk_code = None
        except RuntimeLibraryContractError as exc:
            sdk_code = exc.code
        try:
            transport.enforce_count_relations(module, spec, args)
            vendored_code = None
        except transport.KernelError as exc:
            vendored_code = exc.code
        assert sdk_code == vendored_code, (module, fn, args)


@pytest.mark.skipif(not REPO_DIR, reason="HF_KERNEL_REPO_DIR not set")
def test_card_reads_for_an_external_user():
    card = (Path(REPO_DIR) / "README.md").read_text()
    for needle in ("pip install kernels torch", "trust_remote_code=[", "## What's inside", "## Requirements", "## License", "algenta.ai/pricing", "https://docs.algenta.ai", "discord.gg/w8NDsph9an"):
        assert needle in card, needle
    for banned in ("Built from", "serialized within a process", "count relation", "Decision Engine", "thyn-ai/algenta`", "Kernels Hub"):
        assert banned not in card, banned
    assert max(len(line) for line in card.splitlines() if not line.startswith("|") and "```" not in line and not line.startswith("kernel")) <= 110


@pytest.mark.skipif(not REPO_DIR, reason="HF_KERNEL_REPO_DIR not set")
def test_loads_through_a_symlinked_hub_cache(tmp_path):
    """The Hub cache is symlinks into blobs/; the native closure must load from there (real user path)."""
    import hashlib as _h, shutil, subprocess, sys as _sys
    variant = _cpu_variant(Path(REPO_DIR))
    blobs = tmp_path / "blobs"; snap = tmp_path / "snapshots" / "abc" / "build" / variant.name
    blobs.mkdir(); snap.mkdir(parents=True)
    for p in variant.rglob("*"):
        if p.is_file():
            blob = blobs / _h.sha256(p.read_bytes()).hexdigest()
            shutil.copy2(p, blob)
            dest = snap / p.relative_to(variant); dest.parent.mkdir(parents=True, exist_ok=True)
            dest.symlink_to(os.path.relpath(blob, dest.parent))
    # Exercise a real native call through the symlinked closure without assuming any particular
    # family: load, then call the first contract function (a KernelError is fine — a crash or an
    # import/load failure is not).
    code = f"""
from pathlib import Path
from kernels import get_local_kernel
k = get_local_kernel(Path({str(snap)!r}), backend="cpu")
assert k.modules, "no modules"
mod = sorted(k.CONTRACT["modules"])[0]
fn = sorted(k.CONTRACT["modules"][mod]["functions"])[0]
try:
    k.execute(mod, fn, [])
except k.KernelError:
    pass
print("loaded", len(k.modules), "modules via symlinked cache")
"""
    r = subprocess.run([_sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-800:]


def test_card_templates_link_the_docs():
    """Every kernel card (family and umbrella) points at the docs beside Discord and pricing —
    added 2026-09-23 when the Hub started reporting downloads. Source-level so it runs without
    a generated package; the external-user card test checks the rendered card."""
    import re as _re
    root = Path(__file__).resolve().parents[1]
    for rel in ("scripts/generate_hf_kernel_package.py", "scripts/hf_kernels/generate_umbrella.py"):
        text = (root / rel).read_text()
        support = text[text.index("## Support"):]
        support = support[: support.index('"""')]
        for needle in ("https://docs.algenta.ai", "https://docs.algenta.ai/guides/kernels-on-hugging-face", "discord.gg/w8NDsph9an", "algenta.ai/pricing"):
            assert needle in support, (rel, needle)
        assert not _re.search(r"@algenta\.ai", support), rel
        assert max(len(line) for line in support.splitlines()) <= 110, rel
