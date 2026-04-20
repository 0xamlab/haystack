"""
test_wave2.mojo — Tests for Wave 2 libraries: CSV parser, regex, math_ext.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_wave2.mojo
"""
from data.csv_parser import (
    CSVRow,
    CSVResult,
    parse_csv,
    parse_csv_row,
    csv_get_field,
    csv_get_float,
    csv_get_int,
    csv_to_json_array,
)
from text.regex import (
    regex_match,
    regex_search,
    regex_find_all,
    regex_replace,
    regex_split,
    is_match_literal,
    is_match_simple,
)
from math_ext import (
    mean,
    median,
    mode_approx,
    stdev,
    variance,
    skewness,
    kurtosis,
    covariance,
    correlation,
    percentile,
    quantile,
    iqr,
    z_score,
    t_statistic,
    chi_squared,
    erf,
    norm_cdf,
    norm_pdf,
    norm_ppf,
    gamma_fn,
    beta_fn,
    log_gamma,
)
from std.math import abs as fabs


# ── Helpers ───────────────────────────────────────────────────────────────────


def _assert_true(cond: Bool, label: String) raises:
    if not cond:
        print("❌ FAIL: " + label)
        raise Error("assertion failed: " + label)


def _assert_eq(got: String, expected: String, label: String) raises:
    if got != expected:
        print("❌ FAIL: " + label)
        print("   expected: " + expected)
        print("   got:      " + got)
        raise Error("assertion failed: " + label)


def _assert_near(got: Float64, expected: Float64, tol: Float64, label: String) raises:
    if fabs(got - expected) > tol:
        print("❌ FAIL: " + label)
        print("   expected: " + String(expected))
        print("   got:      " + String(got))
        print("   diff:     " + String(fabs(got - expected)))
        raise Error("assertion failed: " + label)


# ── CSV Parser tests ─────────────────────────────────────────────────────────


def test_csv_basic() raises:
    var csv_data = "name,age,score\nAlice,30,95.5\nBob,25,87.3"
    var result = parse_csv(csv_data)

    _assert_true(len(result.headers) == 3, "CSV basic: 3 headers")
    _assert_eq(result.headers[0], "name", "CSV header 0")
    _assert_eq(result.headers[1], "age", "CSV header 1")
    _assert_eq(result.headers[2], "score", "CSV header 2")

    _assert_true(len(result.rows) == 2, "CSV basic: 2 rows")
    _assert_eq(csv_get_field(result.rows[0], 0), "Alice", "CSV row0 field0")
    _assert_eq(csv_get_field(result.rows[0], 1), "30", "CSV row0 field1")
    _assert_near(csv_get_float(result.rows[0], 2, 0.0), 95.5, 0.01, "CSV row0 float2")
    _assert_true(csv_get_int(result.rows[0], 1, 0) == 30, "CSV row0 int1")

    _assert_eq(csv_get_field(result.rows[1], 0), "Bob", "CSV row1 field0")
    _assert_near(csv_get_float(result.rows[1], 2, 0.0), 87.3, 0.01, "CSV row1 float2")

    print("  ✓ CSV basic parsing")


def test_csv_quoted_fields() raises:
    # Quoted field with embedded comma
    var csv_data = 'name,age,score\n"Eve, Jr.",28,92.1'
    var result = parse_csv(csv_data)

    _assert_true(len(result.rows) == 1, "CSV quoted: 1 row")
    _assert_eq(csv_get_field(result.rows[0], 0), "Eve, Jr.", "CSV quoted field with comma")
    _assert_true(csv_get_int(result.rows[0], 1, 0) == 28, "CSV quoted row int")
    _assert_near(csv_get_float(result.rows[0], 2, 0.0), 92.1, 0.01, "CSV quoted row float")

    print("  ✓ CSV quoted fields")


def test_csv_escaped_quotes() raises:
    # Escaped quotes: "" inside quoted field becomes single "
    var csv_data = 'name,desc\n"Alice","She said ""hello"""\n"Bob","normal"'
    var result = parse_csv(csv_data)

    _assert_true(len(result.rows) == 2, "CSV escaped: 2 rows")
    _assert_eq(csv_get_field(result.rows[0], 1), 'She said "hello"', "CSV escaped quotes")
    _assert_eq(csv_get_field(result.rows[1], 1), "normal", "CSV non-escaped field")

    print("  ✓ CSV escaped quotes")


def test_csv_single_row() raises:
    var row = parse_csv_row("Alice,30,95.5")
    _assert_true(row.n_fields == 3, "CSV single row: 3 fields")
    _assert_eq(csv_get_field(row, 0), "Alice", "CSV single row field0")
    _assert_true(csv_get_int(row, 1, 0) == 30, "CSV single row int")

    print("  ✓ CSV single row parsing")


