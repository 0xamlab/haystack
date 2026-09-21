"""The serve entry's contract ties: what it derives, and what it must not duplicate.

`algenta serve` deliberately adds NO section to `runtime_library_contract.json`
and none to the signed runtime manifest, and the first test here pins that
decision so it stays a decision rather than becoming an omission. Both artifacts
are generated from a source scan of `mojo/engine/**.mojo`: the contract's 643
`modules` are the JSON-frameable runtime libraries and its `engine_kernels` are
the pointer-based kernels declared as capability. A CLI/SDK entry point is
neither, so writing one in by hand would create exactly the hand-maintained list
the generator exists to prevent — and would be reverted the next time anyone ran
`make inventory-refresh`.

What the entry does instead is DERIVE, and each derivation gets a test:

* the backends `--backend` accepts come from the contract's own engine-kernel
  inventory, so a backend the shipped kernel surface does not carry cannot be
  advertised, and one it starts carrying shows up without an edit;
* the model refusals are `algenta.model_capabilities`' own, byte-for-byte the
  conformance CLI's verdict for the same checkpoint, so this gate cannot drift
  into a second opinion about what the engine supports;
* the CUDA engine's output contract is read back from the driver's SOURCE, so a
  change to what the engine prints fails here instead of silently yielding an
  empty completion at a customer site;
* the driver floor is declared once, in the capability table.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_ALGENTA = ROOT / "packages" / "algenta"
for _path in (str(_ALGENTA), str(ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

CONTRACT_PATH = _ALGENTA / "algenta" / "runtime_library_contract.json"
SERVE_PACKAGE = _ALGENTA / "algenta" / "serve"
CUDA_DRIVER = ROOT / "benchmarks" / "llm_smoke" / "conform_generate_cuda.mojo"

from algenta.model_capabilities import (  # noqa: E402
    BACKEND_FACT_RANGES,
    BACKEND_HOST_REQUIREMENTS,
    verdict_for_checkpoint,
)
from algenta.runtime_library_contract import engine_kernel_backends  # noqa: E402
from algenta.serve import published_backends, serve_backends  # noqa: E402
from algenta.serve.engine import ENGINE_OUTPUT_REFUSALS  # noqa: E402
from algenta.serve.gating import model_refusals  # noqa: E402
from algenta.serve.gating import serve_backends as _gate_backends  # noqa: E402


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


# ── the contract delta is a derivation, not a new section ────────────────────


def test_the_serve_entry_adds_no_hand_maintained_section_to_the_contract() -> None:
    """The contract's top-level key set is closed and generated; this pins that
    the serve entry stayed out of it (see this module's docstring for why)."""
    assert set(_contract()) <= {
        "schema_version",
        "module_count",
        "function_count",
        "modules",
        "runtime_bundle",
        "engine_kernels",
    }
    module_names = {module["name"] for module in _contract()["modules"]}
    assert not any("serve" in name for name in module_names)


def test_the_generated_contract_is_still_current() -> None:
    """The serve entry touches no mojo source, so the generated contract must be
    byte-identical after it lands. This is the same gate
    `tests/test_algenta_runtime_library_contract.py` runs; it is repeated here so
    a serve-side change that reaches into the engine sources fails in the serve
    test file rather than in a contract test nobody expected to move."""
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/generate_algenta_runtime_contract.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert proc.returncode == 0, (proc.stderr or proc.stdout) + "\n\nRun: make inventory-refresh"


def test_serve_backends_are_the_contracts_published_engine_backends() -> None:
    """The one place a backend list appears in the serve entry is a derivation."""
    assert published_backends() == tuple(engine_kernel_backends())
    assert serve_backends() == ("auto",) + published_backends()
    assert _gate_backends() == serve_backends()
    # Both racing backends are published, so the entry advertises both.
    assert {"cuda", "metal"} <= set(published_backends())


def test_every_advertised_backend_declares_host_requirements_and_fact_ranges() -> None:
    """An advertised backend with no declared requirements would gate on nothing."""
    for backend in published_backends():
        assert backend in BACKEND_HOST_REQUIREMENTS, backend
        assert backend in BACKEND_FACT_RANGES, backend
        assert BACKEND_FACT_RANGES[backend]["families"], backend


def test_the_cuda_engine_kernels_the_entry_launches_are_the_contracts_own() -> None:
    """The entry launches the CUDA lane; the contract says the CUDA lane is real.
    Ties the advertised backend to shipped kernel count, so "cuda" cannot be
    advertised over an emptied-out inventory."""
    section = _contract()["engine_kernels"]
    assert section["backend_counts"].get("cuda", 0) > 0
    cuda_modules = {module["name"] for module in section["modules"] if module["backend"] == "cuda"}
    # The session modules the CUDA engine binary is composed of, declared in the
    # same inventory the entry derives its backend list from.
    assert any(name.startswith("residentk.session_cuda") for name in cuda_modules)
    assert any(name.startswith("residentk.kernels") for name in cuda_modules)


# ── the model gate IS the conformance CLI's verdict, not a paraphrase ────────


def test_model_refusals_are_the_conformance_verdict_verbatim(tmp_path: Path) -> None:
    checkpoint = tmp_path / "ckpt"
    checkpoint.mkdir()
    (checkpoint / "config.json").write_text(
        json.dumps(
            {
                "hidden_size": 3072,
                "num_hidden_layers": 32,
                "num_attention_heads": 32,
                "num_key_value_heads": 32,
                "head_dim": 96,
                "intermediate_size": 8192,
                "vocab_size": 32064,
                "rope_theta": 10000.0,
                "rms_norm_eps": 1e-5,
            }
        ),
        encoding="utf-8",
    )

    verdict = verdict_for_checkpoint(checkpoint, backend="cuda")
    assert verdict["status"] == "refused"
    conform_messages = [entry["message"] for entry in verdict["refusals"]]

    serve_messages = [refusal.detail for refusal in model_refusals("cuda", checkpoint)]
    assert serve_messages == conform_messages, (
        "algenta serve's model refusals drifted from the conformance CLI's; both must read "
        "from the same capability table"
    )
    assert any("head_dim=96" in message for message in serve_messages)
    assert any("{32, 64, 128, 256}" in message for message in serve_messages)


def test_the_conform_cli_and_the_serve_gate_agree_through_their_own_doors(tmp_path: Path) -> None:
    """End to end rather than by shared internals: the conform CLI's subprocess
    verdict and `algenta serve`'s gate must reach the same conclusion about the
    same file."""
    checkpoint = tmp_path / "ckpt"
    checkpoint.mkdir()
    (checkpoint / "config.json").write_text(
        json.dumps(
            {
                "hidden_size": 1024,
                "num_hidden_layers": 4,
                "num_attention_heads": 16,
                "num_key_value_heads": 8,
                "head_dim": 128,
                "intermediate_size": 3072,
                "vocab_size": 32000,
                "rope_theta": 10000.0,
                "rms_norm_eps": 1e-5,
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(ROOT / "scripts" / "algenta_conform.py"),
            str(checkpoint),
            "--backend",
            "cuda",
            "--quiet",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    # 3 = supported pending the tensor probe: a config-only checkpoint.
    assert proc.returncode == 3, proc.stdout + proc.stderr

    codes = {refusal.code for refusal in model_refusals("cuda", checkpoint)}
    assert codes == {"model_facts_unprobed"}


# ── the engine's output contract is read from the driver's own source ────────


def test_the_engine_output_literals_the_parser_keys_on_exist_in_the_driver() -> None:
    """Not a hand-maintained list of strings: each literal the parser and the
    refusal map key on must be present in the CUDA driver's source, so changing
    the engine's output breaks this test instead of silently producing an empty
    completion at a customer site."""
    assert CUDA_DRIVER.is_file(), (
        f"{CUDA_DRIVER} moved; the serve entry launches this driver's protocol — update "
        "algenta.serve.engine and this test rather than deleting either"
    )
    source = CUDA_DRIVER.read_text(encoding="utf-8")
    for literal in ("CONFORM_TOKENS:", "CONFORM_TIMING:", "CONFORM_REFUSED:"):
        assert literal in source, literal
    for literal, _code, _detail in ENGINE_OUTPUT_REFUSALS:
        if literal.startswith("CONFORM_"):
            continue
        assert literal in source, (
            f"the engine no longer prints {literal!r}; algenta.serve.engine's refusal map "
            "is keyed on it"
        )


def test_the_timing_keys_the_entry_reports_are_the_driver_own() -> None:
    """The driver prints ``" prefill_ms=", prefill_ms`` — Mojo's ``print`` joins
    its arguments with no separator, so the emitted line is
    ``prefill_ms=12.5``. Matched on the literal's tail so the leading space the
    driver bakes in cannot make this assertion miss."""
    source = CUDA_DRIVER.read_text(encoding="utf-8")
    for key in ("prefill_ms", "decode_tok_s", "n_prompt", "n_gen"):
        assert re.search(rf"{re.escape(key)}=\"\s*,", source), (
            f"the driver no longer emits {key}=; the serve entry advertises it in its timing"
        )


def test_the_driver_argv_the_entry_builds_is_the_driver_declared_usage() -> None:
    """`--max-new` is the driver's own flag name; a rename there must fail here."""
    source = CUDA_DRIVER.read_text(encoding="utf-8")
    assert '"--max-new"' in source


# ── one declaration of the driver floor ──────────────────────────────────────


def test_the_driver_floor_is_declared_once_and_only_in_the_capability_table() -> None:
    """No copy of the floor in the serve package: a refusal must name the number
    the table declares, and a second literal is how the two come apart."""
    floor = BACKEND_HOST_REQUIREMENTS["cuda"]["min_driver_version"]
    assert floor == (580, 0)
    rendered = ".".join(str(part) for part in floor)
    for path in sorted(SERVE_PACKAGE.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert rendered not in source, (
            f"{path} hardcodes the driver floor {rendered}; read it from "
            "model_capabilities.BACKEND_HOST_REQUIREMENTS instead"
        )


def test_the_declared_host_requirements_reach_the_operator_through_the_cli(capsys) -> None:
    from algenta.serve import cli as serve_cli

    assert serve_cli.main(["--backends"]) == 0
    out = capsys.readouterr().out
    assert ", ".join(published_backends()) in out
    assert "580.0" in out  # the declared CUDA driver floor, rendered from the table
    assert "7.5" in out  # the declared compute-capability floor
    for family in BACKEND_FACT_RANGES["cuda"]["families"]:
        assert family in out


# ── the entry is reachable from the shipped package surface ──────────────────


def test_the_serve_surface_is_lazily_exported_from_the_package() -> None:
    import algenta

    for name in ("ServeRequest", "ServeOutcome", "ServePlan", "ServeError", "plan_serve"):
        assert name in algenta.__all__, name
        assert getattr(algenta, name) is not None
    # Appended, never reordered: the pre-existing exports must not have moved.
    assert algenta.__all__.index("MojoRuntime") < algenta.__all__.index("plan_serve")


def test_no_top_level_export_shadows_the_serve_subpackage() -> None:
    """Regression: a lazy export named `serve` is cached onto the `algenta`
    package object over the submodule attribute the import machinery sets there,
    after which `import algenta.serve.gating` resolves `algenta.serve` to a
    FUNCTION and dies with "cannot import name 'gating' from 'serve' (unknown
    location)". The entry point is `algenta.serve.serve`, reached the same way
    `algenta.inference.decode` is."""
    import algenta

    assert "serve" not in algenta.__all__
    code = (
        "import algenta\n"
        "assert algenta.plan_serve is not None\n"  # touch the lazy exports first
        "assert algenta.ServeRequest is not None\n"
        "import algenta.serve.gating\n"  # ... then the submodule must still import
        "import algenta.serve.engine\n"
        "import algenta.serve.cli\n"
        "from algenta.serve import serve\n"
        "assert callable(serve)\n"
    )
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        env={"PYTHONPATH": os.pathsep.join([str(_ALGENTA), str(ROOT)]), "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_importing_the_package_still_probes_no_accelerator() -> None:
    """`import algenta` must not shell out to nvidia-smi or read a checkpoint —
    the whole lazy-export discipline exists so a `algenta version` costs nothing."""
    code = (
        "import subprocess, sys\n"
        "real = subprocess.run\n"
        "def guard(*args, **kwargs):\n"
        "    raise AssertionError('importing algenta spawned a subprocess: %r' % (args,))\n"
        "subprocess.run = guard\n"
        "import algenta\n"
        "from algenta import serve_backends\n"
        "assert 'cuda' in serve_backends()\n"
        "subprocess.run = real\n"
    )
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        env={"PYTHONPATH": os.pathsep.join([str(_ALGENTA), str(ROOT)]), "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
