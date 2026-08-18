"""
optimization.model — the model container that lets a general objective reach a solver.

Why this file exists
--------------------
An objective reaches the frozen optimizers only as an integer `func_id` into one of four
incompatible hardcoded tables, as a polynomial coefficient list over one variable, or as
a string AST that no optimizer consumes. The `func_id` route is the dangerous one: every
table returns `0.0` for an unrecognised id, so `convex.gradient_descent` sees a zero
gradient and returns `x0` on iteration 0, and `root_finding.newton_raphson` returns `x0`
immediately — a converged-looking answer to a problem that was never evaluated.

An `OptModel` is the alternative: an objective and constraints as expression arenas over
named variables, validated whole before anything is evaluated, and evaluated with a
status per outcome.

The IR is reused, not reinvented
--------------------------------
Nodes are `types.ExprNode` — `{op, fval, var_idx, left, right, extra}`, a flat POD with
integer child indices. No second node struct is defined here: `expr.mojo` already owns
opcodes 0-38 and their exact semantics, `query.ir` already owns the v2 space above 100,
and a third node type would mean a third evaluator to keep in step. An arena is a
`List[ExprNode]` plus a root index, so it serialises as six parallel lists with no
pointers (`arena_to_flat` / `arena_from_flat`).

Structural validation is `query.ir.validation_error`, called with `n_columns = 0`
-------------------------------------------------------------------------------
That function already enforces the one property that matters: every child index is
strictly LESS than its parent's, which makes a cycle unrepresentable rather than merely
unlikely, so no visited set and no depth limit is needed anywhere below. It is called
with `n_columns = 0` deliberately: `OP_COL_REF` (130) addresses a *batch column*, which a
model has no notion of, and passing 0 makes every `col_ref` node a rejection instead of
letting a query plan be evaluated as if its columns were variables.

What it does not check is added here: an unknown-to-this-evaluator opcode, an arity that
`ir.op_arity` deliberately defers on (it returns -2 for the whole frozen range rather
than duplicating `expr.mojo`'s table), a `var_ref` whose index is outside the model's
variable list, a non-finite literal, and every property of the variables, bounds, senses,
right-hand sides and policy.

Scalar evaluation is written here, and that is not a duplicate
-------------------------------------------------------------
`query.eval` evaluates a whole *column* per node against a `RecordBatch` — the right
shape for a filter over a million rows, and the wrong shape for an optimizer, which needs
one point at a time and cannot build a batch per iterate. The frozen scalar evaluator is
`expr.eval_expr`, and it is unusable as the objective path for three reasons:

  * it MASKS every numeric failure into a plausible number — `x/0` is `0.0`, `ln(x)` for
    `x <= 0` is `log(1e-300) = -690.776`, `sqrt(-4)` is `0.0`, `(-2)^0.5` is `0.0`,
    `exp(1000)` is `exp(709)`, and `x % 0` is `0.0`. A line search that walks into
    `ln(-1)` therefore gets a finite objective and keeps going;
  * a `var_ref` whose index exceeds the point returns `0.0`, so a model that references
    variable 7 of a 3-variable point silently optimises a different function;
  * it is recursive, so a deep arena is a stack risk, and the repo's convention (see
    `stats.fast_sort`, `graph/algorithms.mojo`) is an explicit stack.

So the walk here is iterative over an explicit stack, memoised per node, and returns
`ScalarResult{status, has_value, value, node_index}` — the offending node included. It
matches `expr.eval_expr` value-for-value on every input where the frozen evaluator does
not mask (the test asserts that differentially), and it is *lazy in the same place*:
opcode 20 (`ifgt0`) evaluates only the branch it takes, so `ifgt0(c, a, 1/x)` at `x = 0`
is an answer and not a division error. Bottom-up evaluation of every node was rejected
for exactly that reason — it turns an unreachable subexpression into a model-wide
failure.

Opcodes 22-38 (sin … expm1, including erf, the Lanczos gamma, factorial, Fibonacci) are
NOT reimplemented. Each is evaluated by handing the frozen `expr.eval_expr` a two-literal
arena holding the already-computed children, so those approximations keep exactly one
definition in the tree. Opcodes 0-21 are evaluated directly, because that is where the
masking lives and a domain check has to sit between the operands and the operation.

Absence markers
---------------
`ScalarResult.has_value` is the authority; its `value` is `0.0` when absent and that is
not a claim. NaN was rejected as the marker: it is the loudest possible sentinel in
arithmetic but it does not survive the JSON frame the drivers cross, so it would arrive
as a parse error rather than as an absent value. `sense_violation` returns
`MODEL_VIOLATION_ABSENT = -1.0` for an unknown sense, impossible for a real violation
(which is a magnitude, hence `>= 0`), so an ignored status reads as a loud wrong answer
instead of "constraint satisfied".

Rounding, and the one conversion this file does not make
--------------------------------------------------------
`_floor_f` / `_ceil_f` / `_round_f` are built from `std.math.floor` and `ceil`, never from
`Float64(Int(v))`. `Int()` on a magnitude past the Float64 integer grid is an out-of-range
`fptosi`, which is poison and not a truncation, so with the old spelling
`project_point_flat(x=[1e300], var_kind=[VAR_INTEGER])` passed every check and returned an
ARBITRARY coordinate with status `MODEL_OK` and `n_rounded == 1`. `_round_f` is now the
package's ONE rounding routine: `optimization.integer` imports it as `_nearest_int`, the
name its own byte-identical copy used to have, so no call site there changed and the
`|v| >= 2^52` tie subtlety documented on `_round_f` cannot drift back in a second copy.
Mojo has no access control, so the leading underscore only keeps it out of the runtime
contract — a rounding helper is not a driver — and does not stop a sibling importing it.
The only surviving `Int()` is in the `mod` branch of `evaluate_expr`, where the range guard
runs BEFORE the conversion.

Single definitions this module owns for the whole package
--------------------------------------------------------
`model_finite` is public for the mirror-image reason: it is the package's single definition
of "finite", and `assignment`, `explain`, `flow`, `integer` and `linear` now import it as
`_finite` rather than each carrying a byte-identical private copy. `policy_defect` is the
single definition of a solver policy the package will honour, and the four entry points
that hold loose tolerances rather than an `OptPolicy` reach it through
`_policy_parts_defect` instead of restating the rule.

Ceilings
--------
`MAX_CSR_DIM` is imported from `sparse_numerics.csr`, not redefined: it is already the
tree's declared ceiling for "one slot allocated per row/column/variable regardless of how
much data there is", and a second ceiling would drift. `sparse_numerics.csr.dims_fit` is
called for the dense `A` in `linear_model_flat` rather than rewritten, because
`rows * cols == len(a)` is a wrapping multiply and therefore not a bound at all
(`3 * 6148914691236517206 == 2`).
"""
from std.math import abs as fabs, ceil, exp, floor, isinf, isnan, log, pow, sqrt

from expr import eval_expr
from query.ir import (
    FROZEN_OP_MAX,
    OP_ADD,
    OP_DIV,
    OP_LITERAL,
    OP_MUL,
    OP_NEG,
    OP_SUB,
    OP_VAR_REF,
    op_name,
    validation_error,
)
from sparse_numerics.csr import MAX_CSR_DIM, dims_fit
from types import ExprNode

# ── opcodes beyond the ones query.ir already names ────────────────────────────
# `expr.mojo` owns these numbers; they are repeated as names, never reassigned.

comptime OP_POW: Int = 7
comptime OP_LN: Int = 8
comptime OP_LOG10: Int = 9
comptime OP_LOG2: Int = 10
comptime OP_EXP: Int = 11
comptime OP_SQRT: Int = 12
comptime OP_ABS: Int = 13
comptime OP_FLOOR: Int = 14
comptime OP_CEIL: Int = 15
comptime OP_ROUND: Int = 16
comptime OP_MIN2: Int = 17
comptime OP_MAX2: Int = 18
comptime OP_CLIP: Int = 19
comptime OP_IFGT0: Int = 20
comptime OP_MOD: Int = 21

# 22-38 are the transcendental and special-function ops. They are delegated to the frozen
# evaluator instead of being reimplemented, so `_erf_approx`, the Lanczos `_gamma_approx`,
# `_factorial_f` and `_fibonacci` keep one definition in the tree.
comptime OP_DELEGATED_MIN: Int = 22
comptime OP_DELEGATED_MAX: Int = FROZEN_OP_MAX

# expr.mojo's own guards, repeated here as the thresholds a domain check tests against
# rather than as magic numbers at the call site.
comptime EXP_ARG_MAX: Float64 = 709.0
comptime FACTORIAL_ARG_MAX: Float64 = 170.0

# `Int(v)` on a magnitude past the Float64 integer grid is not a truncation, it is an
# overflow, so integrality questions are answered structurally past this point: an
# interval wider than the grid contains integers by construction.
comptime MODEL_INT_GRID_MAX: Float64 = 9.0e15

# 2^52 — the magnitude at which the spacing between consecutive Float64 values reaches 1.0.
# At or above this every representable double IS an integer, so rounding it is a no-op. Below
# it, `v + 0.5` is representable and `floor(v + 0.5)` is exact. Exactly between the two —
# the band `[2^52, 2^53)` — `v + 0.5` is an exact tie that round-half-to-even carries to the
# neighbouring integer, which is why `_round_f` must short-circuit here rather than rely on
# MODEL_INT_GRID_MAX (9.0e15, which is BELOW 2^53 and so does not cover the band).
comptime MODEL_INT_SPACING_ONE: Float64 = 4503599627370496.0

# ── status codes ──────────────────────────────────────────────────────────────
# One code per outcome, and the code says WHAT while the result's `constraint_index` /
# `var_index` / `node_index` say WHERE. Separate objective/constraint codes were
# rejected: it doubles the table and still needs the index to name which constraint.

comptime MODEL_OK: Int = 0
comptime MODEL_ERR_LENGTH_MISMATCH: Int = 1
comptime MODEL_ERR_DIMENSION_TOO_LARGE: Int = 2
comptime MODEL_ERR_EMPTY_EXPRESSION: Int = 3
comptime MODEL_ERR_EXPR_ROOT: Int = 4
comptime MODEL_ERR_EXPR_STRUCTURE: Int = 5
comptime MODEL_ERR_UNSUPPORTED_OP: Int = 6
comptime MODEL_ERR_MISSING_THIRD_CHILD: Int = 7
comptime MODEL_ERR_VAR_INDEX: Int = 8
comptime MODEL_ERR_NON_FINITE_LITERAL: Int = 9
comptime MODEL_ERR_NON_FINITE_BOUND: Int = 10
comptime MODEL_ERR_NON_FINITE_RHS: Int = 11
comptime MODEL_ERR_BOUNDS_CROSSED: Int = 12
comptime MODEL_ERR_VAR_KIND: Int = 13
comptime MODEL_ERR_VAR_FLAGS: Int = 14
comptime MODEL_ERR_BINARY_BOUNDS: Int = 15
comptime MODEL_ERR_INTEGER_BOUNDS: Int = 16
comptime MODEL_ERR_WARM_START: Int = 17
comptime MODEL_ERR_SENSE: Int = 18
comptime MODEL_ERR_CONSTRAINT_PTR: Int = 19
comptime MODEL_ERR_POLICY: Int = 20
comptime MODEL_ERR_POINT_LENGTH: Int = 21
comptime MODEL_ERR_NON_FINITE_POINT: Int = 22
comptime MODEL_ERR_DIV_BY_ZERO: Int = 23
comptime MODEL_ERR_DOMAIN: Int = 24
comptime MODEL_ERR_OVERFLOW: Int = 25
comptime MODEL_ERR_NON_FINITE_VALUE: Int = 26
comptime MODEL_ERR_EVAL_LIMIT: Int = 27
comptime MODEL_ERR_DENSE_SHAPE: Int = 28
comptime MODEL_ERR_NON_FINITE_COEFFICIENT: Int = 29
comptime MODEL_ERR_FROZEN_EVAL_RAISED: Int = 30

# ── variable kinds ────────────────────────────────────────────────────────────

comptime VAR_CONTINUOUS: Int = 0
comptime VAR_INTEGER: Int = 1
comptime VAR_BINARY: Int = 2

# ── constraint senses ─────────────────────────────────────────────────────────

comptime SENSE_LE: Int = 0
comptime SENSE_EQ: Int = 1
comptime SENSE_GE: Int = 2

