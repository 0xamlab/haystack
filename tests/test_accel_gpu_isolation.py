"""The GPU package must not put a kernel launch into the generated runtime dispatch.

WHY THIS EXISTS
===============

Mojo triggers GPU shader codegen from a statically REACHABLE launch site, at COMPILE time. Measured
on a host with no Metal shader compiler by building the same module three ways:

* a caller that reaches a launch          -> ``Metal Compiler failed to compile metallib``, build fails
* a caller that imports only a CPU function from the SAME module that imports ``std.gpu``
  and defines a kernel                    -> builds
* constructing a ``DeviceContext`` and reading ``.name()``, never launching
                                          -> builds and runs

So codegen follows the call graph, not the import graph. That is what lets ``accel.contract`` and
``accel.device`` be ordinary contract modules — a caller on any host can ask "is there an
accelerator" — while the kernels live in the same package.

The rule it imposes: **every launch entry point in ``accel/launch.mojo`` is private**. The generated
dispatch imports and calls every PUBLIC function of every contract module, so one public launch
function would put a launch site in the dispatch's call graph and every build host without a shader
compiler would start requiring one. That includes Linux CI, which has neither a compiler nor a GPU.

Making a launch function public is a one-character change with a whole-CI consequence, and nothing
about it looks dangerous while you are writing it. Hence this test, which runs everywhere rather than
only where a GPU exists.
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
#: A module-level function, i.e. one that starts in column 0.
_MODULE_FN = re.compile(r"^(?:fn|def)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE)


def _module_level_functions(path: Path) -> list[str]:
    return _MODULE_FN.findall(path.read_text(encoding="utf-8"))


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


def test_contract_exposed_accel_modules_never_launch() -> None:
    """Whatever accel exposes through the contract must be reachable without a shader compiler."""
    exposed = {
        module.import_path: module.path
        for module in discover_runtime_library_modules(ENGINE)
        if module.import_path.startswith("accel.")
    }
    assert exposed, "accel exposes nothing through the contract; this test would pass vacuously"

    offenders = {
        import_path: path.name
        for import_path, path in exposed.items()
        if _LAUNCH_CALL.search(path.read_text(encoding="utf-8"))
    }
    assert not offenders, (
        f"{offenders} are reachable from the generated dispatch AND launch a GPU kernel. "
        "A build host without a shader compiler cannot compile that."
    )


def test_launch_module_is_absent_from_the_contract() -> None:
    """Stated as its own assertion because it is the property, not an implementation detail."""
    paths = {m.import_path for m in discover_runtime_library_modules(ENGINE)}
    assert "accel.launch" not in paths
    # ...while the CPU-side modules ARE exposed. Without this half, deleting accel entirely
    # would pass every assertion in this file.
    assert "accel.contract" in paths
    assert "accel.device" in paths


def test_generated_dispatch_contains_no_gpu_launch() -> None:
    """The end state, checked against the artifact that actually ships."""
    if not DISPATCH.is_file():
        pytest.skip("generated dispatch not present")
    text = DISPATCH.read_text(encoding="utf-8")
    assert "accel.launch" not in text
    assert not _LAUNCH_CALL.search(text), (
        "the generated dispatch contains a GPU launch call; every build host now needs a "
        "shader compiler"
    )


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
