"""
Bench_color_check_image.mojo — direct Mojo compute benchmark for vision color checks.

Run from the repo root:
  cd mojo_env
  pixi run mojo run -I ../mojo/engine ../benchmarks/mojo_benchmarks/bench_color_check_image.mojo
"""

from std.time import perf_counter_ns

from color_check import (
    dominant_background_rgb255,
    preferred_text_color_for_image,
    preferred_text_contrast_for_image,
)

comptime WIDTH: Int = 256
comptime HEIGHT: Int = 256
comptime LEVELS: Int = 8
comptime ITERATIONS: Int = 120


def build_image() -> List[Float64]:
    var image = List[Float64]()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if (x + y) % 16 == 0:
                image.append(20.0)
                image.append(20.0)
                image.append(200.0)
            else:
                image.append(200.0)
                image.append(20.0)
                image.append(20.0)
    return image^


def sum_values(values: List[Float64]) -> Float64:
    var total: Float64 = 0.0
    for value in values:
        total += value
    return total


def main() raises:
    var image = build_image()

    var bg = dominant_background_rgb255(image, WIDTH, HEIGHT, LEVELS)
    var contrast = preferred_text_contrast_for_image(image, WIDTH, HEIGHT, LEVELS)
    var text = preferred_text_color_for_image(image, WIDTH, HEIGHT, LEVELS)

    print("MOJO_RESULT dominant_background_rgb255", bg[0], bg[1], bg[2], bg[3])
    print("MOJO_RESULT preferred_text_contrast_for_image", contrast)
    print("MOJO_RESULT preferred_text_color_for_image", text)

    var checksum_bg: Float64 = 0.0
    var t0_bg = perf_counter_ns()
    for _ in range(ITERATIONS):
        checksum_bg += sum_values(
            dominant_background_rgb255(image, WIDTH, HEIGHT, LEVELS)
        )
    var t1_bg = perf_counter_ns()
    var ns_bg = Float64(t1_bg - t0_bg) / Float64(ITERATIONS)
    print("MOJO_BENCH dominant_background_rgb255", ns_bg, checksum_bg)

    var checksum_contrast: Float64 = 0.0
    var t0_contrast = perf_counter_ns()
    for _ in range(ITERATIONS):
        checksum_contrast += preferred_text_contrast_for_image(
            image, WIDTH, HEIGHT, LEVELS
        )
    var t1_contrast = perf_counter_ns()
    var ns_contrast = Float64(t1_contrast - t0_contrast) / Float64(ITERATIONS)
    print("MOJO_BENCH preferred_text_contrast_for_image", ns_contrast, checksum_contrast)

    var checksum_text: Float64 = 0.0
    var t0_text = perf_counter_ns()
    for _ in range(ITERATIONS):
        if preferred_text_color_for_image(image, WIDTH, HEIGHT, LEVELS) == "#FFFFFF":
            checksum_text += 1.0
    var t1_text = perf_counter_ns()
    var ns_text = Float64(t1_text - t0_text) / Float64(ITERATIONS)
    print("MOJO_BENCH preferred_text_color_for_image", ns_text, checksum_text)