# ── variable flag bits ────────────────────────────────────────────────────────
# A free variable is a flag, not a magnitude. `±inf` as a bound is rejected rather than
# reinterpreted as "no bound", because an infinite bound goes on to participate in
# arithmetic — a projection computes `x - lower` and `inf - inf` is NaN — whereas a
# cleared flag cannot.

comptime VAR_FLAG_HAS_LOWER: Int = 1
comptime VAR_FLAG_HAS_UPPER: Int = 2
comptime VAR_FLAG_HAS_START: Int = 4
comptime VAR_FLAG_ALL: Int = 7
comptime VAR_FLAG_BOXED: Int = 3

# A violation is a magnitude, so a negative one is impossible. -1.0 therefore reports "no
# violation could be computed" loudly, the way graph_analytics uses GRAPH_NO_DISTANCE.
comptime MODEL_VIOLATION_ABSENT: Float64 = -1.0

# ── policy defaults ───────────────────────────────────────────────────────────
comptime DEFAULT_MAX_ITERATIONS: Int = 1000
comptime DEFAULT_MAX_TIME_MS: Float64 = 0.0
comptime DEFAULT_FEASIBILITY_TOL: Float64 = 1e-9
comptime DEFAULT_OPTIMALITY_TOL: Float64 = 1e-9
comptime DEFAULT_INTEGRALITY_TOL: Float64 = 1e-9


def model_status_name(code: Int) -> String:
    """Name for a status code, so a rejection surfaces the defect and not a bare number."""
    if code == MODEL_OK:
        return "ok"
    if code == MODEL_ERR_LENGTH_MISMATCH:
        return "parallel_arrays_length_mismatch"
    if code == MODEL_ERR_DIMENSION_TOO_LARGE:
        return "dimension_too_large"
    if code == MODEL_ERR_EMPTY_EXPRESSION:
        return "empty_expression"
    if code == MODEL_ERR_EXPR_ROOT:
        return "root_out_of_range"
    if code == MODEL_ERR_EXPR_STRUCTURE:
        return "expression_structure"
    if code == MODEL_ERR_UNSUPPORTED_OP:
        return "unsupported_op"
    if code == MODEL_ERR_MISSING_THIRD_CHILD:
        return "missing_third_child"
    if code == MODEL_ERR_VAR_INDEX:
        return "variable_index_out_of_range"
    if code == MODEL_ERR_NON_FINITE_LITERAL:
        return "non_finite_literal"
    if code == MODEL_ERR_NON_FINITE_BOUND:
        return "non_finite_bound"
    if code == MODEL_ERR_NON_FINITE_RHS:
        return "non_finite_rhs"
    if code == MODEL_ERR_BOUNDS_CROSSED:
        return "lower_bound_above_upper_bound"
    if code == MODEL_ERR_VAR_KIND:
        return "unknown_variable_kind"
    if code == MODEL_ERR_VAR_FLAGS:
        return "unknown_variable_flag_bits"
    if code == MODEL_ERR_BINARY_BOUNDS:
        return "binary_variable_not_boxed_in_unit_interval"
    if code == MODEL_ERR_INTEGER_BOUNDS:
        return "integer_variable_range_holds_no_integer"
    if code == MODEL_ERR_WARM_START:
        return "warm_start_outside_bounds"
    if code == MODEL_ERR_SENSE:
        return "unknown_constraint_sense"
    if code == MODEL_ERR_CONSTRAINT_PTR:
        return "constraint_pointer_array_invalid"
    if code == MODEL_ERR_POLICY:
        return "invalid_policy"
    if code == MODEL_ERR_POINT_LENGTH:
        return "point_length_is_not_n_vars"
    if code == MODEL_ERR_NON_FINITE_POINT:
        return "non_finite_point"
    if code == MODEL_ERR_DIV_BY_ZERO:
        return "division_by_zero"
    if code == MODEL_ERR_DOMAIN:
        return "argument_outside_domain"
    if code == MODEL_ERR_OVERFLOW:
        return "overflow"
    if code == MODEL_ERR_NON_FINITE_VALUE:
        return "non_finite_value"
    if code == MODEL_ERR_EVAL_LIMIT:
        return "evaluation_step_limit"
    if code == MODEL_ERR_DENSE_SHAPE:
        return "dense_shape_invalid"
    if code == MODEL_ERR_NON_FINITE_COEFFICIENT:
        return "non_finite_coefficient"
    if code == MODEL_ERR_FROZEN_EVAL_RAISED:
        return "frozen_evaluator_raised"
    return "unknown_status_" + String(code)


def var_kind_name(kind: Int) -> String:
    if kind == VAR_CONTINUOUS:
        return "continuous"
    if kind == VAR_INTEGER:
        return "integer"
    if kind == VAR_BINARY:
        return "binary"
    return "unknown_kind_" + String(kind)


def constraint_sense_name(sense: Int) -> String:
    if sense == SENSE_LE:
        return "le"
    if sense == SENSE_EQ:
        return "eq"
    if sense == SENSE_GE:
        return "ge"
    return "unknown_sense_" + String(sense)


def has_lower_bound(flags: Int) -> Bool:
    return (flags & VAR_FLAG_HAS_LOWER) != 0


def has_upper_bound(flags: Int) -> Bool:
    return (flags & VAR_FLAG_HAS_UPPER) != 0


def has_warm_start(flags: Int) -> Bool:
    return (flags & VAR_FLAG_HAS_START) != 0


def var_flags_valid(flags: Int) -> Bool:
    """True when `flags` sets only bits this module defines.

    An unknown bit is rejected rather than ignored: a caller that thinks bit 3 means
    "semicontinuous" would otherwise get a model that quietly drops the property.
    """
    return flags >= 0 and (flags & VAR_FLAG_ALL) == flags


# ── opcode metadata ───────────────────────────────────────────────────────────


def model_op_arity(op: Int) -> Int:
    """Children this opcode consumes, or -1 for one this evaluator cannot run.

    `query.ir.op_arity` returns -2 for the whole frozen range on purpose — it refuses to
    duplicate `expr.mojo`'s table and defers to `expr.mojo`'s own tolerance. A scalar
    evaluator cannot defer: it has to know how many children to pull before it computes,
    so the table is stated here, transcribed from `expr.eval_expr`'s branches.
    """
    if op == OP_LITERAL or op == OP_VAR_REF:
        return 0
    if op == OP_ADD or op == OP_SUB or op == OP_MUL or op == OP_DIV:
        return 2
    if op == OP_NEG:
        return 1
    if op == OP_POW:
        return 2
    if op == OP_LN or op == OP_LOG10 or op == OP_LOG2 or op == OP_EXP or op == OP_SQRT:
        return 1
    if op == OP_ABS or op == OP_FLOOR or op == OP_CEIL or op == OP_ROUND:
        return 1
    if op == OP_MIN2 or op == OP_MAX2 or op == OP_MOD:
        return 2
    if op == OP_CLIP or op == OP_IFGT0:
        return 3
    if op >= OP_DELEGATED_MIN and op <= OP_DELEGATED_MAX:
        # 33 = comb(n, k) and 36 = hypot(a, b) are the only binary ones in this range.
        if op == 33 or op == 36:
            return 2
        return 1
    return -1


def is_model_op(op: Int) -> Bool:
    """True for an opcode a model expression may use.

    The v2 comparison and logical opcodes (`query.ir` 100+) are deliberately excluded: a
    constraint's relation lives in its `sense` and `rhs`, so a comparison INSIDE the
    expression would mean a second, invisible relation whose 1.0/0.0 result then enters
    arithmetic. `OP_COL_REF` is excluded for the same reason a model has no batch.
    """
    return model_op_arity(op) >= 0


# ── containers ────────────────────────────────────────────────────────────────


@fieldwise_init
struct OptPolicy(Copyable, Movable):
    """What a solver is allowed to spend and what it may call converged.

    `max_time_ms == 0.0` means no wall-clock budget; that is a real setting rather than a
    sentinel for "unset", because a solver with no budget is the common case and a
    negative budget is rejected.
    """

    var max_iterations: Int
    var max_time_ms: Float64
    var feasibility_tol: Float64
    var optimality_tol: Float64
    var integrality_tol: Float64


@fieldwise_init
struct OptVar(Copyable, Movable):
    """One decision variable.

    `has_lower` / `has_upper` are what make a bound present; `lower` / `upper` must be
    finite numbers in every case, including when the matching flag is clear, because an
    "unused" slot holding NaN is exactly how NaN reaches arithmetic three modules later.
    """

    var name: String
    var lower: Float64
    var upper: Float64
    var kind: Int
    var has_lower: Bool
    var has_upper: Bool
    var has_start: Bool
    var start: Float64

    def flags(self) -> Int:
        var bits = 0
        if self.has_lower:
            bits += VAR_FLAG_HAS_LOWER
        if self.has_upper:
            bits += VAR_FLAG_HAS_UPPER
        if self.has_start:
            bits += VAR_FLAG_HAS_START
        return bits

    def is_discrete(self) -> Bool:
        return self.kind == VAR_INTEGER or self.kind == VAR_BINARY


@fieldwise_init
struct OptConstraint(Copyable, Movable):
    """`expr(x) sense rhs`, with the expression as its own arena.

    Each constraint owns its arena rather than sharing one with the objective: a shared
    arena makes dropping or reordering constraints an index rewrite, and a stale index
    into a shared arena evaluates a different expression instead of failing.
    """

    var nodes: List[ExprNode]
    var root: Int
    var sense: Int
    var rhs: Float64
    var name: String


@fieldwise_init
struct OptModel(Copyable, Movable):
    """Variables, an objective (arena + root + direction), constraints and a policy.

    `maximize` is carried, never folded into the objective by negation: a negated arena
    reports a negated optimum, and a caller comparing two models would then be comparing
    numbers whose sign convention it cannot see. `minimization_value` performs the
    conversion explicitly where a minimising solver needs it.
    """

    var variables: List[OptVar]
    var obj_nodes: List[ExprNode]
    var obj_root: Int
    var maximize: Bool
    var constraints: List[OptConstraint]
    var policy: OptPolicy

    def n_vars(self) -> Int:
        return len(self.variables)

    def n_constraints(self) -> Int:
        return len(self.constraints)


# ── return-only result structs ────────────────────────────────────────────────
# Declared in this file because the marshalling spec for a returned struct is parsed per
# file: returning a struct owned by another module drops the function from the runtime
# contract silently, with no error anywhere.


@fieldwise_init
struct ExprCheck(Copyable, Movable):
    """Verdict on one expression arena. `node_index` is -1 when no single node is at fault."""

    var status: Int
    var node_index: Int
    var n_nodes: Int
    var root: Int
    var n_var_refs: Int
    var message: String


@fieldwise_init
struct ScalarResult(Copyable, Movable):
    """One expression's value at one point.

    `has_value` is the authority. When it is False the model has no value at this point —
    `value` is 0.0 and that is not a claim, it is padding. NaN would be the louder marker
    in arithmetic but it does not survive the JSON frame these drivers cross.
    """

    var status: Int
    var has_value: Bool
    var value: Float64
    var node_index: Int
    var nodes_evaluated: Int


@fieldwise_init
struct VarCheck(Copyable, Movable):
    """Verdict on the variable block, plus the census a solver needs to pick a method."""

    var status: Int
    var var_index: Int
    var n_vars: Int
    var n_continuous: Int
    var n_integer: Int
    var n_binary: Int
    var n_free: Int
    var n_warm_started: Int


@fieldwise_init
struct PointResult(Copyable, Movable):
    """A point moved into the feasible box, with what had to move.

    `n_clamped` and `n_rounded` are reported rather than discarded because "the point you
    gave me was already feasible" and "I moved it 40 units" are different answers.
    """

    var status: Int
    var length: Int
    var n_clamped: Int
    var n_rounded: Int
    var x: List[Float64]


@fieldwise_init
struct ModelValidation(Copyable, Movable):
    """Whole-model verdict. On a rejection every count still describes the input, and
    `constraint_index` is -1 when the defect is in the objective or the variables."""

    var status: Int
    var ok: Bool
    var n_vars: Int
    var n_constraints: Int
    var n_objective_nodes: Int
    var n_constraint_nodes: Int
    var n_integer: Int
    var n_binary: Int
    var maximize: Bool
    var var_index: Int
    var constraint_index: Int
    var node_index: Int
    var message: String


