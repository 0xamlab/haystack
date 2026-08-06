"""Compile gate: the contract-reachable accel surface must build for a NO-accelerator target.

WHY THIS EXISTS
===============

The release shard build compiles the generated dispatch AOT on CI runners that have no detectable
accelerator, and on such a target instantiating `DeviceContext` is a COMPILE error in the stdlib
("Unknown GPU architecture detected"). A runtime `if not has_accelerator()` does not prevent it —
elaboration still type-checks the dead branch — so the accel modules must prune GPU instantiation
with `@parameter if`. JIT on a developer machine with a GPU never sees the failure, which is how
build-runtime run 30706203629 broke on both platforms in the FIRST shard build to include accel
while every local run was green.

This file recreates that build shape locally in seconds: it imports exactly what
`runtime_library_dispatch_generated.mojo` imports from accel and CALLS all of it from `main` (calls,
not imports — elaboration follows reachability). Compiled by `make verify-accel-aot` with
`--target-accelerator=none`; if it stops compiling, the release build is broken the same way.

Executable on purpose: run on a no-accelerator build it must answer no-device / refusal statuses,
never crash. On the gated targets `accel_device_probe().status` is `ACCEL_ERR_NO_DEVICE` and the
GEMM refuses with `ACCEL_ERR_SHADER_TOOLCHAIN_ABSENT` — the typed-refusal convention, observable.
"""

from accel.contract import (
    accel_status_name,
    accel_policy_name,
    accel_backend_name,
    accel_policy_known,
    accel_resolve,
    accel_worth_offloading,
)
from accel.device import accel_has_device, accel_device_name_len, accel_device_probe
from accel.gemm_metal import gemm_metal_available, gemm_metal_flat, gemm_metal_agreement


def main():
    var has = accel_has_device()
    var name_len = accel_device_name_len()
    var probe = accel_device_probe()
    print("device:", has, name_len, probe.status, probe.device_present, probe.backend)

    var status = accel_status_name(0)
    var policy = accel_policy_name(0)
    var backend = accel_backend_name(0)
    var known = accel_policy_known(0)
    var resolved = accel_resolve(0, 1, True)
    var worth = accel_worth_offloading(64, 4.0, 10.0, 0.4, 5.0)
    print("contract:", status, policy, backend, known, resolved, worth)

    var avail = gemm_metal_available()
    var a = List[Float64]()
    var b = List[Float64]()
    for _ in range(4):
        a.append(1.0)
        b.append(1.0)
    var g = gemm_metal_flat(a, b, 2, 2, 2)
    var agree = gemm_metal_agreement(a, b, 2, 2, 2)
    print("gemm_metal:", avail, g.status, g.backend_used, agree.status)
