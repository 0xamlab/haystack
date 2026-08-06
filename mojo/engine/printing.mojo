"""
printing.mojo — Printing & Publishing Library. Zero Python imports.

Pure Mojo implementations of fundamental printing and publishing
calculations including DPI/LPI conversion, pixel counts, file sizes,
bleed areas, spine width, ink coverage, paper weight, and colour
difference (CIE76 ΔE).

Public API:
  dpi_to_lpi                — LPI from DPI and screen factor
  pixel_count               — total pixels from dimensions and DPI
  file_size_uncompressed    — raw file size in bytes
  bleed_area                — total area including bleed
  spine_width               — book spine width from page count
  ink_coverage              — total CMYK ink coverage %
  paper_weight_gsm_to_lb    — GSM to pounds (bond basis)
  sheets_per_ream           — standard sheets per ream (500)
  cost_per_page             — cost per printed page
  imposition_pages          — sheets needed for imposition
  color_delta_e             — CIE76 colour difference
  dot_gain_apparent         — apparent dot gain
"""
from std.math import sqrt, abs as fabs


# ── dpi_to_lpi ───────────────────────────────────────────────────────────────


def dpi_to_lpi(dpi: Float64, screen_factor: Float64) -> Float64:
    """LPI = DPI / screen_factor (typical factor ≈ 2)."""
    if screen_factor == 0.0:
        return 0.0
    return dpi / screen_factor


# ── pixel_count ──────────────────────────────────────────────────────────────


def pixel_count(width_inches: Float64, height_inches: Float64, dpi: Float64) -> Float64:
    """Total pixels = (W * DPI) * (H * DPI)."""
    return (width_inches * dpi) * (height_inches * dpi)


# ── file_size_uncompressed ───────────────────────────────────────────────────


def file_size_uncompressed(
    width_px: Float64, height_px: Float64, bit_depth: Float64, channels: Float64
) -> Float64:
    """Bytes = W * H * (bit_depth/8) * channels."""
    return width_px * height_px * (bit_depth / 8.0) * channels


# ── bleed_area ───────────────────────────────────────────────────────────────


def bleed_area(trim_width: Float64, trim_height: Float64, bleed_mm: Float64) -> Float64:
    """Area = (W + 2*bleed) * (H + 2*bleed)."""
    return (trim_width + 2.0 * bleed_mm) * (trim_height + 2.0 * bleed_mm)


# ── spine_width ──────────────────────────────────────────────────────────────


def spine_width(pages: Float64, paper_thickness_mm: Float64) -> Float64:
    """Spine = pages * thickness / 2  (sheets = pages/2)."""
    return pages * paper_thickness_mm / 2.0


# ── ink_coverage ─────────────────────────────────────────────────────────────


def ink_coverage(cmyk_c: Float64, cmyk_m: Float64, cmyk_y: Float64, cmyk_k: Float64) -> Float64:
    """Total ink coverage = C + M + Y + K (max typically 300-400%)."""
    return cmyk_c + cmyk_m + cmyk_y + cmyk_k


# ── paper_weight_gsm_to_lb ──────────────────────────────────────────────────


def paper_weight_gsm_to_lb(gsm: Float64) -> Float64:
    """lb = gsm * 0.67 / 10  (bond basis, approximate)."""
    return gsm * 0.67 / 10.0


# ── sheets_per_ream ──────────────────────────────────────────────────────────


def sheets_per_ream() -> Int:
    """Returns 500 (standard ream)."""
    return 500


# ── cost_per_page ────────────────────────────────────────────────────────────


def cost_per_page(total_cost: Float64, total_pages: Float64) -> Float64:
    """CPP = total_cost / total_pages."""
    if total_pages == 0.0:
        return 0.0
    return total_cost / total_pages


# ── imposition_pages ─────────────────────────────────────────────────────────


def imposition_pages(finished_pages: Float64, pages_per_sheet: Float64) -> Float64:
    """Sheets needed = finished_pages / pages_per_sheet."""
    if pages_per_sheet == 0.0:
        return 0.0
    return finished_pages / pages_per_sheet


# ── color_delta_e ────────────────────────────────────────────────────────────


def color_delta_e(
    l1: Float64, a1: Float64, b1: Float64,
    l2: Float64, a2: Float64, b2: Float64,
) -> Float64:
    """CIE76 ΔE = sqrt((L1-L2)² + (a1-a2)² + (b1-b2)²)."""
    var dl = l1 - l2
    var da = a1 - a2
    var db = b1 - b2
    return sqrt(dl * dl + da * da + db * db)


# ── dot_gain_apparent ────────────────────────────────────────────────────────


def dot_gain_apparent(measured_tone: Float64, actual_tone: Float64) -> Float64:
    """Dot gain = measured_tone - actual_tone."""
    return measured_tone - actual_tone