@fieldwise_init
struct ModelEvaluation(Copyable, Movable):
    """Objective and constraint values at one point.

    On any status other than `MODEL_OK` the three lists are empty and `has_objective` is
    False: a half-evaluated model is not a partial answer, it is a mix of numbers from a
    model that was rejected. `failed_constraint` names which constraint could not be
    evaluated (-1 when the objective is at fault or nothing is).
    """

    var status: Int
    var has_objective: Bool
    var objective: Float64
    var minimization_objective: Float64
    var maximize: Bool
    var n_vars: Int
    var n_constraints: Int
    var feasible: Bool
    var max_violation: Float64
    var worst_constraint: Int
    var n_violated: Int
    var failed_constraint: Int
    var node_index: Int
    var constraint_value: List[Float64]
    var violation: List[Float64]
    var satisfied: List[Bool]


@fieldwise_init
struct ArenaFlat(Copyable, Movable):
    """An expression arena transposed into parallel lists — `ExprNode`'s fields as columns.

    This is the wire form of an arena: `ops`/`var_idx`/`lefts`/`rights`/`extras` are
    `List[Int]` and `values` is `List[Float64]`, all of length `n_nodes`, plus the root.
    """

    var status: Int
    var n_nodes: Int
    var root: Int
    var ops: List[Int]
    var values: List[Float64]
    var var_idx: List[Int]
    var lefts: List[Int]
    var rights: List[Int]
    var extras: List[Int]


@fieldwise_init
struct ModelFlat(Copyable, Movable):
    """A whole model in marshalable lists — the form that crosses the SDK boundary.

    Variables are five parallel lists of length `n_vars`. The objective is one arena. The
    constraints are ONE concatenated arena plus `con_ptr`, a CSR-style offset array of
    length `n_constraints + 1`: constraint `k` owns nodes `[con_ptr[k], con_ptr[k+1])` and
    `con_roots[k]` is its root *relative to that slice*. Relative roots are what let a
    constraint be dropped or reordered without rewriting every index; an absolute root
    into a concatenated arena silently points at another constraint's node after any edit.
    """

    var var_lower: List[Float64]
    var var_upper: List[Float64]
    var var_kind: List[Int]
    var var_flags: List[Int]
    var var_start: List[Float64]
    var maximize: Bool
    var obj_root: Int
    var obj_ops: List[Int]
    var obj_values: List[Float64]
    var obj_var_idx: List[Int]
    var obj_lefts: List[Int]
    var obj_rights: List[Int]
    var obj_extras: List[Int]
    var con_ptr: List[Int]
    var con_roots: List[Int]
    var con_senses: List[Int]
    var con_rhs: List[Float64]
    var con_ops: List[Int]
    var con_values: List[Float64]
    var con_var_idx: List[Int]
    var con_lefts: List[Int]
    var con_rights: List[Int]
    var con_extras: List[Int]
    var max_iterations: Int
    var max_time_ms: Float64
    var feasibility_tol: Float64
    var optimality_tol: Float64
    var integrality_tol: Float64


# ── small numeric helpers ─────────────────────────────────────────────────────


def model_finite(v: Float64) -> Bool:
    """True for a real number: neither NaN nor ±inf.

    PUBLIC on purpose, and the SINGLE definition of "finite" for this package.
    `assignment.mojo`, `explain.mojo`, `flow.mojo`, `integer.mojo` and `linear.mojo` each
    carried a byte-identical private `_finite` while this one was private and therefore
    unimportable. All five now do `from optimization.model import model_finite as _finite`,
    so their call sites are unchanged and there is one definition of the predicate that
    decides whether a bound, a cost or a right-hand side is admissible — six were six
    chances for one of them to drift.
    """
    return not (isnan(v) or isinf(v))


def _floor_f(v: Float64) -> Float64:
    """Greatest integer <= `v`. Total over every finite Float64.

    Built on `std.math.floor`, NEVER on `Float64(Int(v))`. `Int()` on a magnitude past the
    Float64 integer grid is an out-of-range `fptosi`, which is poison rather than a
    truncation: the result is arbitrary, so any guard placed after the conversion is already
    too late. `floor` has no such cliff — past the grid every representable Float64 is
    already an integer and `floor` returns it unchanged.

    `optimization.integer` used to hold a twin of `_round_f` below, under the name
    `_nearest_int`, documenting the same hazard. It now imports `_round_f` under that name;
    the dependency runs the right way round because `integer` already depends on this
    module and nothing here depends on `integer`.
    """
    return floor(v)


def _ceil_f(v: Float64) -> Float64:
    """Least integer >= `v`. Total over every finite Float64; see `_floor_f` for why."""
    return ceil(v)


def _round_f(v: Float64) -> Float64:
    """Round half away from zero, matching `expr.mojo` opcode 16. Total over every Float64.

    This was `Float64(Int(v + 0.5))`, reachable from `project_point` / `project_point_flat`,
    `check_variables` / `variables_validate_flat` / `model_validate` and
    `_delegated_domain_defect` behind nothing but a finiteness guard. So
    `project_point_flat(x=[1e300], var_kind=[VAR_INTEGER], var_flags=[0], ...)` passed every
    check and then converted 1e300 to `Int`: an ARBITRARY coordinate returned under
    `MODEL_OK` with `n_rounded == 1` — a number where none exists, which is exactly what
    this package exists to prevent.

    `floor(v + 0.5)` has no such cliff, but it is NOT exact on its own: in
    `[2^52, 2^53)` the spacing between doubles is exactly 1.0, so `v + 0.5` falls precisely
    halfway between two representable values and round-half-to-even carries it to the
    neighbour. For every ODD integer in that band the sum rounds UP, and `floor` then
    returns `v + 1` — moving an already-integral coordinate to a DIFFERENT integer.
    `_round_f(2^52 + 1)` returned `2^52 + 2`. `MODEL_INT_GRID_MAX` does not screen this:
    9.0e15 is BELOW 2^53, so the whole band is admitted.

    Every double at or above 2^52 is already an integer, because the spacing there is at
    least 1.0. So there is nothing to round and `v` is returned unchanged — which is both
    exact and cheaper. Below that bound `v + 0.5` is representable and `floor` is exact.

    THE package's one rounding routine. `optimization.integer` imported this under its old
    local name with `from optimization.model import _round_f as _nearest_int`, so its call
    sites read the same and the tie subtlety above exists in exactly one place. Do not
    reintroduce a second copy anywhere in `optimization/`.
    """
    if fabs(v) >= MODEL_INT_SPACING_ONE:
        return v
    if v >= 0.0:
        return floor(v + 0.5)
    return -floor(-v + 0.5)


def integer_in_interval(lower: Float64, upper: Float64) -> Bool:
    """True when `[lower, upper]` contains at least one integer.

    An interval reaching past the Float64 integer grid answers True structurally: every
    representable Float64 beyond MODEL_INT_GRID_MAX is itself an integer, so such an
    interval contains one by construction. `_ceil_f` / `_floor_f` are total and would answer
    correctly here as well — the shortcut is the module's stated grid policy, not a guard
    against them. It WAS a guard when they went through `Int()`, which is an overflow and
    not a truncation past the grid.
    """
    if not (model_finite(lower) and model_finite(upper)):
        return False
    if lower > upper:
        return False
    if fabs(lower) > MODEL_INT_GRID_MAX or fabs(upper) > MODEL_INT_GRID_MAX:
        return True
    return _ceil_f(lower) <= _floor_f(upper)


def minimization_value(objective: Float64, maximize: Bool) -> Float64:
    """The number a MINIMISING solver should drive down for this objective.

    Explicit, and applied by the solver rather than by the model: negating the arena at
    build time would make every reported optimum silently sign-flipped.
    """
    if maximize:
        return -objective
    return objective


def sense_violation(value: Float64, sense: Int, rhs: Float64, tol: Float64) -> Float64:
    """How badly `value sense rhs` fails, 0.0 when it holds within `tol`.

    Returns `MODEL_VIOLATION_ABSENT` (-1.0) for an unknown sense or a non-finite input:
    0.0 there would read as "satisfied", which is the failure mode this whole package
    exists to remove. A real violation is a magnitude, so -1.0 is unmistakable.
    """
    if not (model_finite(value) and model_finite(rhs) and model_finite(tol)):
        return MODEL_VIOLATION_ABSENT
    var bound = tol
    if bound < 0.0:
        bound = 0.0
    if sense == SENSE_LE:
        var over = value - rhs
        if over > bound:
            return over
        return 0.0
    if sense == SENSE_GE:
        var under = rhs - value
        if under > bound:
            return under
        return 0.0
    if sense == SENSE_EQ:
        var gap = fabs(value - rhs)
        if gap > bound:
            return gap
        return 0.0
    return MODEL_VIOLATION_ABSENT


# ── constructors ──────────────────────────────────────────────────────────────


# PACKING IS LOAD-BEARING: `mojo_inventory` matches a signature inside a nine-line
# lookahead and SKIPS the function silently on failure, dropping it from the runtime
# contract AND from dispatch with no error — the only symptom is a lower per-module
# count. One parameter per line put this at the limit; keep several per line.
def opt_policy_new(
    max_iterations: Int, max_time_ms: Float64, feasibility_tol: Float64,
    optimality_tol: Float64, integrality_tol: Float64,
) -> OptPolicy:
    return OptPolicy(
        max_iterations, max_time_ms, feasibility_tol, optimality_tol, integrality_tol
    )


def default_policy() -> OptPolicy:
    return OptPolicy(
        DEFAULT_MAX_ITERATIONS,
        DEFAULT_MAX_TIME_MS,
        DEFAULT_FEASIBILITY_TOL,
        DEFAULT_OPTIMALITY_TOL,
        DEFAULT_INTEGRALITY_TOL,
    )


def policy_defect(policy: OptPolicy) -> Int:
    """`MODEL_OK`, or `MODEL_ERR_POLICY` for a policy no solver could honour.

    THE definition of a valid policy, stated once here because the package previously held
    two: this function rejected only `tol < 0.0`, so `model_validate` returned `MODEL_OK`
    for a model whose `optimality_tol` or `integrality_tol` was 0.0 while every solver entry
    point rejected exactly that model. "Valid" has to mean one thing, so the four entry
    points that hold loose tolerances rather than an `OptPolicy` —
    `linear._lp_input_defect`, `integer._milp_input_defect`, `integer.branch_choice` and
    `explain._core_input_defect` — now all route here via `_policy_parts_defect` instead of
    restating the rule inline. Those are FUNCTION names on purpose: the previous version of
    this docstring cited three line numbers, and a concurrent edit moved all three onto
    unrelated code without anything failing.

      * `max_iterations >= 1`. A zero cap is rejected rather than treated as "run forever":
        a solver that returns its starting point because it was allowed no iterations looks
        exactly like a solver that converged there.
      * `max_time_ms` finite and `>= 0.0`; 0.0 means no wall-clock budget, a real setting.
      * `feasibility_tol` finite and `>= 0.0`. ZERO IS VALID here: exact feasibility is an
        askable question — `sense_violation(v, sense, rhs, 0.0)` answers it — and a point
        either satisfies a row exactly or it does not.
      * `optimality_tol` and `integrality_tol` finite and STRICTLY POSITIVE. Zero is not
        "be exact", it is "never converge": no bound gap and no relaxation vertex lands on a
        Float64 exactly, so an LP vertex at 2.9999999999999996 stays fractional forever and
        the search branches on a program whose answer it is already holding
        (`integer.mojo`'s header states the same reasoning for the same constant).
    """
    if policy.max_iterations < 1:
        return MODEL_ERR_POLICY
    if not model_finite(policy.max_time_ms) or policy.max_time_ms < 0.0:
        return MODEL_ERR_POLICY
    if not model_finite(policy.feasibility_tol) or policy.feasibility_tol < 0.0:
        return MODEL_ERR_POLICY
    if not model_finite(policy.optimality_tol) or policy.optimality_tol <= 0.0:
        return MODEL_ERR_POLICY
    if not model_finite(policy.integrality_tol) or policy.integrality_tol <= 0.0:
        return MODEL_ERR_POLICY
    return MODEL_OK


