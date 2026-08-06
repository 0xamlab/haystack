"""test_determinism_manifest.mojo — hand-written tests for the replay manifest and its hash.

Hand-written, never machine-emitted.

Three things are proved here, and the third is the one that decays without a test:

1. **Identity.** Two manifests describing the same run hash equal; changing the seed
   changes the hash. Asserted on the digest string, with `==`.
2. **Refusal.** Every field whose domain has a representable absence is refused rather
   than defaulted, and a refused manifest has NO digest — not a digest of a defaulted
   manifest, which two different runs could share.
3. **Field coverage.** The hash covers every field that can change an answer. The suite
   drives `manifest_perturb_field` from `manifest_field_names()` and requires each name to
   move the digest, and reconciles hashed + derived against the struct's declared field
   count. A field added to the struct and left outside the hash cannot get past all three.

The digest is also cross-checked against the frozen `canonical` path directly: the suite
calls `canonical.hash.versioned_digest` on `manifest_encode` bytes itself and compares. If
this module ever grew a second hashing path, that assertion is what fails.
"""
from canonical.encode import encoding_version, to_hex
from canonical.hash import (
    digest_encoding_version,
    digest_matches_encoding,
    hash_canonical_bytes,
    versioned_digest,
)
from determinism.counter_rng import rng_global_sentinel, rng_version
from determinism.manifest import (
    MANIFEST_DECLARED_FIELDS,
    MANIFEST_ERR_MISSING_INPUT_SHAPE,
    MANIFEST_ERR_MISSING_REDUCTION_SHAPE,
    MANIFEST_ERR_MISSING_RNG_VERSION,
    MANIFEST_ERR_NEGATIVE_DIM,
    MANIFEST_ERR_SHAPE_COUNT,
    MANIFEST_ERR_STREAM_COUNT,
    MANIFEST_ERR_STREAM_ID_RANGE,
    MANIFEST_ERR_UNHASHED_FIELD,
    MANIFEST_ERR_UNNAMED_STREAM,
    MANIFEST_OK,
    manifest_build,
    manifest_build_declared,
    manifest_declared_field_count,
    manifest_derived_field_names,
    manifest_digest,
    manifest_encode,
    manifest_field_names,
    manifest_perturb_field,
    manifest_same_run,
    manifest_status_name,
    manifest_version,
)
from determinism.reduce_det import reduction_shape_id
from determinism.streams import stream_id


def two_streams() -> List[String]:
    var s = List[String]()
    s.append(String("weather"))
    s.append(String("tyre_wear"))
    return s^


def shape_3x4() -> List[Int]:
    var s = List[Int]()
    s.append(3)
    s.append(4)
    return s^


