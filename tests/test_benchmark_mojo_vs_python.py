from __future__ import annotations

from tests import benchmark_mojo_vs_python as bench


def test_python_result_summary_rounds_bilinear_float_matrix() -> None:
    value = [[0.333333333333, 0.666666666667], [1.234567890123, 9.876543210987]]

    assert bench._python_result_summary(
        value,
        lib="image_resize",
        function="bilinear_downscale",
    ) == "list:2:1246361088"


def test_mojo_summary_call_expression_rounds_bilinear_float_matrix() -> None:
    fn = bench.FnInfo(
        name="bilinear_downscale",
        params=[],
        ret="List[List[Float64]]",
        body_lines=[],
        lib="image_resize",
    )

    assert bench._mojo_summary_call_expression("image_resize", fn, "_result") == (
        "_summary_list_list_float64_rounded6(_result)"
    )
