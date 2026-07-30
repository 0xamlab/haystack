"""
numeric.contract — aggregation identity and the null/empty policy. Zero Python.

Tokens map to integer opcodes, so nothing downstream depends on a spelling. Both
`"avg"` and `"mean"` are accepted; `"avg"` is what is echoed back, because that is
what the public wire already carries.

An unrecognised token is an error, not a default. The existing paths fall back to
SUM when they do not recognise a token, which turns a typo into a plausible wrong
number — the single worst outcome for an aggregation, since nothing downstream can
tell that it happened.
"""

comptime AGG_UNKNOWN: Int = -1
comptime AGG_SUM: Int = 0
comptime AGG_AVG: Int = 1
comptime AGG_MIN: Int = 2
comptime AGG_MAX: Int = 3
comptime AGG_COUNT: Int = 4
comptime AGG_VAR: Int = 5
comptime AGG_STD: Int = 6
comptime AGG_MEDIAN: Int = 7

# Echoed in errors so a caller sees what is available instead of guessing.
comptime ACCEPTED_TOKENS: String = "sum, avg (alias mean), min, max, count, var, std, median"


fn parse_aggregation(token: String) -> Int:
    """Opcode for an aggregation token, or `AGG_UNKNOWN`.

    `mean` is accepted as an alias for `avg` so callers written against either
    vocabulary work. Never guesses: an unrecognised token returns AGG_UNKNOWN and the
    caller is expected to raise, not substitute.
    """
    if token == "sum":
        return AGG_SUM
    if token == "avg" or token == "mean":
        return AGG_AVG
    if token == "min":
        return AGG_MIN
    if token == "max":
        return AGG_MAX
    if token == "count":
        return AGG_COUNT
    if token == "var" or token == "variance":
        return AGG_VAR
    if token == "std" or token == "stddev":
        return AGG_STD
    if token == "median":
        return AGG_MEDIAN
    return AGG_UNKNOWN


fn aggregation_token(opcode: Int) -> String:
    """The canonical spelling for an opcode — one name out, whatever came in."""
    if opcode == AGG_SUM:
        return "sum"
    if opcode == AGG_AVG:
        return "avg"
    if opcode == AGG_MIN:
        return "min"
    if opcode == AGG_MAX:
        return "max"
    if opcode == AGG_COUNT:
        return "count"
    if opcode == AGG_VAR:
        return "var"
    if opcode == AGG_STD:
        return "std"
    if opcode == AGG_MEDIAN:
        return "median"
    return "unknown"


fn is_valid_aggregation(token: String) -> Bool:
    return parse_aggregation(token) != AGG_UNKNOWN


fn unknown_aggregation_error(token: String) -> String:
    """The error for an unrecognised token — names the accepted set."""
    return (
        '{"error":"unknown_aggregation: '
        + token
        + '","error_code":"unknown_aggregation","error_message":"Unknown aggregation \''
        + token
        + "'. Accepted: "
        + ACCEPTED_TOKENS
        + '"}'
    )


fn empty_yields_null(opcode: Int) -> Bool:
    """True when an empty input has no answer, as opposed to a zero.

    `count` of nothing is 0 and `sum` of nothing is 0 — those are real answers. The
    average, minimum, maximum, spread or median of nothing is not zero; it does not
    exist. Returning 0.0 there is a wrong answer that looks like a right one, which
    is what the existing path does.
    """
    return opcode != AGG_COUNT and opcode != AGG_SUM


fn requires_two_values(opcode: Int) -> Bool:
    """True for reductions undefined below two observations (sample var/std)."""
    return opcode == AGG_VAR or opcode == AGG_STD
