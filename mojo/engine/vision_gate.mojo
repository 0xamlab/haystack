"""
vision_gate.mojo — Deterministic image-routing policy. Zero Python imports.

The Codna Vision Gate's decision layer: given the cheap scalar signals produced
by perceptual_hash / image_quality / image_features, decide the cheapest valid
path for an image so an expensive vision-model call happens only when nothing
cheaper can deduplicate, answer, OCR, or reject it.

This module is pure branching logic — no pixel math, no allocation. It returns an
Int ACTION CODE (kept Int, not String, so it is runtime-callable with no
inventory whitelist edits). Map the code in the caller:

  ACTION CODES
    0  use_cache               — near-duplicate of an already-analyzed image
    1  answer_from_features    — pixel-level question answered deterministically
    2  ask_for_clearer_image   — too blurry / too dark / too bright to use
    3  ocr_text_regions        — text-bearing image; OCR before any model call
    4  vision_llm_low_res      — send a downscaled whole image to the model
    5  vision_llm_selected_crops — send only the salient region(s)

  INTENT CODES (caller-supplied)
    0  general / describe scene
    1  read text (receipt / invoice / screenshot / document)
    2  simple pixel question (dominant colour, blur, brightness, dimensions)
    3  compare / find duplicates

Public API:
  route_image_request   — full router → action code (0-5)
  should_use_cache      — true when the image is a known duplicate
  needs_clearer_image   — true when blur/exposure make the image unusable
  is_text_heavy         — true when edge density + entropy look text-like
  quality_gate_passed   — true when the image is sharp, exposed, and non-blank
"""


# ── Tunable thresholds (documented defaults for 0-255 grayscale) ────────────────


comptime _BLUR_MIN: Float64 = 100.0          # Laplacian variance below this ⇒ blurry
comptime _BRIGHT_LOW: Float64 = 20.0         # mean brightness below this ⇒ under-exposed
comptime _BRIGHT_HIGH: Float64 = 235.0       # mean brightness above this ⇒ over-exposed
comptime _ENTROPY_MIN: Float64 = 0.5         # 256-bin entropy below this ⇒ near-blank
comptime _TEXT_EDGE_MIN: Float64 = 0.10      # edge density above this with text intent ⇒ OCR
comptime _TEXT_ENTROPY_MIN: Float64 = 3.0    # entropy floor for "text-like"
comptime _CROP_EDGE_MIN: Float64 = 0.15      # edge density above this ⇒ a region dominates


# ── Predicate helpers ───────────────────────────────────────────────────────────


fn should_use_cache(is_duplicate_flag: Bool) -> Bool:
    """True when the image duplicates one already analyzed (reuse the result)."""
    return is_duplicate_flag


fn needs_clearer_image(blur_score: Float64, brightness: Float64) -> Bool:
    """True when blur or exposure make the image not worth a model call."""
    return (
        blur_score < _BLUR_MIN
        or brightness < _BRIGHT_LOW
        or brightness > _BRIGHT_HIGH
    )


fn is_text_heavy(edge_density: Float64, entropy: Float64) -> Bool:
    """Heuristic: dense edges plus moderate entropy look like printed text."""
    return edge_density > _TEXT_EDGE_MIN and entropy > _TEXT_ENTROPY_MIN


fn quality_gate_passed(
    blur_score: Float64, brightness: Float64, entropy: Float64
) -> Bool:
    """True when the image is sharp enough, exposed, and not near-blank."""
    return (
        not needs_clearer_image(blur_score, brightness)
        and entropy >= _ENTROPY_MIN
    )


# ── Router ──────────────────────────────────────────────────────────────────────


fn route_image_request(
    blur_score: Float64,
    brightness: Float64,
    entropy: Float64,
    edge_density: Float64,
    is_duplicate_flag: Bool,
    intent_code: Int,
) -> Int:
    """Pick the cheapest valid action (0-5) for an image. See module docstring."""
    # 1. Known duplicate → reuse cached analysis, regardless of anything else.
    if is_duplicate_flag:
        return 0
    # 2. Pixel-level question → Mojo already has the answer (even if blurry/dark).
    if intent_code == 2:
        return 1
    # 3. Unusable image → ask the user for a better one before spending tokens.
    if needs_clearer_image(blur_score, brightness):
        return 2
    # 4. Near-blank but otherwise fine → nothing to see; answer from features.
    if entropy < _ENTROPY_MIN:
        return 1
    # 5. Read-text intent → OCR the text regions when there is edge content.
    if intent_code == 1:
        if edge_density > _TEXT_EDGE_MIN:
            return 3
        return 4
    # 6. General / compare intent → crop to the salient region if one dominates,
    #    otherwise send a downscaled whole image.
    if edge_density > _CROP_EDGE_MIN:
        return 5
    return 4
