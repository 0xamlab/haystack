"""Generate social.png (1200x630) for the algenta-for-llm-agents Space.

Brand spec: bg #0A0A0F, violet->blue gradient strips (#7C5CFA -> #3B82F6),
letterspaced ALGENTA eyebrow (#A78BFA), bold white title, gray subtitle
(README short_description), footer row. Helvetica Neue (no Inter on this
system). Output: ../social.png (repo root of the Space).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
MARGIN = 72
BG = "#0A0A0F"
VIOLET = (124, 92, 250)  # #7C5CFA
BLUE = (59, 130, 246)  # #3B82F6
EYEBROW_COLOR = "#A78BFA"
TITLE_COLOR = "#FFFFFF"
SUBTITLE_COLOR = "#9CA3AF"
FOOTER_COLOR = "#6B7280"

HELVETICA = "/System/Library/Fonts/HelveticaNeue.ttc"
FACE_REGULAR, FACE_BOLD, FACE_MEDIUM = 0, 1, 10

OUT = Path(__file__).resolve().parent.parent / "social.png"


def font(face: int, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(HELVETICA, size, index=face)


def draw_tracked(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fnt: ImageFont.FreeTypeFont,
    fill: str,
    tracking: int,
) -> int:
    """Draw text with per-character letterspacing; return the end x."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += int(draw.textlength(ch, font=fnt)) + tracking
    return x - tracking


def fit_size(
    draw: ImageDraw.ImageDraw, text: str, face: int, start: int, max_width: int
) -> ImageFont.FreeTypeFont:
    size = start
    while size > 20:
        fnt = font(face, size)
        if draw.textlength(text, font=fnt) <= max_width:
            return fnt
        size -= 2
    return font(face, 20)


def gradient_strip(draw: ImageDraw.ImageDraw, y0: int, y1: int) -> None:
    for x in range(W):
        t = x / (W - 1)
        rgb = tuple(round(a + (b - a) * t) for a, b in zip(VIOLET, BLUE, strict=False))
        draw.line([(x, y0), (x, y1 - 1)], fill=rgb)


def main() -> None:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Gradient accent strips (top + bottom, matching the family OG cards).
    gradient_strip(draw, 0, 8)
    gradient_strip(draw, H - 8, H)

    # Eyebrow.
    draw_tracked(draw, (MARGIN, 88), "ALGENTA", font(FACE_MEDIUM, 30), EYEBROW_COLOR, tracking=9)

    # Title (auto-fit to the margin box).
    title_font = fit_size(draw, "Algenta for LLM Agents", FACE_BOLD, 78, W - 2 * MARGIN)
    draw.text((MARGIN, 178), "Algenta for LLM Agents", font=title_font, fill=TITLE_COLOR)

    # Subtitle = README short_description.
    draw.text(
        (MARGIN, 316),
        "Interactive demos for LLM & agent builders",
        font=font(FACE_REGULAR, 33),
        fill=SUBTITLE_COLOR,
    )

    # Footer row.
    draw.text(
        (MARGIN, 540),
        "algenta.ai  ·  Hugging Face Space",
        font=font(FACE_REGULAR, 24),
        fill=FOOTER_COLOR,
    )

    img.save(OUT, "PNG")
    print(f"wrote {OUT} ({img.size[0]}x{img.size[1]})")


if __name__ == "__main__":
    main()
