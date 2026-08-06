"""
pipelines.mojo — Fit/transform pipeline composition over built-in transforms.
Zero Python imports.

Replaces sklearn.pipeline.Pipeline composed with sklearn.preprocessing
(StandardScaler, MinMaxScaler, FunctionTransformer(log1p), clip,
SimpleImputer(strategy="median")) as a pipeline SPEC executor: transforms
are encoded by integer id, fitted per-column statistics are flattened into
one Float64 buffer, and transform/inverse replay the spec deterministically.
Complements transform.mojo (single stateless whole-list transforms) and
feature_engineering.mojo (scalar per-value scaling): this kernel owns
per-column fitted state and sequential composition on row-major matrices,
fitting each step on the output of the previous steps.

Transform ids (step encoding):
  0 = standardize    — per column z = (x - mean) / std (population std;
                       std == 0 maps to 0.0, inverse then recovers the mean)
  1 = minmax         — per column (x - min) / (max - min) (range == 0 maps
                       to 0.0, inverse then recovers the min)
  2 = log1p          — log(1 + x); 1 + x <= 0 yields NaN
  3 = clip(lo, hi)   — hyperparams: consumes 2 Float64 from `params` per
                       clip step, in step order; requires lo <= hi
  4 = impute_median  — per-column median of non-NaN values replaces NaN
                       (all-NaN column imputes 0.0)

NaN semantics: missing values are IEEE NaN (checked via isnan). Fitting
ignores NaN when learning statistics; standardize/minmax/clip pass NaN
through unchanged; impute_median fills it.

Public API:
  PipelineState          — fitted pipeline (ok, steps, cols, learned, offsets)
  InverseResult          — pipeline_inverse output (ok, data)
  pipeline_fit           — fit steps sequentially on X (row-major flat)
  pipeline_transform     — apply fitted steps in order to new data
  pipeline_inverse       — apply inverses in reverse order (ids 0,1,2 only)
  pipeline_is_invertible — True iff every step has an exact inverse
  step_param_count       — learned-param buffer length for one step id
"""

from std.math import sqrt, log, exp, isnan


# ── result structs ───────────────────────────────────────────────────────────


struct PipelineState(Copyable, Movable):
    """Fitted pipeline.

    ok       — True iff fitting succeeded (invalid spec/data -> False).
    steps    — transform ids in application order.
    cols     — number of columns the pipeline was fitted on.
    learned  — all fitted params flattened, in step order. Layouts:
               standardize: [mean_0..mean_{c-1}, std_0..std_{c-1}];
               minmax: [min_0..min_{c-1}, max_0..max_{c-1}]; log1p: none;
               clip: [lo, hi]; impute_median: [median_0..median_{c-1}].
    offsets  — offsets[i] = start of step i's params within learned.
    """
    var ok: Bool
    var steps: List[Int]
    var cols: Int
    var learned: List[Float64]
    var offsets: List[Int]

    def __init__(out self):
        self.ok = False
        self.steps = List[Int]()
        self.cols = 0
        self.learned = List[Float64]()
        self.offsets = List[Int]()


struct InverseResult(Copyable, Movable):
    """pipeline_inverse output: ok=False when any step is non-invertible."""
    var ok: Bool
    var data: List[Float64]

    def __init__(out self):
        self.ok = False
        self.data = List[Float64]()


# ── helpers ──────────────────────────────────────────────────────────────────


def _nan() -> Float64:
    return Float64(0.0) / Float64(0.0)


def _sift_down(mut arr: List[Float64], start: Int, size: Int):
    """Restore the max-heap property for the subtree rooted at start."""
    var root = start
    while True:
        var child = 2 * root + 1
        if child >= size:
            return
        if child + 1 < size and arr[child + 1] > arr[child]:
            child += 1
        if arr[root] >= arr[child]:
            return
        var tmp = arr[root]
        arr[root] = arr[child]
        arr[child] = tmp
        root = child


def _sort_floats(mut arr: List[Float64]):
    """In-place ascending heapsort. O(n log n) worst case, deterministic."""
    var n = len(arr)
    if n < 2:
        return
    var i = n // 2 - 1
    while i >= 0:
        _sift_down(arr, i, n)
        i -= 1
    var end = n - 1
    while end > 0:
        var tmp = arr[0]
        arr[0] = arr[end]
        arr[end] = tmp
        _sift_down(arr, 0, end)
        end -= 1