def _policy_parts_defect(
    max_iterations: Int, feasibility_tol: Float64,
    optimality_tol: Float64, integrality_tol: Float64,
) -> Int:
    """`policy_defect` for a caller holding loose tolerances instead of an `OptPolicy`.

    DELEGATES, never restates. Every solver entry point in this package validates the
    policy numbers it was handed, and each was doing it inline, so one rule had five
    spellings that agreed only by inspection. This adapter exists so those call sites can
    reach `policy_defect` without first constructing a policy for fields they do not take:

      * `max_time_ms` is filled with 0.0, which `policy_defect` reads as "no wall-clock
        budget" — the honest reading for a caller that has no time field at all.
      * a caller with no `integrality_tol` (an LP, an infeasibility core) passes
        `DEFAULT_INTEGRALITY_TOL`, a known-valid value, so the check is a no-op for it
        rather than a rejection.

    Underscore-prefixed to stay out of the runtime contract — an adapter over a validator
    is not a driver — not to stay inside this file. Mojo has no access control, so a
    sibling module imports it and gets `policy_defect`'s verdict under `policy_defect`'s
    status code.
    """
    return policy_defect(
        opt_policy_new(
            max_iterations, 0.0, feasibility_tol, optimality_tol, integrality_tol
        )
    )


def opt_var(name: String, lower: Float64, upper: Float64, kind: Int) -> OptVar:
    """A boxed variable: both bounds present, no warm start."""
    return OptVar(name, lower, upper, kind, True, True, False, 0.0)


def opt_var_free(name: String, kind: Int) -> OptVar:
    """A variable with no bound on either side. The bound slots hold 0.0, never inf."""
    return OptVar(name, 0.0, 0.0, kind, False, False, False, 0.0)


def opt_var_lower_bounded(name: String, lower: Float64, kind: Int) -> OptVar:
    """`x >= lower`, the shape an LP's default non-negativity actually has."""
    return OptVar(name, lower, 0.0, kind, True, False, False, 0.0)


def opt_var_binary(name: String) -> OptVar:
    """A 0/1 variable, boxed in the unit interval as `VAR_BINARY` requires."""
    return OptVar(name, 0.0, 1.0, VAR_BINARY, True, True, False, 0.0)


def opt_var_warm(
    name: String, lower: Float64, upper: Float64, kind: Int, start: Float64
) -> OptVar:
    return OptVar(name, lower, upper, kind, True, True, True, start)


def make_constraint(
    nodes: List[ExprNode], root: Int, sense: Int, rhs: Float64, name: String
) -> OptConstraint:
    return OptConstraint(nodes.copy(), root, sense, rhs, name)


# PACKING IS LOAD-BEARING: `mojo_inventory` matches a signature inside a nine-line
# lookahead and SKIPS the function silently on failure, dropping it from the runtime
# contract AND from dispatch with no error — the only symptom is a lower per-module
# count. One parameter per line put this at the limit; keep several per line.
def make_model(
    variables: List[OptVar], obj_nodes: List[ExprNode], obj_root: Int,
    maximize: Bool, constraints: List[OptConstraint], policy: OptPolicy,
) -> OptModel:
    return OptModel(
        variables.copy(),
        obj_nodes.copy(),
        obj_root,
        maximize,
        constraints.copy(),
        policy.copy(),
    )


# ── arena pack / unpack ───────────────────────────────────────────────────────


# PACKING IS LOAD-BEARING: `mojo_inventory` matches a signature inside a nine-line
# lookahead and SKIPS the function silently on failure, dropping it from the runtime
# contract AND from dispatch with no error — the only symptom is a lower per-module
# count. One parameter per line put this at the limit; keep several per line.
def arena_flat_defect(
    ops: List[Int], values: List[Float64], var_idx: List[Int],
    lefts: List[Int], rights: List[Int], extras: List[Int],
) -> Int:
    """`MODEL_OK` when the six parallel lists really are parallel and not absurdly long.

    Called before anything indexes them. Six lists of different lengths is the one defect
    that cannot be diagnosed after the fact, because whichever list is short is the one
    that crashes the process on the first read past its end.
    """
    var n = len(ops)
    if (
        len(values) != n
        or len(var_idx) != n
        or len(lefts) != n
        or len(rights) != n
        or len(extras) != n
    ):
        return MODEL_ERR_LENGTH_MISMATCH
    if n > MAX_CSR_DIM:
        return MODEL_ERR_DIMENSION_TOO_LARGE
    return MODEL_OK


# PACKING IS LOAD-BEARING: `mojo_inventory` matches a signature inside a nine-line
# lookahead and SKIPS the function silently on failure, dropping it from the runtime
# contract AND from dispatch with no error — the only symptom is a lower per-module
# count. One parameter per line put this at the limit; keep several per line.
def arena_from_flat(
    ops: List[Int], values: List[Float64], var_idx: List[Int],
    lefts: List[Int], rights: List[Int], extras: List[Int],
) -> List[ExprNode]:
    """Rebuild an arena from its columns. Empty list when the columns are not parallel.

    Mojo-level: the return type names `ExprNode`, which lives in `types.mojo`, so this
    function is not in the runtime contract by design. `arena_roundtrip` is its
    marshalable counterpart.
    """
    var nodes = List[ExprNode]()
    if arena_flat_defect(ops, values, var_idx, lefts, rights, extras) != MODEL_OK:
        return nodes^
    for i in range(len(ops)):
        nodes.append(
            ExprNode(ops[i], values[i], var_idx[i], lefts[i], rights[i], extras[i])
        )
    return nodes^


def arena_to_flat(nodes: List[ExprNode], root: Int) -> ArenaFlat:
    """Transpose an arena into its columns. Mojo-level for the same reason as above."""
    var ops = List[Int]()
    var values = List[Float64]()
    var var_idx = List[Int]()
    var lefts = List[Int]()
    var rights = List[Int]()
    var extras = List[Int]()
    for i in range(len(nodes)):
        ref node = nodes[i]
        ops.append(node.op)
        values.append(node.fval)
        var_idx.append(node.var_idx)
        lefts.append(node.left)
        rights.append(node.right)
        extras.append(node.extra)
    return ArenaFlat(
        MODEL_OK,
        len(nodes),
        root,
        ops^,
        values^,
        var_idx^,
        lefts^,
        rights^,
        extras^,
    )


# THE PACKING OF THE NEXT SIGNATURE IS LOAD-BEARING. `mojo_inventory` matches a signature
# inside a nine-line lookahead window and SILENTLY drops the function from the runtime
# contract and from dispatch if the closing paren lands outside it — no error, the per-module
# count just comes out one lower. One parameter per line closed this on exactly the ninth
# line, so any reflow or one added parameter would have unregistered `arena_roundtrip`.
# Four parameters per line closes it on the fourth line, five clear of the limit. Do not
# expand it back out to one parameter per line.
def arena_roundtrip(
    ops: List[Int], values: List[Float64], var_idx: List[Int], lefts: List[Int],
    rights: List[Int], extras: List[Int], root: Int,
) -> ArenaFlat:
    """Unpack then repack an arena — the pack/unpack pair, exercised end to end.

    Field-for-field identity is the contract: an arena that survives this is one a solver
    on the other side of the wire will read the same way this side wrote it. A length
    mismatch comes back as a status with empty columns rather than as five aligned lists
    and one short one.
    """
    var defect = arena_flat_defect(ops, values, var_idx, lefts, rights, extras)
    if defect != MODEL_OK:
        return ArenaFlat(
            defect,
            0,
            root,
            List[Int](),
            List[Float64](),
            List[Int](),
            List[Int](),
            List[Int](),
            List[Int](),
        )
    var nodes = arena_from_flat(ops, values, var_idx, lefts, rights, extras)
    return arena_to_flat(nodes, root)


def linear_arena(coeffs: List[Float64], constant: Float64) -> ArenaFlat:
    """The arena for `Σ coeffs[i] * x_i + constant`, in canonical node order.

    Layout is fixed rather than value-dependent — every term emits `literal, var_ref, mul`
    and every term after the first emits an `add`, and the constant is always emitted —
    so two callers with the same coefficient count produce byte-identical arenas and the
    arena can be hashed for identity. Node count is `4 * n + 1` for `n >= 1`.

    This is the generalisation of the polynomial-coefficient objective in `optimize.mojo`,
    which is ascending powers of ONE variable and cannot express `2x - 3y`.
    """
    var n = len(coeffs)
    if n > MAX_CSR_DIM:
        return ArenaFlat(
            MODEL_ERR_DIMENSION_TOO_LARGE,
            0,
            -1,
            List[Int](),
            List[Float64](),
            List[Int](),
            List[Int](),
            List[Int](),
            List[Int](),
        )
    if not model_finite(constant):
        return ArenaFlat(
            MODEL_ERR_NON_FINITE_COEFFICIENT,
            0,
            -1,
            List[Int](),
            List[Float64](),
            List[Int](),
            List[Int](),
            List[Int](),
            List[Int](),
        )
    for i in range(n):
        if not model_finite(coeffs[i]):
            return ArenaFlat(
                MODEL_ERR_NON_FINITE_COEFFICIENT,
                0,
                -1,
                List[Int](),
                List[Float64](),
                List[Int](),
                List[Int](),
                List[Int](),
                List[Int](),
            )
    var nodes = List[ExprNode]()
    var acc = -1
    for i in range(n):
        var lit = len(nodes)
        nodes.append(ExprNode(OP_LITERAL, coeffs[i], -1, -1, -1))
        nodes.append(ExprNode(OP_VAR_REF, 0.0, i, -1, -1))
        var product = len(nodes)
        nodes.append(ExprNode(OP_MUL, 0.0, -1, lit, lit + 1))
        if acc < 0:
            acc = product
        else:
            nodes.append(ExprNode(OP_ADD, 0.0, -1, acc, product))
            acc = len(nodes) - 1
    var const_index = len(nodes)
    nodes.append(ExprNode(OP_LITERAL, constant, -1, -1, -1))
    if acc < 0:
        # No variables: the objective is the constant itself, and the constant node is
        # the root. A zero-variable model is a real model with a real answer.
        return arena_to_flat(nodes, const_index)
    nodes.append(ExprNode(OP_ADD, 0.0, -1, acc, const_index))
    return arena_to_flat(nodes, len(nodes) - 1)


# ── expression validation ─────────────────────────────────────────────────────


def check_expr(nodes: List[ExprNode], root: Int, n_vars: Int) -> ExprCheck:
    """Reject a malformed arena whole, before anything evaluates part of it.

    Structure is delegated to `query.ir.validation_error` with `n_columns = 0` — it
    already enforces children-strictly-earlier-than-parent, which is what makes a cycle
    unrepresentable, and it already rejects an unknown opcode and a `col_ref`. Added
    here: this evaluator's arity table, a set third child where the opcode has one, a
    `var_ref` outside `[0, n_vars)` (the frozen evaluator returns 0.0 for that, so the
    model silently becomes a different function), and a non-finite literal.
    """
    var n = len(nodes)
    if n == 0:
        return ExprCheck(MODEL_ERR_EMPTY_EXPRESSION, -1, 0, root, 0, "expression has no nodes")
    if n > MAX_CSR_DIM:
        return ExprCheck(
            MODEL_ERR_DIMENSION_TOO_LARGE, -1, n, root, 0, "expression has too many nodes"
        )
    if root < 0 or root >= n:
        return ExprCheck(
            MODEL_ERR_EXPR_ROOT,
            -1,
            n,
            root,
            0,
            "root index " + String(root) + " is out of range for " + String(n) + " nodes",
        )
    if n_vars < 0:
        return ExprCheck(MODEL_ERR_LENGTH_MISMATCH, -1, n, root, 0, "negative variable count")

    var structural = validation_error(nodes, root, 0)
    if structural.byte_length() > 0:
        return ExprCheck(MODEL_ERR_EXPR_STRUCTURE, -1, n, root, 0, structural)

    var var_refs = 0
    for i in range(n):
        ref node = nodes[i]
        var arity = model_op_arity(node.op)
        if arity < 0:
            return ExprCheck(
                MODEL_ERR_UNSUPPORTED_OP,
                i,
                n,
                root,
                var_refs,
                "node " + String(i) + " uses " + op_name(node.op)
                + ", which a model expression cannot evaluate",
            )
        if node.op == OP_LITERAL and not model_finite(node.fval):
            return ExprCheck(
                MODEL_ERR_NON_FINITE_LITERAL,
                i,
                n,
                root,
                var_refs,
                "node " + String(i) + " is a non-finite literal",
            )
        if node.op == OP_VAR_REF:
            if node.var_idx < 0 or node.var_idx >= n_vars:
                return ExprCheck(
                    MODEL_ERR_VAR_INDEX,
                    i,
                    n,
                    root,
                    var_refs,
                    "node " + String(i) + " references variable " + String(node.var_idx)
                    + " but the model has " + String(n_vars),
                )
            var_refs += 1
        # `ir.validation_error` proves every child index is < i; it cannot prove a needed
        # child is present, because it returns -2 (defer) for the whole frozen range.
        if arity >= 1 and node.left < 0:
            return ExprCheck(
                MODEL_ERR_EXPR_STRUCTURE,
                i,
                n,
                root,
                var_refs,
                "node " + String(i) + " (" + op_name(node.op) + ") needs a left child",
            )
        if arity >= 2 and node.right < 0:
            return ExprCheck(
                MODEL_ERR_EXPR_STRUCTURE,
                i,
                n,
                root,
                var_refs,
                "node " + String(i) + " (" + op_name(node.op) + ") needs a right child",
            )
        if arity >= 3 and node.extra < 0:
            return ExprCheck(
                MODEL_ERR_MISSING_THIRD_CHILD,
                i,
                n,
                root,
                var_refs,
                "node " + String(i) + " (" + op_name(node.op) + ") needs a third child",
            )
        if arity < 1 and node.left >= 0:
            return ExprCheck(
                MODEL_ERR_EXPR_STRUCTURE,
                i,
                n,
                root,
                var_refs,
                "node " + String(i) + " (" + op_name(node.op) + ") takes no children",
            )
        if arity < 2 and node.right >= 0:
            return ExprCheck(
                MODEL_ERR_EXPR_STRUCTURE,
                i,
                n,
                root,
                var_refs,
                "node " + String(i) + " (" + op_name(node.op) + ") has an unused right child",
            )
        if arity < 3 and node.extra >= 0:
            return ExprCheck(
                MODEL_ERR_EXPR_STRUCTURE,
                i,
                n,
                root,
                var_refs,
                "node " + String(i) + " (" + op_name(node.op) + ") has an unused third child",
            )

    return ExprCheck(MODEL_OK, -1, n, root, var_refs, "")


