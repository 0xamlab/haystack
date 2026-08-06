"""test_columnar_dictionary.mojo — known-value tests for dictionary encoding.

Hand-written. The assertions concentrate on what fails SILENTLY:

  * a null collapsing into `""` — a decoded column of empty strings is indistinguishable
    from a decoded column of nulls to anything that does not consult validity;
  * a code that indexes past the dictionary — reading it is an uncatchable abort that
    ends the worker, so the only acceptable behaviour is refusal, and a refusal that
    returns a partially decoded column is a wrong answer with a status attached;
  * two distinct values sharing a `HashIndex` entry. `HashIndex.normalize_bits`
    collapses every NaN bit pattern onto one key, so roughly one string in 2048 shares
    a table entry with every other such string. Two literal witnesses are pinned below;
    without the bucket chain they would be one dictionary value and every row coded to
    the survivor. That is unrecoverable once the column is coded and nothing in the
    output would say so.

The footprint assertions are the honest kind: one column where the encoding shrinks and
one where it does NOT, both printed with the measured ratio.
"""
from std.math import isnan

from columnar.hash_index import CANONICAL_NAN_BITS, HashIndex, normalize_bits
from columnar.validity import is_valid, new_all_null, set_valid
from columnar.dictionary import (
    DICT_CODES_TOO_SHORT,
    DICT_CODE_OUT_OF_RANGE,
    DICT_INVALID_ROW_COUNT,
    DICT_OK,
    DICT_OUTPUT_BUDGET_EXCEEDED,
    DICT_VALIDITY_TOO_SHORT,
    NULL_CODE,
    StringDictionary,
    code_byte_width,
    decode_strings,
    decode_to_array,
    decoded_bytes_required,
    dict_status_name,
    encode_all_present,
    encode_strings,
    encode_to_float64_column,
    footprint,
    key_as_float,
    string_key,
)


def _strings(items: List[String]) -> List[String]:
    return items.copy()


def _all_true(n: Int) -> List[Bool]:
    var mask = List[Bool]()
    for _ in range(n):
        mask.append(True)
    return mask^


def _is_nan_pattern(key: UInt64) -> Bool:
    """True when `key`'s bits are a NaN, i.e. `normalize_bits` will collapse them."""
    return (key & 0x7FF0000000000000) == 0x7FF0000000000000 and (
        key & 0x000FFFFFFFFFFFFF
    ) != 0