def _column_median(buf: List[Float64], rows: Int, cols: Int, j: Int) -> Float64:
    """Median of non-NaN values in column j; 0.0 if the column is all NaN."""
    var vals = List[Float64]()
    for r in range(rows):
        var v = buf[r * cols + j]
        if not isnan(v):
            vals.append(v)
    var m = len(vals)
    if m == 0:
        return 0.0
    _sort_floats(vals)
    if m % 2 == 1:
        return vals[m // 2]
    return (vals[m // 2 - 1] + vals[m // 2]) / 2.0


def _apply_step(
    t: Int,
    learned: List[Float64],
    off: Int,
    mut buf: List[Float64],
    rows: Int,
    cols: Int,
):
    """Apply one fitted step in place. Assumes valid t/off/shape."""
    if t == 0:
        for j in range(cols):
            var m = learned[off + j]
            var sd = learned[off + cols + j]
            for r in range(rows):
                var idx = r * cols + j
                var v = buf[idx]
                if not isnan(v):
                    if sd > 0.0:
                        buf[idx] = (v - m) / sd
                    else:
                        buf[idx] = 0.0
    elif t == 1:
        for j in range(cols):
            var mn = learned[off + j]
            var rng = learned[off + cols + j] - mn
            for r in range(rows):
                var idx = r * cols + j
                var v = buf[idx]
                if not isnan(v):
                    if rng > 0.0:
                        buf[idx] = (v - mn) / rng
                    else:
                        buf[idx] = 0.0
    elif t == 2:
        for i in range(rows * cols):
            var v = buf[i]
            if not isnan(v):
                if 1.0 + v <= 0.0:
                    buf[i] = _nan()
                else:
                    buf[i] = log(1.0 + v)
    elif t == 3:
        var lo = learned[off]
        var hi = learned[off + 1]
        for i in range(rows * cols):
            var v = buf[i]
            if not isnan(v):
                if v < lo:
                    buf[i] = lo
                elif v > hi:
                    buf[i] = hi
    elif t == 4:
        for j in range(cols):
            var med = learned[off + j]
            for r in range(rows):
                var idx = r * cols + j
                if isnan(buf[idx]):
                    buf[idx] = med


# ── step_param_count ─────────────────────────────────────────────────────────


def step_param_count(t: Int, cols: Int) -> Int:
    """Length of the learned-param block one step contributes; -1 if t unknown.

    standardize/minmax: 2*cols; log1p: 0; clip: 2; impute_median: cols.
    """
    if t == 0 or t == 1:
        return 2 * cols
    if t == 2:
        return 0
    if t == 3:
        return 2
    if t == 4:
        return cols
    return -1


# ── pipeline_fit ─────────────────────────────────────────────────────────────


def pipeline_fit(
    x: List[Float64],
    rows: Int,
    cols: Int,
    steps: List[Int],
    params: List[Float64],
) -> PipelineState:
    """Fit a pipeline spec on row-major X (len == rows*cols).

    Each step is fitted on the data as transformed by all previous steps
    (sklearn Pipeline.fit semantics), then applied before fitting the next.
    `params` supplies hyperparams consumed in step order: 2 Float64 (lo, hi)
    per clip step; other steps consume none. Statistics (mean/std/min/max/
    median) are computed over non-NaN values only; population std (ddof=0).
    Returns state with ok=False on: rows <= 0, cols <= 0, size mismatch,
    unknown step id, missing clip params, or clip with NaN bounds or lo > hi.
    """
    var state = PipelineState()
    if rows <= 0 or cols <= 0 or len(x) != rows * cols:
        return state^
    var need = 0
    for s in range(len(steps)):
        var t = steps[s]
        if t < 0 or t > 4:
            return state^
        if t == 3:
            need += 2
    if len(params) < need:
        return state^

    var buf = List[Float64](capacity=rows * cols)
    for i in range(len(x)):
        buf.append(x[i])

    var pcur = 0
    for s in range(len(steps)):
        var t = steps[s]
        var off = len(state.learned)
        state.offsets.append(off)
        if t == 0:
            # means, then population stds, over non-NaN values per column
            var means = List[Float64]()
            var stds = List[Float64]()
            for j in range(cols):
                var total: Float64 = 0.0
                var cnt = 0
                for r in range(rows):
                    var v = buf[r * cols + j]
                    if not isnan(v):
                        total += v
                        cnt += 1
                var m: Float64 = 0.0
                if cnt > 0:
                    m = total / Float64(cnt)
                var ss: Float64 = 0.0
                for r in range(rows):
                    var v = buf[r * cols + j]
                    if not isnan(v):
                        var d = v - m
                        ss += d * d
                var sd: Float64 = 0.0
                if cnt > 0:
                    sd = sqrt(ss / Float64(cnt))
                means.append(m)
                stds.append(sd)
            for j in range(cols):
                state.learned.append(means[j])
            for j in range(cols):
                state.learned.append(stds[j])
        elif t == 1:
            # mins, then maxs, over non-NaN values per column
            var mins = List[Float64]()
            var maxs = List[Float64]()
            for j in range(cols):
                var mn: Float64 = 0.0
                var mx: Float64 = 0.0
                var seen = False
                for r in range(rows):
                    var v = buf[r * cols + j]
                    if not isnan(v):
                        if not seen:
                            mn = v
                            mx = v
                            seen = True
                        else:
                            if v < mn:
                                mn = v
                            if v > mx:
                                mx = v
                mins.append(mn)
                maxs.append(mx)
            for j in range(cols):
                state.learned.append(mins[j])
            for j in range(cols):
                state.learned.append(maxs[j])
        elif t == 3:
            var lo = params[pcur]
            var hi = params[pcur + 1]
            pcur += 2
            if isnan(lo) or isnan(hi) or lo > hi:
                var bad = PipelineState()
                return bad^
            state.learned.append(lo)
            state.learned.append(hi)
        elif t == 4:
            for j in range(cols):
                state.learned.append(_column_median(buf, rows, cols, j))
        # t == 2 (log1p): no learned params.
        _apply_step(t, state.learned, off, buf, rows, cols)

    state.ok = True
    state.steps = steps.copy()
    state.cols = cols
    return state^


# ── pipeline_transform ───────────────────────────────────────────────────────


def pipeline_transform(
    state: PipelineState, x: List[Float64], rows: Int
) -> List[Float64]:
    """Apply the fitted steps in order to row-major X (len == rows*state.cols).

    Returns the transformed flat matrix; empty list if the state is invalid
    or the shape does not match. An empty spec (zero steps) is the identity.
    """
    var out = List[Float64]()
    if not state.ok or rows <= 0 or len(x) != rows * state.cols:
        return out^
    for i in range(len(x)):
        out.append(x[i])
    for s in range(len(state.steps)):
        _apply_step(
            state.steps[s], state.learned, state.offsets[s], out, rows, state.cols
        )
    return out^


# ── pipeline_is_invertible ───────────────────────────────────────────────────


def pipeline_is_invertible(state: PipelineState) -> Bool:
    """True iff state.ok and every step has an exact inverse (ids 0, 1, 2).

    clip (3) and impute_median (4) destroy information and are not
    invertible.
    """
    if not state.ok:
        return False
    for s in range(len(state.steps)):
        var t = state.steps[s]
        if t != 0 and t != 1 and t != 2:
            return False
    return True


# ── pipeline_inverse ─────────────────────────────────────────────────────────


def pipeline_inverse(
    state: PipelineState, y: List[Float64], rows: Int
) -> InverseResult:
    """Invert the pipeline: apply step inverses in reverse order.

    standardize: x = z*std + mean (std==0 column recovers the mean);
    minmax: x = u*(max-min) + min (range==0 column recovers the min);
    log1p: x = exp(u) - 1. ok=False (empty data) if the state is invalid,
    the shape mismatches, or any step is clip/impute_median.
    """
    var res = InverseResult()
    if not pipeline_is_invertible(state):
        return res^
    if rows <= 0 or len(y) != rows * state.cols:
        return res^
    var buf = List[Float64](capacity=len(y))
    for i in range(len(y)):
        buf.append(y[i])
    var cols = state.cols
    for s in range(len(state.steps) - 1, -1, -1):
        var t = state.steps[s]
        var off = state.offsets[s]
        if t == 0:
            for j in range(cols):
                var m = state.learned[off + j]
                var sd = state.learned[off + cols + j]
                for r in range(rows):
                    var idx = r * cols + j
                    buf[idx] = buf[idx] * sd + m
        elif t == 1:
            for j in range(cols):
                var mn = state.learned[off + j]
                var rng = state.learned[off + cols + j] - mn
                for r in range(rows):
                    var idx = r * cols + j
                    buf[idx] = buf[idx] * rng + mn
        else:  # t == 2
            for i in range(rows * cols):
                buf[i] = exp(buf[i]) - 1.0
    res.ok = True
    res.data = buf^
    return res^
