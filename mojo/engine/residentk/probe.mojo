"""
residentk.probe — can this binary, on this host, hold a resident GPU decode session? Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: int
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_residentk_session.mojo
benchmark: benchmarks/llm_smoke/qwen3_generate_metal.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

This module does not import `std.gpu` at all
-----------------------------------------------
`accel.device` already answers "is there an accelerator, and can it be opened", behind its own
`ACCEL_DEVICE_QUERY_COMPILED` compile-time gate that keeps a `DeviceContext` from being ELABORATED
on a target with no accelerator. Opening a second device query here would be a second copy of that
gate — and rule 3's own worked example is a guard duplicated at two different strengths reading as
defence-in-depth while providing one arbitrary behaviour per call site. So this module CALLS
`accel_device_probe()` and adds only the facts `accel` cannot know: whether GPU kernels were
compiled into this binary, and what a session at a given shape would cost.

The consequence is that `residentk` reaches the runtime contract with no GPU import anywhere on the
contract-reachable path. `residentk.kernels` and `residentk.session` are private, are not contract
modules, and are the only files in this package that import `std.gpu`.

Three states, not two — inherited, not re-invented
-----------------------------------------------------
`accel.device`'s three states (no device / device present but not usable / usable) are exactly the
states that matter here too, and a fourth is added by this package: **built without kernels**. A
binary compiled without `-D ALGENTA_GPU` has no shader in it at all, so it cannot run a session on
ANY host — that is a build fact, reported separately from the deployment fact of whether a device
is present, because a caller acts on each differently.

Public API:
  resident_available()                                                  -> Bool
  resident_gpu_kernels_compiled()                                       -> Bool
  resident_session_probe(d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab) -> ResidentProbe
"""

from std.sys import is_defined
from accel.device import accel_device_probe
from residentk.contract import (
    RESIDENT_ERR_NO_DEVICE,
    RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT,
    RESIDENT_MAX_LAYERS,
    RESIDENT_MAX_VOCAB,
    RESIDENT_OK,
    residentk_dims_check,
    residentk_dispatch_budget,
    residentk_weight_elems,
)
# `RESIDENT_MAX_LAYERS` and `RESIDENT_MAX_VOCAB` are imported for their DECLARATION, not their
# value: `resident_session_probe`'s `counts:` block names them as ceilings, and
# `apps/runtime/mojo_capability_manifest.py` resolves such a name only in this file or in a module
# this file imports it from. Writing the literals instead would let the declaration drift away from
# the constant `residentk.contract` actually tests against — which is precisely what naming the
# constant exists to prevent. (A comment, not a docstring: Mojo rejects a bare string expression at
# global scope, which is only reported when a module is COMPILED rather than merely imported.)

comptime RESIDENT_GPU_BUILD: Bool = is_defined["ALGENTA_GPU"]()
"""Whether this binary was built with `mojo build -D ALGENTA_GPU`.

The SAME define `accel.gemm_metal.ACCEL_GPU_BUILD` keys off, deliberately: one flag turns GPU
kernels on for the whole tree, so a caller never has to reason about a binary that has Metal GEMM
but not Metal decode. Declared as its own constant rather than imported from `accel.gemm_metal`
because importing that module here would drag a launch-containing module onto this module's import
graph for no benefit — the value is one `is_defined` call, and
`tests/test_accel_gpu_isolation.py::test_every_gpu_build_gate_keys_off_the_same_define` asserts the
two constants stay in agreement.

Unset by default ON PURPOSE. The default build must work on a host with no shader compiler, which
is every Linux CI runner in this project."""


@fieldwise_init
struct ResidentProbe(Copyable, Movable):
    """What a resident decode session would cost on this host, and whether it could run at all.

    Declared here rather than reusing `accel.device.DeviceProbe` because
    `apps/runtime/mojo_inventory.py` parses struct specs ONE FILE AT A TIME: a public function
    returning a struct owned by another module is silently dropped from the contract and the
    dispatch, with no error anywhere (rule 2). The overlap with `DeviceProbe` is two boolean fields
    and is worth less than the function existing.

    `dispatch_budget` and `resident_f32_elems` are answered on EVERY host, GPU or not, because they
    are arithmetic about the design rather than measurements of the machine — a caller sizing a
    deployment wants them from a laptop."""

    var kernels_compiled: Bool
    var device_present: Bool
    var session_possible: Bool
    var dispatch_budget: Int
    var resident_f32_elems: Int
    var status: Int


def resident_gpu_kernels_compiled() -> Bool:
    """True when this binary was built with `-D ALGENTA_GPU`.

    A build fact, not a host fact: it is the same answer on every machine the binary is copied to.
    Kept separate from `resident_available()` so a deployment can distinguish "we shipped the wrong
    binary" from "we shipped it to the wrong machine".

    @capability resident_gpu_kernels_compiled
    complexity: O(1)
    @endcapability
    """
    return RESIDENT_GPU_BUILD


def resident_available() -> Bool:
    """True when this binary can actually open a resident GPU decode session on this host.

    Both conditions are necessary and they fail independently: the binary must have been BUILT with
    GPU kernels compiled in, and the host must HAVE an openable accelerator.

    @capability resident_available
    complexity: O(1)
    @endcapability
    """

    @parameter
    if not RESIDENT_GPU_BUILD:
        return False
    var probe = accel_device_probe()
    return probe.device_present and probe.name_length > 0


def resident_session_probe(
    d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int, n_layers: Int, vocab: Int
) -> ResidentProbe:
    """The full answer for one model shape: could a session hold it here, and what would it cost.

    `status` distinguishes the three refusals a caller can act on — the shape is unsupported
    (a modelling fact), the binary has no kernels (a build fact), the host has no device (a
    deployment fact) — rather than collapsing them into one boolean.

    Never launches anything, on any path. See the module docstring.

    @capability resident_session_probe
    complexity: O(1)
    counts:
    - dim n_layers <= RESIDENT_MAX_LAYERS [kernel_validated]
    - dim vocab <= RESIDENT_MAX_VOCAB [kernel_validated]
    @endcapability
    """
    var shape = residentk_dims_check(d_model, h_q, h_kv, d_head, d_ff)
    var budget = residentk_dispatch_budget(n_layers)
    var elems = residentk_weight_elems(d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab)

    if shape != RESIDENT_OK or budget <= 0 or elems <= 0:
        # A shape refusal is reported before any host question is asked: it is true everywhere, and
        # answering "no device" for a model that would not fit anyway would send a reader hunting
        # for hardware that could not have helped.
        var bad = shape if shape != RESIDENT_OK else RESIDENT_ERR_NO_DEVICE
        return ResidentProbe(RESIDENT_GPU_BUILD, False, False, 0, 0, bad)

    @parameter
    if not RESIDENT_GPU_BUILD:
        # No kernels in this binary. True on every host it is ever copied to, so this is the only
        # answer such a binary can truthfully give — not a stub for CI's comfort.
        return ResidentProbe(
            False, False, False, budget, elems, RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT
        )

    var dev = accel_device_probe()
    var usable = dev.device_present and dev.name_length > 0
    if not usable:
        return ResidentProbe(True, dev.device_present, False, budget, elems, RESIDENT_ERR_NO_DEVICE)
    return ResidentProbe(True, True, True, budget, elems, RESIDENT_OK)
