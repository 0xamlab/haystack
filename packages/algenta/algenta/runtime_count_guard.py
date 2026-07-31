"""Refuse an element count that exceeds the list it measures, before the runtime sees it.

Many kernels take a list and a separate count of how many of its elements to read. Reading
past the end inside the runtime is not an exception a caller can catch — it ends the whole
runtime process, and with it every dataset that process was holding for other calls. That
makes it something the client has to decline, not something the runtime can report.

The relation between a count and the list it measures is published per function in the
bundled contract (`count_relations`). A function with no published relation is passed
through untouched: guessing from a parameter name would refuse valid calls, because a
parameter called `n` is an element count in one function and a dimension in another.

Two things this guard deliberately does NOT skip, because skipping them made it decorative
on the functions that declare a relation:

* A NEGATIVE value. For a count it is harmless — `for i in range(-3)` reads nothing — but a
  relation whose `role` is `index` (or that carries a `plus`) describes a direct subscript,
  and the runtime does not read a negative index from the end of the list: it aborts the
  process. `count_fits` therefore takes the role.
* A bounded argument that is not a Python list. `"@u8:<base64>"` is a supported spelling of
  `List[Float64]`, and its element count is exact, so it is measured like any other list. A
  bounded argument that is present but whose length cannot be established here — a deferred
  `"@handle"` or `"$k"` reference — is REFUSED, because the failure being prevented is a dead
  process rather than an error response.

This mirrors the server-side check in ``apps/runtime/mojo_count_relations.py``;
``tests/test_runtime_count_relations.py`` asserts the two agree case by case, including the
negative-index, packed-buffer and deferred-reference cases. The two files must be changed
together — a guard that is stricter on one path than the other means the same call is
accepted or refused depending on which SDK made it.
"""

from __future__ import annotations

from typing import Any

from algenta.runtime_library_contract import (
    RuntimeCountRelation,
    RuntimeFunctionSpec,
    RuntimeLibraryContractError,
)

__all__ = [
    "COUNT_RELATION_ERROR_CODE",
    "PACKED_FLOAT64_PREFIX",
    "UNMEASURABLE_ARGUMENT_ERROR_CODE",
    "count_fits",
    "enforce_count_relations",
    "measured_element_count",
    "packed_float64_element_count",
]

COUNT_RELATION_ERROR_CODE = "count_exceeds_list_length"

# A bounded argument whose length cannot be established is refused with the existing
# `invalid_arguments` code rather than a new one: nothing was found to exceed anything, so
# calling it `count_exceeds_list_length` would be a false statement about the call.
UNMEASURABLE_ARGUMENT_ERROR_CODE = "invalid_arguments"

_ROLE_COUNT = "count"
_ROLE_INDEX = "index"

# A packed uint8 buffer: one decoded byte is one Float64. Accepted wherever
# `List[Float64]` is accepted (`runtime_library_transport._normalize_value`).
PACKED_FLOAT64_PREFIX = "@u8:"

# The base64 alphabet the runtime's decoder accepts. Everything else — `=` padding,
# whitespace, anything invalid — it SKIPS, so this must skip it too or the two sides would
# disagree about the element count.
_BASE64_SEXTETS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
)


def _subscripts_directly(relation: RuntimeCountRelation) -> bool:
    """Whether a negative value would be a read at a negative offset, not an empty loop.

    True for `role="index"` and for any relation with a positive `plus`: `x + 1 <= len(a)` is
    the statement that the element at offset `x` is read, so `x < 0` reads `a[-1]`.
    """
    return relation.role == _ROLE_INDEX or relation.plus > 0


