"""
database.mojo — In-memory table simulation with query operations. Zero Python imports.

Replaces sqlalchemy core patterns with pure Mojo implementations for
table creation, insertion, selection, filtering, aggregation, sorting,
joining, and grouping.

Public API:
  Table                — struct with columns, n_rows, data (column-major)
  table_create         — Create empty table
  table_insert_row     — Insert a row
  table_select_column  — Get column data
  table_where          — Filter rows by condition
  table_aggregate      — Aggregate column (sum/mean/min/max/count)
  table_sort_by        — Sort indices by column
  table_join_inner     — Inner join on matching column values
  table_group_aggregate — Group by + aggregate
  table_row_count      — Number of rows
"""


# ── Table struct ──────────────────────────────────────────────────────────────


struct Table(Copyable, Movable):
    """In-memory table: column-major storage."""

    var columns: List[String]
    var n_rows: Int
    var data: List[List[Float64]]

    fn __init__(out self):
        self.columns = List[String]()
        self.n_rows = 0
        self.data = List[List[Float64]]()

    fn __init__(out self, columns: List[String], n_rows: Int, data: List[List[Float64]]):
        self.columns = columns.copy()
        self.n_rows = n_rows
        self.data = data.copy()

    fn __copyinit__(out self, copy: Self):
        self.columns = copy.columns.copy()
        self.n_rows = copy.n_rows
        self.data = copy.data.copy()


# ── Table creation ────────────────────────────────────────────────────────────


fn table_create(columns: List[String], n_rows: Int) -> Table:
    """Create empty table with given column names and 0 rows."""
    var data = List[List[Float64]]()
    var n_cols = len(columns)
    for _ in range(n_cols):
        data.append(List[Float64]())
    return Table(columns, 0, data)


# ── Row insertion ─────────────────────────────────────────────────────────────


fn table_insert_row(mut table: Table, row: List[Float64]):
    """Insert a row. row length must match number of columns."""
    var n_cols = len(table.columns)
    if len(row) != n_cols:
        return
    if len(table.data) < n_cols:
        return  # column storage shorter than columns: data[c] would abort
    for c in range(n_cols):
        table.data[c].append(row[c])
    table.n_rows += 1


# ── Column selection ──────────────────────────────────────────────────────────


fn table_select_column(table: Table, col_idx: Int) -> List[Float64]:
    """Get column data by index."""
    if col_idx < 0 or col_idx >= len(table.columns):
        return List[Float64]()
    return table.data[col_idx].copy()


# ── Filtering ─────────────────────────────────────────────────────────────────


fn table_where(table: Table, col_idx: Int, op: Int, value: Float64) -> List[Int]:
    """Filter rows. op: 0=eq, 1=gt, 2=lt, 3=gte, 4=lte. Returns row indices."""
    var result = List[Int]()
    if col_idx < 0 or col_idx >= len(table.columns):
        return result^
    for r in range(table.n_rows):
        var v = table.data[col_idx][r]
        var matched = False
        if op == 0:
            matched = v == value
        elif op == 1:
            matched = v > value
        elif op == 2:
            matched = v < value
        elif op == 3:
            matched = v >= value
        elif op == 4:
            matched = v <= value
        if matched:
            result.append(r)
    return result^


# ── Aggregation ───────────────────────────────────────────────────────────────


fn table_aggregate(table: Table, col_idx: Int, agg: Int) -> Float64:
    """Aggregate: 0=sum, 1=mean, 2=min, 3=max, 4=count."""
    if col_idx < 0 or col_idx >= len(table.columns) or table.n_rows == 0:
        return 0.0
    var n = table.n_rows
    if agg == 4:
        return Float64(n)
    if agg == 2:
        var mn = table.data[col_idx][0]
        for i in range(1, n):
            if table.data[col_idx][i] < mn:
                mn = table.data[col_idx][i]
        return mn
    if agg == 3:
        var mx = table.data[col_idx][0]
        for i in range(1, n):
            if table.data[col_idx][i] > mx:
                mx = table.data[col_idx][i]
        return mx
    var s: Float64 = 0.0
    for i in range(n):
        s += table.data[col_idx][i]
    if agg == 1:
        return s / Float64(n)
    return s  # agg == 0 (sum)


