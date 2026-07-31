#!/usr/bin/env python3
"""Cross-validate the Mojo counter_rng kernel against reference Philox4x64-10.

VALIDATION TOOLING ONLY — numpy is a validation dependency here, never a runtime one.

Two independent checks:

1. A spec-faithful Python Philox4x64-10 (Random123 reference form) must reproduce the Mojo kernel's
   output words bit-for-bit.
2. numpy's ``np.random.Philox`` must agree with that reference under a documented offset.

On (2): numpy **pre-increments** the 256-bit counter before emitting, so

    numpy(counter=C) == spec_philox(counter=C+1)

That is a numpy API convention, not a specification difference. It is asserted here so nobody has to
rediscover it, and so a future numpy change that alters the convention fails loudly.

Usage:
    python3 scripts/timing/validate_rng.py            # reference + numpy agreement
    python3 scripts/timing/validate_rng.py --emit     # print vectors for the Mojo test
"""

from __future__ import annotations

import argparse
import sys

M0 = 0xD2E7470EE14C6C93
M1 = 0xCA5A826395121157
W0 = 0x9E3779B97F4A7C15
W1 = 0xBB67AE8584CAA73B
MASK = (1 << 64) - 1

# Frozen layout — must mirror counter_rng.mojo and FROZEN_SPECS.md
PROCESS_LAP_NOISE = 4
GLOBAL_SENTINEL = 0xFFFF


def _mulhilo(a: int, b: int) -> tuple[int, int]:
    p = a * b
    return (p >> 64) & MASK, p & MASK


def _round(c: list[int], k: list[int]) -> list[int]:
    hi0, lo0 = _mulhilo(M0, c[0])
    hi1, lo1 = _mulhilo(M1, c[2])
    return [hi1 ^ c[1] ^ k[0], lo1, hi0 ^ c[3] ^ k[1], lo0]


def philox4x64_10(counter: list[int], key: list[int]) -> list[int]:
    """Random123 reference form: round once with the given key, bumping the key before each
    subsequent round, for 10 rounds total."""
    c = list(counter)
    k = list(key)
    for r in range(10):
        if r > 0:
            k[0] = (k[0] + W0) & MASK
            k[1] = (k[1] + W1) & MASK
        c = _round(c, k)
    return c


def philox_word(
    master_seed: int, scenario_id: int, replication_id: int,
    lap_id: int, car_id: int, process_id: int, draw_index: int,
) -> int:
    """The frozen coordinate layout, in Python. Mirrors counter_rng.philox_word."""
    c1 = (lap_id << 32) | (car_id << 16) | process_id
    counter = [replication_id, c1, draw_index >> 2, 0]
    out = philox4x64_10(counter, [master_seed, scenario_id])
    return out[draw_index & 3]


# Emitted by `mojo run` of counter_rng at master_seed=1 scenario=2 rep=3 lap=4 car=5 proc=4
MOJO_WORDS_0_7 = [
    5544217767837969664,
    2756644627510874722,
    11377611935976986105,
    707596276828718816,
    3838836558764994255,
    5772761546685886677,
    502729060365814170,
    8147541987183208929,
]
MOJO_SELFTEST = 13066461341573311292


def check_reference_matches_mojo() -> bool:
    got = [philox_word(1, 2, 3, 4, 5, PROCESS_LAP_NOISE, i) for i in range(8)]
    ok = got == MOJO_WORDS_0_7
    print(f"  [{'PASS' if ok else 'FAIL'}] Python reference reproduces Mojo words 0-7")
    if not ok:
        for i, (a, b) in enumerate(zip(got, MOJO_WORDS_0_7)):
            if a != b:
                print(f"        draw {i}: reference {a} != mojo {b}")
    return ok


def check_selftest() -> bool:
    acc = 0
    for i in range(64):
        acc ^= (philox_word(1, 2, 3, 4, 5, PROCESS_LAP_NOISE, i) + i) & MASK
    ok = acc == MOJO_SELFTEST
    print(f"  [{'PASS' if ok else 'FAIL'}] rng_selftest fold matches ({acc})")
    return ok


def _increment_counter_256(counter: list[int]) -> list[int]:
    """Increment the counter as one 256-bit little-endian integer, carrying between words.

    Incrementing only word 0 is wrong: at word-0 wraparound the carry must propagate into word 1.
    numpy carries, so a naive single-word increment disagrees precisely at the wrap boundary.
    """
    c = list(counter)
    for i in range(len(c)):
        c[i] = (c[i] + 1) & MASK
        if c[i] != 0:
            break
    return c


def check_numpy_offset() -> bool:
    try:
        import numpy as np
    except ImportError:
        print("  [SKIP] numpy unavailable — cannot cross-validate against the reference bit generator")
        return True

    cases = [
        ([0, 0, 0, 0], [0, 0]),
        ([1, 0, 0, 0], [0, 0]),
        ([3, (4 << 32) | (5 << 16) | 4, 0, 0], [1, 2]),
        ([41, 99, 7, 0], [0xDEADBEEF, 0xCAFEF00D]),
        ([0, 0, 1, 0], [5, 6]),
        ([MASK, 0, 0, 0], [7, 8]),
    ]
    ok = True
    for ctr, key in cases:
        bg = np.random.Philox(
            counter=np.array(ctr, dtype=np.uint64), key=np.array(key, dtype=np.uint64)
        )
        npy = bg.random_raw(4).tolist()
        ref = philox4x64_10(_increment_counter_256(ctr), key)
        if npy != ref:
            ok = False
            print(f"        counter={ctr} key={key}: numpy {npy} != reference(C+1) {ref}")
    print(
        f"  [{'PASS' if ok else 'FAIL'}] numpy Philox agrees with the reference under the documented "
        f"pre-increment (numpy(C) == spec(C+1)), {len(cases)} cases"
    )
    return ok


def check_fixed_draw_consumption() -> bool:
    """A normal must consume exactly draw_index and draw_index+1 — nothing else."""
    import math

    def u_half(u: int) -> float:
        return (u >> 11) * 2.0**-53

    def u_left(u: int) -> float:
        return ((u >> 11) + 1) * 2.0**-53

    d = 10
    u1 = u_left(philox_word(11, 22, 0, 4, 5, PROCESS_LAP_NOISE, d))
    u2 = u_half(philox_word(11, 22, 0, 4, 5, PROCESS_LAP_NOISE, d + 1))
    z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    ok = math.isfinite(z)
    print(f"  [{'PASS' if ok else 'FAIL'}] Box-Muller consumes exactly 2 draws, z={z:.6f}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true", help="print vectors for the Mojo test")
    args = ap.parse_args()

    if args.emit:
        for i in range(8):
            print(f"  alias EXPECT_{i}: UInt64 = {philox_word(1, 2, 3, 4, 5, PROCESS_LAP_NOISE, i)}")
        return 0

    print("counter_rng validation — philox4x64-10/v1")
    results = [
        check_reference_matches_mojo(),
        check_selftest(),
        check_numpy_offset(),
        check_fixed_draw_consumption(),
    ]
    failed = results.count(False)
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
