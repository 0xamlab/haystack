"""
bench_video_accessibility_direct.mojo — direct Mojo benchmark for video accessibility kernels.

Run from the repo root:
  cd mojo_env
  pixi run mojo run -I ../mojo/engine ../benchmarks/mojo_benchmarks/bench_video_accessibility_direct.mojo
"""

from std.time import perf_counter_ns

from video_accessibility import (
    frame_min_preferred_text_contrast_for_video,
    frame_preferred_text_color_for_video,
    sampled_video_min_text_contrast,
    sampled_video_wcag_safe_ratio,
    needs_text_backplate_for_video,
    subtitle_band_min_preferred_text_contrast_for_video,
    subtitle_band_preferred_text_color_for_video,
    sampled_subtitle_band_wcag_safe_ratio,
    subtitle_band_needs_backplate_for_video,
)

comptime WIDTH: Int = 96
comptime HEIGHT: Int = 64
comptime FRAMES: Int = 12
comptime CHANNELS: Int = 3
comptime SAMPLE_FRAMES: Int = 6
comptime BAND_ROWS: Int = 12
comptime FONT_SIZE_PT: Float64 = 16.0
comptime IS_BOLD: Bool = False
comptime ITERATIONS: Int = 24


def _scene(frame_index: Int) -> Int:
    if frame_index < 4:
        return 0
    if frame_index < 8:
        return 1
    return 2