def count_fits(factors: list[int], available: int, *, role: str = _ROLE_COUNT) -> bool:
    """Whether the product of `factors` is at most `available`, without multiplying.

    The naive `rows * cols <= len(a)` is wrong: inside the runtime `Int` is 64 bits wide and
    the multiply WRAPS, so `3 * 6148914691236517206 == 2` satisfies such a check and the
    kernel then reads far past the end of a two-element list. Dividing instead of
    multiplying is exact for integers — `f * p <= L` iff `p <= L // f`, so the floor discards
    nothing — and it asks the same question the runtime's own shape check asks, so the two
    sides agree on which shapes are admissible.

    `role` decides what a non-positive factor means, and it is the difference between a
    refusal and a dead process:

    * `count` — a factor of 0 makes the product 0, and a negative factor makes that
      dimension's loop empty (`range(-3)` reads nothing), so nothing is read.
    * `index` — the value is a subscript. A negative subscript is not read from the end of
      the list; it aborts the runtime process. Inadmissible.
    """
    if available < 0:
        return False
    if role == _ROLE_INDEX and any(factor < 0 for factor in factors):
        return False
    if any(factor == 0 for factor in factors):
        # The product is 0 whatever the other factors are, so nothing is read. Checked before
        # the loop: `[1, 0]` needs 0 elements, and dividing incrementally would refuse it on
        # the leading 1.
        return True
    remaining = available
    for factor in factors:
        if factor < 0:
            return True
        if factor > remaining:
            return False
        remaining //= factor
    return True


def packed_float64_element_count(value: str) -> int:
    """Elements the runtime will decode from a `"@u8:<base64>"` buffer.

    Counted the way the runtime's decoder counts: each base64-alphabet character contributes
    6 bits, a byte is emitted for every 8 bits accumulated, and any other character is
    skipped. `"@u8:AQID"` is 4 sextets → 3 bytes → 3 elements.
    """
    sextets = sum(
        1 for character in value[len(PACKED_FLOAT64_PREFIX) :] if character in _BASE64_SEXTETS
    )
    return (sextets * 6) // 8


def measured_element_count(value: Any) -> int | None:
    """How many elements the runtime will see in `value`, or `None` if that is unknowable.

    `None` means the length does not exist on this side of the wire: a `"@handle"` dataset
    reference (the runtime reports a resident dataset's BYTES, not its element count) or a
    `"$k"` pipeline reference (node `k` has not run yet).
    """
    if isinstance(value, list):
        return len(value)
    if isinstance(value, str) and value.startswith(PACKED_FLOAT64_PREFIX):
        return packed_float64_element_count(value)
    return None


def _requirement(relation: RuntimeCountRelation, factors: list[int]) -> str:
    names = " * ".join(relation.factors)
    values = " * ".join(str(value) for value in factors)
    if relation.plus:
        return f"{names} + {relation.plus} = {values} + {relation.plus}"
    return f"{names} = {values}"


def _relation_text(relation: RuntimeCountRelation, list_name: str) -> str:
    product = " * ".join(relation.factors)
    if relation.plus:
        product = f"{product} + {relation.plus}"
    if relation.scope == "element_length":
        return f"{product} <= len({list_name}[k])"
    return f"{product} <= len({list_name})"


def _measured_lengths(
    relation: RuntimeCountRelation, listed: Any
) -> list[tuple[int | None, int | None]]:
    """`(element count, element index)` pairs to check; a `None` count is UNMEASURABLE."""
    if relation.scope == "length":
        return [(measured_element_count(listed), None)]
    if not isinstance(listed, list):
        return [(None, None)]
    return [(measured_element_count(element), index) for index, element in enumerate(listed)]