# The packing below is LOAD-BEARING, not style. `mojo_inventory` follows a signature at
# most nine lines past its first (`min(index + 10, ...)`), and one parameter per line closed
# this eight-parameter signature on exactly the tenth — the last line inside the window. Any
# later edit that added a parameter on its own line, or reflowed the return type onto a line
# of its own, would push the closing paren past the window and `expr_validate_flat` would
# vanish from the runtime contract and the dispatch with no error anywhere. Three parameters
# per line leaves five lines of headroom.
def expr_validate_flat(
    ops: List[Int], values: List[Float64], var_idx: List[Int],
    lefts: List[Int], rights: List[Int], extras: List[Int],
    root: Int, n_vars: Int,
) -> ExprCheck:
    """`check_expr` over the wire form."""
    var defect = arena_flat_defect(ops, values, var_idx, lefts, rights, extras)
    if defect != MODEL_OK:
        return ExprCheck(defect, -1, 0, root, 0, model_status_name(defect))
    var nodes = arena_from_flat(ops, values, var_idx, lefts, rights, extras)
    return check_expr(nodes, root, n_vars)


# ── scalar evaluation ─────────────────────────────────────────────────────────


def _frozen_delegate(op: Int, a: Float64, b: Float64, mut raised: Bool) -> Float64:
    """Evaluate one opcode 22-38 node through the FROZEN evaluator.

    A two-literal arena carrying the already-computed children means `expr.eval_expr`
    supplies the semantics — `_erf_approx`, the Lanczos `_gamma_approx`, `_factorial_f`,
    `_fibonacci`, the trig clamps — so this file holds no second copy of any of them.
    Reimplementing them was rejected: two approximations of erf in one tree drift, and
    the drift shows up as a wrong objective rather than as an error.
    """
    var mini = List[ExprNode]()
    mini.append(ExprNode(OP_LITERAL, a, -1, -1, -1))
    mini.append(ExprNode(OP_LITERAL, b, -1, -1, -1))
    mini.append(ExprNode(op, 0.0, -1, 0, 1))
    var no_sample = List[Float64]()
    try:
        return eval_expr(mini, 2, no_sample)
    except:
        raised = True
        return 0.0


def _delegated_domain_defect(op: Int, a: Float64, b: Float64) -> Int:
    """`MODEL_OK`, or the code for an argument the frozen evaluator would CLAMP.

    Every case below is one where `expr.eval_expr` returns a finite, plausible number for
    an argument outside the function's domain: `asin(2)` becomes `asin(1)`, `gamma(0)`
    becomes `gamma(1e-10)`, `factorial(-1)` becomes 0.0, `factorial(200)` becomes 1e308,
    `comb(2, 5)` becomes 0.0, `fib(-3)` becomes 0.0, `log1p(-2)` becomes `log(0)`.
    """
    if op == 25 or op == 26:  # asin, acos — clamped to [-1, 1]
        if a < -1.0 or a > 1.0:
            return MODEL_ERR_DOMAIN
        return MODEL_OK
    if op == 28:  # gamma — clamped to >= 1e-10
        if a <= 0.0:
            return MODEL_ERR_DOMAIN
        return MODEL_OK
    if op == 32:  # factorial — negative becomes 0.0, > 170 becomes 1e308
        if a < 0.0 or a != _floor_f(a):
            return MODEL_ERR_DOMAIN
        if a > FACTORIAL_ARG_MAX:
            return MODEL_ERR_OVERFLOW
        return MODEL_OK
    if op == 33:  # comb(n, k) — out-of-range becomes 0.0
        if a < 0.0 or b < 0.0 or b > a or a != _floor_f(a) or b != _floor_f(b):
            return MODEL_ERR_DOMAIN
        if a > FACTORIAL_ARG_MAX:
            return MODEL_ERR_OVERFLOW
        return MODEL_OK
    if op == 34:  # fibonacci — negative becomes 0.0
        if a < 0.0 or a != _floor_f(a):
            return MODEL_ERR_DOMAIN
        return MODEL_OK
    if op == 37:  # log1p — x <= -1 becomes log of a clamped zero
        if a <= -1.0:
            return MODEL_ERR_DOMAIN
        return MODEL_OK
    return MODEL_OK


def _no_value(status: Int, node_index: Int, evaluated: Int) -> ScalarResult:
    return ScalarResult(status, False, 0.0, node_index, evaluated)


def evaluate_expr(
    nodes: List[ExprNode], root: Int, x: List[Float64], n_vars: Int
) -> ScalarResult:
    """Value of one arena at one point, or a status naming what has no value.

    Validated first, then walked with an explicit stack — no recursion, one memoised value
    per node, and `ifgt0` evaluates only the branch it takes so an unreachable
    subexpression cannot fail the evaluation.
    """
    var check = check_expr(nodes, root, n_vars)
    if check.status != MODEL_OK:
        return _no_value(check.status, check.node_index, 0)
    if len(x) != n_vars:
        return _no_value(MODEL_ERR_POINT_LENGTH, -1, 0)
    for i in range(len(x)):
        if not model_finite(x[i]):
            return _no_value(MODEL_ERR_NON_FINITE_POINT, -1, 0)

    var n = len(nodes)
    var value = List[Float64]()
    var done = List[Bool]()
    for _ in range(n):
        value.append(0.0)
        done.append(False)

    var stack = List[Int]()
    stack.append(root)
    # A node is examined at most (arity + 1) times per push and pushed at most once per
    # parent slot, so 7n bounds the loop for a validated arena. The budget is a tripwire
    # for a future change that breaks that reasoning, not a working part of the algorithm.
    var budget = 8 * n + 16
    var steps = 0
    var evaluated = 0

    while len(stack) > 0:
        steps += 1
        if steps > budget:
            return _no_value(MODEL_ERR_EVAL_LIMIT, -1, evaluated)
        var i = stack[len(stack) - 1]
        if done[i]:
            _ = stack.pop()
            continue
        ref node = nodes[i]
        var op = node.op

        if op == OP_IFGT0:
            # Lazy on purpose: the frozen evaluator takes one branch, and evaluating both
            # would turn `ifgt0(c, a, 1/x)` at x = 0 into a division error where the
            # frozen kernel — correctly — has an answer.
            if not done[node.left]:
                stack.append(node.left)
                continue
            var branch = node.right
            if value[node.left] <= 0.0:
                branch = node.extra
            if not done[branch]:
                stack.append(branch)
                continue
            value[i] = value[branch]
            done[i] = True
            evaluated += 1
            _ = stack.pop()
            continue

        var arity = model_op_arity(op)
        var pending = -1
        if arity >= 1 and not done[node.left]:
            pending = node.left
        elif arity >= 2 and not done[node.right]:
            pending = node.right
        elif arity >= 3 and not done[node.extra]:
            pending = node.extra
        if pending >= 0:
            stack.append(pending)
            continue

        var a: Float64 = 0.0
        var b: Float64 = 0.0
        var c: Float64 = 0.0
        if arity >= 1:
            a = value[node.left]
        if arity >= 2:
            b = value[node.right]
        if arity >= 3:
            c = value[node.extra]

        var out: Float64 = 0.0
        if op == OP_LITERAL:
            out = node.fval
        elif op == OP_VAR_REF:
            # check_expr proved var_idx is in [0, n_vars) and n_vars == len(x).
            out = x[node.var_idx]
        elif op == OP_ADD:
            out = a + b
        elif op == OP_SUB:
            out = a - b
        elif op == OP_MUL:
            out = a * b
        elif op == OP_DIV:
            if b == 0.0:
                return _no_value(MODEL_ERR_DIV_BY_ZERO, i, evaluated)
            out = a / b
        elif op == OP_NEG:
            out = -a
        elif op == OP_POW:
            if a < 0.0:
                # The frozen evaluator returns 0.0 here. A negative base with a
                # non-integer exponent has no real value at all, and with an integer
                # exponent it has one the frozen kernel refuses to compute; either way
                # 0.0 is not it.
                return _no_value(MODEL_ERR_DOMAIN, i, evaluated)
            if a == 0.0 and b < 0.0:
                return _no_value(MODEL_ERR_DIV_BY_ZERO, i, evaluated)
            out = pow(a, b)
        elif op == OP_LN:
            if a <= 0.0:
                return _no_value(MODEL_ERR_DOMAIN, i, evaluated)
            out = log(a)
        elif op == OP_LOG10:
            if a <= 0.0:
                return _no_value(MODEL_ERR_DOMAIN, i, evaluated)
            out = log(a) / 2.302585092994046
        elif op == OP_LOG2:
            if a <= 0.0:
                return _no_value(MODEL_ERR_DOMAIN, i, evaluated)
            out = log(a) / 0.6931471805599453
        elif op == OP_EXP:
            if a > EXP_ARG_MAX:
                # The frozen evaluator clamps to exp(709) ~ 8.2e307, a finite number that
                # a line search reads as a real objective.
                return _no_value(MODEL_ERR_OVERFLOW, i, evaluated)
            out = exp(a)
        elif op == OP_SQRT:
            if a < 0.0:
                return _no_value(MODEL_ERR_DOMAIN, i, evaluated)
            out = sqrt(a)
        elif op == OP_ABS:
            out = fabs(a)
        elif op == OP_FLOOR:
            # The grid guard stays even though `_floor_f`/`_ceil_f`/`_round_f` are now total
            # (they are `std.math.floor`/`ceil`): past MODEL_INT_GRID_MAX the operation is
            # the identity, so an expression asking to round there is asking a vacuous
            # question — reporting absence is honest, while returning the argument unchanged
            # would look like a rounding that happened. It is no longer a guard AGAINST the
            # helpers, and nothing may rely on it as one.
            if fabs(a) > MODEL_INT_GRID_MAX:
                return _no_value(MODEL_ERR_OVERFLOW, i, evaluated)
            out = _floor_f(a)
        elif op == OP_CEIL:
            if fabs(a) > MODEL_INT_GRID_MAX:
                return _no_value(MODEL_ERR_OVERFLOW, i, evaluated)
            out = _ceil_f(a)
        elif op == OP_ROUND:
            if fabs(a) > MODEL_INT_GRID_MAX:
                return _no_value(MODEL_ERR_OVERFLOW, i, evaluated)
            out = _round_f(a)
        elif op == OP_MIN2:
            out = a if a < b else b
        elif op == OP_MAX2:
            out = a if a > b else b
        elif op == OP_CLIP:
            if b > c:
                # clip(v, lo, hi) with lo > hi denotes an empty interval, so it has no
                # value; the frozen evaluator returns `lo`, which is outside the interval
                # the caller asked for.
                return _no_value(MODEL_ERR_DOMAIN, i, evaluated)
            out = b if a < b else (c if a > c else a)
        elif op == OP_MOD:
            if b == 0.0:
                return _no_value(MODEL_ERR_DIV_BY_ZERO, i, evaluated)
            if fabs(a / b) > MODEL_INT_GRID_MAX:
                return _no_value(MODEL_ERR_OVERFLOW, i, evaluated)
            # `Int()` is sound HERE and only here: the guard above runs BEFORE the
            # conversion and proves |a/b| <= 9e15 < 2**63, so the fptosi is in range and
            # truncates toward zero, which is what `fmod` needs. A guard placed after the
            # conversion would prove nothing — the out-of-range result is already poison.
            out = a - Float64(Int(a / b)) * b
        else:
            var domain = _delegated_domain_defect(op, a, b)
            if domain != MODEL_OK:
                return _no_value(domain, i, evaluated)
            var raised = False
            out = _frozen_delegate(op, a, b, raised)
            if raised:
                return _no_value(MODEL_ERR_FROZEN_EVAL_RAISED, i, evaluated)

        if not model_finite(out):
            # Every masked case above is already a status, so reaching here means the
            # arithmetic itself overflowed (1e300 * 1e300) or produced NaN (inf - inf).
            return _no_value(MODEL_ERR_NON_FINITE_VALUE, i, evaluated)
        value[i] = out
        done[i] = True
        evaluated += 1
        _ = stack.pop()

    return ScalarResult(MODEL_OK, True, value[root], -1, evaluated)


