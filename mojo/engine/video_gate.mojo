"""
video_gate.mojo — Deterministic routing policy for videos. Zero Python imports.

This mirrors `vision_gate` for temporal media. The caller supplies cheap scalar
signals from `video_ops`, `video_features`, and `video_quality`, and the router
chooses the cheapest valid next action.

ACTION CODES
  0 use_cache
  1 answer_from_features
  2 ask_for_clearer_video
  3 extract_keyframes_ocr
  4 vision_llm_keyframes
  5 vision_llm_full_clip

INTENT CODES
  0 general / describe scene
  1 read text from video or slides
  2 simple temporal question (motion, cuts, brightness, static vs dynamic)
  3 compare / dedupe clips

Public API:
  should_use_cached_video   — true when the clip already has a cached answer
  needs_clearer_video       — true when quality is too low or flicker too high
  quality_gate_passed_video — inverse of needs_clearer_video
  is_mostly_static_video    — true when motion is low and most transitions are frozen
  should_extract_keyframes  — true when keyframes are enough for the intent
  route_video_request       — full router → action code (0-5)
"""


comptime _VIDEO_QUALITY_MIN: Float64 = 0.35
comptime _VIDEO_FLICKER_MAX: Float64 = 80.0
comptime _STATIC_MOTION_MAX: Float64 = 4.0
comptime _STATIC_FREEZE_MIN: Float64 = 0.85
comptime _KEYFRAME_SCENE_RATE_MIN: Float64 = 0.20


def should_use_cached_video(is_duplicate_flag: Bool) -> Bool:
    return is_duplicate_flag


def needs_clearer_video(video_quality: Float64, flicker_score: Float64) -> Bool:
    return video_quality < _VIDEO_QUALITY_MIN or flicker_score > _VIDEO_FLICKER_MAX


def quality_gate_passed_video(video_quality: Float64, flicker_score: Float64) -> Bool:
    return not needs_clearer_video(video_quality, flicker_score)


def is_mostly_static_video(motion_score: Float64, freeze_ratio: Float64) -> Bool:
    return motion_score <= _STATIC_MOTION_MAX and freeze_ratio >= _STATIC_FREEZE_MIN


def should_extract_keyframes(scene_cut_rate: Float64, motion_score: Float64, intent_code: Int) -> Bool:
    if intent_code == 1:
        return True
    if is_mostly_static_video(motion_score, 1.0):
        return True
    return scene_cut_rate >= _KEYFRAME_SCENE_RATE_MIN


def route_video_request(
    video_quality: Float64,
    motion_score: Float64,
    freeze_ratio: Float64,
    flicker_score: Float64,
    scene_cut_rate_val: Float64,
    is_duplicate_flag: Bool,
    intent_code: Int,
) -> Int:
    if is_duplicate_flag:
        return 0
    if intent_code == 2:
        return 1
    if needs_clearer_video(video_quality, flicker_score):
        return 2
    if intent_code == 1:
        return 3
    if should_extract_keyframes(scene_cut_rate_val, motion_score, intent_code):
        return 4
    if is_mostly_static_video(motion_score, freeze_ratio):
        return 4
    return 5