def main() raises:
    var failures = 0
    var checks = 0

    # ── the schema identity is distinct from the encoding and shape identities ─
    checks += 1
    if manifest_version() != String("algenta-replay-manifest/v1"):
        print("  ❌ manifest_version drifted:", manifest_version())
        failures += 1
    checks += 1
    if manifest_version() == encoding_version():
        print("  ❌ the manifest schema and the byte encoding must be separate identities")
        failures += 1

    # ── a well-formed manifest builds, and reuses the owning kernels' values ──
    var m = manifest_build(UInt64(12345), 2, two_streams(), 2, shape_3x4())
    checks += 1
    if m.status != MANIFEST_OK:
        print("  ❌ a complete manifest was refused:", manifest_status_name(m.status))
        failures += 1
    checks += 1
    if m.rng_version != rng_version():
        print("  ❌ manifest_build must read counter_rng.rng_version, got", m.rng_version)
        failures += 1
    checks += 1
    if m.rng_global_sentinel != rng_global_sentinel():
        print("  ❌ manifest_build must read counter_rng.rng_global_sentinel")
        failures += 1
    checks += 1
    if m.reduction_shape != reduction_shape_id():
        print("  ❌ manifest_build must read reduce_det.reduction_shape_id")
        failures += 1
    # The name -> id mapping is pinned by the frozen streams kernel, not restated.
    checks += 1
    if len(m.stream_ids) != 2:
        print("  ❌ stream ids were not derived, len =", len(m.stream_ids))
        failures += 1
    else:
        if m.stream_ids[0] != stream_id(String("weather")) or m.stream_ids[
            1
        ] != stream_id(String("tyre_wear")):
            print("  ❌ derived stream ids disagree with determinism.streams.stream_id")
            failures += 1

    # ── same run -> same digest; different seed -> different digest ───────────
    var again = manifest_build(UInt64(12345), 2, two_streams(), 2, shape_3x4())
    var d1 = manifest_digest(m)
    var d2 = manifest_digest(again)
    checks += 1
    if not (d1.present and d2.present):
        print("  ❌ a valid manifest must have a digest")
        failures += 1
    checks += 1
    if d1.digest != d2.digest:
        print("  ❌ same run hashed differently:", d1.digest, d2.digest)
        failures += 1
    checks += 1
    if not manifest_same_run(m, again):
        print("  ❌ manifest_same_run must be True for identical runs")
        failures += 1

    var other_seed = manifest_build(UInt64(12346), 2, two_streams(), 2, shape_3x4())
    var d3 = manifest_digest(other_seed)
    checks += 1
    if d3.digest == d1.digest:
        print("  ❌ a different master_seed must change the digest")
        failures += 1
    checks += 1
    if manifest_same_run(m, other_seed):
        print("  ❌ manifest_same_run must be False across seeds")
        failures += 1

    # A seed of 0 is a legitimate seed and must hash differently from 12345 —
    # 0 is not "absent".
    var zero_seed = manifest_build(UInt64(0), 2, two_streams(), 2, shape_3x4())
    checks += 1
    if zero_seed.status != MANIFEST_OK:
        print("  ❌ seed 0 must be accepted, not read as missing")
        failures += 1
    checks += 1
    if manifest_digest(zero_seed).digest == d1.digest:
        print("  ❌ seed 0 and seed 12345 hashed the same")
        failures += 1

    # A seed above 2^63-1 must not collide with anything: the encoder writes bytes,
    # not a signed Int. -1 as a UInt64 is 2^64-1.
    var big_seed = manifest_build(UInt64(18446744073709551615), 2, two_streams(), 2,
                                  shape_3x4())
    var small_seed = manifest_build(UInt64(9223372036854775807), 2, two_streams(), 2,
                                    shape_3x4())
    checks += 1
    if big_seed.status != MANIFEST_OK or small_seed.status != MANIFEST_OK:
        print("  ❌ large seeds must be accepted")
        failures += 1
    checks += 1
    if manifest_digest(big_seed).digest == manifest_digest(small_seed).digest:
        print("  ❌ 2^64-1 and 2^63-1 hashed identically — the seed encoding wraps")
        failures += 1

    # Order of stream names is part of the run: streams are addressed positionally.
    var swapped = List[String]()
    swapped.append(String("tyre_wear"))
    swapped.append(String("weather"))
    checks += 1
    if manifest_digest(manifest_build(UInt64(12345), 2, swapped, 2, shape_3x4())).digest \
            == d1.digest:
        print("  ❌ reordering the stream names must change the digest")
        failures += 1

    # A different input shape is a different run.
    var shape_4x3 = List[Int]()
    shape_4x3.append(4)
    shape_4x3.append(3)
    checks += 1
    if manifest_digest(manifest_build(UInt64(12345), 2, two_streams(), 2,
                                      shape_4x3)).digest == d1.digest:
        print("  ❌ 3x4 and 4x3 hashed identically")
        failures += 1

    # ── cross-check against the frozen canonical path, directly ──────────────
    var bytes = manifest_encode(m)
    checks += 1
    if len(bytes) == 0:
        print("  ❌ a valid manifest encoded to zero bytes")
        failures += 1
    checks += 1
    if versioned_digest(bytes) != d1.digest:
        print("  ❌ manifest_digest does not equal canonical.hash.versioned_digest over",
              "manifest_encode bytes — there is a second hashing path")
        failures += 1
    checks += 1
    if digest_encoding_version(d1.digest) != encoding_version():
        print("  ❌ the digest does not carry the encoding version:", d1.digest)
        failures += 1
    checks += 1
    if not digest_matches_encoding(d1.digest):
        print("  ❌ digest_matches_encoding rejected our own digest")
        failures += 1
    # The bare SHA-256 must be the tail of the versioned digest.
    checks += 1
    if d1.digest != encoding_version() + ":" + hash_canonical_bytes(bytes):
        print("  ❌ versioned digest is not <encoding-version>:<sha256 of canonical bytes>")
        failures += 1
    # Byte-level determinism: encoding twice gives the same bytes.
    checks += 1
    if to_hex(bytes) != to_hex(manifest_encode(again)):
        print("  ❌ two manifests of the same run encoded to different bytes")
        failures += 1

    # ── rule 4: an incomplete manifest is refused, and has no digest ──────────
    var empty_names = List[String]()
    var empty_shape = List[Int]()

    # rng_version not recorded
    var no_rng = manifest_build_declared(
        String(""), rng_global_sentinel(), UInt64(1), 2, two_streams(), 2, shape_3x4(),
        reduction_shape_id()
    )
    checks += 1
    if no_rng.status != MANIFEST_ERR_MISSING_RNG_VERSION:
        print("  ❌ empty rng_version not refused:", manifest_status_name(no_rng.status))
        failures += 1
    var nd = manifest_digest(no_rng)
    checks += 1
    if nd.present or len(nd.digest) != 0:
        print("  ❌ a refused manifest must have NO digest, got", nd.digest)
        failures += 1
    checks += 1
    if len(manifest_encode(no_rng)) != 0:
        print("  ❌ a refused manifest must not encode to bytes")
        failures += 1
    checks += 1
    if manifest_same_run(no_rng, no_rng):
        print("  ❌ two refused manifests must not compare as the same run")
        failures += 1

    # reduction shape not recorded
    var no_shape_id = manifest_build_declared(
        rng_version(), rng_global_sentinel(), UInt64(1), 2, two_streams(), 2,
        shape_3x4(), String("")
    )
    checks += 1
    if no_shape_id.status != MANIFEST_ERR_MISSING_REDUCTION_SHAPE:
        print("  ❌ empty reduction_shape not refused:",
              manifest_status_name(no_shape_id.status))
        failures += 1

    # input shape not recorded at all (empty list, declared 0)
    var no_input = manifest_build(UInt64(1), 2, two_streams(), 0, empty_shape)
    checks += 1
    if no_input.status != MANIFEST_ERR_MISSING_INPUT_SHAPE:
        print("  ❌ an unrecorded input shape not refused:",
              manifest_status_name(no_input.status))
        failures += 1
    # ... but a zero-row input IS a shape: [0], not [].
    var zero_rows = List[Int]()
    zero_rows.append(0)
    var zr = manifest_build(UInt64(1), 2, two_streams(), 1, zero_rows)
    checks += 1
    if zr.status != MANIFEST_OK:
        print("  ❌ shape [0] must be accepted:", manifest_status_name(zr.status))
        failures += 1
    checks += 1
    if manifest_digest(zr).digest == d1.digest:
        print("  ❌ shape [0] and shape [3,4] hashed the same")
        failures += 1

    # a negative dimension is not a shape
    var neg_shape = List[Int]()
    neg_shape.append(3)
    neg_shape.append(-1)
    checks += 1
    if manifest_build(UInt64(1), 2, two_streams(), 2, neg_shape).status \
            != MANIFEST_ERR_NEGATIVE_DIM:
        print("  ❌ a negative dimension not refused")
        failures += 1

    # an unnamed stream is not a named stream
    var blank = List[String]()
    blank.append(String("weather"))
    blank.append(String(""))
    checks += 1
    if manifest_build(UInt64(1), 2, blank, 2, shape_3x4()).status \
            != MANIFEST_ERR_UNNAMED_STREAM:
        print("  ❌ an empty stream name not refused")
        failures += 1

    # ── rule 1: declared counts are rejected on mismatch, never trusted ──────
    # If any of these indexed past the list, the process would die here.
    checks += 1
    var over_streams = manifest_build(UInt64(1), 25, two_streams(), 2, shape_3x4())
    if over_streams.status != MANIFEST_ERR_STREAM_COUNT:
        print("  ❌ n_streams=25 over a 2-name list not refused:",
              manifest_status_name(over_streams.status))
        failures += 1
    checks += 1
    if manifest_build(UInt64(1), 1, two_streams(), 2, shape_3x4()).status \
            != MANIFEST_ERR_STREAM_COUNT:
        print("  ❌ an UNDER-declared stream count must also be refused: the hash would",
              "record the whole list")
        failures += 1
    checks += 1
    if manifest_build(UInt64(1), -1, two_streams(), 2, shape_3x4()).status \
            != MANIFEST_ERR_STREAM_COUNT:
        print("  ❌ a negative stream count not refused")
        failures += 1
    checks += 1
    var over_dims = manifest_build(UInt64(1), 2, two_streams(), 25, shape_3x4())
    if over_dims.status != MANIFEST_ERR_SHAPE_COUNT:
        print("  ❌ n_dims=25 over a 2-element shape not refused:",
              manifest_status_name(over_dims.status))
        failures += 1
    checks += 1
    if manifest_build(UInt64(1), 2, two_streams(), 1, shape_3x4()).status \
            != MANIFEST_ERR_SHAPE_COUNT:
        print("  ❌ an under-declared dimension count not refused")
        failures += 1
    checks += 1
    if manifest_build(UInt64(1), -3, empty_names, -3, empty_shape).status \
            != MANIFEST_ERR_STREAM_COUNT:
        print("  ❌ negative counts on empty lists not refused")
        failures += 1

    # A run that consumed no randomness is a real, DECLARED statement: count 0 over an
    # empty list. It is accepted, and it hashes differently from a run with streams.
    var no_draws = manifest_build(UInt64(7), 0, empty_names, 2, shape_3x4())
    checks += 1
    if no_draws.status != MANIFEST_OK:
        print("  ❌ zero declared streams must be accepted:",
              manifest_status_name(no_draws.status))
        failures += 1
    checks += 1
    if manifest_digest(no_draws).digest == manifest_digest(
        manifest_build(UInt64(7), 2, two_streams(), 2, shape_3x4())
    ).digest:
        print("  ❌ a no-randomness run hashed the same as a two-stream run")
        failures += 1

    # A sentinel outside the sixteen-bit stream field addresses a stream the run
    # cannot have used.
    checks += 1
    if manifest_build_declared(
        rng_version(), UInt64(65536), UInt64(1), 2, two_streams(), 2, shape_3x4(),
        reduction_shape_id()
    ).status != MANIFEST_ERR_STREAM_ID_RANGE:
        print("  ❌ a sentinel above 0xFFFF not refused")
        failures += 1

    # ── THE FIELD-COVERAGE GATE ──────────────────────────────────────────────
    var hashed = manifest_field_names()
    var derived = manifest_derived_field_names()
    checks += 1
    if len(hashed) + len(derived) != manifest_declared_field_count():
        print("  ❌ field registry does not reconcile:", len(hashed), "hashed +",
              len(derived), "derived !=", manifest_declared_field_count(),
              "declared. A field was added to ReplayManifest without being classified,",
              "so it may be drifting outside the hash.")
        failures += 1
    checks += 1
    if manifest_declared_field_count() != MANIFEST_DECLARED_FIELDS:
        print("  ❌ manifest_declared_field_count does not report the constant")
        failures += 1
    # Names distinct, and canonically ordered (the encoder relies on both).
    var dup = 0
    for i in range(len(hashed)):
        for j in range(i + 1, len(hashed)):
            if hashed[i] == hashed[j]:
                dup += 1
    checks += 1
    if dup != 0:
        print("  ❌ duplicate hashed field names:", dup)
        failures += 1
    var unsorted = 0
    for i in range(1, len(hashed)):
        if not (hashed[i - 1] < hashed[i]):
            unsorted += 1
    checks += 1
    if unsorted != 0:
        print("  ❌ hashed field names are not in canonical order")
        failures += 1
    # No name appears in both lists.
    var overlap = 0
    for i in range(len(hashed)):
        for j in range(len(derived)):
            if hashed[i] == derived[j]:
                overlap += 1
    checks += 1
    if overlap != 0:
        print("  ❌ a field is classified as both hashed and derived")
        failures += 1

    # Every hashed field, perturbed on its own, must move the digest. This is what
    # fails when a new field is registered but written by a no-op.
    for i in range(len(hashed)):
        var perturbed = manifest_perturb_field(m, hashed[i])
        checks += 1
        if perturbed.status != MANIFEST_OK:
            print("  ❌ perturbing", hashed[i], "produced status",
                  manifest_status_name(perturbed.status),
                  "— the field is registered but manifest_perturb_field has no case for",
                  "it, so its hash coverage is unproven")
            failures += 1
            continue
        var pd = manifest_perturb_field(m, hashed[i])
        var pdig = manifest_digest(pd)
        checks += 1
        if not pdig.present:
            print("  ❌ perturbed manifest has no digest for field", hashed[i])
            failures += 1
        elif pdig.digest == d1.digest:
            print("  ❌ field", hashed[i], "is NOT covered by the hash: perturbing it",
                  "left the digest unchanged")
            failures += 1

    # An unregistered name is reported, not silently ignored.
    var unknown = manifest_perturb_field(m, String("a_field_nobody_registered"))
    checks += 1
    if unknown.status != MANIFEST_ERR_UNHASHED_FIELD:
        print("  ❌ an unknown field name must be refused, got",
              manifest_status_name(unknown.status))
        failures += 1
    checks += 1
    if manifest_digest(unknown).present:
        print("  ❌ an unhashed-field refusal must not produce a digest")
        failures += 1

    # The derived field is genuinely outside the hash, which is the reason it is
    # classified separately rather than forgotten.
    checks += 1
    if manifest_perturb_field(m, String("status")).status != MANIFEST_ERR_UNHASHED_FIELD:
        print("  ❌ `status` must not be perturbable as a hashed field")
        failures += 1

    # ── status names are total ────────────────────────────────────────────────
    var codes = List[Int]()
    codes.append(MANIFEST_OK)
    codes.append(MANIFEST_ERR_MISSING_RNG_VERSION)
    codes.append(MANIFEST_ERR_MISSING_REDUCTION_SHAPE)
    codes.append(MANIFEST_ERR_MISSING_INPUT_SHAPE)
    codes.append(MANIFEST_ERR_STREAM_COUNT)
    codes.append(MANIFEST_ERR_UNNAMED_STREAM)
    codes.append(MANIFEST_ERR_SHAPE_COUNT)
    codes.append(MANIFEST_ERR_NEGATIVE_DIM)
    codes.append(MANIFEST_ERR_UNHASHED_FIELD)
    codes.append(MANIFEST_ERR_STREAM_ID_RANGE)
    for i in range(len(codes)):
        checks += 1
        if manifest_status_name(codes[i]) == String("unknown_status"):
            print("  ❌ status", codes[i], "has no name")
            failures += 1
    checks += 1
    if manifest_status_name(-999) != String("unknown_status"):
        print("  ❌ an unallocated code must not get a name")
        failures += 1
    # The two determinism modules must not have claimed the same integer (rule 4e).
    checks += 1
    if MANIFEST_OK == 200:
        print("  ❌ manifest reused reduce_det's status range")
        failures += 1

    # One ✅ per check that did not fail, so the A-Z harness reports a real count
    # rather than 0/0. `checks` is derived from the ❌ sites, never hardcoded.
    for _ in range(checks - failures):
        print("  ✅ manifest check")
    print("  [determinism.manifest] Passed:", checks - failures, "Failed:", failures)
    if failures != 0:
        raise Error("test_determinism_manifest failed")