# Packed for the same reason as `expr_validate_flat` above: one parameter per line closed
# this signature on the tenth line, the last one `mojo_inventory`'s nine-line lookahead
# reaches, so the function was one added parameter away from silently leaving the contract.
def expr_evaluate_flat(
    ops: List[Int], values: List[Float64], var_idx: List[Int],
    lefts: List[Int], rights: List[Int], extras: List[Int],
    root: Int, x: List[Float64],
) -> ScalarResult:
    """`evaluate_expr` over the wire form; the variable count is `len(x)`."""
    var defect = arena_flat_defect(ops, values, var_idx, lefts, rights, extras)
    if defect != MODEL_OK:
        return _no_value(defect, -1, 0)
    var nodes = arena_from_flat(ops, values, var_idx, lefts, rights, extras)
    return evaluate_expr(nodes, root, x, len(x))


# ── variables ─────────────────────────────────────────────────────────────────


def check_variables(variables: List[OptVar], integrality_tol: Float64) -> VarCheck:
    """Reject a variable block whole, and census the kinds while walking it."""
    var n = len(variables)
    var n_cont = 0
    var n_int = 0
    var n_bin = 0
    var n_free = 0
    var n_warm = 0
    if n > MAX_CSR_DIM:
        return VarCheck(MODEL_ERR_DIMENSION_TOO_LARGE, -1, n, 0, 0, 0, 0, 0)
    # Strictly positive, the same definition `policy_defect` states and every solver entry
    # point in the package already enforced. A zero integrality tolerance would make this
    # function accept a policy that `model_validate` rejects, for the same tolerance.
    if not model_finite(integrality_tol) or integrality_tol <= 0.0:
        return VarCheck(MODEL_ERR_POLICY, -1, n, 0, 0, 0, 0, 0)
    for i in range(n):
        ref v = variables[i]
        if not (model_finite(v.lower) and model_finite(v.upper)):
            return VarCheck(MODEL_ERR_NON_FINITE_BOUND, i, n, 0, 0, 0, 0, 0)
        if v.kind == VAR_CONTINUOUS:
            n_cont += 1
        elif v.kind == VAR_INTEGER:
            n_int += 1
        elif v.kind == VAR_BINARY:
            n_bin += 1
        else:
            return VarCheck(MODEL_ERR_VAR_KIND, i, n, 0, 0, 0, 0, 0)
        if v.has_lower and v.has_upper and v.lower > v.upper:
            return VarCheck(MODEL_ERR_BOUNDS_CROSSED, i, n, 0, 0, 0, 0, 0)
        if not v.has_lower and not v.has_upper:
            n_free += 1
        if v.kind == VAR_BINARY:
            if not (v.has_lower and v.has_upper):
                return VarCheck(MODEL_ERR_BINARY_BOUNDS, i, n, 0, 0, 0, 0, 0)
            if v.lower < 0.0 or v.upper > 1.0:
                # Not silently rewritten to [0, 1]: a model that stops meaning what the
                # caller wrote is the failure mode, not the bounds.
                return VarCheck(MODEL_ERR_BINARY_BOUNDS, i, n, 0, 0, 0, 0, 0)
        if v.kind == VAR_INTEGER and v.has_lower and v.has_upper:
            if not integer_in_interval(v.lower, v.upper):
                # [0.2, 0.8] has no integer, so this model is infeasible by construction
                # and no solver should be started on it.
                return VarCheck(MODEL_ERR_INTEGER_BOUNDS, i, n, 0, 0, 0, 0, 0)
        if v.has_start:
            n_warm += 1
            if not model_finite(v.start):
                return VarCheck(MODEL_ERR_WARM_START, i, n, 0, 0, 0, 0, 0)
            if v.has_lower and v.start < v.lower:
                return VarCheck(MODEL_ERR_WARM_START, i, n, 0, 0, 0, 0, 0)
            if v.has_upper and v.start > v.upper:
                return VarCheck(MODEL_ERR_WARM_START, i, n, 0, 0, 0, 0, 0)
            # `_round_f` is total, so this holds past the integer grid too — and it holds
            # trivially there, because every representable Float64 beyond
            # MODEL_INT_GRID_MAX already IS an integer. That is the same structural answer
            # `integer_in_interval` gives, not a conversion.
            if v.is_discrete() and fabs(v.start - _round_f(v.start)) > integrality_tol:
                return VarCheck(MODEL_ERR_WARM_START, i, n, 0, 0, 0, 0, 0)
    return VarCheck(MODEL_OK, -1, n, n_cont, n_int, n_bin, n_free, n_warm)


def _variables_from_flat(
    var_lower: List[Float64],
    var_upper: List[Float64],
    var_kind: List[Int],
    var_flags: List[Int],
    var_start: List[Float64],
) -> List[OptVar]:
    """Rebuild the variable list. Empty when the five columns are not parallel."""
    var out = List[OptVar]()
    var n = len(var_lower)
    if (
        len(var_upper) != n
        or len(var_kind) != n
        or len(var_flags) != n
        or len(var_start) != n
    ):
        return out^
    for i in range(n):
        var flags = var_flags[i]
        out.append(
            OptVar(
                "x" + String(i),
                var_lower[i],
                var_upper[i],
                var_kind[i],
                has_lower_bound(flags),
                has_upper_bound(flags),
                has_warm_start(flags),
                var_start[i],
            )
        )
    return out^


def variables_defect_flat(
    var_lower: List[Float64],
    var_upper: List[Float64],
    var_kind: List[Int],
    var_flags: List[Int],
) -> Int:
    """`MODEL_OK` when the four bound columns are parallel, in range and flag-legal."""
    var n = len(var_lower)
    if len(var_upper) != n or len(var_kind) != n or len(var_flags) != n:
        return MODEL_ERR_LENGTH_MISMATCH
    if n > MAX_CSR_DIM:
        return MODEL_ERR_DIMENSION_TOO_LARGE
    for i in range(n):
        if not var_flags_valid(var_flags[i]):
            return MODEL_ERR_VAR_FLAGS
    return MODEL_OK


# PACKING IS LOAD-BEARING: `mojo_inventory` matches a signature inside a nine-line
# lookahead and SKIPS the function silently on failure, dropping it from the runtime
# contract AND from dispatch with no error — the only symptom is a lower per-module
# count. One parameter per line put this at the limit; keep several per line.
def variables_validate_flat(
    var_lower: List[Float64], var_upper: List[Float64], var_kind: List[Int],
    var_flags: List[Int], var_start: List[Float64], integrality_tol: Float64,
) -> VarCheck:
    """`check_variables` over the wire form."""
    var n = len(var_lower)
    if (
        len(var_upper) != n
        or len(var_kind) != n
        or len(var_flags) != n
        or len(var_start) != n
    ):
        return VarCheck(MODEL_ERR_LENGTH_MISMATCH, -1, 0, 0, 0, 0, 0, 0)
    var flag_defect = variables_defect_flat(var_lower, var_upper, var_kind, var_flags)
    if flag_defect != MODEL_OK:
        return VarCheck(flag_defect, -1, n, 0, 0, 0, 0, 0)
    var variables = _variables_from_flat(
        var_lower, var_upper, var_kind, var_flags, var_start
    )
    return check_variables(variables, integrality_tol)


def project_point(
    x: List[Float64], variables: List[OptVar], integrality_tol: Float64
) -> PointResult:
    """Move `x` into the box and onto the integer grid, reporting what had to move.

    This is the projection a projected-gradient or rounding step needs, and it lives with
    the variables because the box is the variables' property. It refuses rather than
    guesses when the block is invalid: projecting onto `[3, 1]` has no answer.
    """
    var n = len(variables)
    if len(x) != n:
        return PointResult(MODEL_ERR_POINT_LENGTH, 0, 0, 0, List[Float64]())
    var check = check_variables(variables, integrality_tol)
    if check.status != MODEL_OK:
        return PointResult(check.status, 0, 0, 0, List[Float64]())
    var out = List[Float64]()
    var clamped = 0
    var rounded = 0
    for i in range(n):
        var value = x[i]
        if not model_finite(value):
            return PointResult(MODEL_ERR_NON_FINITE_POINT, 0, 0, 0, List[Float64]())
        ref v = variables[i]
        # The snap is guarded by the integer grid, the module's one ceiling for this
        # question: past MODEL_INT_GRID_MAX every representable Float64 is already an
        # integer, so the projection there is the IDENTITY and skipping it keeps
        # `n_rounded` honest — it counts moves, and nothing moved. The guard also documents
        # why nothing may reintroduce `Float64(Int(v + 0.5))` here: with that spelling
        # `x = 1e300` returned an arbitrary coordinate under MODEL_OK and counted a rounding.
        if v.is_discrete() and fabs(value) <= MODEL_INT_GRID_MAX:
            var snapped = _round_f(value)
            if snapped != value:
                rounded += 1
                value = snapped
        # Bounds are applied AFTER rounding: rounding 2.6 to 3 can leave the box, and a
        # rounded-then-unclamped point is infeasible while a clamped-then-rounded one can
        # be non-integral.
        if v.has_lower and value < v.lower:
            value = v.lower
            clamped += 1
        elif v.has_upper and value > v.upper:
            value = v.upper
            clamped += 1
        if v.is_discrete() and fabs(value) <= MODEL_INT_GRID_MAX:
            var resnapped = _round_f(value)
            if resnapped != value:
                # A clamp to a fractional bound moved it off the grid; the grid wins,
                # inwards, so the result stays inside the box.
                if v.has_lower and resnapped < v.lower:
                    resnapped = _ceil_f(value)
                if v.has_upper and resnapped > v.upper:
                    resnapped = _floor_f(value)
                value = resnapped
                rounded += 1
        out.append(value)
    return PointResult(MODEL_OK, n, clamped, rounded, out^)


# THE PACKING OF THE NEXT SIGNATURE IS LOAD-BEARING, for the reason spelled out above
# `arena_roundtrip`: `mojo_inventory`'s nine-line lookahead window drops a function whose
# signature closes outside it, with no error anywhere. One parameter per line closed this on
# exactly the ninth line. Three per line closes it on the fifth, four clear of the limit; do
# not re-expand it to one parameter per line.
def project_point_flat(
    x: List[Float64], var_lower: List[Float64], var_upper: List[Float64],
    var_kind: List[Int], var_flags: List[Int], var_start: List[Float64],
    integrality_tol: Float64,
) -> PointResult:
    var n = len(var_lower)
    if (
        len(var_upper) != n
        or len(var_kind) != n
        or len(var_flags) != n
        or len(var_start) != n
    ):
        return PointResult(MODEL_ERR_LENGTH_MISMATCH, 0, 0, 0, List[Float64]())
    var flag_defect = variables_defect_flat(var_lower, var_upper, var_kind, var_flags)
    if flag_defect != MODEL_OK:
        return PointResult(flag_defect, 0, 0, 0, List[Float64]())
    var variables = _variables_from_flat(
        var_lower, var_upper, var_kind, var_flags, var_start
    )
    return project_point(x, variables, integrality_tol)


