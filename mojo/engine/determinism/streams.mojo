"""
determinism.streams — name-addressed independent RNG streams. Zero Python.

`counter_rng` needs a `stream_id` to keep draws from different concerns
independent. Hardcoding integers works for one consumer and breaks the moment
there are two: whoever picks 4 second silently collides with whoever picked 4
first, and the two streams stop being independent without anything failing.

Deriving the id from a name fixes that. `stream_id("weather")` is stable across
runs, machines and languages (FNV-1a over the name's bytes is fully specified), so
the same name always addresses the same stream and two different names essentially
never collide.

Reserved range
--------------
Ids 1-7 were assigned to named processes by this kernel's first consumer. Reusing
them would change values that consumer already drew, so derived ids are mapped
strictly above `RESERVED_STREAM_MAX` and below the 16-bit field width the counter
layout allocates.

Determinism contract
--------------------
A draw is addressed by `(master_seed, scenario_id, replication_id, dim0, dim1,
stream_id, draw_index)` and is a pure function of those coordinates — no state, no
ordering dependency. Two runs that request the same coordinates get the same value
even if they did entirely different work beforehand, which is what makes common
random numbers valid across alternatives that consume different numbers of draws.
"""
from feature_hashing import hash_feature

from determinism.counter_rng import GLOBAL_SENTINEL, RESERVED_STREAM_MAX

# The counter layout gives stream_id 16 bits: (dim0 << 32) | (dim1 << 16) | stream_id.
comptime STREAM_ID_WIDTH: UInt64 = 0xFFFF

# GLOBAL_SENTINEL (0xFFFF) addresses process-wide draws, so derived ids must stay
# below it as well as above the reserved block.
comptime DERIVED_STREAM_MIN: UInt64 = 8
comptime DERIVED_STREAM_SPAN: UInt64 = 0xFFFF - 8  # exclusive of the sentinel


fn stream_id(name: String) -> UInt64:
    """Stable 16-bit stream id for `name`, outside the reserved range.

    Same name -> same id, on any machine, in any language that implements FNV-1a
    the same way. Distinct names collide only on a 1-in-65527 hash coincidence,
    which is a correctness *silence* risk rather than a crash — so prefer a few
    well-known names over generating them programmatically.
    """
    # Reuses the frozen feature_hashing kernel rather than reimplementing FNV-1a:
    # one specified hash, one place it can drift. Seed 0 is fixed so a name's id is
    # stable forever — a different seed would silently re-address every stream.
    var bucket = hash_feature(name, Int(DERIVED_STREAM_SPAN), 0)
    return DERIVED_STREAM_MIN + UInt64(bucket)


fn is_reserved_stream(id: UInt64) -> Bool:
    """True for the ids the first consumer already assigned, plus 0."""
    return id <= RESERVED_STREAM_MAX


fn is_global_stream(id: UInt64) -> Bool:
    return id == GLOBAL_SENTINEL


fn pack_coordinates(dim0: UInt64, dim1: UInt64, id: UInt64) -> UInt64:
    """The `c1` counter word: (dim0 << 32) | (dim1 << 16) | stream_id.

    Exposed so a caller can assert the packing rather than infer it, and so a test
    can prove the field boundaries did not move.
    """
    return (dim0 << 32) | ((dim1 & 0xFFFF) << 16) | (id & STREAM_ID_WIDTH)
