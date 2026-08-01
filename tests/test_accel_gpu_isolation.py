"""A GPU launch must never be reachable from the default build of the worker.

WHY THIS EXISTS
===============

Mojo triggers GPU shader codegen from a statically REACHABLE launch site, at COMPILE time. Measured
on a host with no Metal shader compiler by building the same module three ways:

* a caller that reaches a launch          -> ``Metal Compiler failed to compile metallib``, build fails
* a caller that imports only a CPU function from the SAME module that imports ``std.gpu``
  and defines a kernel                    -> builds
* constructing a ``DeviceContext`` and reading ``.name()``, never launching
                                          -> builds and runs

So codegen follows the CALL GRAPH, not the import graph. There are two ways to keep a launch out of
that graph, and this file guards both because ``accel`` uses both:

1. **Private.** ``accel/launch.mojo`` exports nothing public, so the generated dispatch — which calls
   every public function of every contract module — never reaches it.
2. **Compile-time gated.** ``accel/gemm_metal.mojo`` IS contract-reachable and DOES launch a kernel.
   That is safe because the launch sits inside ``@parameter if ACCEL_GPU_BUILD``, keyed off
   ``is_defined["ALGENTA_GPU"]``. With the flag unset the branch is removed before codegen runs, so
   the default build has no launch site at all and reports ``shader_toolchain_absent`` at runtime.

A RUNTIME ``if`` satisfies neither. ``if gpu_available():`` around a launch still leaves the launch
reachable, so codegen still happens and the build still needs a compiler. That distinction is why
these tests inspect the gate rather than merely checking that something guards the call.

Either mistake is a one-character change with a whole-CI consequence — Linux runners have neither a
shader compiler nor a GPU — and neither looks dangerous while you are writing it. Hence this file,
which runs everywhere rather than only where a GPU exists.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from apps.runtime.mojo_inventory import discover_runtime_library_modules

ENGINE = Path(__file__).resolve().parents[1] / "mojo" / "engine"
ACCEL = ENGINE / "accel"
DISPATCH = ENGINE / "runtime_library_dispatch_generated.mojo"

#: The one call that makes the Mojo compiler emit a GPU shader.
_LAUNCH_CALL = re.compile(r"\benqueue_function\b")
#: The compile-time branch that removes a launch before codegen. A RUNTIME `if` does not count
#: and must not match: codegen happens at compile time for anything reachable.
_COMPILE_TIME_GATE = re.compile(r"@parameter\s*\n\s*if\s+(?:not\s+)?ACCEL_GPU_BUILD")
#: A module-level function, i.e. one that starts in column 0.
_MODULE_FN = re.compile(r"^(?:fn|def)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE)


def _module_level_functions(path: Path) -> list[str]:
    return _MODULE_FN.findall(path.read_text(encoding="utf-8"))


def _launching_helpers(text: str) -> set[str]:
    """Names of module-level functions in `text` whose body contains a launch."""
    lines = text.splitlines()
    current: str | None = None
    launching: set[str] = set()
    for line in lines:
        header = _MODULE_FN.match(line)
        if header is not None:
            current = header.group(1)
        elif line and not line[0].isspace() and not line.startswith(("#", '"', "'", ")", "]")):
            current = None
        if current is not None and _LAUNCH_CALL.search(line):
            launching.add(current)
    return launching


def _gated_line_numbers(text: str) -> set[int]:
    """1-indexed lines that sit inside a `@parameter if ...ACCEL_GPU_BUILD` block.

    Indentation-based, which is enough here and deliberately simple: a real parser would be a second
    implementation of Mojo's grammar living in a test, and the thing being guarded is one specific
    idiom rather than the language.
    """
    lines = text.splitlines()
    gated: set[int] = set()
    i = 0
    while i < len(lines):
        if lines[i].strip() == "@parameter" and i + 1 < len(lines):
            head = lines[i + 1]
            if "ACCEL_GPU_BUILD" in head and head.strip().startswith("if "):
                indent = len(head) - len(head.lstrip(" "))
                j = i + 2
                while j < len(lines):
                    body = lines[j]
                    if body.strip():
                        body_indent = len(body) - len(body.lstrip(" "))
                        if body_indent <= indent and not body.strip().startswith(("else", "elif")):
                            break
                    gated.add(j + 1)
                    j += 1
                i = j
                continue
        i += 1
    return gated


def test_launch_module_exports_nothing_public() -> None:
    """THE REGRESSION GUARD. A public name here reaches the dispatch and breaks GPU-less builds."""
    assert ACCEL.is_dir(), "accel/ moved; update this test rather than deleting it"
    launch = ACCEL / "launch.mojo"
    assert launch.is_file(), "accel/launch.mojo moved; update this test rather than deleting it"

    public = [name for name in _module_level_functions(launch) if not name.startswith("_")]
    assert not public, (
        f"accel/launch.mojo exports {public} publicly. Public functions enter the runtime "
        "contract, so the generated dispatch would import and call them — putting a GPU launch "
        "in its call graph and making every build host require a shader compiler. Prefix with "
        "an underscore."
    )


def test_the_launch_module_still_contains_a_launch() -> None:
    """The guard above is only meaningful while there is something to guard."""
    launch = ACCEL / "launch.mojo"
    assert _LAUNCH_CALL.search(launch.read_text(encoding="utf-8")), (
        "accel/launch.mojo no longer launches a kernel, so the isolation test above proves "
        "nothing. Either restore the launch or retire both tests deliberately."
    )


def test_every_contract_reachable_launch_is_compile_time_gated() -> None:
    """THE REGRESSION GUARD, in its general form.

    A contract-exposed module MAY contain a GPU launch — `accel.gemm_metal` does, so a Metal kernel
    is an ordinary runtime-library call rather than something only a benchmark can reach. What makes
    that safe is that the launch sits behind ``@parameter if ACCEL_GPU_BUILD``, a COMPILE-TIME branch
    on ``is_defined["ALGENTA_GPU"]``. With the flag unset the branch is removed before shader codegen
    runs, so a host with no shader compiler still builds the file.

    A runtime ``if`` would NOT do this. Codegen happens at compile time for anything reachable, so
    ``if gpu_available():`` around a launch still forces a shader compiler. That distinction is the
    whole reason this test inspects the gate rather than merely checking that some condition guards
    the call.
    """
    exposed = {
        module.import_path: module.path
        for module in discover_runtime_library_modules(ENGINE)
        if module.import_path.startswith("accel.")
    }
    assert exposed, "accel exposes nothing through the contract; this test would pass vacuously"

    ungated: dict[str, str] = {}
    for import_path, path in exposed.items():
        text = path.read_text(encoding="utf-8")
        if not _LAUNCH_CALL.search(text):
            continue

        gated_lines = _gated_line_numbers(text)
        helpers = _launching_helpers(text)
        lines = text.splitlines()

        # A launch is safe under EITHER pattern:
        #   (a) the launch itself sits inside the compile-time block, or
        #   (b) it sits in a private helper whose every call site is inside the block.
        # `accel.gemm_metal` uses (b) — the launch lives in `_run_metal_gemm` and the public entry
        # gates the call — because a `raises` helper is easier to read than a launch nested three
        # levels inside a parameter branch. Both are checked; neither is assumed.
        reached_ungated: set[str] = set()
        for number, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "fn ", "def ")):
                continue
            if number in gated_lines:
                continue
            for helper_name in helpers:
                if f"{helper_name}(" in line:
                    reached_ungated.add(helper_name)
                    ungated[import_path] = f"{path.name}:{number} calls {helper_name} ungated"

        # A raw launch line is only a problem when its enclosing helper is ALSO reachable ungated.
        # Otherwise the gate is at the call site, which is pattern (b) and is exactly as safe.
        current: str | None = None
        for number, line in enumerate(lines, start=1):
            header = _MODULE_FN.match(line)
            if header is not None:
                current = header.group(1)
            elif line and not line[0].isspace() and not line.startswith(("#", '"', "'", ")", "]")):
                current = None
            if not _LAUNCH_CALL.search(line) or number in gated_lines:
                continue
            if current is None or current in reached_ungated:
                ungated[import_path] = f"{path.name}:{number} launches with no gate on any path"

    assert not ungated, (
        f"{ungated} are reachable from the generated dispatch and launch a GPU kernel without a "
        "compile-time gate. Every build host would need a shader compiler. Wrap the launch in "
        "`@parameter if ACCEL_GPU_BUILD:`."
    )


def test_the_gate_defaults_to_off() -> None:
    """The flag must be opt-IN. A default-on gate protects nothing."""
    gemm = ACCEL / "gemm_metal.mojo"
    text = gemm.read_text(encoding="utf-8")
    assert 'is_defined["ALGENTA_GPU"]' in text, (
        "the GPU build flag was renamed or removed; the gate no longer keys off an explicit define"
    )
    # `is_defined` is false unless `-D ALGENTA_GPU` is passed, so absence of a default is the point.
    assert "ACCEL_GPU_BUILD: Bool = is_defined" in text


def test_a_gated_module_still_reports_honestly_when_off() -> None:
    """Compiled out is not the same as pretending to work.

    With the kernels elided the module must return a status saying so, not silently fall back to a
    CPU path — `accel.contract.accel_resolve` is where a caller opts into a fallback, and a kernel
    that substituted one quietly would defeat it.
    """
    gemm = (ACCEL / "gemm_metal.mojo").read_text(encoding="utf-8")
    assert "ACCEL_ERR_SHADER_TOOLCHAIN_ABSENT" in gemm, (
        "the GPU-less path no longer reports the toolchain as absent"
    )
    assert "sgemm_flat" in gemm, "the CPU kernel import vanished; agreement can no longer be measured"


def test_launch_module_is_absent_from_the_contract() -> None:
    """Stated as its own assertion because it is the property, not an implementation detail."""
    paths = {m.import_path for m in discover_runtime_library_modules(ENGINE)}
    assert "accel.launch" not in paths
    # ...while the CPU-side modules ARE exposed. Without this half, deleting accel entirely
    # would pass every assertion in this file.
    assert "accel.contract" in paths
    assert "accel.device" in paths


def test_generated_dispatch_only_reaches_gated_launches() -> None:
    """The end state, checked against the artifact that actually ships.

    The dispatch is allowed to import a module containing a launch — that is how a Metal GEMM became
    callable — but every such launch must be behind the compile-time gate, or the default build of
    the worker would need a shader compiler.
    """
    if not DISPATCH.is_file():
        pytest.skip("generated dispatch not present")
    text = DISPATCH.read_text(encoding="utf-8")

    # The dispatch itself never writes a launch; it only calls into modules.
    assert not _LAUNCH_CALL.search(text), (
        "the generated dispatch contains a launch call directly, which no gate can protect"
    )
    assert "accel.launch" not in text, "the ungated launch module leaked into the dispatch"


def test_device_module_may_import_gpu_without_launching() -> None:
    """The measured fact this whole layout rests on, pinned so a future reader does not undo it.

    `accel/device.mojo` imports `std.gpu` and constructs a `DeviceContext`. That is deliberate and
    safe. If someone "tidies" it by moving the import out, the capability query stops working; if
    someone adds a launch to it, GPU-less builds break. Both directions are asserted.
    """
    device = ACCEL / "device.mojo"
    text = device.read_text(encoding="utf-8")
    assert "std.gpu" in text, "accel/device.mojo no longer queries the GPU at all"
    assert not _LAUNCH_CALL.search(text), "accel/device.mojo must not launch a kernel"

def test_the_gpu_gemm_is_reachable_through_the_generated_dispatch() -> None:
    """The positive half: gating the launch must not have made the kernel uncallable.

    Everything else in this file checks that a launch cannot break a GPU-less build. That is only
    half the requirement — a module that was simply excluded would pass all of it. This asserts the
    GEMM is actually wired into the dispatch, which is what makes it batch-dispatchable through the
    existing `batch_execute` frame with no new message type and no SDK code.

    Checked here rather than only in the benchmark because the benchmark imports the monolithic
    dispatch, which currently costs ~19 GB and half an hour to compile. A property that important
    should be asserted by something that runs.
    """
    if not DISPATCH.is_file():
        pytest.skip("generated dispatch not present")
    text = DISPATCH.read_text(encoding="utf-8")
    for fn in ("gemm_metal_flat", "gemm_metal_available", "gemm_metal_agreement"):
        assert f"gemm_metal import" in text or fn in text, (
            f"{fn} is not reachable from the generated dispatch; the GPU GEMM is not callable"
        )
    assert "accel.gemm_metal" in text, "the GPU GEMM module is not imported by the dispatch"