def _refuse_unmeasurable(
    module_name: str,
    function: RuntimeFunctionSpec,
    relation: RuntimeCountRelation,
    list_name: str,
    listed: Any,
    element_index: int | None,
) -> None:
    target = f"{list_name}[{element_index}]" if element_index is not None else list_name
    if element_index is not None and isinstance(listed, list):
        shown = listed[element_index]
    else:
        shown = listed
    encoding = shown if isinstance(shown, str) else type(shown).__name__
    # Word for word the message `mojo_count_relations._unmeasurable_details` produces; the
    # shared-table test compares the text, not only the verdict.
    message = (
        f"{module_name}.{function.name}: '{target}' is bounded by a declared element count "
        f"({_relation_text(relation, list_name)}), and the length of {encoding!r} cannot "
        "be determined before the call. Reading past the end of that list inside the runtime "
        "worker is an uncatchable abort of the whole process, so the call is declined rather "
        f"than sent unchecked. Pass '{list_name}' as a list, or as a "
        f'"{PACKED_FLOAT64_PREFIX}<base64>" buffer, both of which can be measured here.'
    )
    details: dict[str, Any] = {
        "module": module_name,
        "function": function.name,
        "parameter": (
            relation.factors[0] if len(relation.factors) == 1 else list(relation.factors)
        ),
        "list_parameter": list_name,
        "unmeasurable_argument": encoding,
        "reason": "unmeasurable_bounded_argument",
        "role": relation.role,
    }
    if element_index is not None:
        details["list_element_index"] = element_index
    raise RuntimeLibraryContractError(
        UNMEASURABLE_ARGUMENT_ERROR_CODE, message, details
    )


def enforce_count_relations(
    module_name: str,
    function: RuntimeFunctionSpec,
    normalized_args: list[Any],
) -> None:
    """Raise for the first published relation the arguments break; otherwise return.

    Fail-open is per function and cannot leak: an undeclared function has no relations and
    returns on the first line, which is independent of every other function's check.

    An argument that was never PASSED is a pass — an omitted defaulted parameter cannot be
    over-read. An argument that IS passed in a form whose length cannot be measured is
    refused: a deferred handle is resolved inside the runtime, so an over-read through it is
    not an error the runtime can return, it is the process ending. A count of the wrong type
    is still a pass, and the normal type checks report it.
    """
    if not function.count_relations:
        return
    supplied = dict(zip((param.name for param in function.params), normalized_args, strict=False))

    for relation in function.count_relations:
        factors: list[int] = []
        for name in relation.factors:
            value = supplied.get(name)
            if isinstance(value, bool) or not isinstance(value, int):
                factors = []
                break
            factors.append(value)
        if not factors:
            continue
        role = _ROLE_INDEX if _subscripts_directly(relation) else _ROLE_COUNT

        for list_name in relation.bounds:
            if list_name not in supplied:
                continue
            listed = supplied[list_name]
            for length, element_index in _measured_lengths(relation, listed):
                if length is None:
                    _refuse_unmeasurable(
                        module_name, function, relation, list_name, listed, element_index
                    )
                    return
                if count_fits(factors, length - relation.plus, role=role):
                    continue
                target = f"{list_name}[{element_index}]" if element_index is not None else list_name
                counted = ", ".join(
                    f"{name}={value}"
                    for name, value in zip(relation.factors, factors, strict=True)
                )
                requirement = _requirement(relation, factors)
                if role == _ROLE_INDEX and any(factor < 0 for factor in factors):
                    message = (
                        f"{module_name}.{function.name}: {counted} is a negative index into "
                        f"'{target}'. The runtime does not read a negative index from the end "
                        "of the list; it aborts the whole worker process. An index must be 0 "
                        "or greater."
                    )
                elif role == _ROLE_INDEX:
                    message = (
                        f"{module_name}.{function.name}: {counted} indexes past the end of "
                        f"'{target}', which has {length} element(s); reading it would abort "
                        f"the runtime worker. '{list_name}' must hold at least "
                        f"{requirement} element(s)."
                    )
                else:
                    message = (
                        f"{module_name}.{function.name}: {counted} counts more elements than "
                        f"'{target}' holds ({length}); reading them would abort the runtime "
                        f"worker. '{list_name}' must hold at least {requirement} element(s)."
                    )
                details: dict[str, Any] = {
                    "module": module_name,
                    "function": function.name,
                    "parameter": (
                        relation.factors[0]
                        if len(relation.factors) == 1
                        else list(relation.factors)
                    ),
                    "count": factors[0] if len(factors) == 1 else factors,
                    "required_elements": requirement,
                    "list_parameter": list_name,
                    "actual_length": length,
                    "role": role,
                }
                if element_index is not None:
                    details["list_element_index"] = element_index
                raise RuntimeLibraryContractError(
                    COUNT_RELATION_ERROR_CODE, message, details
                )