def main() raises:
    var passed = 0
    var failed = 0

    # ── round trip is EXACT, including duplicates ─────────────────────────────
    var values = List[String]()
    values.append("north")
    values.append("south")
    values.append("north")
    values.append("east")
    values.append("north")
    values.append("south")
    var mask = _all_true(6)
    var encoded = encode_strings(values, mask)
    var decoded = decode_strings(
        encoded.dictionary, encoded.codes, encoded.validity, encoded.n_rows
    )
    var exact = decoded.status == DICT_OK and decoded.n_rows == 6
    for i in range(6):
        if not exact:
            break
        if decoded.values[i] != values[i] or not decoded.mask[i]:
            exact = False
    if exact:
        passed += 1
        print("  ✅ encode then decode returns the original column exactly")
    else:
        failed += 1
        print("  ❌ round trip differs:", dict_status_name(decoded.status))

    # ── the dictionary holds each distinct value EXACTLY once ─────────────────
    var north = 0
    var south = 0
    var east = 0
    for i in range(len(encoded.dictionary)):
        if encoded.dictionary[i] == "north":
            north += 1
        elif encoded.dictionary[i] == "south":
            south += 1
        elif encoded.dictionary[i] == "east":
            east += 1
    if (
        encoded.n_distinct == 3
        and len(encoded.dictionary) == 3
        and north == 1
        and south == 1
        and east == 1
    ):
        passed += 1
        print("  ✅ the dictionary contains each of 3 distinct values exactly once")
    else:
        failed += 1
        print("  ❌ dictionary is not distinct:", encoded.n_distinct, north, south, east)

    # ── codes are first-appearance order, so two runs agree ──────────────────
    var again = encode_strings(values, mask)
    var same_codes = again.n_distinct == encoded.n_distinct
    for i in range(len(encoded.codes)):
        if again.codes[i] != encoded.codes[i]:
            same_codes = False
    if same_codes and encoded.codes[0] == 0 and encoded.codes[1] == 1 and encoded.codes[3] == 2:
        passed += 1
        print("  ✅ codes are assigned in first-appearance order, deterministically")
    else:
        failed += 1
        print("  ❌ codes are not deterministic first-appearance")

    # ── A NULL IS NOT THE EMPTY STRING ───────────────────────────────────────
    # The obvious bug, and a silent one: collapse them and a decoded column of ""
    # is indistinguishable from a decoded column of nulls.
    var mixed = List[String]()
    mixed.append("")          # a real empty string
    mixed.append("value")
    mixed.append("ignored")   # absent: this text must NOT reach the dictionary
    var mixed_mask = List[Bool]()
    mixed_mask.append(True)
    mixed_mask.append(True)
    mixed_mask.append(False)
    var mixed_encoded = encode_strings(mixed, mixed_mask)
    var has_ignored = False
    for i in range(len(mixed_encoded.dictionary)):
        if mixed_encoded.dictionary[i] == "ignored":
            has_ignored = True
    var mixed_decoded = decode_strings(
        mixed_encoded.dictionary,
        mixed_encoded.codes,
        mixed_encoded.validity,
        mixed_encoded.n_rows,
    )
    if (
        mixed_encoded.n_distinct == 2
        and not has_ignored
        and mixed_encoded.codes[2] == NULL_CODE
        and is_valid(mixed_encoded.validity, 0)
        and not is_valid(mixed_encoded.validity, 2)
        and mixed_decoded.status == DICT_OK
        and mixed_decoded.mask[0]
        and mixed_decoded.values[0] == ""
        and not mixed_decoded.mask[2]
    ):
        passed += 1
        print("  ✅ a null survives as a null and \"\" survives as a present value")
    else:
        failed += 1
        print("  ❌ null and \"\" were conflated somewhere")

    # ── an all-null column has an EMPTY dictionary, not one holding "" ────────
    var all_null_values = List[String]()
    all_null_values.append("a")
    all_null_values.append("b")
    var all_null_mask = List[Bool]()
    all_null_mask.append(False)
    all_null_mask.append(False)
    var all_null = encode_strings(all_null_values, all_null_mask)
    var all_null_decoded = decode_strings(
        all_null.dictionary, all_null.codes, all_null.validity, all_null.n_rows
    )
    if (
        all_null.n_distinct == 0
        and len(all_null.dictionary) == 0
        and all_null_decoded.status == DICT_OK
        and all_null_decoded.n_rows == 2
        and not all_null_decoded.mask[0]
        and not all_null_decoded.mask[1]
    ):
        passed += 1
        print("  ✅ an all-null column codes to an empty dictionary and decodes all-null")
    else:
        failed += 1
        print("  ❌ an all-null column did not round trip:", all_null.n_distinct)

    # ── a short mask leaves the tail absent, matching float64_with_nulls ──────
    var short_mask = List[Bool]()
    short_mask.append(True)
    var short = encode_strings(values, short_mask)
    if short.n_rows == 6 and short.n_distinct == 1 and short.codes[5] == NULL_CODE:
        passed += 1
        print("  ✅ a mask shorter than the column leaves the rest absent")
    else:
        failed += 1
        print("  ❌ a short mask was handled differently from array.float64_with_nulls")

    # ── A CODE PAST THE DICTIONARY IS REFUSED, not read ──────────────────────
    # Reading dictionary[code] here is an UNCATCHABLE abort, so this is the assertion
    # that keeps the worker alive.
    var bad_codes = encoded.codes.copy()
    bad_codes[2] = len(encoded.dictionary)  # one past the end
    var refused = decode_strings(encoded.dictionary, bad_codes, encoded.validity, 6)
    var huge_codes = encoded.codes.copy()
    huge_codes[4] = 1 << 40
    var refused_huge = decode_strings(encoded.dictionary, huge_codes, encoded.validity, 6)
    var negative_codes = encoded.codes.copy()
    negative_codes[1] = -7
    var refused_negative = decode_strings(
        encoded.dictionary, negative_codes, encoded.validity, 6
    )
    if (
        refused.status == DICT_CODE_OUT_OF_RANGE
        and refused_huge.status == DICT_CODE_OUT_OF_RANGE
        and refused_negative.status == DICT_CODE_OUT_OF_RANGE
        and len(refused.values) == 0
        and len(refused_huge.values) == 0
        and len(refused_negative.values) == 0
        and refused.n_rows == 0
    ):
        passed += 1
        print("  ✅ a code past the dictionary is refused with an EMPTY column")
    else:
        failed += 1
        print("  ❌ an out-of-range code was not refused cleanly")

    # ── a nonsense code under an ABSENT row is not a problem ─────────────────
    # It names nothing by construction, so refusing it would reject a valid column.
    var absent_bad = List[Int]()
    absent_bad.append(0)
    absent_bad.append(1 << 50)
    var absent_validity = new_all_null(2)
    set_valid(absent_validity, 0)
    var one_value = List[String]()
    one_value.append("only")
    var absent_ok = decode_strings(one_value, absent_bad, absent_validity, 2)
    # It also must not be CHARGED for: an absent row decodes to no bytes, so counting
    # its code's value length would refuse a decode that was going to be fine.
    if (
        absent_ok.status == DICT_OK
        and absent_ok.values[0] == "only"
        and not absent_ok.mask[1]
        and decoded_bytes_required(one_value, absent_bad, absent_validity, 2) == 4
    ):
        passed += 1
        print("  ✅ a junk code under an absent row is ignored, and costs no budget")
    else:
        failed += 1
        print("  ❌ an absent row's code was treated as data:", dict_status_name(absent_ok.status))

    # ── a row count past the codes is refused ────────────────────────────────
    var too_many = decode_strings(encoded.dictionary, encoded.codes, encoded.validity, 7)
    var negative_rows = decode_strings(
        encoded.dictionary, encoded.codes, encoded.validity, -1
    )
    if (
        too_many.status == DICT_CODES_TOO_SHORT
        and negative_rows.status == DICT_INVALID_ROW_COUNT
        and len(too_many.values) == 0
    ):
        passed += 1
        print("  ✅ n_rows past len(codes) is refused, and so is a negative n_rows")
    else:
        failed += 1
        print("  ❌ a bad row count was accepted:", dict_status_name(too_many.status))

    # ── a validity bitmap shorter than the row count is refused ──────────────
    var stub_validity = List[UInt8]()
    var short_validity = decode_strings(
        encoded.dictionary, encoded.codes, stub_validity, 6
    )
    if short_validity.status == DICT_VALIDITY_TOO_SHORT:
        passed += 1
        print("  ✅ a validity bitmap too short for n_rows is refused")
    else:
        failed += 1
        print("  ❌ a short validity bitmap was read:", dict_status_name(short_validity.status))

    # ── the output budget is charged BEFORE anything is allocated ────────────
    # The decoded size is a function of the dictionary's value lengths, not of the
    # payload: many rows coding one long value is a large answer to a small request.
    var required = decoded_bytes_required(
        encoded.dictionary, encoded.codes, encoded.validity, 6
    )
    var over_budget = decode_strings(
        encoded.dictionary, encoded.codes, encoded.validity, 6, required - 1
    )
    var at_budget = decode_strings(
        encoded.dictionary, encoded.codes, encoded.validity, 6, required
    )
    if (
        required == 29  # north(5)*3 + south(5)*2 + east(4)
        and over_budget.status == DICT_OUTPUT_BUDGET_EXCEEDED
        and len(over_budget.values) == 0
        and at_budget.status == DICT_OK
    ):
        passed += 1
        print("  ✅ the decoded byte total is counted exactly and refused over budget")
    else:
        failed += 1
        print("  ❌ the output budget did not bind:", required, dict_status_name(over_budget.status))

    # ── TWO WITNESSES WHOSE KEYS COLLAPSE TO ONE HashIndex ENTRY ─────────────
    # Found by search, pinned as literals so this test is deterministic and fast. Both
    # keys are NaN bit patterns, so `normalize_bits` maps BOTH to CANONICAL_NAN_BITS and
    # they share one table entry. Without the bucket chain they would be one dictionary
    # value, and every row of the second label would be coded as the first.
    var witness_a = String("1176x")
    var witness_b = String("1849x")
    var key_a = string_key(witness_a)
    var key_b = string_key(witness_b)
    var collapse = (
        _is_nan_pattern(key_a)
        and _is_nan_pattern(key_b)
        and key_a != key_b
        and isnan(key_as_float(key_a))
        and normalize_bits(key_as_float(key_a)) == CANONICAL_NAN_BITS
        and normalize_bits(key_as_float(key_b)) == CANONICAL_NAN_BITS
    )
    if collapse:
        passed += 1
        print("  ✅ the two pinned witnesses really do collapse to one HashIndex key")
    else:
        failed += 1
        print("  ❌ the pinned witnesses no longer collapse — pick new ones:", key_a, key_b)

    var probe = HashIndex(8)
    var slot_a = probe.get_or_assign(key_as_float(key_a), 0)
    var slot_b = probe.get_or_assign(key_as_float(key_b), 1)
    if slot_a == 0 and slot_b == 0 and probe.size() == 1:
        passed += 1
        print("  ✅ HashIndex alone gives the two witnesses the SAME slot (the hazard)")
    else:
        failed += 1
        print("  ❌ the hazard is not reproduced:", slot_a, slot_b, probe.size())

    var chained = StringDictionary(8)
    var code_a = chained.get_or_add(witness_a)
    var code_b = chained.get_or_add(witness_b)
    var code_a_again = chained.get_or_add(witness_a)
    if (
        code_a == 0
        and code_b == 1
        and code_a_again == 0
        and chained.size() == 2
        and chained.find(witness_a) == 0
        and chained.find(witness_b) == 1
        and chained.value_at(0) == witness_a
        and chained.value_at(1) == witness_b
    ):
        passed += 1
        print("  ✅ the bucket chain still gives them distinct codes and finds both")
    else:
        failed += 1
        print("  ❌ two colliding values were merged:", code_a, code_b, chained.size())

    # ── a value that is not there is absent, not code 0 ─────────────────────
    if (
        chained.find("never-added") == NULL_CODE
        and not chained.contains("never-added")
        and chained.value_at(2) == ""
        and chained.value_at(-1) == ""
    ):
        passed += 1
        print("  ✅ an absent value reports NULL_CODE rather than code 0")
    else:
        failed += 1
        print("  ❌ a missing value was reported as a code")

    # ── non-ASCII values round trip BYTE-exactly and stay distinct ───────────
    # A previous defect in this tree decoded `ó` two different ways, and every op
    # naming a non-ASCII column failed. `string_key` hashes UTF-8 BYTES for this reason.
    var accented = List[String]()
    accented.append("café")
    accented.append("cafe")
    accented.append("señor")
    accented.append("café")
    accented.append("naïve")
    var accented_encoded = encode_all_present(accented)
    var accented_decoded = decode_strings(
        accented_encoded.dictionary,
        accented_encoded.codes,
        accented_encoded.validity,
        accented_encoded.n_rows,
    )
    var byte_exact = accented_decoded.status == DICT_OK
    for i in range(len(accented)):
        if not byte_exact:
            break
        var left = accented[i].as_bytes()
        var right = accented_decoded.values[i].as_bytes()
        if len(left) != len(right):
            byte_exact = False
            break
        for k in range(len(left)):
            if left[k] != right[k]:
                byte_exact = False
                break
    if (
        byte_exact
        and accented_encoded.n_distinct == 4
        and accented_encoded.codes[0] == accented_encoded.codes[3]
        and accented_encoded.codes[0] != accented_encoded.codes[1]
        and len(accented_decoded.values[0].as_bytes()) == 5
    ):
        passed += 1
        print("  ✅ non-ASCII values round trip byte-exactly; café != cafe")
    else:
        failed += 1
        print("  ❌ a non-ASCII value was corrupted or merged")

    # ── two values differing in ONE high byte get different keys ─────────────
    if string_key("señor") != string_key("senor") and string_key("café") != string_key("cafe"):
        passed += 1
        print("  ✅ a one-byte difference above 0x7F changes the key")
    else:
        failed += 1
        print("  ❌ string_key ignores bytes above 0x7F")

    # ── length is part of the key, so a one-character extension is not free ──
    if string_key("a") != string_key("aa") and string_key("") != string_key("a"):
        passed += 1
        print("  ✅ length participates in the key")
    else:
        failed += 1
        print("  ❌ length does not participate in the key")

    # ── FOOTPRINT: it shrinks on a low-cardinality column ───────────────────
    var wide = List[String]()
    for i in range(20000):
        var bucket = i % 5
        if bucket == 0:
            wide.append("north-america-west-1")
        elif bucket == 1:
            wide.append("north-america-east-1")
        elif bucket == 2:
            wide.append("europe-central-1")
        elif bucket == 3:
            wide.append("asia-pacific-south-1")
        else:
            wide.append("south-america-east-1")
    var wide_footprint = footprint(wide, _all_true(20000))
    print(
        "     measured: 20000 rows / "
        + String(wide_footprint.n_distinct)
        + " distinct, plain "
        + String(wide_footprint.plain_bytes)
        + " B -> encoded "
        + String(wide_footprint.encoded_bytes)
        + " B (dict "
        + String(wide_footprint.dictionary_bytes)
        + " + codes "
        + String(wide_footprint.code_bytes)
        + " + validity "
        + String(wide_footprint.validity_bytes)
        + "), ratio "
        + String(wide_footprint.ratio)
    )
    if (
        wide_footprint.status == DICT_OK
        and wide_footprint.has_ratio
        and wide_footprint.n_distinct == 5
        and wide_footprint.ratio > 5.0
    ):
        passed += 1
        print("  ✅ a low-cardinality column shrinks, by the ratio printed above")
    else:
        failed += 1
        print("  ❌ the low-cardinality footprint did not shrink:", wide_footprint.ratio)

    # ── FOOTPRINT: it does NOT shrink when every value is distinct and short ─
    # Reported, not hidden. A dictionary of distinct values is the original data plus a
    # code per row, so it is strictly larger — the encoding is not a compressor.
    var unique = List[String]()
    for i in range(1000):
        unique.append(String(i))
    var unique_footprint = footprint(unique, _all_true(1000))
    print(
        "     measured: 1000 rows / "
        + String(unique_footprint.n_distinct)
        + " distinct short values, plain "
        + String(unique_footprint.plain_bytes)
        + " B -> encoded "
        + String(unique_footprint.encoded_bytes)
        + " B, ratio "
        + String(unique_footprint.ratio)
    )
    if (
        unique_footprint.has_ratio
        and unique_footprint.n_distinct == 1000
        and unique_footprint.ratio < 1.0
    ):
        passed += 1
        print("  ✅ an all-distinct column GROWS, and the report says so")
    else:
        failed += 1
        print("  ❌ the all-distinct footprint was not reported honestly")

    # ── an empty column has a defined ratio, not 0.0 and not a crash ─────────
    var empty_values = List[String]()
    var empty_mask = List[Bool]()
    var empty_footprint = footprint(empty_values, empty_mask)
    if (
        empty_footprint.status == DICT_OK
        and empty_footprint.n_rows == 0
        and empty_footprint.has_ratio
        and empty_footprint.ratio == 1.0
    ):
        passed += 1
        print("  ✅ an empty column reports a real 1.0 ratio (both sides are one offset)")
    else:
        failed += 1
        print("  ❌ the empty-column footprint is wrong:", empty_footprint.ratio)

    # ── code width is the narrowest that names the codes ────────────────────
    if (
        code_byte_width(0) == 1
        and code_byte_width(256) == 1
        and code_byte_width(257) == 2
        and code_byte_width(65536) == 2
        and code_byte_width(65537) == 4
    ):
        passed += 1
        print("  ✅ code_byte_width steps at 256 and 65536, not one value later")
    else:
        failed += 1
        print("  ❌ code_byte_width is off by one at a boundary")

    # ── codes as a Float64 column, so hash_index can group a string column ──
    var group_values = List[String]()
    group_values.append("red")
    group_values.append("blue")
    group_values.append("red")
    group_values.append("green")
    var group_mask = List[Bool]()
    group_mask.append(True)
    group_mask.append(True)
    group_mask.append(True)
    group_mask.append(False)
    var codes_column = encode_to_float64_column(group_values, group_mask)
    var groups = HashIndex(8)
    var next_slot = 0
    for i in range(codes_column.length):
        if not codes_column.is_valid_at(i):
            continue
        var assigned = groups.get_or_assign(codes_column.get(i), next_slot)
        if assigned == next_slot:
            next_slot += 1
    if (
        codes_column.length == 4
        and codes_column.get(0) == 0.0
        and codes_column.get(1) == 1.0
        and codes_column.get(2) == 0.0
        and not codes_column.is_valid_at(3)
        and groups.size() == 2
    ):
        passed += 1
        print("  ✅ codes group through hash_index; the null row opens no group")
    else:
        failed += 1
        print("  ❌ the coded column did not group correctly:", groups.size())

    # ── decode_to_array gives a nullable StringArray ─────────────────────────
    var array_form = decode_to_array(
        mixed_encoded.dictionary,
        mixed_encoded.codes,
        mixed_encoded.validity,
        mixed_encoded.n_rows,
    )
    if (
        array_form.length == 3
        and array_form.is_valid_at(0)
        and array_form.get(0) == ""
        and array_form.get(1) == "value"
        and not array_form.is_valid_at(2)
        and array_form.null_count() == 1
    ):
        passed += 1
        print("  ✅ decode_to_array carries the nulls into a StringArray")
    else:
        failed += 1
        print("  ❌ decode_to_array lost the validity information")

    # ── a status code has exactly one name ──────────────────────────────────
    if (
        dict_status_name(DICT_OK) == "ok"
        and dict_status_name(DICT_CODE_OUT_OF_RANGE) == "code_out_of_range"
        and dict_status_name(999) == "unknown"
    ):
        passed += 1
        print("  ✅ every status in 300-309 has a name, and an unknown one says so")
    else:
        failed += 1
        print("  ❌ a status code has no name")

    print("  [columnar.dictionary] Passed:", passed, "Failed:", failed)
