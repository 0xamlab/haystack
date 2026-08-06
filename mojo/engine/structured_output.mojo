"""
structured_output.mojo — Structured output engine: JSON/SQL/schema decoding, validation.
Zero Python imports.

Public API:
  json_next_token_valid          — JSON FSM: is next token valid
  schema_field_confidence        — field extraction confidence
  sql_clause_transition          — SQL parser state transition score
  xml_nesting_depth_valid        — XML nesting depth check
  output_repair_edit_distance    — edit distance for output repair
  regex_constraint_match         — regex constraint satisfaction
  type_coercion_score            — value type coercion confidence
  field_extraction_recall        — structured field recall rate
  output_diversity_score         — output schema diversity
  format_compliance_rate         — format adherence metric
"""
from std.math import sqrt, log, exp


def json_next_token_valid(
    fsm_state: Float64, token_type: Float64
) -> Float64:
    """JSON finite state machine: valid transition score.

    States: 0=start, 1=object, 2=array, 3=string, 4=value, 5=end
    token_type: 0={, 1=}, 2=[, 3=], 4=", 5=:, 6=,, 7=number, 8=bool/null

    Returns 1.0 if transition is valid, 0.0 if invalid.

    Args:
        fsm_state: Current JSON parser state.
        token_type: Type of candidate next token.

    Returns:
        1.0 if valid JSON transition.
    """
    # Simplified: allow most transitions; block only obvious invalids
    # e.g. { cannot follow { without key first
    if fsm_state == 1.0 and token_type == 0.0:  # object after object open
        return 0.0  # Need key first
    if fsm_state == 5.0:  # End state: nothing valid
        return 0.0
    return 1.0


def schema_field_confidence(
    field_log_prob: Float64, schema_match_score: Float64
) -> Float64:
    """Confidence of extracted field matching schema.

    confidence = exp(log_prob) × schema_match

    Args:
        field_log_prob: Log probability of generated field value.
        schema_match_score: Type/format match score (0–1).

    Returns:
        Field extraction confidence (0–1).
    """
    return exp(field_log_prob) * schema_match_score


def sql_clause_transition(
    current_clause: Float64, next_clause: Float64
) -> Float64:
    """SQL clause ordering validity score.

    Valid order: SELECT(1) → FROM(2) → WHERE(3) → GROUP(4) → HAVING(5) → ORDER(6) → LIMIT(7)

    Returns 1.0 if transition follows valid SQL clause order.

    Args:
        current_clause: Current clause type (numeric code).
        next_clause: Proposed next clause.

    Returns:
        1.0 if valid transition.
    """
    if next_clause > current_clause:
        return 1.0
    if next_clause == current_clause:
        return 0.5  # Same clause continuation
    return 0.0  # Backward transition invalid


def xml_nesting_depth_valid(
    current_depth: Float64, max_depth: Float64
) -> Float64:
    """XML nesting depth validity check.

    Args:
        current_depth: Current XML nesting depth.
        max_depth: Maximum allowed depth.

    Returns:
        1.0 if depth is valid, 0.0 if exceeds max.
    """
    if current_depth <= max_depth and current_depth >= 0.0:
        return 1.0
    return 0.0


def output_repair_edit_distance(
    original_len: Float64, n_edits: Float64
) -> Float64:
    """Normalised edit distance for output repair effort.

    distance = n_edits / original_len

    Args:
        original_len: Length of malformed output.
        n_edits: Character edits needed for repair.

    Returns:
        Normalised edit distance (0 = no repair needed).
    """
    if original_len <= 0.0:
        return 0.0
    return n_edits / original_len


def regex_constraint_match(
    token_char_code: Float64, pattern_accept_min: Float64,
    pattern_accept_max: Float64
) -> Float64:
    """Regex character class constraint: is char in [min, max] range.

    Args:
        token_char_code: Unicode code point of token character.
        pattern_accept_min: Minimum accepted code point.
        pattern_accept_max: Maximum accepted code point.

    Returns:
        1.0 if character matches constraint.
    """
    if token_char_code >= pattern_accept_min and token_char_code <= pattern_accept_max:
        return 1.0
    return 0.0


def type_coercion_score(
    raw_value: Float64, target_type: Float64
) -> Float64:
    """Confidence that raw value can be coerced to target type.

    target_type: 0=int, 1=float, 2=bool, 3=string.

    Args:
        raw_value: Generated numeric value.
        target_type: Target schema type.

    Returns:
        Coercion confidence (1.0 = exact type match).
    """
    if target_type == 0.0:  # int
        return 1.0 if raw_value == Float64(Int64(raw_value)) else 0.5
    if target_type == 1.0:  # float: always compatible
        return 1.0
    if target_type == 2.0:  # bool: 0 or 1
        return 1.0 if (raw_value == 0.0 or raw_value == 1.0) else 0.0
    return 0.8  # string: usually coercible


def field_extraction_recall(
    required_fields_extracted: Float64, total_required_fields: Float64
) -> Float64:
    """Recall of required schema fields in structured output.

    Args:
        required_fields_extracted: Required fields present in output.
        total_required_fields: Total required fields in schema.

    Returns:
        Field recall (0–1).
    """
    if total_required_fields <= 0.0:
        return 1.0
    return required_fields_extracted / total_required_fields


def output_diversity_score(
    n_unique_outputs: Float64, total_outputs: Float64
) -> Float64:
    """Diversity of structured outputs across requests.

    Args:
        n_unique_outputs: Distinct structured outputs generated.
        total_outputs: Total outputs generated.

    Returns:
        Diversity ratio (1.0 = all unique).
    """
    if total_outputs <= 0.0:
        return 0.0
    return n_unique_outputs / total_outputs


def format_compliance_rate(
    compliant_outputs: Float64, total_outputs: Float64
) -> Float64:
    """Fraction of outputs fully compliant with requested format.

    Args:
        compliant_outputs: Outputs passing schema validation.
        total_outputs: Total outputs generated.

    Returns:
        Compliance rate (0–1).
    """
    if total_outputs <= 0.0:
        return 1.0
    return compliant_outputs / total_outputs
