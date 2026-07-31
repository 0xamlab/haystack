"""
determinism.manifest — a replay manifest and its canonical hash. Zero Python.

What a manifest is for
----------------------
A run is reproducible only if everything that fed it can be restated. The rest of this
package makes each individual ingredient addressable — `counter_rng` makes a draw a pure
function of its coordinates, `streams` makes a stream name resolve to a fixed id,
`reduce_det` makes a sum a pure function of its length. None of that helps if the run does
not record WHICH coordinates, WHICH names and WHICH reduction shape it used. This module
is that record, plus one hash over it, so "same run" becomes a 64-character comparison
instead of an argument.

The hash goes through the frozen `canonical` path — `canonical.encode` bytes fed to
`canonical.hash.versioned_digest` — so two manifests describing the same run hash equal in
any language that calls this kernel, and any difference in any hashed field changes the
digest. Nothing is hashed here that is not encoded there; there is no second encoder.

Refusal, not defaults (rule 4)
------------------------------
A manifest missing a field that affects the result is not a manifest. It is a claim of
reproducibility that cannot be checked, and it is WORSE than no manifest because a reader
stops looking. So an incomplete manifest is REFUSED — `status != MANIFEST_OK` and
`manifest_digest` returns `present = False` with no digest at all. It is never completed
with a default and hashed anyway, because a defaulted field produces a digest that two
different runs can share.

Four things are refusable, and each one is refusable because its domain has a
representable absence:

* `rng_version == ""` — the generator was not recorded, so no draw can be re-derived.
* `reduction_shape == ""` — the summation order was not recorded, so no aggregate can be.
* `input_shape` empty — a run always has at least one dimension; a zero-row input is
  `[0]`, not `[]`. An empty list therefore means "unrecorded", not "zero-dimensional".
* a stream name that is the empty string — an unnamed stream is not a named stream.

`master_seed` is deliberately NOT refusable: every `UInt64` is a legitimate seed, `0`
included, so there is no value that could mean "absent". What protects it is that the
build entry points take it positionally and the field-coverage gate below proves it is
hashed.

`n_streams == 0` is ACCEPTED and means "this run consumed no randomness". That is a real
statement rather than an inference, because the caller had to state the count and the
count is checked against the list it describes (rule 1c: derive the dimension from the
payload, or reject a mismatch — this rejects).

The field-coverage gate
-----------------------
The silent failure mode is a field that drifts outside the hash: someone adds an input to
`ReplayManifest`, the digest keeps working, and two runs that differ in that input now
hash equal. Three mechanisms make that impossible to do quietly, and they are listed here
because each one on its own is defeatable:

1. **Compile break.** `ReplayManifest` has no defaulted initialiser; every construction
   site is positional and complete. Adding a `var` fails to compile until the author has
   touched every builder in this file.
2. **Count agreement.** `manifest_field_names()` (hashed) plus
   `manifest_derived_field_names()` (computed, so intentionally not hashed) must sum to
   `MANIFEST_DECLARED_FIELDS`, which sits beside the struct's `var` block. The suite
   asserts it. A new field that is not classified fails.
3. **Per-field mutation.** `manifest_perturb_field` is driven by the same name list, and
   the suite requires EVERY name in that list to change the digest when perturbed. A field
   that is registered but written by a no-op leaves the digest unchanged and fails. A field
   that is added to the struct but not to the perturb table is reported as unknown and
   fails.

Together: a new field must be added to the struct (1), classified (2), encoded, and
perturbable (3) before the suite goes green. Registering a name the encoder does not
handle is refused with `MANIFEST_ERR_UNHASHED_FIELD` rather than skipped.

Status codes
------------
Package `determinism` allocates 200-209 to `determinism.reduce_det` and 210-229 to this
module; pick from what is left (rule 4e).

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: required
supported_dtypes: int64
backend: mojo
surfaces: none
golden_vectors: mojo/tests/libs/test_determinism_manifest.mojo
benchmark: benchmarks/mojo_benchmarks/bench_determinism_reduce_det.mojo
docs: none
version_introduced: unreleased
deprecation_state: active
@endcapability
"""
from canonical.encode import (
    sort_keys,
    write_array_header,
    write_int,
    write_int_list,
    write_object_header,
    write_string,
    write_string_list,
)
from canonical.hash import versioned_digest
from determinism.counter_rng import rng_global_sentinel, rng_version
from determinism.reduce_det import reduction_shape_id
from determinism.streams import stream_id

