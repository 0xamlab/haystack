"""
bench_video_color_direct.mojo — direct Mojo benchmark for video color kernels.

Run from the repo root:
  cd mojo_env
  pixi run mojo run -I ../mojo/engine ../benchmarks/mojo_benchmarks/bench_video_color_direct.mojo
"""

from std.time import perf_counter_ns

from video_color import (
    clip_mean_rgb255,
    dominant_clip_color_rgb255,
    clip_mean_saturation_rgb255,
    warm_frame_ratio_rgb255,
    color_drift_score_rgb255,
    preferred_text_contrast_for_video,
    preferred_text_color_for_video,
)

comptime WIDTH: Int = 96
comptime HEIGHT: Int = 64
comptime FRAMES: Int = 12
comptime CHANNELS: Int = 3
comptime LEVELS: Int = 8
comptime SAMPLE_FRAMES: Int = 6
comptime WARM_MIN_SATURATION: Float64 = 0.25
comptime ITERATIONS: Int = 24


fn _scene(frame_index: Int) -> Int:
    if frame_index < 3:
        return 0
    if frame_index < 8:
        return 1
    return 2


def build_clip() -> List[Float64]:
    var clip = List[Float64]()
    for frame_index in range(FRAMES):
        var scene = _scene(frame_index)
        var x_offset = (frame_index * 3) % WIDTH
        var y_offset = (frame_index * 2) % HEIGHT
        for y in range(HEIGHT):
            for x in range(WIDTH):
                var px = (x + x_offset) % WIDTH
                var py = (y + y_offset) % HEIGHT
                if scene == 0:
                    clip.append(Float64((px * 2 + py + frame_index * 7) % 256))
                    clip.append(Float64((px + 40 + frame_index * 5) % 256))
                    clip.append(Float64((180 - py + frame_index * 3 + 256) % 256))
                elif scene == 1:
                    if px < WIDTH // 2:
                        clip.append(220.0)
                    else:
                        clip.append(25.0)
                    clip.append(Float64((py * 3 + frame_index * 13) % 256))
                    clip.append(Float64((255 - px + frame_index * 11 + 256) % 256))
                else:
                    var stripe = 255.0 if ((px // 8 + py // 8 + frame_index) % 2) == 0 else 20.0
                    clip.append(stripe)
                    clip.append(Float64((60 + py * 2 + frame_index * 9) % 256))
                    clip.append(Float64((30 + px * 3 + frame_index * 4) % 256))
    return clip^


fn _sum_list_float(values: List[Float64]) -> Float64:
    var total: Float64 = 0.0
    for index in range(len(values)):
        total += values[index]
    return total


def main() raises:
    var clip = build_clip()

    var clip_mean = clip_mean_rgb255(clip, WIDTH, HEIGHT, CHANNELS)
    var dominant = dominant_clip_color_rgb255(
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        LEVELS,
        SAMPLE_FRAMES,
    )
    var saturation = clip_mean_saturation_rgb255(clip, WIDTH, HEIGHT, CHANNELS)
    var warm_ratio = warm_frame_ratio_rgb255(
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        WARM_MIN_SATURATION,
    )
    var drift = color_drift_score_rgb255(clip, WIDTH, HEIGHT, CHANNELS)
    var text_contrast = preferred_text_contrast_for_video(
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        LEVELS,
        SAMPLE_FRAMES,
    )
    var text_color = preferred_text_color_for_video(
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        LEVELS,
        SAMPLE_FRAMES,
    )

    print("MOJO_RESULT clip_mean_rgb255", clip_mean[0], clip_mean[1], clip_mean[2])
    print(
        "MOJO_RESULT dominant_clip_color_rgb255",
        dominant[0],
        dominant[1],
        dominant[2],
        dominant[3],
    )
    print("MOJO_RESULT clip_mean_saturation_rgb255", saturation)
    print("MOJO_RESULT warm_frame_ratio_rgb255", warm_ratio)
    print("MOJO_RESULT color_drift_score_rgb255", drift)
    print("MOJO_RESULT preferred_text_contrast_for_video", text_contrast)
    print("MOJO_RESULT preferred_text_color_for_video", text_color)

    var checksum_clip_mean: Float64 = 0.0
    var t0_clip_mean = perf_counter_ns()
    for _ in range(ITERATIONS):
        checksum_clip_mean += _sum_list_float(clip_mean_rgb255(clip, WIDTH, HEIGHT, CHANNELS))
    var t1_clip_mean = perf_counter_ns()
    print(
        "MOJO_BENCH clip_mean_rgb255",
        Float64(t1_clip_mean - t0_clip_mean) / Float64(ITERATIONS),
        checksum_clip_mean,
    )

    var checksum_dominant: Float64 = 0.0
    var t0_dominant = perf_counter_ns()
    for _ in range(ITERATIONS):
        checksum_dominant += _sum_list_float(
            dominant_clip_color_rgb255(
                clip,
                WIDTH,
                HEIGHT,
                CHANNELS,
                LEVELS,
                SAMPLE_FRAMES,
            )
        )
    var t1_dominant = perf_counter_ns()
    print(
        "MOJO_BENCH dominant_clip_color_rgb255",
        Float64(t1_dominant - t0_dominant) / Float64(ITERATIONS),
        checksum_dominant,
    )

    var checksum_saturation: Float64 = 0.0
    var t0_saturation = perf_counter_ns()
    for _ in range(ITERATIONS):
        checksum_saturation += clip_mean_saturation_rgb255(clip, WIDTH, HEIGHT, CHANNELS)
    var t1_saturation = perf_counter_ns()
    print(
        "MOJO_BENCH clip_mean_saturation_rgb255",
        Float64(t1_saturation - t0_saturation) / Float64(ITERATIONS),
        checksum_saturation,
    )

    var checksum_warm_ratio: Float64 = 0.0
    var t0_warm_ratio = perf_counter_ns()
    for _ in range(ITERATIONS):
        checksum_warm_ratio += warm_frame_ratio_rgb255(
            clip,
            WIDTH,
            HEIGHT,
            CHANNELS,
            WARM_MIN_SATURATION,
        )
    var t1_warm_ratio = perf_counter_ns()
    print(
        "MOJO_BENCH warm_frame_ratio_rgb255",
        Float64(t1_warm_ratio - t0_warm_ratio) / Float64(ITERATIONS),
        checksum_warm_ratio,
    )

    var checksum_drift: Float64 = 0.0
    var t0_drift = perf_counter_ns()
    for _ in range(ITERATIONS):
        checksum_drift += color_drift_score_rgb255(clip, WIDTH, HEIGHT, CHANNELS)
    var t1_drift = perf_counter_ns()
    print(
        "MOJO_BENCH color_drift_score_rgb255",
        Float64(t1_drift - t0_drift) / Float64(ITERATIONS),
        checksum_drift,
    )

    var checksum_text_contrast: Float64 = 0.0
    var t0_text_contrast = perf_counter_ns()
    for _ in range(ITERATIONS):
        checksum_text_contrast += preferred_text_contrast_for_video(
            clip,
            WIDTH,
            HEIGHT,
            CHANNELS,
            LEVELS,
            SAMPLE_FRAMES,
        )
    var t1_text_contrast = perf_counter_ns()
    print(
        "MOJO_BENCH preferred_text_contrast_for_video",
        Float64(t1_text_contrast - t0_text_contrast) / Float64(ITERATIONS),
        checksum_text_contrast,
    )

    var checksum_text_color: Float64 = 0.0
    var t0_text_color = perf_counter_ns()
    for _ in range(ITERATIONS):
        var color = preferred_text_color_for_video(
            clip,
            WIDTH,
            HEIGHT,
            CHANNELS,
            LEVELS,
            SAMPLE_FRAMES,
        )
        checksum_text_color += 1.0 if color == "#FFFFFF" else 0.0
    var t1_text_color = perf_counter_ns()
    print(
        "MOJO_BENCH preferred_text_color_for_video",
        Float64(t1_text_color - t0_text_color) / Float64(ITERATIONS),
        checksum_text_color,
    )
