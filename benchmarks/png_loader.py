from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Any


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _paeth_predictor(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _defilter_row(filter_type: int, row: bytes, prev_row: bytes, *, bpp: int) -> bytearray:
    out = bytearray(row)
    if filter_type == 0:
        return out
    if filter_type == 1:
        for i in range(len(out)):
            left = out[i - bpp] if i >= bpp else 0
            out[i] = (out[i] + left) & 0xFF
        return out
    if filter_type == 2:
        for i in range(len(out)):
            out[i] = (out[i] + prev_row[i]) & 0xFF
        return out
    if filter_type == 3:
        for i in range(len(out)):
            left = out[i - bpp] if i >= bpp else 0
            up = prev_row[i]
            out[i] = (out[i] + ((left + up) // 2)) & 0xFF
        return out
    if filter_type == 4:
        for i in range(len(out)):
            left = out[i - bpp] if i >= bpp else 0
            up = prev_row[i]
            up_left = prev_row[i - bpp] if i >= bpp else 0
            out[i] = (out[i] + _paeth_predictor(left, up, up_left)) & 0xFF
        return out
    raise ValueError(f"Unsupported PNG filter type: {filter_type}")


def load_png_rgb(path: str | Path) -> dict[str, Any]:
    payload = Path(path).read_bytes()
    if payload[:8] != PNG_SIGNATURE:
        raise ValueError(f"{path!s} is not a PNG file")

    pos = 8
    width = height = bit_depth = color_type = interlace = None
    idat_chunks: list[bytes] = []

    while pos < len(payload):
        length = struct.unpack(">I", payload[pos : pos + 4])[0]
        chunk_type = payload[pos + 4 : pos + 8]
        chunk_data = payload[pos + 8 : pos + 8 + length]
        pos += 12 + length

        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _compression, _filter, interlace = struct.unpack(
                ">IIBBBBB", chunk_data
            )
        elif chunk_type == b"IDAT":
            idat_chunks.append(chunk_data)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None or bit_depth is None or color_type is None or interlace is None:
        raise ValueError(f"{path!s} is missing required PNG chunks")
    if bit_depth != 8:
        raise ValueError(f"{path!s} uses unsupported bit depth {bit_depth}")
    if interlace != 0:
        raise ValueError(f"{path!s} uses unsupported interlace mode {interlace}")
    if color_type not in {2, 6}:
        raise ValueError(f"{path!s} uses unsupported PNG color type {color_type}")

    bytes_per_pixel = 3 if color_type == 2 else 4
    stride = width * bytes_per_pixel
    raw = zlib.decompress(b"".join(idat_chunks))
    expected = height * (stride + 1)
    if len(raw) != expected:
        raise ValueError(
            f"{path!s} decompressed to {len(raw)} bytes; expected {expected} for {width}x{height}"
        )

    flat_rgb: list[float] = []
    flat_gray: list[float] = []
    prev_row = bytes(stride)
    offset = 0
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        current = _defilter_row(filter_type, raw[offset : offset + stride], prev_row, bpp=bytes_per_pixel)
        offset += stride
        prev_row = bytes(current)

        if color_type == 2:
            step = 3
        else:
            step = 4
        for i in range(0, len(current), step):
            r = float(current[i])
            g = float(current[i + 1])
            b = float(current[i + 2])
            flat_rgb.extend((r, g, b))
            flat_gray.append(0.299 * r + 0.587 * g + 0.114 * b)

    return {
        "width": width,
        "height": height,
        "flat_rgb": flat_rgb,
        "flat_gray": flat_gray,
    }