# ── status codes (determinism package range 210-229) ──────────────────────────
# One code per refusable defect: a caller whose manifest was refused has to be told which
# field it forgot, and "invalid" would send it checking all seven.

comptime MANIFEST_OK: Int = 210
comptime MANIFEST_ERR_MISSING_RNG_VERSION: Int = 211
comptime MANIFEST_ERR_MISSING_REDUCTION_SHAPE: Int = 212
comptime MANIFEST_ERR_MISSING_INPUT_SHAPE: Int = 213
comptime MANIFEST_ERR_STREAM_COUNT: Int = 214
comptime MANIFEST_ERR_UNNAMED_STREAM: Int = 215
comptime MANIFEST_ERR_SHAPE_COUNT: Int = 216
comptime MANIFEST_ERR_NEGATIVE_DIM: Int = 217
comptime MANIFEST_ERR_UNHASHED_FIELD: Int = 218
comptime MANIFEST_ERR_STREAM_ID_RANGE: Int = 219

# The counter layout in `counter_rng` gives `stream_id` sixteen bits. An id above this
# would be silently truncated into a DIFFERENT stream by `streams.pack_coordinates`, so a
# manifest recording one is recording a stream the run did not use.
comptime MAX_STREAM_ID: UInt64 = 0xFFFF

# Number of `var`s on ReplayManifest. Beside the struct on purpose: it is the count the
# suite reconciles against `manifest_field_names()` + `manifest_derived_field_names()`.
# ADDING A FIELD? Update this, add the name to one of those two lists, encode it in
# `_write_field`, and add a case to `manifest_perturb_field`. The suite fails until all
# four are done — that is the whole design of the gate.
comptime MANIFEST_DECLARED_FIELDS: Int = 8

comptime MANIFEST_VERSION: String = "algenta-replay-manifest/v1"


@fieldwise_init
struct ReplayManifest(Copyable, Movable):
    """Everything that has to be restated for a run to be re-derivable.

    Eight fields; seven are hashed and `status` is not, because `status` is this builder's
    verdict on the other seven rather than an input to the run. Declared in this file
    rather than assembled from other packages' structs: `apps/runtime/mojo_inventory.py`
    reads struct specs one file at a time, so a public signature mentioning a struct from
    elsewhere is dropped from the runtime contract with no error (rule 2). Flat fields for
    the same reason.
    """

    var rng_version: String
    var rng_global_sentinel: UInt64
    var master_seed: UInt64
    var stream_names: List[String]
    var stream_ids: List[UInt64]
    var input_shape: List[Int]
    var reduction_shape: String
    var status: Int


@fieldwise_init
struct ManifestDigest(Copyable, Movable):
    """A manifest's identity, or the reason it does not have one.

    `present == False` means the manifest was refused and there is NO digest — `digest` is
    the empty string and is not one. A refused manifest must not hash to anything, because
    a digest is a claim that the run it describes can be replayed.
    """

    var digest: String
    var present: Bool
    var status: Int


fn manifest_version() -> String:
    """Identity of the manifest schema. Deterministic, zero-argument.

    Distinct from `canonical.encode.encoding_version` (how bytes are formed) and from
    `determinism.reduce_det.reduction_shape_id` (how sums are ordered). Bumping this means
    the SET of recorded fields changed, which changes every digest.
    """
    return MANIFEST_VERSION


fn manifest_status_name(code: Int) -> String:
    """Name for a status code, so a refusal names the missing field, not a number."""
    if code == MANIFEST_OK:
        return "ok"
    if code == MANIFEST_ERR_MISSING_RNG_VERSION:
        return "rng_version_not_recorded"
    if code == MANIFEST_ERR_MISSING_REDUCTION_SHAPE:
        return "reduction_shape_not_recorded"
    if code == MANIFEST_ERR_MISSING_INPUT_SHAPE:
        return "input_shape_not_recorded"
    if code == MANIFEST_ERR_STREAM_COUNT:
        return "declared_stream_count_does_not_match_names"
    if code == MANIFEST_ERR_UNNAMED_STREAM:
        return "stream_name_is_empty"
    if code == MANIFEST_ERR_SHAPE_COUNT:
        return "declared_dimension_count_does_not_match_shape"
    if code == MANIFEST_ERR_NEGATIVE_DIM:
        return "input_shape_has_a_negative_dimension"
    if code == MANIFEST_ERR_UNHASHED_FIELD:
        return "field_is_not_covered_by_the_hash"
    if code == MANIFEST_ERR_STREAM_ID_RANGE:
        return "stream_id_exceeds_the_sixteen_bit_field"
    return "unknown_status"