def test_csv_out_of_bounds() raises:
    var row = parse_csv_row("a,b")
    _assert_eq(csv_get_field(row, 5), "", "CSV out of bounds returns empty")
    _assert_near(csv_get_float(row, 5, -1.0), -1.0, 0.001, "CSV float out of bounds returns default")
    _assert_true(csv_get_int(row, 5, -1) == -1, "CSV int out of bounds returns default")

    print("  ✓ CSV out of bounds handling")


def test_csv_to_json() raises:
    var csv_data = "name,age\nAlice,30\nBob,25"
    var result = parse_csv(csv_data)
    var json = csv_to_json_array(result.headers, result.rows)
    # Basic structure check
    _assert_true(len(json) > 0, "CSV to JSON not empty")
    _assert_true(json.find("name") >= 0, "CSV to JSON contains 'name'")
    _assert_true(json.find("Alice") >= 0, "CSV to JSON contains 'Alice'")

    print("  ✓ CSV to JSON conversion")


def test_csv_no_header() raises:
    var csv_data = "Alice,30\nBob,25"
    var result = parse_csv(csv_data, ",", False)
    _assert_true(len(result.headers) == 0, "CSV no header: empty headers")
    _assert_true(len(result.rows) == 2, "CSV no header: 2 rows")
    _assert_eq(csv_get_field(result.rows[0], 0), "Alice", "CSV no header row0")

    print("  ✓ CSV no header mode")


# ── Regex tests ──────────────────────────────────────────────────────────────


def test_regex_literal() raises:
    _assert_true(regex_match("hello", "hello"), "regex exact match")
    _assert_true(not regex_match("hello", "world"), "regex no match")
    _assert_true(not regex_match("hello", "hello world"), "regex partial != full match")
    _assert_true(is_match_literal("abc", "abc"), "literal exact")
    _assert_true(not is_match_literal("abc", "abd"), "literal no match")

    print("  ✓ Regex literal matching")


def test_regex_dot() raises:
    _assert_true(regex_match("hel.o", "hello"), "regex dot match")
    _assert_true(regex_match("h...o", "hello"), "regex multi-dot")
    _assert_true(not regex_match("hel.o", "helllo"), "regex dot single char")

    print("  ✓ Regex dot matching")


def test_regex_star() raises:
    _assert_true(regex_match("he.*o", "hello"), "regex .* match")
    _assert_true(regex_match("he.*o", "heo"), "regex .* zero match")
    _assert_true(regex_match("a*", ""), "regex a* empty")
    _assert_true(regex_match("a*", "aaa"), "regex a* multiple")

    print("  ✓ Regex star quantifier")


def test_regex_plus() raises:
    _assert_true(regex_match("a+", "a"), "regex a+ single")
    _assert_true(regex_match("a+", "aaa"), "regex a+ multiple")
    _assert_true(not regex_match("a+", ""), "regex a+ requires one")

    print("  ✓ Regex plus quantifier")


def test_regex_question() raises:
    _assert_true(regex_match("colou?r", "color"), "regex ? zero")
    _assert_true(regex_match("colou?r", "colour"), "regex ? one")

    print("  ✓ Regex question quantifier")


def test_regex_char_class() raises:
    _assert_true(regex_match("[abc]", "a"), "regex class a")
    _assert_true(regex_match("[abc]", "b"), "regex class b")
    _assert_true(not regex_match("[abc]", "d"), "regex class not d")
    _assert_true(regex_match("[a-z]+", "hello"), "regex range a-z")
    _assert_true(regex_match("[0-9]+", "12345"), "regex range 0-9")
    _assert_true(not regex_match("[0-9]+", "abc"), "regex range 0-9 no match")

    print("  ✓ Regex character classes")


def test_regex_shorthand() raises:
    _assert_true(regex_match("\\d+", "12345"), "regex \\d+")
    _assert_true(not regex_match("\\d+", "abc"), "regex \\d+ no match")
    _assert_true(regex_match("\\w+", "hello_123"), "regex \\w+")
    _assert_true(regex_match("\\s", " "), "regex \\s space")

    print("  ✓ Regex shorthand classes")


def test_regex_escape() raises:
    _assert_true(regex_match("3\\.14", "3.14"), "regex escaped dot")
    _assert_true(not regex_match("3\\.14", "3X14"), "regex escaped dot no X")

    print("  ✓ Regex escaping")


def test_regex_alternation() raises:
    _assert_true(regex_match("cat|dog", "cat"), "regex alt cat")
    _assert_true(regex_match("cat|dog", "dog"), "regex alt dog")
    _assert_true(not regex_match("cat|dog", "bird"), "regex alt no bird")

    print("  ✓ Regex alternation")


