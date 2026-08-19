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

#: The calls that make the Mojo compiler emit a GPU shader.
#:
#: `enqueue_function\w*` rather than `enqueue_function\b`, and that widening is not cosmetic: this
#: regex used to be `\benqueue_function\b`, which does NOT match `enqueue_function_unchecked` —
#: the `\b` fails against the following underscore. `residentk.session` launches exclusively
#: through the unchecked form (the only spelling whose compiled-handle type can be written down as
#: a struct field), so every one of its launches was invisible to this file until the regex was
#: widened. A guard that silently matches nothing is worse than no guard.
#:
#: `compile_function` is included for the same reason and it is the sharper case: it is not a
#: launch, but it is what actually triggers metallib generation for a kernel, so an UNGATED
#: `compile_function` breaks a shader-compiler-less build exactly as a launch does. Measured, not
#: assumed — building `mojo/tests/libs/test_residentk_session.mojo` with the flag unset but the
#: session constructor reachable failed with `Metal Compiler failed to compile metallib`, and the
#: only GPU call on that path was `compile_function_unchecked`.
_LAUNCH_CALL = re.compile(r"\b(?:enqueue_function|compile_function)\w*")
#: The compile-time branch that removes a launch before codegen. A RUNTIME `if` does not count
#: and must not match: codegen happens at compile time for anything reachable.
#:
#: The name is matched as ``*_GPU_BUILD`` rather than literally ``ACCEL_GPU_BUILD``. When this file
#: was written `accel` was the only package with a GPU launch, so the filter below also said
#: ``accel.``; `residentk` (resident decode state) is the second, and it declares its own
#: ``RESIDENT_GPU_BUILD`` off the same ``is_defined["ALGENTA_GPU"]``. A per-package constant is the
#: right shape — a package should not import a launch-containing module just to read a boolean —
#: but a test that hardcoded one package's spelling would have gone silently vacuous for the
#: second one, which is the failure mode this whole file exists to prevent.
_GPU_BUILD_GATE_NAME = re.compile(r"\b[A-Z][A-Z0-9_]*_GPU_BUILD\b")
_COMPILE_TIME_GATE = re.compile(r"@parameter\s*\n\s*if\s+(?:not\s+)?[A-Z][A-Z0-9_]*_GPU_BUILD")
#: A module-level function, i.e. one that starts in column 0.
_MODULE_FN = re.compile(r"^(?:fn|def)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE)


def _docstring_line_numbers(text: str) -> set[int]:
    """1-indexed lines that sit inside a triple-quoted string.

    These files DOCUMENT `enqueue_function` heavily — `accel/launch.mojo` spells out the launch
    idiom that "cost six attempts to find", and `residentk` records the measurement that
    `enqueue_function` BLOCKS on the Metal backend. Prose is not a call site, and a checker that
    could not tell the difference would either fire on every well-documented module or push authors
    to stop naming the thing they are documenting.

    Deliberately a triple-quote-fence toggle rather than a Mojo parser: a docstring fence appearing
    inside an ordinary single-line string literal would fool it, no such line exists in this tree,
    and a second implementation of Mojo's grammar living in a test is worse than this limitation.
    """
    inside: set[int] = set()
    open_block = False
    for number, line in enumerate(text.splitlines(), start=1):
        fences = line.count('"""')
        if open_block:
            inside.add(number)
            if fences % 2 == 1:
                open_block = False
        elif fences:
            inside.add(number)
            if fences % 2 == 1:
                open_block = True
    return inside


def _code_only(text: str) -> str:
    """`text` with every docstring line and every whole-line `#` comment blanked.

    Line NUMBERS are preserved — blanked lines become empty rather than disappearing — because the
    callers report the line a violation sits on and an off-by-N there would send a reader to the
    wrong place.

    Whole-line comments only. A trailing `#` comment on a line of real code is left alone: cutting
    at the first `#` would also cut one inside a string literal, and a line that both launches a
    kernel and talks about launching one is a launch either way.
    """
    docs = _docstring_line_numbers(text)
    kept: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if number in docs or line.lstrip().startswith("#"):
            kept.append("")
        else:
            kept.append(line)
    return "\n".join(kept)


def _module_level_functions(path: Path) -> list[str]:
    return _MODULE_FN.findall(path.read_text(encoding="utf-8"))


def _launching_helpers(text: str) -> set[str]:
    """Names of module-level functions in `text` whose body contains a launch."""
    lines = _code_only(text).splitlines()
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
    """1-indexed lines that sit inside a `@parameter if ...<PKG>_GPU_BUILD` block.

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
            if _GPU_BUILD_GATE_NAME.search(head) and head.strip().startswith("if "):
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
    assert _LAUNCH_CALL.search(_code_only(launch.read_text(encoding="utf-8"))), (
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
    }
    assert exposed, "nothing is exposed through the contract; this test would pass vacuously"
    # The property is about the CONTRACT, not about one package. Restricting this to `accel.` (as it
    # originally was) meant a second package with a GPU launch would be invisible here — and
    # `residentk` is that second package. Every contract-reachable module in the tree is checked.
    assert any(path.startswith("accel.") for path in exposed), (
        "accel vanished from the contract; this test lost the case it was written for"
    )

    ungated: dict[str, str] = {}
    for import_path, path in exposed.items():
        raw = path.read_text(encoding="utf-8")
        text = _code_only(raw)
        if not _LAUNCH_CALL.search(text):
            continue

        gated_lines = _gated_line_numbers(raw)
        helpers = _launching_helpers(raw)
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
        "`@parameter if <PKG>_GPU_BUILD:`."
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
    assert not _LAUNCH_CALL.search(_code_only(text)), "accel/device.mojo must not launch a kernel"

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


# ─────────────────────────────────────────────────────────────────────────────
# residentk — the SECOND package with GPU launches, and the first to prove the
# generalisations above are load-bearing rather than decorative.
# ─────────────────────────────────────────────────────────────────────────────

RESIDENTK = ENGINE / "residentk"


def test_residentk_launch_modules_export_nothing_public() -> None:
    """`residentk.kernels` and `residentk.session` follow `accel/launch.mojo`'s rule exactly.

    Both contain `enqueue_function`. Neither may export a public name: the generated dispatch calls
    every public function of every contract module, so one missing underscore would put a resident
    GPU session in the worker's call graph and every build host would need a Metal compiler.
    """
    assert RESIDENTK.is_dir(), "residentk/ moved; update this test rather than deleting it"
    for name in ("kernels.mojo", "session.mojo"):
        path = RESIDENTK / name
        assert path.is_file(), f"residentk/{name} moved; update this test rather than deleting it"
        public = [fn for fn in _module_level_functions(path) if not fn.startswith("_")]
        assert not public, (
            f"residentk/{name} exports {public} publicly. Public functions enter the runtime "
            "contract, so the generated dispatch would import and call them — putting a GPU launch "
            "in its call graph and making every build host require a shader compiler. Prefix with "
            "an underscore."
        )


def test_the_residentk_launch_modules_still_contain_a_launch() -> None:
    """The guard above is only meaningful while there is something to guard."""
    launching = [
        name
        for name in ("kernels.mojo", "session.mojo")
        if _LAUNCH_CALL.search(_code_only((RESIDENTK / name).read_text(encoding="utf-8")))
    ]
    assert launching, (
        "neither residentk/kernels.mojo nor residentk/session.mojo launches a kernel any more, so "
        "the isolation test above proves nothing. Either restore the launch or retire both tests "
        "deliberately."
    )


def test_residentk_launch_modules_are_absent_from_the_contract() -> None:
    """Stated as its own assertion because it is the property, not an implementation detail."""
    paths = {m.import_path for m in discover_runtime_library_modules(ENGINE)}
    assert "residentk.session" not in paths
    assert "residentk.kernels" not in paths
    # ...while the CPU-side modules ARE exposed. Without this half, deleting residentk entirely
    # would pass every assertion in this file.
    assert "residentk.contract" in paths
    assert "residentk.probe" in paths


def test_residentk_session_gates_every_launch_at_compile_time() -> None:
    """Belt AND braces: private is the first defence, the compile-time gate is the second.

    `residentk.session` is not contract-reachable, so `test_every_contract_reachable_launch_is_...`
    does not reach it. That is exactly why this is asserted separately: the day someone makes it
    reachable, the gate has to already be there.
    """
    raw = (RESIDENTK / "session.mojo").read_text(encoding="utf-8")
    gated = _gated_line_numbers(raw)
    ungated = [
        number
        for number, line in enumerate(_code_only(raw).splitlines(), start=1)
        if "enqueue_function" in line and number not in gated
    ]
    assert not ungated, (
        f"residentk/session.mojo launches a kernel ungated at line(s) {ungated}. With "
        "-D ALGENTA_GPU unset the launch must be removed BEFORE shader codegen, or a host with no "
        "Metal compiler cannot build the file at all. Wrap it in `@parameter if RESIDENT_GPU_BUILD:`."
    )


def test_the_resident_session_is_only_ever_constructed_behind_the_gate() -> None:
    """The one GPU call in `residentk` that CANNOT carry its own gate, guarded at its call sites.

    `_ResidentQwen3.__init__` opens a `DeviceContext` and calls `compile_function_unchecked` eight
    times. A constructor cannot open with `@parameter if not RESIDENT_GPU_BUILD: return <status>` —
    it has to initialise every field, and there is no Float32 stand-in for a `DeviceContext`. So the
    protection is structural: the struct is constructed ONLY from inside a
    `@parameter if RESIDENT_GPU_BUILD` branch, and on a build without the flag the constructor is
    therefore never elaborated.

    THIS IS NOT HYPOTHETICAL. `mojo/tests/libs/test_residentk_session.mojo` was first written with
    the GPU section after an early `return` inside the parameter branch rather than inside its
    `else:`. An early return does not prune what follows it, so the constructor stayed reachable,
    and the default build failed with `Metal Compiler failed to compile metallib` — the exact
    whole-CI failure this file exists to prevent, reproduced in the change that added the second GPU
    package. One `else:` was the fix, and nothing but this assertion would catch it recurring.

    `compile_function`, not just `enqueue_function`, is what triggers metallib generation. That is
    the measured lesson from the same failure: there was no launch on the reachable path at all.
    """
    root = ENGINE.parents[1]
    sites: list[str] = []
    for path in sorted(root.glob("**/*.mojo")):
        if "residentk/session.mojo" in path.as_posix():
            continue
        raw = path.read_text(encoding="utf-8")
        if "_ResidentQwen3(" not in raw:
            continue
        gated = _gated_line_numbers(raw)
        for number, line in enumerate(_code_only(raw).splitlines(), start=1):
            if "_ResidentQwen3(" in line and number not in gated:
                sites.append(f"{path.relative_to(root)}:{number}")
    assert not sites, (
        f"{sites} construct a resident GPU session outside a `@parameter if RESIDENT_GPU_BUILD` "
        "block. The constructor compiles eight Metal shaders, so every build host would need a "
        "shader compiler. Note that an early `return` inside the parameter branch does NOT prune "
        "what follows it — the construction must sit inside the branch's `else:`."
    )


def test_qwen3_decode_constructs_the_gpu_struct_only_behind_the_gate() -> None:
    """`metaldispatch.qwen3_decode` is the FIRST public, contract-reachable entry point that
    constructs a `metaldispatch.session` GPU struct (`_MBQwen3I8AllSimd7`) directly — `accel.
    gemm_metal`'s public functions launch through a private helper instead (pattern (b) above), and
    `residentk.session`'s own struct is never contract-reachable at all. So this file's own gate is
    asserted directly rather than only by the general contract-wide sweep: a missed gate here is not
    only a GPU-less build failure, it is THE one new capability this task added.
    """
    path = ENGINE / "metaldispatch" / "qwen3_decode.mojo"
    assert path.is_file(), "metaldispatch/qwen3_decode.mojo moved; update this test rather than deleting it"
    raw = path.read_text(encoding="utf-8")
    assert "_MBQwen3I8AllSimd7(" in _code_only(raw), (
        "metaldispatch/qwen3_decode.mojo no longer constructs _MBQwen3I8AllSimd7; the isolation "
        "check below proves nothing. Either restore the construction or retire this test deliberately."
    )
    gated = _gated_line_numbers(raw)
    ungated = [
        number
        for number, line in enumerate(_code_only(raw).splitlines(), start=1)
        if "_MBQwen3I8AllSimd7(" in line and number not in gated
    ]
    assert not ungated, (
        f"metaldispatch/qwen3_decode.mojo constructs _MBQwen3I8AllSimd7 outside a `@parameter if "
        f"MB_GPU_BUILD` block at line(s) {ungated}. That constructor compiles eight Metal shaders, "
        "so every build host — including every Linux CI runner — would need a shader compiler."
    )
    assert "metaldispatch.qwen3_decode" in {
        module.import_path for module in discover_runtime_library_modules(ENGINE)
    }, "metaldispatch.qwen3_decode is no longer contract-reachable; this test's premise is gone"


def test_every_gpu_build_gate_keys_off_the_same_define() -> None:
    """The GPU build flag scheme has TWO tiers, and each tier must stay unfragmented.

    Tier 1 — `-D ALGENTA_GPU`: the portable GPU kernels. One flag turns them on for the whole
    tree. Each package declares its own `<PKG>_GPU_BUILD` constant rather than importing another
    package's — importing `accel.gemm_metal` merely to read a boolean would drag a launch-containing
    module onto the importer's graph for no benefit. The cost of that choice is that the constants
    can drift apart, producing a binary with a Metal GEMM but no Metal decode, which nobody would
    ever want and nothing else would catch. So it is asserted.

    Tier 2 — backend selectors on top of tier 1. A GPU build is never "GPU" in the abstract; it is
    compiled for ONE backend, and the define says which:
      * Metal build = `-D ALGENTA_GPU -D ALGENTA_METAL`
      * CUDA build  = `-D ALGENTA_GPU -D ALGENTA_CUDA`
      * CPU build   = neither
    `ALGENTA_METAL` gates the metaldispatch shim machinery specifically: `metaldispatch.ffi`
    `external_call`s into the Objective-C batched-dispatch shim, and those calls are undefined
    symbols at LINK time when the shim object is not linked (ffi.mojo's own contract says so). A
    CUDA build has `ALGENTA_GPU` on but no shim in the link, so the metaldispatch gate must
    require MORE than `ALGENTA_GPU` — it conjuncts `ALGENTA_METAL`. `ALGENTA_CUDA` selects the
    backend answer `accel.device.accel_device_probe` reports.
    """
    declarations = {
        "accel/gemm_metal.mojo": "ACCEL_GPU_BUILD",
        "residentk/probe.mojo": "RESIDENT_GPU_BUILD",
        "residentk/session.mojo": "RESIDENT_GPU_BUILD",
    }
    for relative, constant in declarations.items():
        text = (ENGINE / relative).read_text(encoding="utf-8")
        assert f'{constant}: Bool = is_defined["ALGENTA_GPU"]()' in text, (
            f"{relative} no longer declares {constant} off is_defined[\"ALGENTA_GPU\"]; the GPU "
            "build flag has fragmented and a binary can now have some GPU kernels but not others"
        )

    # The metaldispatch gate is tier 2: it must require the METAL define in addition to the
    # portable-kernel tier, or a CUDA build (GPU on, shim absent) dies at link time on the shim's
    # undefined symbols — the exact failure the define split exists to prevent.
    metal_session = (ENGINE / "metaldispatch" / "session.mojo").read_text(encoding="utf-8")
    assert (
        'comptime MB_GPU_BUILD: Bool = RESIDENT_GPU_BUILD and is_defined["ALGENTA_METAL"]()'
        in metal_session
    ), (
        "metaldispatch/session.mojo's MB_GPU_BUILD no longer conjuncts RESIDENT_GPU_BUILD with "
        'is_defined["ALGENTA_METAL"]. The Metal batched-dispatch shim is linked only into Metal '
        "builds; gating this package on ALGENTA_GPU alone makes a CUDA build (GPU kernels on, no "
        "shim) fail at LINK time with undefined algenta_* symbols."
    )

    # The backend selector: a CUDA build must answer ACCEL_BACKEND_CUDA from the define, and the
    # Metal answer must remain the default for every other accelerator build.
    device = (ENGINE / "accel" / "device.mojo").read_text(encoding="utf-8")
    assert 'is_defined["ALGENTA_CUDA"]()' in device, (
        "accel/device.mojo no longer discriminates the CUDA backend off is_defined[\"ALGENTA_CUDA\"]"
    )
    assert "ACCEL_BACKEND_CUDA" in device and "ACCEL_BACKEND_METAL" in device, (
        "accel/device.mojo lost one of its backend answers"
    )

    # The build script is where the tier combinations are actually formed. Assert the exact
    # pairings so a knob edit cannot silently ship a GPU build with no backend selector (or a
    # backend selector with no GPU tier).
    build_script = (ENGINE.parents[1] / "scripts" / "build_mojo_binary.sh").read_text(
        encoding="utf-8"
    )
    assert "-D ALGENTA_GPU -D ALGENTA_METAL" in build_script, (
        "scripts/build_mojo_binary.sh no longer passes BOTH -D ALGENTA_GPU and -D ALGENTA_METAL "
        "for a Metal build; metaldispatch would compile out of every Metal binary"
    )
    assert "-D ALGENTA_GPU -D ALGENTA_CUDA" in build_script, (
        "scripts/build_mojo_binary.sh no longer passes BOTH -D ALGENTA_GPU and -D ALGENTA_CUDA "
        "for a CUDA build; the portable GPU kernels would compile out of every CUDA binary"
    )