# ── the field registry: the authoritative list of what the hash covers ────────


fn manifest_field_names() -> List[String]:
    """The hashed fields, in canonical byte order.

    Returned already sorted by `canonical.encode.sort_keys` rather than hand-ordered, so
    the object-key ordering is the frozen encoder's decision and not this file's. The
    encoder iterates THIS list, so a name here that `_write_field` cannot write is a
    refusal, and a struct field absent from here is caught by the count reconciliation.
    """
    var names = List[String]()
    names.append(String("rng_version"))
    names.append(String("rng_global_sentinel"))
    names.append(String("master_seed"))
    names.append(String("stream_names"))
    names.append(String("stream_ids"))
    names.append(String("input_shape"))
    names.append(String("reduction_shape"))
    return sort_keys(names)


fn manifest_derived_field_names() -> List[String]:
    """Fields deliberately NOT hashed, with the reason recorded in this docstring.

    `status` is this builder's verdict on the other seven fields, not an input to the run.
    Hashing it would make a refused manifest hash to something, which rule 4 forbids, and
    it cannot differ between two manifests whose other fields agree.
    """
    var names = List[String]()
    names.append(String("status"))
    return names^


fn manifest_declared_field_count() -> Int:
    """`MANIFEST_DECLARED_FIELDS` — the number of `var`s on `ReplayManifest`."""
    return MANIFEST_DECLARED_FIELDS


# ── encoding ──────────────────────────────────────────────────────────────────


fn _write_u64(mut out: List[UInt8], value: UInt64):
    """A `UInt64` as eight big-endian byte values inside a canonical array.

    NOT `write_int(Int(value))`: an `Int` is signed, so a seed above `2^63 - 1` would wrap
    to a negative and two distinct seeds could encode identically. NOT a decimal string
    either — `canonical.encode` puts no decimal formatting on the wire anywhere, precisely
    so nothing depends on a language's number formatter.
    """
    write_array_header(out, 8)
    for shift in range(7, -1, -1):
        write_int(out, Int((value >> UInt64(shift * 8)) & 0xFF))


fn _write_u64_list(mut out: List[UInt8], values: List[UInt64]):
    write_array_header(out, len(values))
    for i in range(len(values)):
        _write_u64(out, values[i])


fn _write_field(mut out: List[UInt8], m: ReplayManifest, name: String) -> Bool:
    """Append one field's canonical value. False when `name` is not a field this handles.

    False is a refusal, not a skip: a name registered in `manifest_field_names()` that
    reaches here unhandled means the registry and the encoder disagree, and the honest
    response is no digest at all.
    """
    if name == String("rng_version"):
        write_string(out, m.rng_version)
        return True
    if name == String("rng_global_sentinel"):
        _write_u64(out, m.rng_global_sentinel)
        return True
    if name == String("master_seed"):
        _write_u64(out, m.master_seed)
        return True
    if name == String("stream_names"):
        write_string_list(out, m.stream_names)
        return True
    if name == String("stream_ids"):
        _write_u64_list(out, m.stream_ids)
        return True
    if name == String("input_shape"):
        write_int_list(out, m.input_shape)
        return True
    if name == String("reduction_shape"):
        write_string(out, m.reduction_shape)
        return True
    return False


fn manifest_encode(m: ReplayManifest) -> List[UInt8]:
    """Canonical bytes for a manifest, or an EMPTY list if it cannot be encoded.

    An empty return is unambiguous: a real encoding always begins with an object tag and a
    count, so it is never empty. `manifest_digest` treats empty as a refusal.

    Encodes only the hashed registry, as a canonical object with byte-sorted keys, so the
    byte stream is the frozen encoder's and this module contributes no formatting of its
    own.
    """
    var out = List[UInt8]()
    if m.status != MANIFEST_OK:
        # A refused manifest has no bytes. Encoding it would produce a digest for a run
        # that cannot be replayed, which is the exact claim rule 4 forbids.
        return out^
    var names = manifest_field_names()
    write_object_header(out, len(names))
    for i in range(len(names)):
        write_string(out, names[i])
        if not _write_field(out, m, names[i]):
            var refused = List[UInt8]()
            return refused^
    return out^


