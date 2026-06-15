"""Terminal branding helpers for Codna CLI and demo surfaces."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable

_TITLE_ART = (
    " █████╗ ██╗      ██████╗ ███████╗███╗   ██╗████████╗ █████╗ ",
    "██╔══██╗██║     ██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██╔══██╗",
    "███████║██║     ██║  ███╗█████╗  ██╔██╗ ██║   ██║   ███████║",
    "██╔══██║██║     ██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██╔══██║",
    "██║  ██║███████╗╚██████╔╝███████╗██║ ╚████║   ██║   ██║  ██║",
    "╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝",
)

_TITLE_COLORS = (
    "\033[38;5;75m",
    "\033[38;5;81m",
    "\033[38;5;111m",
    "\033[38;5;141m",
    "\033[38;5;176m",
    "\033[38;5;204m",
)
_MUTED = "\033[38;5;245m"
_ACCENT = "\033[38;5;183m"
_RESET = "\033[0m"


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def runtime_banner(title: str, lines: Iterable[str]) -> str:
    """Return a branded terminal banner for runtime-first entrypoints."""
    detail_lines = [line.rstrip() for line in lines]
    if not detail_lines:
        detail_lines = [""]

    if _supports_color():
        art = "\n".join(
            f"{color}{segment}{_RESET}"
            for color, segment in zip(_TITLE_COLORS, _TITLE_ART, strict=True)
        )
        border = f"{_MUTED}┌{'─' * 60}┐{_RESET}"
        footer = f"{_MUTED}└{'─' * 60}┘{_RESET}"
        title_line = (
            f"{_MUTED}│{_RESET} {_ACCENT}{title}{_RESET}"
            f"{' ' * max(0, 59 - len(title))}{_MUTED}│{_RESET}"
        )
        body = [title_line]
        for line in detail_lines:
            padded = line[:58].ljust(58)
            body.append(f"{_MUTED}│{_RESET} {padded} {_MUTED}│{_RESET}")
        return "\n".join([art, border, *body, footer])

    art = "\n".join(_TITLE_ART)
    width = 60
    border = f"+{'-' * width}+"
    body = [f"| {title[: width - 2].ljust(width - 2)} |"]
    for line in detail_lines:
        body.append(f"| {line[: width - 2].ljust(width - 2)} |")
    return "\n".join([art, border, *body, border])


def source_import_banner(
    *,
    source_name: str,
    source_ref: str,
    mode: str,
    status: str,
    row_count: int | None,
    fields: Iterable[str] = (),
    schema_revision: str | None = None,
    latency_ms: float | None = None,
) -> str:
    """Return a branded banner for source import and registration events."""
    field_list = [field.strip() for field in fields if field and field.strip()]
    field_count = len(field_list)
    preview = ", ".join(field_list[:3])
    if field_count > 3:
        preview = f"{preview}, +{field_count - 3} more"
    if not preview:
        preview = "(no schema fields detected)"

    schema_label = schema_revision[:12] if schema_revision else "n/a"
    latency_label = f"{latency_ms:.3f}ms" if latency_ms is not None else "n/a"
    row_label = str(row_count) if row_count is not None else "unknown"
    return runtime_banner(
        "Codna Source Import",
        [
            f"Mode: {mode} | Status: {status}",
            f"Source: {source_name}",
            f"Origin: {source_ref}",
            f"Rows: {row_label} | Fields: {field_count}",
            f"Preview: {preview}",
            f"Schema: {schema_label} | Latency: {latency_label}",
        ],
    )


def source_bundle_banner(
    *,
    mode: str,
    imported_count: int,
    failure_count: int,
    total_rows: int,
    source_names: Iterable[str],
    overlaps: Iterable[str] = (),
    failures: Iterable[str] = (),
) -> str:
    """Return a branded banner for multi-source local import previews."""
    names = [name.strip() for name in source_names if name and name.strip()]
    overlap_lines = [line.strip() for line in overlaps if line and line.strip()]
    failure_lines = [line.strip() for line in failures if line and line.strip()]
    detail_lines = [
        f"Mode: {mode} | Imported: {imported_count} | Failures: {failure_count}",
        f"Rows: {total_rows}",
        "Sources:",
    ]
    if names:
        detail_lines.extend(f"- {name}" for name in names)
    else:
        detail_lines.append("- (no sources imported)")

    detail_lines.append("Shared fields:")
    if overlap_lines:
        detail_lines.extend(f"- {line}" for line in overlap_lines[:3])
    else:
        detail_lines.append("- No deterministic shared-field overlaps detected.")

    detail_lines.append("Failures:")
    if failure_lines:
        detail_lines.extend(f"- {line}" for line in failure_lines[:3])
    else:
        detail_lines.append("- None")

    return runtime_banner("Codna Source Bundle", detail_lines)