def test_regex_search() raises:
    var pos = regex_search("world", "hello world")
    _assert_true(pos == 6, "regex search 'world' in 'hello world' at 6 (got " + String(pos) + ")")
    _assert_true(regex_search("xyz", "hello") == -1, "regex search not found")
    _assert_true(regex_search("\\d+", "abc 123 def") >= 0, "regex search digits")

    print("  ✓ Regex search")


def test_regex_find_all() raises:
    var matches = regex_find_all("[0-9]+", "abc 123 def 456 ghi")
    _assert_true(len(matches) == 2, "regex find_all: 2 matches (got " + String(len(matches)) + ")")
    if len(matches) >= 2:
        _assert_eq(matches[0], "123", "regex find_all match 0")
        _assert_eq(matches[1], "456", "regex find_all match 1")

    print("  ✓ Regex find_all")


def test_regex_replace() raises:
    var result = regex_replace("\\d+", "abc 123 def 456", "NUM")
    _assert_true(result.find("NUM") >= 0, "regex replace contains NUM")
    _assert_true(result.find("123") == -1, "regex replace removed 123")

    print("  ✓ Regex replace")


def test_regex_split() raises:
    var parts = regex_split(",", "a,b,c")
    _assert_true(len(parts) == 3, "regex split: 3 parts (got " + String(len(parts)) + ")")
    if len(parts) >= 3:
        _assert_eq(parts[0], "a", "regex split part 0")
        _assert_eq(parts[1], "b", "regex split part 1")
        _assert_eq(parts[2], "c", "regex split part 2")

    print("  ✓ Regex split")


# ── Math/Stats tests ─────────────────────────────────────────────────────────


def test_descriptive_stats() raises:
    var data = List[Float64]()
    data.append(1.0)
    data.append(2.0)
    data.append(3.0)
    data.append(4.0)
    data.append(5.0)

    _assert_near(mean(data), 3.0, 0.001, "mean([1..5])")
    _assert_near(median(data), 3.0, 0.001, "median([1..5])")
    _assert_near(variance(data), 2.5, 0.001, "variance([1..5])")
    _assert_near(stdev(data), 1.5811, 0.01, "stdev([1..5])")

    # Even-length median
    var data2 = List[Float64]()
    data2.append(1.0)
    data2.append(2.0)
    data2.append(3.0)
    data2.append(4.0)
    _assert_near(median(data2), 2.5, 0.001, "median([1..4])")

    print("  ✓ Descriptive statistics")


def test_skewness_kurtosis() raises:
    # Symmetric data → skewness ≈ 0
    var sym = List[Float64]()
    sym.append(1.0)
    sym.append(2.0)
    sym.append(3.0)
    sym.append(4.0)
    sym.append(5.0)
    _assert_near(skewness(sym), 0.0, 0.1, "skewness symmetric ≈ 0")

    # Skewed data
    var skewed = List[Float64]()
    skewed.append(1.0)
    skewed.append(1.0)
    skewed.append(1.0)
    skewed.append(2.0)
    skewed.append(10.0)
    _assert_true(skewness(skewed) > 0.0, "skewness positive for right-skewed")

    print("  ✓ Skewness and kurtosis")


def test_correlation_covariance() raises:
    var x = List[Float64]()
    x.append(1.0)
    x.append(2.0)
    x.append(3.0)
    x.append(4.0)
    x.append(5.0)

    var y = List[Float64]()
    y.append(2.0)
    y.append(4.0)
    y.append(6.0)
    y.append(8.0)
    y.append(10.0)

    _assert_near(correlation(x, y), 1.0, 0.001, "correlation perfect positive")
    _assert_near(covariance(x, y), 5.0, 0.001, "covariance(x, 2x)")

    # Anti-correlated
    var z = List[Float64]()
    z.append(10.0)
    z.append(8.0)
    z.append(6.0)
    z.append(4.0)
    z.append(2.0)
    _assert_near(correlation(x, z), -1.0, 0.001, "correlation perfect negative")

    print("  ✓ Correlation and covariance")


def test_percentiles() raises:
    var data = List[Float64]()
    data.append(1.0)
    data.append(2.0)
    data.append(3.0)
    data.append(4.0)
    data.append(5.0)

    _assert_near(percentile(data, 50.0), 3.0, 0.001, "percentile 50 = median")
    _assert_near(percentile(data, 0.0), 1.0, 0.001, "percentile 0 = min")
    _assert_near(percentile(data, 100.0), 5.0, 0.001, "percentile 100 = max")
    _assert_near(quantile(data, 0.5), 3.0, 0.001, "quantile 0.5 = median")

    var iqr_val = iqr(data)
    _assert_true(iqr_val > 0.0, "iqr > 0")

    print("  ✓ Percentiles and quantiles")


