"""
test_wave4.mojo — Tests for Wave 4 library: DataFrame.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_wave4.mojo
"""
from data.dataframe import DataFrame, Column, df_from_columns
from std.math import abs as fabs


def main() raises:
    print("━━━ Wave 4 test suite (DataFrame) ━━━")
    print("")

    # ── Construction ──
    var df = DataFrame()
    var ages = List[Float64]()
    ages.append(30.0)
    ages.append(25.0)
    ages.append(28.0)
    ages.append(35.0)
    ages.append(25.0)
    var scores = List[Float64]()
    scores.append(95.0)
    scores.append(87.0)
    scores.append(92.0)
    scores.append(78.0)
    scores.append(88.0)
    var dept = List[Float64]()
    dept.append(1.0)
    dept.append(2.0)
    dept.append(1.0)
    dept.append(2.0)
    dept.append(1.0)
    df.add_column("age", ages)
    df.add_column("score", scores)
    df.add_column("dept", dept)
    if df.n_rows != 5:
        raise Error("n_rows != 5, got " + String(df.n_rows))
    if df.n_cols != 3:
        raise Error("n_cols != 3, got " + String(df.n_cols))
    print("✅ DataFrame construction")

    # ── Access ──
    if df.get_value(0, "age") != 30.0:
        raise Error("get_value(0, age) != 30.0")
    if df.get_value(1, "score") != 87.0:
        raise Error("get_value(1, score) != 87.0")
    print("✅ DataFrame access")

    # ── Aggregate ──
    if fabs(df.mean_col("age") - 28.6) > 0.1:
        raise Error("mean_col(age) != 28.6, got " + String(df.mean_col("age")))
    if fabs(df.sum("score") - 440.0) > 0.1:
        raise Error("sum(score) != 440.0, got " + String(df.sum("score")))
    if df.min_col("age") != 25.0:
        raise Error("min_col(age) != 25.0")
    if df.max_col("age") != 35.0:
        raise Error("max_col(age) != 35.0")
    if df.count() != 5:
        raise Error("count() != 5")
    # std_col: ages = [30,25,28,35,25], mean=28.6
    # var = ((1.4^2)+(3.6^2)+(0.6^2)+(6.4^2)+(3.6^2))/4 = (1.96+12.96+0.36+40.96+12.96)/4 = 69.2/4 = 17.3
    # std = sqrt(17.3) ≈ 4.159
    var age_std = df.std_col("age")
    if fabs(age_std - 4.159) > 0.1:
        raise Error("std_col(age) ≈ 4.159, got " + String(age_std))
    print("✅ DataFrame aggregate")

    # ── Filter ──
    var young = df.filter_lt("age", 30.0)
    if young.n_rows != 3:
        raise Error("filter_lt n_rows != 3, got " + String(young.n_rows))

    var exact = df.filter_eq("age", 25.0)
    if exact.n_rows != 2:
        raise Error("filter_eq n_rows != 2, got " + String(exact.n_rows))

    var older = df.filter_gt("age", 28.0)
    if older.n_rows != 2:
        raise Error("filter_gt n_rows != 2, got " + String(older.n_rows))

    var between = df.filter_between("age", 25.0, 30.0)
    if between.n_rows != 4:
        raise Error("filter_between n_rows != 4, got " + String(between.n_rows))
    print("✅ DataFrame filter")

    # ── Sort ──
    var sorted_df = df.sort_by("score", ascending=False)
    if sorted_df.get_value(0, "score") != 95.0:
        raise Error("sort desc: first != 95.0, got " + String(sorted_df.get_value(0, "score")))
    if sorted_df.get_value(4, "score") != 78.0:
        raise Error("sort desc: last != 78.0")

    var sorted_asc = df.sort_by("age", ascending=True)
    if sorted_asc.get_value(0, "age") != 25.0:
        raise Error("sort asc: first != 25.0")
    if sorted_asc.get_value(4, "age") != 35.0:
        raise Error("sort asc: last != 35.0")
    print("✅ DataFrame sort")

    # ── GroupBy ──
    var grouped = df.groupby_agg("dept", "score", "mean")
    if grouped.n_rows != 2:
        raise Error("groupby n_rows != 2, got " + String(grouped.n_rows))
    # dept 1 (rows 0,2,4): mean score = (95+92+88)/3 = 91.67
    # dept 2 (rows 1,3): mean score = (87+78)/2 = 82.5
    # Find dept 1 and dept 2 results
    var dept1_mean: Float64 = 0.0
    var dept2_mean: Float64 = 0.0
    for i in range(grouped.n_rows):
        if fabs(grouped.get_value(i, "dept") - 1.0) < 0.01:
            dept1_mean = grouped.get_value(i, "score")
        elif fabs(grouped.get_value(i, "dept") - 2.0) < 0.01:
            dept2_mean = grouped.get_value(i, "score")
    if fabs(dept1_mean - 91.667) > 0.1:
        raise Error("groupby dept1 mean != 91.67, got " + String(dept1_mean))
    if fabs(dept2_mean - 82.5) > 0.1:
        raise Error("groupby dept2 mean != 82.5, got " + String(dept2_mean))

    # GroupBy sum
    var grouped_sum = df.groupby_agg("dept", "score", "sum")
    var dept1_sum: Float64 = 0.0
    for i in range(grouped_sum.n_rows):
        if fabs(grouped_sum.get_value(i, "dept") - 1.0) < 0.01:
            dept1_sum = grouped_sum.get_value(i, "score")
    if fabs(dept1_sum - 275.0) > 0.1:
        raise Error("groupby sum dept1 != 275.0, got " + String(dept1_sum))

    # GroupBy count
    var grouped_count = df.groupby_agg("dept", "score", "count")
    var dept1_count: Float64 = 0.0
    for i in range(grouped_count.n_rows):
        if fabs(grouped_count.get_value(i, "dept") - 1.0) < 0.01:
            dept1_count = grouped_count.get_value(i, "score")
    if fabs(dept1_count - 3.0) > 0.1:
        raise Error("groupby count dept1 != 3, got " + String(dept1_count))
    print("✅ DataFrame groupby")

    # ── Transform ──
    df.add_computed_column("age_plus_score", "age", "+", "score")
    if fabs(df.get_value(0, "age_plus_score") - 125.0) > 0.1:
        raise Error("computed col (0) != 125.0, got " + String(df.get_value(0, "age_plus_score")))
    if fabs(df.get_value(1, "age_plus_score") - 112.0) > 0.1:
        raise Error("computed col (1) != 112.0")
    # Now df has 4 columns
    if df.n_cols != 4:
        raise Error("n_cols after computed != 4")

    # apply_scalar
    var scaled = df.apply_scalar("score", "*", 2.0)
    if fabs(scaled.get_value(0, "score") - 190.0) > 0.1:
        raise Error("apply_scalar(0,score)*2 != 190.0")
    # Original column should be unchanged
    if fabs(scaled.get_value(0, "age") - 30.0) > 0.1:
        raise Error("apply_scalar: age should be unchanged")
    print("✅ DataFrame transform")

    # ── Select/Drop ──
    var names = List[String]()
    names.append("age")
    names.append("score")
    var subset = df.select(names)
    if subset.n_cols != 2:
        raise Error("select n_cols != 2, got " + String(subset.n_cols))
    if subset.col_index("age") < 0:
        raise Error("select: missing 'age'")
    if subset.col_index("score") < 0:
        raise Error("select: missing 'score'")
    if subset.col_index("dept") >= 0:
        raise Error("select: should not have 'dept'")

    var drop_names = List[String]()
    drop_names.append("dept")
    var dropped = df.drop(drop_names)
    if dropped.col_index("dept") >= 0:
        raise Error("drop: should not have 'dept'")
    if dropped.n_cols != 3:
        raise Error("drop n_cols != 3, got " + String(dropped.n_cols))
    print("✅ DataFrame select/drop")

    # ── Slice rows ──
    var sliced = df.slice_rows(1, 3)
    if sliced.n_rows != 2:
        raise Error("slice_rows n_rows != 2, got " + String(sliced.n_rows))
    if fabs(sliced.get_value(0, "age") - 25.0) > 0.1:
        raise Error("slice_rows(0,age) != 25.0")
    if fabs(sliced.get_value(1, "age") - 28.0) > 0.1:
        raise Error("slice_rows(1,age) != 28.0")
    print("✅ DataFrame slice_rows")

    # ── Merge ──
    var df2 = DataFrame()
    var dept2 = List[Float64]()
    dept2.append(1.0)
    dept2.append(2.0)
    var budget = List[Float64]()
    budget.append(100000.0)
    budget.append(80000.0)
    df2.add_column("dept", dept2)
    df2.add_column("budget", budget)
    var merged = df.merge_inner(df2, "dept")
    if merged.n_rows != 5:
        raise Error("merge n_rows != 5, got " + String(merged.n_rows))
    if merged.col_index("budget") < 0:
        raise Error("merge: missing 'budget' column")
    # Row 0: dept=1.0, budget should be 100000.0
    if fabs(merged.get_value(0, "budget") - 100000.0) > 0.1:
        raise Error("merge(0,budget) != 100000.0, got " + String(merged.get_value(0, "budget")))
    # Row 1: dept=2.0, budget should be 80000.0
    if fabs(merged.get_value(1, "budget") - 80000.0) > 0.1:
        raise Error("merge(1,budget) != 80000.0, got " + String(merged.get_value(1, "budget")))
    print("✅ DataFrame merge")

    # ── I/O ──
    var json_str = df.to_json()
    if len(json_str) <= 10:
        raise Error("to_json too short: " + String(len(json_str)))
    var csv_str = df.to_csv()
    if len(csv_str) <= 10:
        raise Error("to_csv too short: " + String(len(csv_str)))
    print("✅ DataFrame I/O")

    # ── Describe ──
    var desc = df.describe()
    if len(desc) <= 10:
        raise Error("describe too short: " + String(len(desc)))
    print("✅ DataFrame describe")

    # ── Head ──
    var head_str = df.head(3)
    if len(head_str) <= 5:
        raise Error("head too short")
    print("✅ DataFrame head")

    # ── Shape ──
    var s = df.shape()
    if s[0] != 5:
        raise Error("shape rows != 5")
    if s[1] != 4:
        raise Error("shape cols != 4")
    print("✅ DataFrame shape")

    # ── col_index ──
    if df.col_index("age") != 0:
        raise Error("col_index(age) != 0")
    if df.col_index("nonexistent") != -1:
        raise Error("col_index(nonexistent) != -1")
    print("✅ DataFrame col_index")

    # ── df_from_columns static factory ──
    var fnames = List[String]()
    fnames.append("x")
    fnames.append("y")
    var fcols = List[List[Float64]]()
    var xdata = List[Float64]()
    xdata.append(1.0)
    xdata.append(2.0)
    xdata.append(3.0)
    var ydata = List[Float64]()
    ydata.append(4.0)
    ydata.append(5.0)
    ydata.append(6.0)
    fcols.append(xdata^)
    fcols.append(ydata^)
    var df3 = df_from_columns(fnames, fcols)
    if df3.n_rows != 3:
        raise Error("from_columns n_rows != 3")
    if df3.n_cols != 2:
        raise Error("from_columns n_cols != 2")
    if fabs(df3.get_value(2, "x") - 3.0) > 0.01:
        raise Error("from_columns get_value failed")
    print("✅ DataFrame from_columns factory")

    print("")
    print("━━━ All Wave 4 tests passed ━━━")