def warm_start_point(variables: List[OptVar], integrality_tol: Float64) -> PointResult:
    """The warm start as a point, or a status when even one variable has none.

    A partial warm start is not a starting point: filling the gaps with 0.0 or with a
    bound would hand a solver a point the caller never chose, and it would be
    indistinguishable from one that was chosen.
    """
    var check = check_variables(variables, integrality_tol)
    if check.status != MODEL_OK:
        return PointResult(check.status, 0, 0, 0, List[Float64]())
    if check.n_warm_started != check.n_vars:
        return PointResult(MODEL_ERR_WARM_START, 0, 0, 0, List[Float64]())
    var out = List[Float64]()
    for i in range(len(variables)):
        out.append(variables[i].start)
    return PointResult(MODEL_OK, len(variables), 0, 0, out^)


# ── model validation ──────────────────────────────────────────────────────────


def _rejected(
    status: Int,
    message: String,
    n_vars: Int,
    n_cons: Int,
    n_obj_nodes: Int,
    n_con_nodes: Int,
    maximize: Bool,
    var_index: Int,
    constraint_index: Int,
    node_index: Int,
) -> ModelValidation:
    return ModelValidation(
        status,
        False,
        n_vars,
        n_cons,
        n_obj_nodes,
        n_con_nodes,
        0,
        0,
        maximize,
        var_index,
        constraint_index,
        node_index,
        message,
    )


def validate_model(model: OptModel) -> ModelValidation:
    """Accept or reject the whole model. Nothing is evaluated until this returns `MODEL_OK`.

    A model is rejected whole rather than repaired, and the status says which check
    failed while `var_index` / `constraint_index` / `node_index` say where. A zero-variable
    model is ACCEPTED: its objective is a constant, which is a real answer — unlike an
    empty objective, which is no expression at all.
    """
    var n_vars = model.n_vars()
    var n_cons = model.n_constraints()
    var n_obj_nodes = len(model.obj_nodes)
    var n_con_nodes = 0
    for k in range(n_cons):
        n_con_nodes += len(model.constraints[k].nodes)

    var policy = policy_defect(model.policy)
    if policy != MODEL_OK:
        return _rejected(
            policy,
            "policy is not one a solver could honour",
            n_vars,
            n_cons,
            n_obj_nodes,
            n_con_nodes,
            model.maximize,
            -1,
            -1,
            -1,
        )

    var vars_check = check_variables(model.variables, model.policy.integrality_tol)
    if vars_check.status != MODEL_OK:
        return _rejected(
            vars_check.status,
            "variable " + String(vars_check.var_index) + ": "
            + model_status_name(vars_check.status),
            n_vars,
            n_cons,
            n_obj_nodes,
            n_con_nodes,
            model.maximize,
            vars_check.var_index,
            -1,
            -1,
        )

    var obj = check_expr(model.obj_nodes, model.obj_root, n_vars)
    if obj.status != MODEL_OK:
        return _rejected(
            obj.status,
            "objective: " + obj.message,
            n_vars,
            n_cons,
            n_obj_nodes,
            n_con_nodes,
            model.maximize,
            -1,
            -1,
            obj.node_index,
        )

    if n_cons > MAX_CSR_DIM:
        return _rejected(
            MODEL_ERR_DIMENSION_TOO_LARGE,
            "too many constraints",
            n_vars,
            n_cons,
            n_obj_nodes,
            n_con_nodes,
            model.maximize,
            -1,
            -1,
            -1,
        )

    for k in range(n_cons):
        ref con = model.constraints[k]
        if con.sense != SENSE_LE and con.sense != SENSE_EQ and con.sense != SENSE_GE:
            return _rejected(
                MODEL_ERR_SENSE,
                "constraint " + String(k) + " has sense " + String(con.sense),
                n_vars,
                n_cons,
                n_obj_nodes,
                n_con_nodes,
                model.maximize,
                -1,
                k,
                -1,
            )
        if not model_finite(con.rhs):
            return _rejected(
                MODEL_ERR_NON_FINITE_RHS,
                "constraint " + String(k) + " has a non-finite right-hand side",
                n_vars,
                n_cons,
                n_obj_nodes,
                n_con_nodes,
                model.maximize,
                -1,
                k,
                -1,
            )
        var con_check = check_expr(con.nodes, con.root, n_vars)
        if con_check.status != MODEL_OK:
            return _rejected(
                con_check.status,
                "constraint " + String(k) + ": " + con_check.message,
                n_vars,
                n_cons,
                n_obj_nodes,
                n_con_nodes,
                model.maximize,
                -1,
                k,
                con_check.node_index,
            )

    return ModelValidation(
        MODEL_OK,
        True,
        n_vars,
        n_cons,
        n_obj_nodes,
        n_con_nodes,
        vars_check.n_integer,
        vars_check.n_binary,
        model.maximize,
        -1,
        -1,
        -1,
        "",
    )


# ── model evaluation ──────────────────────────────────────────────────────────


def _no_evaluation(
    status: Int, n_vars: Int, n_cons: Int, maximize: Bool, failed: Int, node_index: Int
) -> ModelEvaluation:
    return ModelEvaluation(
        status,
        False,
        0.0,
        0.0,
        maximize,
        n_vars,
        n_cons,
        False,
        MODEL_VIOLATION_ABSENT,
        -1,
        0,
        failed,
        node_index,
        List[Float64](),
        List[Float64](),
        List[Bool](),
    )


def evaluate_objective(model: OptModel, x: List[Float64]) -> ScalarResult:
    """The objective's raw value at `x` — not sign-flipped for a maximisation."""
    var verdict = validate_model(model)
    if verdict.status != MODEL_OK:
        return _no_value(verdict.status, verdict.node_index, 0)
    return evaluate_expr(model.obj_nodes, model.obj_root, x, model.n_vars())


def evaluate_model(model: OptModel, x: List[Float64]) -> ModelEvaluation:
    """Objective and every constraint at one point, or a status and no numbers.

    `feasible` is computed against `policy.feasibility_tol`, and `max_violation` is the
    worst single violation — so a caller can tell "feasible" from "feasible by 1e-12".
    """
    var n_vars = model.n_vars()
    var n_cons = model.n_constraints()
    var verdict = validate_model(model)
    if verdict.status != MODEL_OK:
        return _no_evaluation(
            verdict.status, n_vars, n_cons, model.maximize, verdict.constraint_index,
            verdict.node_index,
        )
    if len(x) != n_vars:
        return _no_evaluation(
            MODEL_ERR_POINT_LENGTH, n_vars, n_cons, model.maximize, -1, -1
        )

    var objective = evaluate_expr(model.obj_nodes, model.obj_root, x, n_vars)
    if objective.status != MODEL_OK:
        return _no_evaluation(
            objective.status, n_vars, n_cons, model.maximize, -1, objective.node_index
        )

    var tol = model.policy.feasibility_tol
    var values = List[Float64]()
    var violations = List[Float64]()
    var satisfied = List[Bool]()
    var worst: Float64 = 0.0
    var worst_index = -1
    var n_violated = 0

    for k in range(n_cons):
        ref con = model.constraints[k]
        var value = evaluate_expr(con.nodes, con.root, x, n_vars)
        if value.status != MODEL_OK:
            return _no_evaluation(
                value.status, n_vars, n_cons, model.maximize, k, value.node_index
            )
        var violation = sense_violation(value.value, con.sense, con.rhs, tol)
        if violation == MODEL_VIOLATION_ABSENT:
            # validate_model proved the sense is known and the rhs finite, so the only way
            # here is a non-finite difference — an overflow in `value - rhs`.
            return _no_evaluation(
                MODEL_ERR_NON_FINITE_VALUE, n_vars, n_cons, model.maximize, k, -1
            )
        values.append(value.value)
        violations.append(violation)
        satisfied.append(violation == 0.0)
        if violation > 0.0:
            n_violated += 1
        if violation > worst:
            worst = violation
            worst_index = k
    return ModelEvaluation(
        MODEL_OK,
        True,
        objective.value,
        minimization_value(objective.value, model.maximize),
        model.maximize,
        n_vars,
        n_cons,
        n_violated == 0,
        worst,
        worst_index,
        n_violated,
        -1,
        -1,
        values^,
        violations^,
        satisfied^,
    )


# ── the flat wire model ───────────────────────────────────────────────────────


def flat_defect(flat: ModelFlat) -> Int:
    """`MODEL_OK` when every array-length and pointer invariant of a `ModelFlat` holds.

    Called before ANY index into a `ModelFlat`, because a struct arriving over the wire
    can carry any field values at all and a short column is an uncatchable crash, not an
    exception. Checked: the five variable columns are parallel, both arenas are internally
    parallel, `con_ptr` starts at 0, never decreases and ends at the concatenated node
    count, and there is one root, sense and rhs per constraint.
    """
    var n_vars = len(flat.var_lower)
    if (
        len(flat.var_upper) != n_vars
        or len(flat.var_kind) != n_vars
        or len(flat.var_flags) != n_vars
        or len(flat.var_start) != n_vars
    ):
        return MODEL_ERR_LENGTH_MISMATCH
    if n_vars > MAX_CSR_DIM:
        return MODEL_ERR_DIMENSION_TOO_LARGE
    for i in range(n_vars):
        if not var_flags_valid(flat.var_flags[i]):
            return MODEL_ERR_VAR_FLAGS

    var obj_defect = arena_flat_defect(
        flat.obj_ops,
        flat.obj_values,
        flat.obj_var_idx,
        flat.obj_lefts,
        flat.obj_rights,
        flat.obj_extras,
    )
    if obj_defect != MODEL_OK:
        return obj_defect

    var con_defect = arena_flat_defect(
        flat.con_ops,
        flat.con_values,
        flat.con_var_idx,
        flat.con_lefts,
        flat.con_rights,
        flat.con_extras,
    )
    if con_defect != MODEL_OK:
        return con_defect

    var ptr_len = len(flat.con_ptr)
    if ptr_len == 0:
        # No pointer array means no constraints, and then the concatenated arena must be
        # empty too — otherwise nodes exist that belong to nobody.
        if len(flat.con_ops) != 0:
            return MODEL_ERR_CONSTRAINT_PTR
        if len(flat.con_roots) != 0 or len(flat.con_senses) != 0 or len(flat.con_rhs) != 0:
            return MODEL_ERR_LENGTH_MISMATCH
        return MODEL_OK
    # These three checks are `sparse_numerics.csr.csr_validate_flat`'s row-pointer block,
    # and the reasoning is imported from there verbatim: a zero head, monotone
    # non-decreasing entries and a tail equal to the entry count TOGETHER bound every
    # `con_ptr` entry to `[0, len(con_ops)]`, which is why `model_from_flat`'s
    # `for j in range(con_ptr[k], con_ptr[k+1])` needs no separate range check and cannot
    # read past the end of the concatenated arena. Do not weaken one of the three: each is
    # load-bearing only in combination.
    #
    # `csr_validate_flat` itself cannot be CALLED here, and the difference is not cosmetic:
    #   * it validates an (indptr, indices, values) triple, deriving nnz from `len(values)`
    #     and requiring `len(indices) == len(values)` with every index in `[0, ncols)`. A
    #     constraint arena has no column index at all — its six columns are already checked
    #     by `arena_flat_defect` — so satisfying that call would mean manufacturing two
    #     throwaway lists of length nnz, an O(nnz) allocation to prove an O(n_cons) property.
    #   * it takes `nrows` as an INPUT and requires `len(indptr) == nrows + 1`. Here the
    #     constraint count is DERIVED as `ptr_len - 1`, and `ptr_len == 0` is a legal
    #     encoding of "no constraints" (handled above) that `csr_validate_flat` would report
    #     as a shape error.
    #   * its CSR_ERR_* codes are a different numbering from MODEL_ERR_*, so the status would
    #     need remapping at the boundary anyway.
    if flat.con_ptr[0] != 0:
        return MODEL_ERR_CONSTRAINT_PTR
    for k in range(1, ptr_len):
        if flat.con_ptr[k] < flat.con_ptr[k - 1]:
            return MODEL_ERR_CONSTRAINT_PTR
    if flat.con_ptr[ptr_len - 1] != len(flat.con_ops):
        return MODEL_ERR_CONSTRAINT_PTR
    var n_cons = ptr_len - 1
    if n_cons > MAX_CSR_DIM:
        return MODEL_ERR_DIMENSION_TOO_LARGE
    if (
        len(flat.con_roots) != n_cons
        or len(flat.con_senses) != n_cons
        or len(flat.con_rhs) != n_cons
    ):
        return MODEL_ERR_LENGTH_MISMATCH
    return MODEL_OK