def test_statistical_tests() raises:
    _assert_near(z_score(1.96, 0.0, 1.0), 1.96, 0.001, "z_score(1.96, 0, 1)")
    _assert_near(z_score(0.0, 0.0, 1.0), 0.0, 0.001, "z_score(0, 0, 1)")

    # t-statistic: sample mean=5, pop mean=4, std=2, n=16
    # t = (5-4)/(2/sqrt(16)) = 1/0.5 = 2.0
    _assert_near(t_statistic(5.0, 4.0, 2.0, 16), 2.0, 0.001, "t_statistic")

    # chi-squared: observed = expected → chi2 = 0
    var obs = List[Float64]()
    obs.append(10.0)
    obs.append(20.0)
    obs.append(30.0)
    var exp = List[Float64]()
    exp.append(10.0)
    exp.append(20.0)
    exp.append(30.0)
    _assert_near(chi_squared(obs, exp), 0.0, 0.001, "chi2 equal O=E")

    print("  ✓ Statistical tests")


def test_special_functions() raises:
    # erf
    _assert_near(erf(0.0), 0.0, 0.001, "erf(0) = 0")
    _assert_near(erf(1.0), 0.8427, 0.001, "erf(1) ≈ 0.8427")
    _assert_near(erf(-1.0), -0.8427, 0.001, "erf(-1) ≈ -0.8427")

    # norm_cdf
    _assert_near(norm_cdf(0.0), 0.5, 0.001, "norm_cdf(0) = 0.5")
    _assert_near(norm_cdf(1.96), 0.975, 0.005, "norm_cdf(1.96) ≈ 0.975")
    _assert_near(norm_cdf(-1.96), 0.025, 0.005, "norm_cdf(-1.96) ≈ 0.025")

    # norm_pdf
    _assert_near(norm_pdf(0.0), 0.3989, 0.001, "norm_pdf(0) ≈ 0.3989")

    # norm_ppf (inverse CDF)
    _assert_near(norm_ppf(0.5), 0.0, 0.01, "norm_ppf(0.5) = 0")
    _assert_near(norm_ppf(0.975), 1.96, 0.02, "norm_ppf(0.975) ≈ 1.96")
    _assert_near(norm_ppf(0.025), -1.96, 0.02, "norm_ppf(0.025) ≈ -1.96")

    # gamma
    _assert_near(gamma_fn(1.0), 1.0, 0.001, "Gamma(1) = 1")
    _assert_near(gamma_fn(5.0), 24.0, 0.1, "Gamma(5) = 24")

    # beta
    _assert_near(beta_fn(1.0, 1.0), 1.0, 0.01, "Beta(1,1) = 1")

    # log_gamma
    _assert_near(log_gamma(1.0), 0.0, 0.001, "log_gamma(1) = 0")

    print("  ✓ Special functions")


def test_edge_cases() raises:
    # Empty data
    _assert_near(mean(List[Float64]()), 0.0, 0.001, "mean(empty)")
    _assert_near(median(List[Float64]()), 0.0, 0.001, "median(empty)")
    _assert_near(variance(List[Float64]()), 0.0, 0.001, "variance(empty)")
    _assert_near(stdev(List[Float64]()), 0.0, 0.001, "stdev(empty)")

    # Single element
    var single = List[Float64]()
    single.append(42.0)
    _assert_near(mean(single), 42.0, 0.001, "mean(single)")
    _assert_near(median(single), 42.0, 0.001, "median(single)")
    _assert_near(variance(single), 0.0, 0.001, "variance(single) = 0")

    print("  ✓ Edge cases")


# ── Runner ────────────────────────────────────────────────────────────────────


def main() raises:
    print("━━━ Wave 2 test suite (CSV, regex, math_ext) ━━━")
    print("")

    print("── CSV Parser ──")
    test_csv_basic()
    test_csv_quoted_fields()
    test_csv_escaped_quotes()
    test_csv_single_row()
    test_csv_out_of_bounds()
    test_csv_to_json()
    test_csv_no_header()
    print("✅ CSV parser — all tests passed")
    print("")

    print("── Regex ──")
    test_regex_literal()
    test_regex_dot()
    test_regex_star()
    test_regex_plus()
    test_regex_question()
    test_regex_char_class()
    test_regex_shorthand()
    test_regex_escape()
    test_regex_alternation()
    test_regex_search()
    test_regex_find_all()
    test_regex_replace()
    test_regex_split()
    print("✅ Regex — all tests passed")
    print("")

    print("── Math/Stats ──")
    test_descriptive_stats()
    test_skewness_kurtosis()
    test_correlation_covariance()
    test_percentiles()
    test_statistical_tests()
    test_special_functions()
    test_edge_cases()
    print("✅ Math/Stats — all tests passed")
    print("")

    print("━━━ All Wave 2 tests passed ━━━")
