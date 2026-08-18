"""
color.mojo — Color space conversion. Zero Python imports.

Replaces colormath/colour with pure Mojo implementations for RGB,
HSL, HSV conversions, hex encoding/decoding, interpolation, and
color distance.

Public API:
  RGB             — r, g, b (range 0-1)
  HSL             — h (0-360), s, l (0-1)
  HSV             — h (0-360), s, v (0-1)
  rgb_to_hsl      — RGB to HSL conversion
  hsl_to_rgb      — HSL to RGB conversion
  rgb_to_hsv      — RGB to HSV conversion
  hsv_to_rgb      — HSV to RGB conversion
  rgb_to_hex      — RGB to "#RRGGBB"
  hex_to_rgb      — Parse "#RRGGBB" or "RRGGBB" to RGB
  rgb_lerp        — Linear interpolation between two colors
  color_distance  — Euclidean distance in RGB space
  grayscale       — Luminance-based grayscale
  complement      — Complementary color
  clamp01         — Clamp value to [0, 1]
"""
from std.math import sqrt, abs as fabs


# ── clamp01 ───────────────────────────────────────────────────────────────────


def clamp01(v: Float64) -> Float64:
    """Clamp value to [0, 1]."""
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


# ── RGB struct ────────────────────────────────────────────────────────────────


struct RGB(Copyable, Movable):
    """RGB color with channels in [0, 1]."""

    var r: Float64
    var g: Float64
    var b: Float64

    def __init__(out self, r: Float64, g: Float64, b: Float64):
        self.r = r
        self.g = g
        self.b = b


# ── HSL struct ────────────────────────────────────────────────────────────────


struct HSL(Copyable, Movable):
    """HSL color: h in [0, 360], s and l in [0, 1]."""

    var h: Float64
    var s: Float64
    var l: Float64

    def __init__(out self, h: Float64, s: Float64, l: Float64):
        self.h = h
        self.s = s
        self.l = l


# ── HSV struct ────────────────────────────────────────────────────────────────


struct HSV(Copyable, Movable):
    """HSV color: h in [0, 360], s and v in [0, 1]."""

    var h: Float64
    var s: Float64
    var v: Float64

    def __init__(out self, h: Float64, s: Float64, v: Float64):
        self.h = h
        self.s = s
        self.v = v


# ── rgb_to_hsl ────────────────────────────────────────────────────────────────


def rgb_to_hsl(c: RGB) -> HSL:
    """RGB to HSL conversion."""
    var r = c.r
    var g = c.g
    var b = c.b
    var mx = r
    if g > mx:
        mx = g
    if b > mx:
        mx = b
    var mn = r
    if g < mn:
        mn = g
    if b < mn:
        mn = b
    var l = (mx + mn) / 2.0
    if mx == mn:
        return HSL(0.0, 0.0, l)
    var d = mx - mn
    var s: Float64
    if l > 0.5:
        s = d / (2.0 - mx - mn)
    else:
        s = d / (mx + mn)
    var h: Float64
    if mx == r:
        h = (g - b) / d
        if g < b:
            h += 6.0
    elif mx == g:
        h = (b - r) / d + 2.0
    else:
        h = (r - g) / d + 4.0
    h *= 60.0
    return HSL(h, s, l)


# ── _hue_to_rgb (helper) ─────────────────────────────────────────────────────


def _hue_to_rgb(p: Float64, q: Float64, t_in: Float64) -> Float64:
    """Helper for HSL to RGB conversion."""
    var t = t_in
    if t < 0.0:
        t += 1.0
    if t > 1.0:
        t -= 1.0
    if t < 1.0 / 6.0:
        return p + (q - p) * 6.0 * t
    if t < 1.0 / 2.0:
        return q
    if t < 2.0 / 3.0:
        return p + (q - p) * (2.0 / 3.0 - t) * 6.0
    return p


# ── hsl_to_rgb ────────────────────────────────────────────────────────────────


def hsl_to_rgb(c: HSL) -> RGB:
    """HSL to RGB conversion."""
    if c.s == 0.0:
        return RGB(c.l, c.l, c.l)
    var q: Float64
    if c.l < 0.5:
        q = c.l * (1.0 + c.s)
    else:
        q = c.l + c.s - c.l * c.s
    var p = 2.0 * c.l - q
    var h = c.h / 360.0
    var r = _hue_to_rgb(p, q, h + 1.0 / 3.0)
    var g = _hue_to_rgb(p, q, h)
    var b = _hue_to_rgb(p, q, h - 1.0 / 3.0)
    return RGB(r, g, b)


# ── rgb_to_hsv ────────────────────────────────────────────────────────────────


def rgb_to_hsv(c: RGB) -> HSV:
    """RGB to HSV conversion."""
    var r = c.r
    var g = c.g
    var b = c.b
    var mx = r
    if g > mx:
        mx = g
    if b > mx:
        mx = b
    var mn = r
    if g < mn:
        mn = g
    if b < mn:
        mn = b
    var v = mx
    var d = mx - mn
    if mx == 0.0:
        return HSV(0.0, 0.0, v)
    var s = d / mx
    if d == 0.0:
        return HSV(0.0, s, v)
    var h: Float64
    if mx == r:
        h = (g - b) / d
        if g < b:
            h += 6.0
    elif mx == g:
        h = (b - r) / d + 2.0
    else:
        h = (r - g) / d + 4.0
    h *= 60.0
    return HSV(h, s, v)