def model_from_flat(flat: ModelFlat) -> OptModel:
    """Unpack the wire model. Returns an EMPTY model when `flat_defect` rejects the input.

    Mojo-level: the return type owns `List[ExprNode]`. Callers that need to tell "empty
    model" from "rejected model" call `flat_defect` first — which every driver here does,
    and reports its code rather than the downstream "empty objective".
    """
    if flat_defect(flat) != MODEL_OK:
        return OptModel(
            List[OptVar](), List[ExprNode](), -1, flat.maximize, List[OptConstraint](),
            default_policy(),
        )
    var variables = _variables_from_flat(
        flat.var_lower, flat.var_upper, flat.var_kind, flat.var_flags, flat.var_start
    )
    var obj_nodes = arena_from_flat(
        flat.obj_ops,
        flat.obj_values,
        flat.obj_var_idx,
        flat.obj_lefts,
        flat.obj_rights,
        flat.obj_extras,
    )
    var constraints = List[OptConstraint]()
    var ptr_len = len(flat.con_ptr)
    if ptr_len > 0:
        for k in range(ptr_len - 1):
            var start = flat.con_ptr[k]
            var stop = flat.con_ptr[k + 1]
            var nodes = List[ExprNode]()
            for j in range(start, stop):
                nodes.append(
                    ExprNode(
                        flat.con_ops[j],
                        flat.con_values[j],
                        flat.con_var_idx[j],
                        flat.con_lefts[j],
                        flat.con_rights[j],
                        flat.con_extras[j],
                    )
                )
            constraints.append(
                OptConstraint(
                    nodes^, flat.con_roots[k], flat.con_senses[k], flat.con_rhs[k],
                    "c" + String(k),
                )
            )
    var policy = OptPolicy(
        flat.max_iterations,
        flat.max_time_ms,
        flat.feasibility_tol,
        flat.optimality_tol,
        flat.integrality_tol,
    )
    return OptModel(
        variables^, obj_nodes^, flat.obj_root, flat.maximize, constraints^, policy^
    )


def model_to_flat(model: OptModel) -> ModelFlat:
    """Pack a model into its wire form — the other half of `model_from_flat`.

    Constraint arenas are concatenated in order and `con_roots[k]` stays RELATIVE to
    constraint `k`'s slice, so a round trip returns the same constraint list even after
    the constraints have been reordered.
    """
    var var_lower = List[Float64]()
    var var_upper = List[Float64]()
    var var_kind = List[Int]()
    var var_flags = List[Int]()
    var var_start = List[Float64]()
    for i in range(len(model.variables)):
        ref v = model.variables[i]
        var_lower.append(v.lower)
        var_upper.append(v.upper)
        var_kind.append(v.kind)
        var_flags.append(v.flags())
        var_start.append(v.start)

    var obj = arena_to_flat(model.obj_nodes, model.obj_root)

    var con_ptr = List[Int]()
    var con_roots = List[Int]()
    var con_senses = List[Int]()
    var con_rhs = List[Float64]()
    var con_ops = List[Int]()
    var con_values = List[Float64]()
    var con_var_idx = List[Int]()
    var con_lefts = List[Int]()
    var con_rights = List[Int]()
    var con_extras = List[Int]()
    con_ptr.append(0)
    for k in range(len(model.constraints)):
        ref con = model.constraints[k]
        for j in range(len(con.nodes)):
            ref node = con.nodes[j]
            con_ops.append(node.op)
            con_values.append(node.fval)
            con_var_idx.append(node.var_idx)
            con_lefts.append(node.left)
            con_rights.append(node.right)
            con_extras.append(node.extra)
        con_ptr.append(len(con_ops))
        con_roots.append(con.root)
        con_senses.append(con.sense)
        con_rhs.append(con.rhs)

    return ModelFlat(
        var_lower^,
        var_upper^,
        var_kind^,
        var_flags^,
        var_start^,
        model.maximize,
        obj.root,
        obj.ops.copy(),
        obj.values.copy(),
        obj.var_idx.copy(),
        obj.lefts.copy(),
        obj.rights.copy(),
        obj.extras.copy(),
        con_ptr^,
        con_roots^,
        con_senses^,
        con_rhs^,
        con_ops^,
        con_values^,
        con_var_idx^,
        con_lefts^,
        con_rights^,
        con_extras^,
        model.policy.max_iterations,
        model.policy.max_time_ms,
        model.policy.feasibility_tol,
        model.policy.optimality_tol,
        model.policy.integrality_tol,
    )


def model_validate(flat: ModelFlat) -> ModelValidation:
    """Validate a wire model. The structural defect of the FLAT form is reported as
    itself, never as the "empty objective" it would degenerate into."""
    var defect = flat_defect(flat)
    if defect != MODEL_OK:
        return _rejected(
            defect, model_status_name(defect), 0, 0, 0, 0, flat.maximize, -1, -1, -1
        )
    return validate_model(model_from_flat(flat))


def model_evaluate(flat: ModelFlat, x: List[Float64]) -> ModelEvaluation:
    """Evaluate a wire model at a point."""
    var defect = flat_defect(flat)
    if defect != MODEL_OK:
        return _no_evaluation(defect, 0, 0, flat.maximize, -1, -1)
    return evaluate_model(model_from_flat(flat), x)


def model_objective(flat: ModelFlat, x: List[Float64]) -> ScalarResult:
    """The objective of a wire model at a point — the call an optimizer makes per iterate."""
    var defect = flat_defect(flat)
    if defect != MODEL_OK:
        return _no_value(defect, -1, 0)
    return evaluate_objective(model_from_flat(flat), x)


def _empty_flat(maximize: Bool) -> ModelFlat:
    """A ModelFlat with nothing in it, used as the rejection value of `linear_model_flat`.

    `obj_root` is -1, which `check_expr` rejects, so an ignored status cannot be evaluated
    as if it were a model.
    """
    return ModelFlat(
        List[Float64](),
        List[Float64](),
        List[Int](),
        List[Int](),
        List[Float64](),
        maximize,
        -1,
        List[Int](),
        List[Float64](),
        List[Int](),
        List[Int](),
        List[Int](),
        List[Int](),
        List[Int](),
        List[Int](),
        List[Int](),
        List[Float64](),
        List[Int](),
        List[Float64](),
        List[Int](),
        List[Int](),
        List[Int](),
        List[Int](),
        DEFAULT_MAX_ITERATIONS,
        DEFAULT_MAX_TIME_MS,
        DEFAULT_FEASIBILITY_TOL,
        DEFAULT_OPTIMALITY_TOL,
        DEFAULT_INTEGRALITY_TOL,
    )


@fieldwise_init
struct LinearModel(Copyable, Movable):
    """A linear program packed into the general model form, plus the verdict on it.

    Returned instead of a bare `ModelFlat` because `ModelFlat` has no status field: the
    model is the answer and the status is about the REQUEST, and folding "your matrix was
    the wrong shape" into a model with no objective is exactly the conflation this package
    removes.
    """

    var status: Int
    var n_vars: Int
    var n_constraints: Int
    var model: ModelFlat


def linear_model_flat(
    c: List[Float64], a: List[Float64], rows: Int, cols: Int,
    senses: List[Int], rhs: List[Float64],
    var_lower: List[Float64], var_upper: List[Float64],
    var_kind: List[Int], var_flags: List[Int], maximize: Bool,
) -> LinearModel:
    """Build the general model for `c·x` subject to row-wise `A x sense b` and the box.

    This is the bridge from the shape every LP caller already has to the shape a general
    solver can consume, and it is why `linear_programming.lp_solve_2var`'s two-variable
    limit stops being the ceiling on the tree.

    The dense `A` is validated with `sparse_numerics.csr.dims_fit`, not with
    `rows * cols == len(a)`: that product is a wrapping 64-bit multiply, so
    `3 * 6148914691236517206 == 2` passes such a check and then reads far past the end of
    a two-element list — an uncatchable process crash reachable from the SDK.
    """
    # The parameters are packed several per line ON PURPOSE. `mojo_inventory` follows a
    # signature at most nine lines past its first, so a one-parameter-per-line signature
    # with eleven parameters never closes inside that window and the function is dropped
    # from the runtime contract with no error anywhere. Verified: this function was
    # invisible to `discover_runtime_library_modules` until the signature was reflowed.
    if rows < 0 or cols < 0:
        return LinearModel(MODEL_ERR_DENSE_SHAPE, 0, 0, _empty_flat(maximize))
    if not dims_fit(rows, cols, len(a)):
        return LinearModel(MODEL_ERR_DENSE_SHAPE, 0, 0, _empty_flat(maximize))
    if len(c) != cols:
        return LinearModel(MODEL_ERR_LENGTH_MISMATCH, 0, 0, _empty_flat(maximize))
    if len(senses) != rows or len(rhs) != rows:
        return LinearModel(MODEL_ERR_LENGTH_MISMATCH, 0, 0, _empty_flat(maximize))
    var bounds_defect = variables_defect_flat(var_lower, var_upper, var_kind, var_flags)
    if bounds_defect != MODEL_OK:
        return LinearModel(bounds_defect, 0, 0, _empty_flat(maximize))
    if len(var_lower) != cols:
        return LinearModel(MODEL_ERR_LENGTH_MISMATCH, 0, 0, _empty_flat(maximize))
    for i in range(rows):
        if senses[i] != SENSE_LE and senses[i] != SENSE_EQ and senses[i] != SENSE_GE:
            return LinearModel(MODEL_ERR_SENSE, 0, 0, _empty_flat(maximize))
        if not model_finite(rhs[i]):
            return LinearModel(MODEL_ERR_NON_FINITE_RHS, 0, 0, _empty_flat(maximize))
    for i in range(len(a)):
        if not model_finite(a[i]):
            return LinearModel(MODEL_ERR_NON_FINITE_COEFFICIENT, 0, 0, _empty_flat(maximize))

    var objective = linear_arena(c, 0.0)
    if objective.status != MODEL_OK:
        return LinearModel(objective.status, 0, 0, _empty_flat(maximize))

    var con_ptr = List[Int]()
    var con_roots = List[Int]()
    var con_senses = List[Int]()
    var con_rhs = List[Float64]()
    var con_ops = List[Int]()
    var con_values = List[Float64]()
    var con_var_idx = List[Int]()
    var con_lefts = List[Int]()
    var con_rights = List[Int]()
    var con_extras = List[Int]()
    con_ptr.append(0)
    for i in range(rows):
        var row = List[Float64]()
        for j in range(cols):
            row.append(a[i * cols + j])
        var arena = linear_arena(row, 0.0)
        if arena.status != MODEL_OK:
            return LinearModel(arena.status, 0, 0, _empty_flat(maximize))
        for t in range(arena.n_nodes):
            con_ops.append(arena.ops[t])
            con_values.append(arena.values[t])
            con_var_idx.append(arena.var_idx[t])
            con_lefts.append(arena.lefts[t])
            con_rights.append(arena.rights[t])
            con_extras.append(arena.extras[t])
        con_ptr.append(len(con_ops))
        con_roots.append(arena.root)
        con_senses.append(senses[i])
        con_rhs.append(rhs[i])

    var var_start = List[Float64]()
    for _ in range(cols):
        var_start.append(0.0)

    var flat = ModelFlat(
        var_lower.copy(),
        var_upper.copy(),
        var_kind.copy(),
        var_flags.copy(),
        var_start^,
        maximize,
        objective.root,
        objective.ops.copy(),
        objective.values.copy(),
        objective.var_idx.copy(),
        objective.lefts.copy(),
        objective.rights.copy(),
        objective.extras.copy(),
        con_ptr^,
        con_roots^,
        con_senses^,
        con_rhs^,
        con_ops^,
        con_values^,
        con_var_idx^,
        con_lefts^,
        con_rights^,
        con_extras^,
        DEFAULT_MAX_ITERATIONS,
        DEFAULT_MAX_TIME_MS,
        DEFAULT_FEASIBILITY_TOL,
        DEFAULT_OPTIMALITY_TOL,
        DEFAULT_INTEGRALITY_TOL,
    )
    var verdict = model_validate(flat)
    if verdict.status != MODEL_OK:
        return LinearModel(verdict.status, cols, rows, _empty_flat(maximize))
    return LinearModel(MODEL_OK, cols, rows, flat^)