# ── Sorting ───────────────────────────────────────────────────────────────────


fn table_sort_by(table: Table, col_idx: Int, ascending: Bool) -> List[Int]:
    """Sort indices by column values (insertion sort)."""
    var indices = List[Int]()
    if col_idx < 0 or col_idx >= len(table.columns):
        return indices^
    var n = table.n_rows
    for i in range(n):
        indices.append(i)
    for i in range(1, n):
        var key_idx = indices[i]
        var key_val = table.data[col_idx][key_idx]
        var j = i - 1
        while j >= 0:
            var cmp_val = table.data[col_idx][indices[j]]
            var should_swap = False
            if ascending:
                should_swap = cmp_val > key_val
            else:
                should_swap = cmp_val < key_val
            if not should_swap:
                break
            indices[j + 1] = indices[j]
            j -= 1
        indices[j + 1] = key_idx
    return indices^


# ── Inner join ────────────────────────────────────────────────────────────────


fn table_join_inner(t1: Table, col1: Int, t2: Table, col2: Int) -> List[List[Int]]:
    """Inner join: returns [[t1_row, t2_row], ...] for matching values."""
    var result = List[List[Int]]()
    if col1 < 0 or col1 >= len(t1.columns) or col2 < 0 or col2 >= len(t2.columns):
        return result^
    for r1 in range(t1.n_rows):
        var v1 = t1.data[col1][r1]
        for r2 in range(t2.n_rows):
            var v2 = t2.data[col2][r2]
            if v1 == v2:
                var pair = List[Int]()
                pair.append(r1)
                pair.append(r2)
                result.append(pair^)
    return result^


# ── Group-by aggregate ────────────────────────────────────────────────────────


fn _find_group(groups: List[Float64], value: Float64) -> Int:
    """Find index of value in groups list, or -1."""
    for i in range(len(groups)):
        if groups[i] == value:
            return i
    return -1


fn table_group_aggregate(
    table: Table, group_col: Int, agg_col: Int, agg: Int
) -> List[List[Float64]]:
    """Group by group_col, aggregate agg_col. Returns [[group_value, agg_result], ...]."""
    var result = List[List[Float64]]()
    if group_col < 0 or group_col >= len(table.columns):
        return result^
    if agg_col < 0 or agg_col >= len(table.columns):
        return result^

    # Collect unique group values and their member rows
    var group_keys = List[Float64]()
    var group_rows = List[List[Int]]()

    for r in range(table.n_rows):
        var gv = table.data[group_col][r]
        var idx = _find_group(group_keys, gv)
        if idx < 0:
            group_keys.append(gv)
            var rows = List[Int]()
            rows.append(r)
            group_rows.append(rows^)
        else:
            group_rows[idx].append(r)

    # Aggregate each group
    for g in range(len(group_keys)):
        var n = len(group_rows[g])
        var agg_val: Float64 = 0.0

        if agg == 4:  # count
            agg_val = Float64(n)
        elif agg == 2:  # min
            agg_val = table.data[agg_col][group_rows[g][0]]
            for i in range(1, n):
                var v = table.data[agg_col][group_rows[g][i]]
                if v < agg_val:
                    agg_val = v
        elif agg == 3:  # max
            agg_val = table.data[agg_col][group_rows[g][0]]
            for i in range(1, n):
                var v = table.data[agg_col][group_rows[g][i]]
                if v > agg_val:
                    agg_val = v
        else:  # sum or mean
            var s: Float64 = 0.0
            for i in range(n):
                s += table.data[agg_col][group_rows[g][i]]
            if agg == 1:  # mean
                agg_val = s / Float64(n)
            else:  # sum
                agg_val = s

        var pair = List[Float64]()
        pair.append(group_keys[g])
        pair.append(agg_val)
        result.append(pair^)

    return result^


# ── Row count ─────────────────────────────────────────────────────────────────


fn table_row_count(table: Table) -> Int:
    """Number of rows."""
    return table.n_rows
