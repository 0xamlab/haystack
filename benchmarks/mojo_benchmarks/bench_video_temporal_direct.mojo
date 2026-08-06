"""
bench_video_temporal_direct.mojo — direct Mojo benchmark for video temporal kernels.

Run from the repo root:
  cd mojo_env
  pixi run mojo run -I ../mojo/engine ../benchmarks/mojo_benchmarks/bench_video_temporal_direct.mojo
"""

from std.time import perf_counter_ns

from video_features import scene_cut_count
from video_ops import temporal_mean_abs_diff
from video_quality import video_quality_score
from video_storyboard import longest_scene_index, storyboard_frame_indices

comptime WIDTH: Int = 96
comptime HEIGHT: Int = 64
comptime FRAMES: Int = 12
comptime CHANNELS: Int = 3
comptime SAMPLE_FRAMES: Int = 6
comptime CUT_THRESHOLD: Float64 = 0.18
comptime STORYBOARD_MAX_FRAMES: Int = 2
comptime ITERATIONS: Int = 24


def _scene(frame_index: Int) -> Int:
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


def _sum_list_int(values: List[Int]) -> Float64:
    var total: Float64 = 0.0
    for index in range(len(values)):
        total += Float64(values[index])
    return total


def _csv_list_int(values: List[Int]) -> String:
    if len(values) == 0:
        return "empty"

    var out = String("")
    for index in range(len(values)):
        if index > 0:
            out += ","
        out += String(values[index])
    return out


def main() raises:
    var clip = build_clip()

    var temporal = temporal_mean_abs_diff(clip, WIDTH, HEIGHT, CHANNELS)
    var cuts = scene_cut_count(clip, WIDTH, HEIGHT, CHANNELS, CUT_THRESHOLD)
    var quality = video_quality_score(clip, WIDTH, HEIGHT, CHANNELS, SAMPLE_FRAMES)
    var longest = longest_scene_index(clip, WIDTH, HEIGHT, CHANNELS, CUT_THRESHOLD)
    var storyboard = storyboard_frame_indices(
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        CUT_THRESHOLD,
        STORYBOARD_MAX_FRAMES,
    )

    print("MOJO_RESULT temporal_mean_abs_diff", temporal)
    print("MOJO_RESULT scene_cut_count", cuts)
    print("MOJO_RESULT video_quality_score", quality)
    print("MOJO_RESULT longest_scene_index", longest)
    print("MOJO_RESULT storyboard_frame_indices", _csv_list_int(storyboard))

    var checksum_temporal: Float64 = 0.0
    var t0_temporal = perf_counter_ns()
    for _ in range(ITERATIONS):
        checksum_temporal += temporal_mean_abs_diff(clip, WIDTH, HEIGHT, CHANNELS)
    var t1_temporal = perf_counter_ns()
    print(
        "MOJO_BENCH temporal_mean_abs_diff",
        Float64(t1_temporal - t0_temporal) / Float64(ITERATIONS),
        checksum_temporal,
    )

    var checksum_cuts: Float64 = 0.0
    var t0_cuts = perf_counter_ns()
    for _ in range(ITERATIONS):
        checksum_cuts += Float64(
            scene_cut_count(clip, WIDTH, HEIGHT, CHANNELS, CUT_THRESHOLD)
        )
    var t1_cuts = perf_counter_ns()
    print(
        "MOJO_BENCH scene_cut_count",
        Float64(t1_cuts - t0_cuts) / Float64(ITERATIONS),
        checksum_cuts,
    )

    var checksum_quality: Float64 = 0.0
    var t0_quality = perf_counter_ns()
    for _ in range(ITERATIONS):
        checksum_quality += video_quality_score(
            clip,
            WIDTH,
            HEIGHT,
            CHANNELS,
            SAMPLE_FRAMES,
        )
    var t1_quality = perf_counter_ns()
    print(
        "MOJO_BENCH video_quality_score",
        Float64(t1_quality - t0_quality) / Float64(ITERATIONS),
        checksum_quality,
    )

    var checksum_longest: Float64 = 0.0
    var t0_longest = perf_counter_ns()
    for _ in range(ITERATIONS):
        checksum_longest += Float64(
            longest_scene_index(clip, WIDTH, HEIGHT, CHANNELS, CUT_THRESHOLD)
        )
    var t1_longest = perf_counter_ns()
    print(
        "MOJO_BENCH longest_scene_index",
        Float64(t1_longest - t0_longest) / Float64(ITERATIONS),
        checksum_longest,
    )

    var checksum_storyboard: Float64 = 0.0
    var t0_storyboard = perf_counter_ns()
    for _ in range(ITERATIONS):
        checksum_storyboard += _sum_list_int(
            storyboard_frame_indices(
                clip,
                WIDTH,
                HEIGHT,
                CHANNELS,
                CUT_THRESHOLD,
                STORYBOARD_MAX_FRAMES,
            )
        )
    var t1_storyboard = perf_counter_ns()
    print(
        "MOJO_BENCH storyboard_frame_indices",
        Float64(t1_storyboard - t0_storyboard) / Float64(ITERATIONS),
        checksum_storyboard,
    )