fn manifest_digest(m: ReplayManifest) -> ManifestDigest:
    """`<encoding-version>:<sha256>` over the manifest's canonical bytes, or absent.

    Goes through `canonical.hash.versioned_digest`, so the digest carries the encoding
    rules that produced it and a future encoding is visibly different rather than merely
    unequal.
    """
    if m.status != MANIFEST_OK:
        return ManifestDigest(String(""), False, m.status)
    var bytes = manifest_encode(m)
    if len(bytes) == 0:
        return ManifestDigest(String(""), False, MANIFEST_ERR_UNHASHED_FIELD)
    return ManifestDigest(versioned_digest(bytes), True, MANIFEST_OK)


# ── building ──────────────────────────────────────────────────────────────────


fn _validate(
    rng_version_in: String, n_streams: Int, stream_names: List[String],
    n_dims: Int, input_shape: List[Int], reduction_shape: String
) -> Int:
    """The one validation path. Every builder routes through it (rule 4d).

    `master_seed` is not a parameter because there is nothing to check: every `UInt64` is a
    legitimate seed, so no value of it can mean "absent".

    Count relations, both rejected on mismatch rather than trusted:
        n_streams == len(stream_names)
        n_dims    == len(input_shape)
    Equality rather than `<=` because a declared count that is merely small still
    describes a different manifest than the list it came with, and the hash would record
    the list. Rejecting the mismatch is what makes the two agree.
    """
    if n_streams < 0 or n_streams != len(stream_names):
        return MANIFEST_ERR_STREAM_COUNT
    if n_dims < 0 or n_dims != len(input_shape):
        return MANIFEST_ERR_SHAPE_COUNT
    if len(rng_version_in) == 0:
        return MANIFEST_ERR_MISSING_RNG_VERSION
    if len(reduction_shape) == 0:
        return MANIFEST_ERR_MISSING_REDUCTION_SHAPE
    if n_dims == 0:
        return MANIFEST_ERR_MISSING_INPUT_SHAPE
    for i in range(n_dims):
        if input_shape[i] < 0:
            return MANIFEST_ERR_NEGATIVE_DIM
    for i in range(n_streams):
        if len(stream_names[i]) == 0:
            return MANIFEST_ERR_UNNAMED_STREAM
    return MANIFEST_OK


fn _derive_stream_ids(n_streams: Int, stream_names: List[String]) -> List[UInt64]:
    """Ids for the named streams, via the frozen `determinism.streams.stream_id`.

    Derived rather than accepted, and hashed alongside the names, so the manifest pins the
    name -> id mapping. If that mapping ever changed the digest would change, which is
    correct: the same names would then address different draws.

    Rule 1c arithmetic: ONE `UInt64` array of `n_streams`, and `_validate` has already
    established `n_streams == len(stream_names)`, so the allocation is bounded by an array
    the caller already holds. No separate ceiling is needed.
    """
    var ids = List[UInt64]()
    for i in range(n_streams):
        ids.append(stream_id(stream_names[i]))
    return ids^


fn _refused(status: Int) -> ReplayManifest:
    """A refused manifest. Every field is empty and none of them is a record of anything.

    Positional and complete on purpose: adding a `var` to `ReplayManifest` breaks this
    call site, which is mechanism 1 of the field-coverage gate.
    """
    return ReplayManifest(
        String(""), 0, 0, List[String](), List[UInt64](), List[Int](), String(""), status
    )


# Signature packing below is LOAD-BEARING: `apps/runtime/mojo_inventory.py` matches a
# signature inside a nine-line window, so a reflow that pushes the closing paren past line
# nine drops the function from the contract with no error (rule 2).
fn manifest_build_declared(
    rng_version_in: String, sentinel: UInt64, master_seed: UInt64,
    n_streams: Int, stream_names: List[String],
    n_dims: Int, input_shape: List[Int], reduction_shape: String
) -> ReplayManifest:
    """Build a manifest from explicitly declared identities, refusing an incomplete one.

    The explicit form exists so a caller replaying an ARCHIVED run can state the versions
    that run used rather than the ones this build implements — and so the refusal paths are
    reachable at all, which `manifest_build` cannot make them because it fills those
    fields from the kernels that own them.

    @capability manifest_build_declared
    complexity: O(n_streams + n_dims)
    counts:
    - n_streams == len(stream_names) [kernel_validated]
    - n_dims == len(input_shape) [kernel_validated]
    @endcapability
    """
    var status = _validate(
        rng_version_in, n_streams, stream_names, n_dims, input_shape, reduction_shape
    )
    if status != MANIFEST_OK:
        return _refused(status)
    if sentinel > MAX_STREAM_ID:
        return _refused(MANIFEST_ERR_STREAM_ID_RANGE)
    var ids = _derive_stream_ids(n_streams, stream_names)
    for i in range(len(ids)):
        if ids[i] > MAX_STREAM_ID:
            return _refused(MANIFEST_ERR_STREAM_ID_RANGE)
    var shape = List[Int]()
    for i in range(n_dims):
        shape.append(input_shape[i])
    var names = List[String]()
    for i in range(n_streams):
        names.append(stream_names[i])
    return ReplayManifest(
        rng_version_in, sentinel, master_seed, names^, ids^, shape^,
        reduction_shape, MANIFEST_OK
    )


