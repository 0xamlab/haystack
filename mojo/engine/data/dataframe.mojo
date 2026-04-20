"""
dataframe.mojo — Columnar DataFrame for tabular data. Zero Python imports.
Replaces: pandas.DataFrame core operations (select, filter, sort, groupby, aggregate, merge).
Column-major storage for cache-friendly column operations.
"""
from std.math import sqrt, abs as fabs


# ── Column struct ─────────────────────────────────────────────────────────────


struct Column(Copyable, Movable):
    """A single named column of Float64 values."""
    var name: String
    var data: List[Float64]
    var n: Int

    fn __init__(out self):
        self.name = String("")
        self.data = List[Float64]()
        self.n = 0

    fn __init__(out self, name: String, data: List[Float64]):
        self.name = name
        self.data = data.copy()
        self.n = len(data)

    fn __copyinit__(out self, copy: Self):
        self.name = copy.name
        self.data = copy.data.copy()
        self.n = copy.n


# ── DataFrame struct ──────────────────────────────────────────────────────────


struct DataFrame(Copyable, Movable):
    """Columnar tabular data structure."""
    var columns: List[Column]
    var n_cols: Int
    var n_rows: Int
    var col_names: List[String]

    fn __init__(out self):
        self.columns = List[Column]()
        self.n_cols = 0
        self.n_rows = 0
        self.col_names = List[String]()

    fn __copyinit__(out self, copy: Self):
        self.columns = copy.columns.copy()
        self.n_cols = copy.n_cols
        self.n_rows = copy.n_rows
        self.col_names = copy.col_names.copy()

    # ── Construction ──────────────────────────────────────────────────────

    fn add_column(mut self, name: String, data: List[Float64]):
        """Add a column. If first column, sets n_rows."""
        var col = Column(name, data)
        if self.n_cols == 0:
            self.n_rows = col.n
        self.columns.append(col^)
        self.col_names.append(name)
        self.n_cols += 1

    # ── Access ────────────────────────────────────────────────────────────

    fn col_index(self, name: String) -> Int:
        """Return index of column with given name, or -1 if not found."""
        for i in range(self.n_cols):
            if self.col_names[i] == name:
                return i
        return -1

    fn get_column(self, name: String) -> List[Float64]:
        """Get column data by name. Returns empty list if not found."""
        var idx = self.col_index(name)
        if idx < 0:
            return List[Float64]()
        return self.columns[idx].data.copy()

    fn get_column_idx(self, idx: Int) -> List[Float64]:
        """Get column data by index."""
        if idx < 0 or idx >= self.n_cols:
            return List[Float64]()
        return self.columns[idx].data.copy()

    fn get_value(self, row: Int, col: String) -> Float64:
        """Get a single value at (row, col_name)."""
        var idx = self.col_index(col)
        if idx < 0 or row < 0 or row >= self.n_rows:
            return 0.0
        return self.columns[idx].data[row]

    # ── Info ──────────────────────────────────────────────────────────────

    fn shape(self) -> Tuple[Int, Int]:
        """Return (n_rows, n_cols)."""
        return (self.n_rows, self.n_cols)

    fn count(self) -> Int:
        """Return number of rows."""
        return self.n_rows

    fn head(self, n: Int = 5) -> String:
        """First n rows as formatted string."""
        var rows_to_show = n
        if rows_to_show > self.n_rows:
            rows_to_show = self.n_rows
        var result = String("")
        # Header
        for c in range(self.n_cols):
            if c > 0:
                result += "\t"
            result += self.col_names[c]
        result += "\n"
        # Rows
        for r in range(rows_to_show):
            for c in range(self.n_cols):
                if c > 0:
                    result += "\t"
                result += String(self.columns[c].data[r])
            result += "\n"
        return result

    fn describe(self) -> String:
        """Summary stats per column (count, mean, std, min, 25%, 50%, 75%, max)."""
        var result = String("")
        for c in range(self.n_cols):
            var n = self.columns[c].n
            if n == 0:
                continue

            # Compute sum, min, max
            var sum_val: Float64 = 0.0
            var min_val = self.columns[c].data[0]
            var max_val = self.columns[c].data[0]
            for i in range(n):
                var v = self.columns[c].data[i]
                sum_val += v
                if v < min_val:
                    min_val = v
                if v > max_val:
                    max_val = v
            var mean_val = sum_val / Float64(n)

            # Variance and std
            var var_val: Float64 = 0.0
            for i in range(n):
                var d = self.columns[c].data[i] - mean_val
                var_val += d * d
            if n > 1:
                var_val = var_val / Float64(n - 1)
            var std_val = sqrt(var_val)

            # Sort a copy for percentiles
            var sorted_data = self.columns[c].data.copy()
            _insertion_sort(sorted_data, n)

            var p25 = sorted_data[max(0, min((n - 1) * 25 // 100, n - 1))]
            var p50 = sorted_data[max(0, min((n - 1) * 50 // 100, n - 1))]
            var p75 = sorted_data[max(0, min((n - 1) * 75 // 100, n - 1))]

            result += self.columns[c].name + ": count=" + String(n)
            result += " mean=" + String(mean_val)
            result += " std=" + String(std_val)
            result += " min=" + String(min_val)
            result += " 25%=" + String(p25)
            result += " 50%=" + String(p50)
            result += " 75%=" + String(p75)
            result += " max=" + String(max_val)
            result += "\n"

        return result

    # ── Selection ─────────────────────────────────────────────────────────

    fn select(self, selected_names: List[String]) -> DataFrame:
        """Select specific columns by name."""
        var result = DataFrame()
        for i in range(len(selected_names)):
            var idx = self.col_index(selected_names[i])
            if idx >= 0:
                result.add_column(self.col_names[idx], self.columns[idx].data.copy())
        return result^

    fn drop(self, drop_names: List[String]) -> DataFrame:
        """Drop specific columns by name."""
        var result = DataFrame()
        for c in range(self.n_cols):
            var should_drop = False
            for d in range(len(drop_names)):
                if self.col_names[c] == drop_names[d]:
                    should_drop = True
                    break
            if not should_drop:
                result.add_column(self.col_names[c], self.columns[c].data.copy())
        return result^

    fn slice_rows(self, start: Int, end: Int) -> DataFrame:
        """Row range selection [start, end)."""
        var result = DataFrame()
        var s = start
        var e = end
        if s < 0:
            s = 0
        if e > self.n_rows:
            e = self.n_rows
        for c in range(self.n_cols):
            var new_data = List[Float64]()
            for r in range(s, e):
                new_data.append(self.columns[c].data[r])
            result.add_column(self.col_names[c], new_data^)
        return result^

    # ── Filter ────────────────────────────────────────────────────────────

    fn filter_gt(self, col: String, threshold: Float64) -> DataFrame:
        """Rows where col > threshold."""
        var idx = self.col_index(col)
        if idx < 0:
            return DataFrame()
        # Build boolean mask
        var mask = List[Bool]()
        for r in range(self.n_rows):
            mask.append(self.columns[idx].data[r] > threshold)
        return self._apply_mask(mask)

    fn filter_lt(self, col: String, threshold: Float64) -> DataFrame:
        """Rows where col < threshold."""
        var idx = self.col_index(col)
        if idx < 0:
            return DataFrame()
        var mask = List[Bool]()
        for r in range(self.n_rows):
            mask.append(self.columns[idx].data[r] < threshold)
        return self._apply_mask(mask)

    fn filter_eq(self, col: String, value: Float64) -> DataFrame:
        """Rows where col == value."""
        var idx = self.col_index(col)
        if idx < 0:
            return DataFrame()
        var mask = List[Bool]()
        for r in range(self.n_rows):
            mask.append(fabs(self.columns[idx].data[r] - value) < 1e-12)
        return self._apply_mask(mask)

    fn filter_between(self, col: String, low: Float64, high: Float64) -> DataFrame:
        """Rows where low <= col <= high."""
        var idx = self.col_index(col)
        if idx < 0:
            return DataFrame()
        var mask = List[Bool]()
        for r in range(self.n_rows):
            var v = self.columns[idx].data[r]
            mask.append(v >= low and v <= high)
        return self._apply_mask(mask)

    fn _apply_mask(self, mask: List[Bool]) -> DataFrame:
        """Internal: build new DataFrame with only rows where mask is True."""
        var result = DataFrame()
        for c in range(self.n_cols):
            var new_data = List[Float64]()
            for r in range(self.n_rows):
                if mask[r]:
                    new_data.append(self.columns[c].data[r])
            result.add_column(self.col_names[c], new_data^)
        return result^

    # ── Sort ──────────────────────────────────────────────────────────────

    fn sort_by(self, col: String, ascending: Bool = True) -> DataFrame:
        """Sort all columns by values in the specified column."""
        var idx = self.col_index(col)
        if idx < 0:
            return DataFrame()
        var col_data = self.columns[idx].data.copy()

        # Create index array
        var indices = List[Int]()
        for i in range(self.n_rows):
            indices.append(i)

        # Insertion sort on indices by column values
        for i in range(1, self.n_rows):
            var key_idx = indices[i]
            var key_val = col_data[key_idx]
            var j = i - 1
            while j >= 0:
                var should_swap: Bool
                if ascending:
                    should_swap = col_data[indices[j]] > key_val
                else:
                    should_swap = col_data[indices[j]] < key_val
                if not should_swap:
                    break
                indices[j + 1] = indices[j]
                j -= 1
            indices[j + 1] = key_idx

        # Build new DataFrame with reordered rows
        var result = DataFrame()
        for c in range(self.n_cols):
            var new_data = List[Float64]()
            for r in range(self.n_rows):
                new_data.append(self.columns[c].data[indices[r]])
            result.add_column(self.col_names[c], new_data^)
        return result^

    # ── Aggregate ─────────────────────────────────────────────────────────

    fn sum(self, col: String) -> Float64:
        """Sum of column values."""
        var idx = self.col_index(col)
        if idx < 0:
            return 0.0
        var total: Float64 = 0.0
        for i in range(self.n_rows):
            total += self.columns[idx].data[i]
        return total

    fn mean_col(self, col: String) -> Float64:
        """Mean of column values."""
        var idx = self.col_index(col)
        if idx < 0 or self.n_rows == 0:
            return 0.0
        var total: Float64 = 0.0
        for i in range(self.n_rows):
            total += self.columns[idx].data[i]
        return total / Float64(self.n_rows)

    fn std_col(self, col: String) -> Float64:
        """Standard deviation (sample) of column values."""
        var idx = self.col_index(col)
        if idx < 0 or self.n_rows <= 1:
            return 0.0
        var m = self.mean_col(col)
        var s: Float64 = 0.0
        for i in range(self.n_rows):
            var d = self.columns[idx].data[i] - m
            s += d * d
        return sqrt(s / Float64(self.n_rows - 1))

    fn min_col(self, col: String) -> Float64:
        """Minimum of column values."""
        var idx = self.col_index(col)
        if idx < 0 or self.n_rows == 0:
            return 0.0
        var result = self.columns[idx].data[0]
        for i in range(1, self.n_rows):
            if self.columns[idx].data[i] < result:
                result = self.columns[idx].data[i]
        return result

    fn max_col(self, col: String) -> Float64:
        """Maximum of column values."""
        var idx = self.col_index(col)
        if idx < 0 or self.n_rows == 0:
            return 0.0
        var result = self.columns[idx].data[0]
        for i in range(1, self.n_rows):
            if self.columns[idx].data[i] > result:
                result = self.columns[idx].data[i]
        return result

    # ── GroupBy + Aggregate ───────────────────────────────────────────────

    fn groupby_agg(self, group_col: String, agg_col: String, agg_fn: String) -> DataFrame:
        """Group by group_col and aggregate agg_col.
        agg_fn: "sum", "mean", "min", "max", "count", "std".
        Returns DataFrame with 2 columns: [group_col, agg_result]."""
        var g_idx = self.col_index(group_col)
        var a_idx = self.col_index(agg_col)
        if g_idx < 0 or a_idx < 0:
            return DataFrame()

        var g_data = self.columns[g_idx].data.copy()
        var a_data = self.columns[a_idx].data.copy()

        # Find unique group values (linear scan)
        var unique_vals = List[Float64]()
        for i in range(self.n_rows):
            var found = False
            for j in range(len(unique_vals)):
                if fabs(g_data[i] - unique_vals[j]) < 1e-12:
                    found = True
                    break
            if not found:
                unique_vals.append(g_data[i])

        # For each unique value, compute aggregate
        var result_groups = List[Float64]()
        var result_agg = List[Float64]()

        for g in range(len(unique_vals)):
            var gval = unique_vals[g]
            var vals = List[Float64]()
            for i in range(self.n_rows):
                if fabs(g_data[i] - gval) < 1e-12:
                    vals.append(a_data[i])

            var n = len(vals)
            var agg_result: Float64 = 0.0

            if agg_fn == "sum":
                for i in range(n):
                    agg_result += vals[i]
            elif agg_fn == "mean":
                var t: Float64 = 0.0
                for i in range(n):
                    t += vals[i]
                agg_result = t / Float64(n)
            elif agg_fn == "min":
                agg_result = vals[0]
                for i in range(1, n):
                    if vals[i] < agg_result:
                        agg_result = vals[i]
            elif agg_fn == "max":
                agg_result = vals[0]
                for i in range(1, n):
                    if vals[i] > agg_result:
                        agg_result = vals[i]
            elif agg_fn == "count":
                agg_result = Float64(n)
            elif agg_fn == "std":
                var m: Float64 = 0.0
                for i in range(n):
                    m += vals[i]
                m = m / Float64(n)
                var sv: Float64 = 0.0
                for i in range(n):
                    var d = vals[i] - m
                    sv += d * d
                if n > 1:
                    agg_result = sqrt(sv / Float64(n - 1))

            result_groups.append(gval)
            result_agg.append(agg_result)

        var result = DataFrame()
        result.add_column(group_col, result_groups^)
        result.add_column(agg_col, result_agg^)
        return result^

    # ── Transform ─────────────────────────────────────────────────────────

    fn add_computed_column(mut self, name: String, col_a: String, op: String, col_b: String):
        """Add new column: result = col_a op col_b. op: "+", "-", "*", "/"."""
        var a_idx = self.col_index(col_a)
        var b_idx = self.col_index(col_b)
        if a_idx < 0 or b_idx < 0:
            return
        var new_data = List[Float64]()
        for r in range(self.n_rows):
            var va = self.columns[a_idx].data[r]
            var vb = self.columns[b_idx].data[r]
            var result: Float64 = 0.0
            if op == "+":
                result = va + vb
            elif op == "-":
                result = va - vb
            elif op == "*":
                result = va * vb
            elif op == "/":
                if fabs(vb) > 1e-15:
                    result = va / vb
            new_data.append(result)
        self.add_column(name, new_data^)

    fn apply_scalar(self, col: String, op: String, scalar: Float64) -> DataFrame:
        """Apply scalar operation to a column. op: "+", "-", "*", "/"."""
        var result = DataFrame()
        var target_idx = self.col_index(col)
        for c in range(self.n_cols):
            if c == target_idx:
                var new_data = List[Float64]()
                for r in range(self.n_rows):
                    var val = self.columns[c].data[r]
                    if op == "+":
                        new_data.append(val + scalar)
                    elif op == "-":
                        new_data.append(val - scalar)
                    elif op == "*":
                        new_data.append(val * scalar)
                    elif op == "/":
                        new_data.append(val / scalar)
                    else:
                        new_data.append(val)
                result.add_column(self.col_names[c], new_data^)
            else:
                result.add_column(self.col_names[c], self.columns[c].data.copy())
        return result^

    # ── Merge/Join ────────────────────────────────────────────────────────

    fn merge_inner(self, other: DataFrame, on: String) -> DataFrame:
        """Inner join on a common column name. O(n*m) for simplicity."""
        var self_key_idx = self.col_index(on)
        var other_key_idx = other.col_index(on)
        if self_key_idx < 0 or other_key_idx < 0:
            return DataFrame()

        var self_keys = self.columns[self_key_idx].data.copy()
        var other_keys = other.columns[other_key_idx].data.copy()

        # Collect matching row pairs
        var self_indices = List[Int]()
        var other_indices = List[Int]()

        for i in range(self.n_rows):
            for j in range(other.n_rows):
                if fabs(self_keys[i] - other_keys[j]) < 1e-12:
                    self_indices.append(i)
                    other_indices.append(j)

        var n_matches = len(self_indices)

        # Build result: all columns from self + non-key columns from other
        var result = DataFrame()

        # Add all columns from self
        for c in range(self.n_cols):
            var new_data = List[Float64]()
            for r in range(n_matches):
                new_data.append(self.columns[c].data[self_indices[r]])
            result.add_column(self.col_names[c], new_data^)

        # Add non-key columns from other
        for c in range(other.n_cols):
            if other.col_names[c] != on:
                var new_data = List[Float64]()
                for r in range(n_matches):
                    new_data.append(other.columns[c].data[other_indices[r]])
                result.add_column(other.col_names[c], new_data^)

        return result^

    # ── I/O ───────────────────────────────────────────────────────────────

    fn to_json(self) -> String:
        """JSON array of row objects."""
        var result = String("[")
        for r in range(self.n_rows):
            if r > 0:
                result += ","
            result += "{"
            for c in range(self.n_cols):
                if c > 0:
                    result += ","
                result += '"' + self.col_names[c] + '":'
                result += String(self.columns[c].data[r])
            result += "}"
        result += "]"
        return result

    fn to_csv(self) -> String:
        """CSV string with headers."""
        var result = String("")
        # Headers
        for c in range(self.n_cols):
            if c > 0:
                result += ","
            result += self.col_names[c]
        result += "\n"
        # Rows
        for r in range(self.n_rows):
            for c in range(self.n_cols):
                if c > 0:
                    result += ","
                result += String(self.columns[c].data[r])
            result += "\n"
        return result


# ── Module-level factory ──────────────────────────────────────────────────────


fn df_from_columns(names: List[String], cols: List[List[Float64]]) -> DataFrame:
    """Create DataFrame from column names and data lists."""
    var df = DataFrame()
    var n = len(names)
    for i in range(n):
        if i < len(cols):
            df.add_column(names[i], cols[i])
    return df^


# ── Internal helpers ──────────────────────────────────────────────────────────


fn _insertion_sort(mut data: List[Float64], n: Int):
    """In-place insertion sort for percentile computation."""
    for i in range(1, n):
        var key = data[i]
        var j = i - 1
        while j >= 0 and data[j] > key:
            data[j + 1] = data[j]
            j -= 1
        data[j + 1] = key
