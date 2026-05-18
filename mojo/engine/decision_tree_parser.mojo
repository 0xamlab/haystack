"""
decision_tree_parser.mojo — Mojo-native decision tree path enumeration.

Replaces apps/api_server/compute/python_engine/decision_tree.py
(_Node, _enumerate_paths, _merge_variables).

Uses json/parser.mojo for JSON extraction — zero Python imports.

Public API:
  flatten_decision_tree(nodes_json, base_variables_json, default_objective) -> List[TreePath]
  merge_variables(base_json, override_json) -> String
  granularity_to_dt(g) -> Float64
"""

from json.parser import (
    json_get_string,
    json_get_float,
    json_get_array,
    json_array_len,
    json_array_get,
)


# ── TreePath: one flattened root-to-leaf path ─────────────────────────────


struct TreePath(Copyable, Movable):
    """A single root-to-leaf path through a decision tree."""
    var label: String              # " > "-joined node names along the path
    var probability: Float64       # product of probabilities along the path
    var variables_json: String     # merged variables as raw JSON array string
    var objective_function: String # leaf node's objective_function (or inherited)

    fn __init__(out self, label: String, probability: Float64,
                variables_json: String, objective_function: String):
        self.label = label
        self.probability = probability
        self.variables_json = variables_json
        self.objective_function = objective_function


# ── Internal: DFS stack frame ─────────────────────────────────────────────


struct _StackFrame(Copyable, Movable):
    """State for iterative DFS through the decision tree."""
    var node_json: String        # raw JSON object for this node
    var label_so_far: String     # path label accumulated to this node
    var prob_so_far: Float64     # cumulative probability product to this node
    var vars_json: String        # merged variables JSON array to this node
    var objective: String        # inherited objective_function

    fn __init__(out self, node_json: String, label_so_far: String,
                prob_so_far: Float64, vars_json: String, objective: String):
        self.node_json = node_json
        self.label_so_far = label_so_far
        self.prob_so_far = prob_so_far
        self.vars_json = vars_json
        self.objective = objective


# ── granularity_to_dt ─────────────────────────────────────────────────────


fn granularity_to_dt(g: String) -> Float64:
    """Convert granularity string to dt (fraction of year per step).

    Replaces the GRANULARITY_TO_YEARS dict from python_engine/time_series.py.
    Lookup table:
      "day"     -> 1/365
      "week"    -> 1/52
      "month"   -> 1/12
      "quarter" -> 0.25
      "year"    -> 1.0
      default   -> 1/12
    """
    if g == "day":
        return 1.0 / 365.0
    if g == "week":
        return 1.0 / 52.0
    if g == "month":
        return 1.0 / 12.0
    if g == "quarter":
        return 0.25
    if g == "year":
        return 1.0
    return 1.0 / 12.0


# ── merge_variables ───────────────────────────────────────────────────────


fn merge_variables(base_json: String, override_json: String) -> String:
    """Merge base variables with per-node overrides.

    Override variables replace base variables with the same name.
    Variables in override that aren't in base are appended.
    Returns a JSON array string of the merged variables.
    """
    # Handle empty/missing cases
    if len(override_json) == 0 or override_json == "[]":
        return base_json
    if len(base_json) == 0 or base_json == "[]":
        return override_json

    var n_base = json_array_len(base_json)
    var n_over = json_array_len(override_json)

    if n_base == 0:
        return override_json
    if n_over == 0:
        return base_json

    # Extract override names + raw elements for lookup
    var over_names = List[String]()
    var over_elements = List[String]()
    for i in range(n_over):
        var elem = json_array_get(override_json, i)
        over_names.append(json_get_string(elem, "name"))
        over_elements.append(elem)

    # Track which overrides have been consumed
    var over_used = List[Bool]()
    for _ in range(n_over):
        over_used.append(False)

    # Build result array
    var result = String("[")
    var first = True

    # Pass 1: iterate base — replace matching names with override element
    for i in range(n_base):
        var base_elem = json_array_get(base_json, i)
        var base_name = json_get_string(base_elem, "name")

        if not first:
            result += ","
        first = False

        var replaced = False
        for j in range(n_over):
            if over_names[j] == base_name:
                result += over_elements[j]
                over_used[j] = True
                replaced = True
                break
        if not replaced:
            result += base_elem

    # Pass 2: append override vars not yet consumed (new names)
    for j in range(n_over):
        if not over_used[j]:
            if not first:
                result += ","
            first = False
            result += over_elements[j]

    result += "]"
    return result