fn manifest_build(
    master_seed: UInt64, n_streams: Int, stream_names: List[String],
    n_dims: Int, input_shape: List[Int]
) -> ReplayManifest:
    """Build a manifest for a run of THIS build, refusing an incomplete one.

    The generator identity, the global sentinel and the reduction shape are read from the
    kernels that own them — `counter_rng.rng_version`, `counter_rng.rng_global_sentinel`
    and `reduce_det.reduction_shape_id` — rather than restated here. A second copy of any
    of those numbers is a second thing to keep in step, and the copy is what drifts.

    @capability manifest_build
    complexity: O(n_streams + n_dims)
    counts:
    - n_streams == len(stream_names) [kernel_validated]
    - n_dims == len(input_shape) [kernel_validated]
    @endcapability
    """
    return manifest_build_declared(
        rng_version(), rng_global_sentinel(), master_seed, n_streams, stream_names,
        n_dims, input_shape, reduction_shape_id()
    )


fn manifest_same_run(a: ReplayManifest, b: ReplayManifest) -> Bool:
    """True when both manifests are valid and describe the same run.

    Compares digests rather than fields, so this cannot drift away from what the hash
    covers: if a field were dropped from the hash, this would stop distinguishing runs
    that differ in it, which the suite's per-field mutation test detects.
    """
    var da = manifest_digest(a)
    var db = manifest_digest(b)
    if not (da.present and db.present):
        return False
    return da.digest == db.digest


# ── the field-coverage harness ────────────────────────────────────────────────


fn manifest_perturb_field(m: ReplayManifest, field: String) -> ReplayManifest:
    """`m` with exactly one hashed field changed, for the coverage gate.

    Exported rather than test-local on purpose: the gate has to be driven by the SAME name
    list the encoder uses, and a mutation table living in the suite could fall out of step
    with the registry without anything failing. An unrecognised name returns a manifest
    whose status is `MANIFEST_ERR_UNHASHED_FIELD`, so a field added to the struct but not
    here is reported instead of silently passing.

    Every branch reconstructs the struct positionally, so adding a `var` breaks this
    function too.
    """
    if m.status != MANIFEST_OK:
        return _refused(m.status)
    var rv = m.rng_version
    var sent = m.rng_global_sentinel
    var seed = m.master_seed
    var names = m.stream_names.copy()
    var ids = m.stream_ids.copy()
    var shape = m.input_shape.copy()
    var shape_id = m.reduction_shape

    if field == String("rng_version"):
        rv = rv + "!"
    elif field == String("rng_global_sentinel"):
        # Downward, so the perturbed value stays inside the sixteen-bit field the counter
        # layout allocates. `rng_global_sentinel()` IS `MAX_STREAM_ID`, so `+ 1` would
        # produce a manifest the builder itself would refuse.
        sent = sent - 1 if sent > 0 else sent + 1
    elif field == String("master_seed"):
        seed = seed + 1
    elif field == String("stream_names"):
        names.append(String("perturbation"))
    elif field == String("stream_ids"):
        if len(ids) == 0:
            ids.append(UInt64(1))
        else:
            ids[0] = ids[0] + 1
    elif field == String("input_shape"):
        shape.append(1)
    elif field == String("reduction_shape"):
        shape_id = shape_id + "!"
    else:
        return _refused(MANIFEST_ERR_UNHASHED_FIELD)

    return ReplayManifest(
        rv, sent, seed, names^, ids^, shape^, shape_id, MANIFEST_OK
    )