# ── hsv_to_rgb ────────────────────────────────────────────────────────────────


def hsv_to_rgb(c: HSV) -> RGB:
    """HSV to RGB conversion."""
    if c.s == 0.0:
        return RGB(c.v, c.v, c.v)
    var h = c.h / 60.0
    var i = Int(h)
    var f = h - Float64(i)
    var p = c.v * (1.0 - c.s)
    var q = c.v * (1.0 - c.s * f)
    var t = c.v * (1.0 - c.s * (1.0 - f))
    if i == 0:
        return RGB(c.v, t, p)
    elif i == 1:
        return RGB(q, c.v, p)
    elif i == 2:
        return RGB(p, c.v, t)
    elif i == 3:
        return RGB(p, q, c.v)
    elif i == 4:
        return RGB(t, p, c.v)
    else:
        return RGB(c.v, p, q)


# ── _hex_char (helper) ───────────────────────────────────────────────────────

comptime _HEX_CHARS = "0123456789ABCDEF"


@always_inline
def _hex_char(v: Int) -> String:
    """Convert 0-15 to hex char."""
    return chr(Int(_HEX_CHARS.as_bytes()[v]))


def _to_hex_byte(v: Int) -> String:
    """Convert 0-255 to two hex chars."""
    var hi = v >> 4
    var lo = v & 0x0F
    return _hex_char(hi) + _hex_char(lo)


# ── rgb_to_hex ────────────────────────────────────────────────────────────────


def rgb_to_hex(c: RGB) -> String:
    """RGB to hex string '#RRGGBB'."""
    var ri = Int(clamp01(c.r) * 255.0 + 0.5)
    var gi = Int(clamp01(c.g) * 255.0 + 0.5)
    var bi = Int(clamp01(c.b) * 255.0 + 0.5)
    return "#" + _to_hex_byte(ri) + _to_hex_byte(gi) + _to_hex_byte(bi)


# ── _hex_char_val (helper) ───────────────────────────────────────────────────


def _hex_char_val(b: UInt8) -> Int:
    """Convert single hex byte value to 0-15."""
    var o = Int(b)
    if o >= 48 and o <= 57:    # 0-9
        return o - 48
    if o >= 97 and o <= 102:   # a-f
        return o - 97 + 10
    if o >= 65 and o <= 70:    # A-F
        return o - 65 + 10
    return 0


def _is_hex_byte(b: UInt8) -> Bool:
    """True when b is an ASCII hex digit."""
    var o = Int(b)
    return (o >= 48 and o <= 57) or (o >= 65 and o <= 70) or (o >= 97 and o <= 102)


# ── hex_to_rgb ────────────────────────────────────────────────────────────────


def hex_to_rgb(hex: String) -> RGB:
    """Parse '#RRGGBB' or 'RRGGBB' to RGB."""
    var bspan = hex.as_bytes()
    var offset = 0
    if hex.byte_length() > 0 and Int(bspan[0]) == 35:  # '#' == 35
        offset = 1
    # Need a full RRGGBB body of hex digits, else the fixed offsets abort.
    if hex.byte_length() < offset + 6:
        return RGB(0.0, 0.0, 0.0)
    for i in range(offset, offset + 6):
        if not _is_hex_byte(bspan[i]):
            return RGB(0.0, 0.0, 0.0)
    var r_hi = _hex_char_val(bspan[offset])
    var r_lo = _hex_char_val(bspan[offset + 1])
    var g_hi = _hex_char_val(bspan[offset + 2])
    var g_lo = _hex_char_val(bspan[offset + 3])
    var b_hi = _hex_char_val(bspan[offset + 4])
    var b_lo = _hex_char_val(bspan[offset + 5])
    var ri = r_hi * 16 + r_lo
    var gi = g_hi * 16 + g_lo
    var bi = b_hi * 16 + b_lo
    return RGB(Float64(ri) / 255.0, Float64(gi) / 255.0, Float64(bi) / 255.0)


# ── rgb_lerp ──────────────────────────────────────────────────────────────────


def rgb_lerp(a: RGB, b: RGB, t: Float64) -> RGB:
    """Linear interpolation between two colors."""
    var tt = clamp01(t)
    return RGB(
        a.r + (b.r - a.r) * tt,
        a.g + (b.g - a.g) * tt,
        a.b + (b.b - a.b) * tt,
    )


# ── color_distance ────────────────────────────────────────────────────────────


def color_distance(a: RGB, b: RGB) -> Float64:
    """Euclidean distance in RGB space."""
    var dr = a.r - b.r
    var dg = a.g - b.g
    var db = a.b - b.b
    return sqrt(dr * dr + dg * dg + db * db)


# ── grayscale ─────────────────────────────────────────────────────────────────


def grayscale(c: RGB) -> RGB:
    """Convert to grayscale using luminance weights (0.299R + 0.587G + 0.114B)."""
    var gray = 0.299 * c.r + 0.587 * c.g + 0.114 * c.b
    return RGB(gray, gray, gray)


# ── complement ────────────────────────────────────────────────────────────────


def complement(c: RGB) -> RGB:
    """Complementary color (1-r, 1-g, 1-b)."""
    return RGB(1.0 - c.r, 1.0 - c.g, 1.0 - c.b)