# ── flatten_decision_tree ─────────────────────────────────────────────────


fn flatten_decision_tree(
    nodes_json: String,
    base_variables_json: String,
    default_objective: String,
) -> List[TreePath]:
    """Flatten a decision tree JSON into a list of paths.

    Args:
        nodes_json: JSON array of tree nodes, e.g.:
            [{"id":"launch","name":"Launch","probability":1.0,"children":[
                {"id":"accept","name":"Accepts","probability":0.6},
                {"id":"reject","name":"Rejects","probability":0.4}
            ]}]
        base_variables_json: JSON array of base variables from the request.
        default_objective: The objective_function from the top-level request.

    Returns:
        List of TreePath structs, one per root-to-leaf path.
        Probabilities are normalized so they sum to 1.0.

    Algorithm:
        1. Parse the JSON array of root nodes.
        2. Iterative DFS with explicit stack.
        3. At each node: accumulate label, multiply probability,
           merge variables, inherit/override objective_function.
        4. Leaf nodes (no children) emit a TreePath.
        5. Normalize probabilities at the end.
    """
    var paths = List[TreePath]()

    var n_roots = json_array_len(nodes_json)
    if n_roots == 0:
        return paths^

    # ── Build DFS stack seeded with root nodes ──
    var stack = List[_StackFrame]()

    # Push roots in reverse so first root is popped first (LIFO)
    for ri in range(n_roots - 1, -1, -1):
        var node_str = json_array_get(nodes_json, ri)
        var node_id = json_get_string(node_str, "id")
        var node_name = json_get_string(node_str, "name")
        if len(node_name) == 0:
            node_name = node_id

        var node_prob = json_get_float(node_str, "probability", 1.0)
        var node_vars = json_get_array(node_str, "variables")
        var node_obj = json_get_string(node_str, "objective_function")

        # Merge base variables with this root node's overrides
        var merged = base_variables_json
        if len(node_vars) > 0:
            merged = merge_variables(base_variables_json, node_vars)

        # Objective: node's own if set, else top-level default
        var obj = default_objective
        if len(node_obj) > 0:
            obj = node_obj

        stack.append(_StackFrame(node_str, node_name, node_prob, merged, obj))

    # ── DFS loop ──
    while len(stack) > 0:
        var frame = stack.pop()
        var children_json = json_get_array(frame.node_json, "children")
        var n_children = json_array_len(children_json)

        if n_children == 0:
            # Leaf — emit a path
            paths.append(TreePath(
                frame.label_so_far,
                frame.prob_so_far,
                frame.vars_json,
                frame.objective,
            ))
        else:
            # Internal — push children in reverse for correct DFS order
            for ci in range(n_children - 1, -1, -1):
                var child_str = json_array_get(children_json, ci)
                var child_id = json_get_string(child_str, "id")
                var child_name = json_get_string(child_str, "name")
                if len(child_name) == 0:
                    child_name = child_id

                var child_prob = json_get_float(child_str, "probability", 1.0)
                var child_vars = json_get_array(child_str, "variables")
                var child_obj = json_get_string(child_str, "objective_function")

                # Accumulate label with arrow separator
                var label = frame.label_so_far + " > " + child_name

                # Cumulative probability = parent * child
                var prob = frame.prob_so_far * child_prob

                # Merge parent's accumulated variables with child overrides
                var merged = frame.vars_json
                if len(child_vars) > 0:
                    merged = merge_variables(frame.vars_json, child_vars)

                # Objective: child's own if set, else inherited from parent
                var obj = frame.objective
                if len(child_obj) > 0:
                    obj = child_obj

                stack.append(_StackFrame(child_str, label, prob, merged, obj))

    # ── Normalize probabilities so they sum to 1.0 ──
    var total: Float64 = 0.0
    for i in range(len(paths)):
        total += paths[i].probability
    if total > 0.0 and total != 1.0:
        for i in range(len(paths)):
            paths[i].probability = paths[i].probability / total

    return paths^