def build_clip() -> List[Float64]:
    var clip = List[Float64]()
    for frame_index in range(FRAMES):
        var scene = _scene(frame_index)
        var x_offset = (frame_index * 5) % WIDTH
        var y_offset = (frame_index * 3) % HEIGHT
        for y in range(HEIGHT):
            for x in range(WIDTH):
                var px = (x + x_offset) % WIDTH
                var py = (y + y_offset) % HEIGHT
                if scene == 0:
                    var base = 220.0 if ((px // 6 + py // 6 + frame_index) % 2) == 0 else 20.0
                    clip.append(base)
                    clip.append(base)
                    clip.append(base)
                elif scene == 1:
                    var base = 25.0 if px < WIDTH // 2 else 230.0
                    var accent = 240.0 if (py + frame_index) % 12 < 6 else 15.0
                    clip.append(base)
                    clip.append(accent)
                    clip.append(Float64((40 + px * 2 + frame_index * 7) % 256))
                else:
                    if py >= HEIGHT - BAND_ROWS:
                        var band = 235.0 if ((px // 8 + frame_index) % 2) == 0 else 20.0
                        clip.append(band)
                        clip.append(band)
                        clip.append(band)
                    else:
                        clip.append(Float64((60 + px + frame_index * 3) % 256))
                        clip.append(Float64((20 + py * 2 + frame_index * 5) % 256))
                        clip.append(Float64((180 + px // 2 - py + frame_index * 4 + 512) % 256))
    return clip^


def _bool_to_sum(value: Bool) -> Float64:
    return 1.0 if value else 0.0


def main() raises:
    var clip = build_clip()

    var frame_contrast = frame_min_preferred_text_contrast_for_video(
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        5,
    )
    var frame_color = frame_preferred_text_color_for_video(
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        5,
    )
    var sampled_contrast = sampled_video_min_text_contrast(
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        SAMPLE_FRAMES,
    )
    var sampled_safe_ratio = sampled_video_wcag_safe_ratio(
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        SAMPLE_FRAMES,
        FONT_SIZE_PT,
        IS_BOLD,
    )
    var sampled_backplate = needs_text_backplate_for_video(
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        SAMPLE_FRAMES,
        FONT_SIZE_PT,
        IS_BOLD,
    )
    var band_contrast = subtitle_band_min_preferred_text_contrast_for_video(
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        SAMPLE_FRAMES,
        BAND_ROWS,
    )
    var band_color = subtitle_band_preferred_text_color_for_video(
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        SAMPLE_FRAMES,
        BAND_ROWS,
    )
    var band_safe_ratio = sampled_subtitle_band_wcag_safe_ratio(
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        SAMPLE_FRAMES,
        BAND_ROWS,
        FONT_SIZE_PT,
        IS_BOLD,
    )
    var band_backplate = subtitle_band_needs_backplate_for_video(
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        SAMPLE_FRAMES,
        BAND_ROWS,
        FONT_SIZE_PT,
        IS_BOLD,
    )

    print("MOJO_RESULT frame_min_preferred_text_contrast_for_video", frame_contrast)
    print("MOJO_RESULT frame_preferred_text_color_for_video", frame_color)
    print("MOJO_RESULT sampled_video_min_text_contrast", sampled_contrast)
    print("MOJO_RESULT sampled_video_wcag_safe_ratio", sampled_safe_ratio)
    print("MOJO_RESULT needs_text_backplate_for_video", sampled_backplate)
    print("MOJO_RESULT subtitle_band_min_preferred_text_contrast_for_video", band_contrast)
    print("MOJO_RESULT subtitle_band_preferred_text_color_for_video", band_color)
    print("MOJO_RESULT sampled_subtitle_band_wcag_safe_ratio", band_safe_ratio)
    print("MOJO_RESULT subtitle_band_needs_backplate_for_video", band_backplate)

    var checksum_frame_contrast: Float64 = 0.0
    var t0_frame_contrast = perf_counter_ns()
    for _ in range(ITERATIONS):
        checksum_frame_contrast += frame_min_preferred_text_contrast_for_video(
            clip,
            WIDTH,
            HEIGHT,
            CHANNELS,
            5,
        )
    var t1_frame_contrast = perf_counter_ns()
    print(
        "MOJO_BENCH frame_min_preferred_text_contrast_for_video",
        Float64(t1_frame_contrast - t0_frame_contrast) / Float64(ITERATIONS),
        checksum_frame_contrast,
    )

    var checksum_frame_color: Float64 = 0.0
    var t0_frame_color = perf_counter_ns()
    for _ in range(ITERATIONS):
        var color = frame_preferred_text_color_for_video(clip, WIDTH, HEIGHT, CHANNELS, 5)
        checksum_frame_color += 1.0 if color == "#FFFFFF" else 0.0
    var t1_frame_color = perf_counter_ns()
    print(
        "MOJO_BENCH frame_preferred_text_color_for_video",
        Float64(t1_frame_color - t0_frame_color) / Float64(ITERATIONS),
        checksum_frame_color,
    )

    var checksum_sampled_contrast: Float64 = 0.0
    var t0_sampled_contrast = perf_counter_ns()
    for _ in range(ITERATIONS):
        checksum_sampled_contrast += sampled_video_min_text_contrast(
            clip,
            WIDTH,
            HEIGHT,
            CHANNELS,
            SAMPLE_FRAMES,
        )
    var t1_sampled_contrast = perf_counter_ns()
    print(
        "MOJO_BENCH sampled_video_min_text_contrast",
        Float64(t1_sampled_contrast - t0_sampled_contrast) / Float64(ITERATIONS),
        checksum_sampled_contrast,
    )

    var checksum_sampled_safe_ratio: Float64 = 0.0
    var t0_sampled_safe_ratio = perf_counter_ns()
    for _ in range(ITERATIONS):
        checksum_sampled_safe_ratio += sampled_video_wcag_safe_ratio(
            clip,
            WIDTH,
            HEIGHT,
            CHANNELS,
            SAMPLE_FRAMES,
            FONT_SIZE_PT,
            IS_BOLD,
        )
    var t1_sampled_safe_ratio = perf_counter_ns()
    print(
        "MOJO_BENCH sampled_video_wcag_safe_ratio",
        Float64(t1_sampled_safe_ratio - t0_sampled_safe_ratio) / Float64(ITERATIONS),
        checksum_sampled_safe_ratio,
    )

    var checksum_sampled_backplate: Float64 = 0.0
    var t0_sampled_backplate = perf_counter_ns()
    for _ in range(ITERATIONS):
        checksum_sampled_backplate += _bool_to_sum(
            needs_text_backplate_for_video(
                clip,
                WIDTH,
                HEIGHT,
                CHANNELS,
                SAMPLE_FRAMES,
                FONT_SIZE_PT,
                IS_BOLD,
            )
        )
    var t1_sampled_backplate = perf_counter_ns()
    print(
        "MOJO_BENCH needs_text_backplate_for_video",
        Float64(t1_sampled_backplate - t0_sampled_backplate) / Float64(ITERATIONS),
        checksum_sampled_backplate,
    )

    var checksum_band_contrast: Float64 = 0.0
    var t0_band_contrast = perf_counter_ns()
    for _ in range(ITERATIONS):
        checksum_band_contrast += subtitle_band_min_preferred_text_contrast_for_video(
            clip,
            WIDTH,
            HEIGHT,
            CHANNELS,
            SAMPLE_FRAMES,
            BAND_ROWS,
        )
    var t1_band_contrast = perf_counter_ns()
    print(
        "MOJO_BENCH subtitle_band_min_preferred_text_contrast_for_video",
        Float64(t1_band_contrast - t0_band_contrast) / Float64(ITERATIONS),
        checksum_band_contrast,
    )

    var checksum_band_color: Float64 = 0.0
    var t0_band_color = perf_counter_ns()
    for _ in range(ITERATIONS):
        var color = subtitle_band_preferred_text_color_for_video(
            clip,
            WIDTH,
            HEIGHT,
            CHANNELS,
            SAMPLE_FRAMES,
            BAND_ROWS,
        )
        checksum_band_color += 1.0 if color == "#FFFFFF" else 0.0
    var t1_band_color = perf_counter_ns()
    print(
        "MOJO_BENCH subtitle_band_preferred_text_color_for_video",
        Float64(t1_band_color - t0_band_color) / Float64(ITERATIONS),
        checksum_band_color,
    )

    var checksum_band_safe_ratio: Float64 = 0.0
    var t0_band_safe_ratio = perf_counter_ns()
    for _ in range(ITERATIONS):
        checksum_band_safe_ratio += sampled_subtitle_band_wcag_safe_ratio(
            clip,
            WIDTH,
            HEIGHT,
            CHANNELS,
            SAMPLE_FRAMES,
            BAND_ROWS,
            FONT_SIZE_PT,
            IS_BOLD,
        )
    var t1_band_safe_ratio = perf_counter_ns()
    print(
        "MOJO_BENCH sampled_subtitle_band_wcag_safe_ratio",
        Float64(t1_band_safe_ratio - t0_band_safe_ratio) / Float64(ITERATIONS),
        checksum_band_safe_ratio,
    )

    var checksum_band_backplate: Float64 = 0.0
    var t0_band_backplate = perf_counter_ns()
    for _ in range(ITERATIONS):
        checksum_band_backplate += _bool_to_sum(
            subtitle_band_needs_backplate_for_video(
                clip,
                WIDTH,
                HEIGHT,
                CHANNELS,
                SAMPLE_FRAMES,
                BAND_ROWS,
                FONT_SIZE_PT,
                IS_BOLD,
            )
        )
    var t1_band_backplate = perf_counter_ns()
    print(
        "MOJO_BENCH subtitle_band_needs_backplate_for_video",
        Float64(t1_band_backplate - t0_band_backplate) / Float64(ITERATIONS),
        checksum_band_backplate,
    )
