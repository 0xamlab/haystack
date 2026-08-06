"""test_determinism_streams.mojo — known-value tests for name-addressed RNG streams.

Hand-written. The properties that matter are stability (a name always maps to the
same id), range safety (never into the reserved block or the global sentinel), and
that the frozen counter packing has not moved.
"""
from determinism.counter_rng import (
    GLOBAL_SENTINEL,
    RESERVED_STREAM_MAX,
    philox_word,
    rng_uniform,
)
from determinism.streams import (
    DERIVED_STREAM_MIN,
    is_global_stream,
    is_reserved_stream,
    pack_coordinates,
    stream_id,
)


def main() raises:
    var passed = 0
    var failed = 0

    # ── a name maps to the same id every time ────────────────────────────────
    var a = stream_id("weather")
    var b = stream_id("weather")
    if a == b:
        passed += 1
        print("  ✅ stream_id is stable for the same name")
    else:
        failed += 1
        print("  ❌ stream_id unstable:", a, b)

    # ── different names map to different streams ────────────────────────────
    if stream_id("weather") != stream_id("demand"):
        passed += 1
        print("  ✅ distinct names map to distinct streams")
    else:
        failed += 1
        print("  ❌ 'weather' and 'demand' collided")

    # ── derived ids never land in the reserved block or on the sentinel ──────
    var names = List[String]()
    names.append("weather")
    names.append("demand")
    names.append("arrivals")
    names.append("service")
    names.append("")
    names.append("a-very-long-stream-name-with-hyphens-and-numbers-12345")
    var all_safe = True
    for i in range(len(names)):
        var id = stream_id(names[i])
        if is_reserved_stream(id) or is_global_stream(id) or id < DERIVED_STREAM_MIN:
            all_safe = False
            print("    unsafe id", id, "for name", names[i])
    if all_safe:
        passed += 1
        print("  ✅ derived ids avoid the reserved block and the global sentinel")
    else:
        failed += 1
        print("  ❌ a derived id landed in a forbidden range")

    # ── the reserved predicate matches the documented boundary ──────────────
    if (
        is_reserved_stream(0)
        and is_reserved_stream(RESERVED_STREAM_MAX)
        and not is_reserved_stream(RESERVED_STREAM_MAX + 1)
    ):
        passed += 1
        print("  ✅ reserved range is 0..RESERVED_STREAM_MAX inclusive")
    else:
        failed += 1
        print("  ❌ reserved boundary wrong")

    if is_global_stream(GLOBAL_SENTINEL) and not is_global_stream(DERIVED_STREAM_MIN):
        passed += 1
        print("  ✅ global sentinel recognised, ordinary ids are not")
    else:
        failed += 1
        print("  ❌ global sentinel check wrong")

    # ── the frozen counter packing has not moved ─────────────────────────────
    # (dim0 << 32) | (dim1 << 16) | stream_id — changing this changes every value
    # ever drawn, so it is pinned by an explicit expected constant.
    var packed = pack_coordinates(3, 5, 9)
    var expected = (UInt64(3) << 32) | (UInt64(5) << 16) | UInt64(9)
    if packed == expected and packed == 0x0000000300050009:
        passed += 1
        print("  ✅ counter packing is unchanged: dim0<<32 | dim1<<16 | stream_id")
    else:
        failed += 1
        print("  ❌ packing moved:", packed, "expected", expected)

    # ── field widths clamp rather than bleed into a neighbour ────────────────
    var clamped = pack_coordinates(0, 0xFFFFF, 0xFFFFF)
    if (clamped >> 32) == 0:
        passed += 1
        print("  ✅ oversized dim1/stream_id cannot bleed into dim0")
    else:
        failed += 1
        print("  ❌ field bleed:", clamped)

    # ── two named streams are independent at the same coordinates ───────────
    # Same seed, scenario, replication, dims and draw index — only the stream
    # differs, so equal values would mean the streams are not independent.
    var u1 = rng_uniform(42, 1, 0, 0, 0, stream_id("weather"), 0)
    var u2 = rng_uniform(42, 1, 0, 0, 0, stream_id("demand"), 0)
    if u1 != u2 and u1 >= 0.0 and u1 < 1.0 and u2 >= 0.0 and u2 < 1.0:
        passed += 1
        print("  ✅ named streams are independent at identical coordinates")
    else:
        failed += 1
        print("  ❌ streams not independent:", u1, u2)

    # ── a draw is addressable: same coordinates, same value, no state ────────
    if rng_uniform(42, 1, 0, 0, 0, stream_id("weather"), 7) == rng_uniform(
        42, 1, 0, 0, 0, stream_id("weather"), 7
    ):
        passed += 1
        print("  ✅ the same coordinates always yield the same draw")
    else:
        failed += 1
        print("  ❌ draws are not addressable")

    # ── changing only the seed changes the value ────────────────────────────
    if philox_word(42, 1, 0, 0, 0, 8, 0) != philox_word(43, 1, 0, 0, 0, 8, 0):
        passed += 1
        print("  ✅ master_seed participates in the keying")
    else:
        failed += 1
        print("  ❌ seed does not affect the draw")

    print("  [determinism.streams] Passed:", passed, "Failed:", failed)
