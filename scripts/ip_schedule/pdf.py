#!/usr/bin/env python3
"""Render the IP schedule workbook and the Markdown documents to PDF with nothing clipped.

The workbook has tabs up to 18 columns wide with cells of several hundred characters; printed
as a grid they overflow any page. This renderer chooses the layout per tab:

* narrow tabs (few columns, short cells) become wrapped landscape tables with the header
  repeated on every page;
* wide tabs become one card per row — a two-column field/value table headed by the row's
  first cell — so every character is on the page.

Markdown documents (narrative, valuation note) render as portrait documents. ReportLab does
the typesetting; it is not part of the repository environment, so this is an optional step:
``python3 scripts/ip_schedule/pdf.py --dir <output folder>`` with a Python that has
``reportlab`` and ``openpyxl`` installed.
"""

from __future__ import annotations

import argparse
import html
import io
import re
import sys
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

WIDE_COLUMNS = 8  # more columns than this, or a very long cell, switches a tab to cards
LONG_CELL = 300
INTERNAL_MARK = "(internal"  # tabs whose title carries this never reach the external PDF
NAVY = colors.HexColor("#1F3A5F")
HEAD_BG = colors.HexColor("#E8EEF6")
KEY_BG = colors.HexColor("#F4F6FA")
GRID = colors.HexColor("#BBBBBB")

_ss = getSampleStyleSheet()
S_TITLE = ParagraphStyle(
    "t", parent=_ss["Title"], fontSize=22, leading=27, alignment=TA_LEFT, spaceAfter=6
)
S_H2 = ParagraphStyle(
    "h2",
    parent=_ss["Heading2"],
    fontSize=13,
    leading=16,
    textColor=NAVY,
    spaceBefore=0,
    spaceAfter=6,
)
S_H3 = ParagraphStyle(
    "h3",
    parent=_ss["Heading3"],
    fontSize=9.5,
    leading=12,
    textColor=NAVY,
    spaceBefore=6,
    spaceAfter=2,
)
S_BODY = ParagraphStyle("b", parent=_ss["BodyText"], fontSize=9, leading=12, spaceAfter=5)
S_META = ParagraphStyle("m", parent=S_BODY, textColor=colors.HexColor("#444444"))
S_NOTE = ParagraphStyle(
    "n",
    parent=S_BODY,
    fontName="Helvetica-Oblique",
    textColor=colors.HexColor("#444444"),
    spaceBefore=4,
)
S_CELL = ParagraphStyle(
    "c", parent=S_BODY, fontSize=7.5, leading=9.5, spaceAfter=0, splitLongWords=True
)
S_CELL_D = ParagraphStyle("cd", parent=S_CELL, fontSize=6.8, leading=8.6)
S_HEAD = ParagraphStyle("hd", parent=S_CELL, fontName="Helvetica-Bold")
S_HEAD_D = ParagraphStyle("hdd", parent=S_CELL_D, fontName="Helvetica-Bold")
S_KEY = ParagraphStyle("k", parent=S_CELL, fontName="Helvetica-Bold", fontSize=8, leading=10)
S_VAL = ParagraphStyle("v", parent=S_CELL, fontSize=8, leading=10.5)
S_DOC = ParagraphStyle("doc", parent=S_BODY, fontSize=10, leading=14, spaceAfter=7)
S_DOC_H1 = ParagraphStyle("dh1", parent=S_TITLE, fontSize=19, leading=23)
S_DOC_H2 = ParagraphStyle("dh2", parent=S_H2, fontSize=13.5, leading=17, spaceBefore=10)
S_DOC_H3 = ParagraphStyle("dh3", parent=S_H3, fontSize=11, leading=14)


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------


def esc(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, int):
        return f"{v:,}"
    text = str(v).replace("\U0001f525", "[U+1F525 fire emoji]")  # no glyph in the PDF fonts
    return html.escape(text).replace("\n", "<br/>")


def md_inline(text: str) -> str:
    """Markdown bold/italic/code → ReportLab paragraph markup, everything else escaped."""
    out = []
    pos = 0
    for m in re.finditer(r"(\*\*[^*]+\*\*|`[^`]+`|\*[^*\n]+\*|_[^_\n]+_)", text):
        out.append(html.escape(text[pos : m.start()]))
        tok = m.group(0)
        if tok.startswith("**"):
            out.append(f"<b>{html.escape(tok[2:-2])}</b>")
        elif tok.startswith("`"):
            out.append(f"<font face='Courier'>{html.escape(tok[1:-1])}</font>")
        else:
            out.append(f"<i>{html.escape(tok[1:-1])}</i>")
        pos = m.end()
    out.append(html.escape(text[pos:]))
    return "".join(out)


def _footer(title: str, total: int):  # noqa: ANN202 - ReportLab onPage callback
    def draw(canv: canvas.Canvas, _doc: Any) -> None:
        canv.saveState()
        canv.setFont("Helvetica", 7.5)
        canv.setFillColor(colors.HexColor("#555555"))
        w, _h = canv._pagesize
        canv.drawString(12 * mm, 8 * mm, title)
        canv.drawRightString(w - 12 * mm, 8 * mm, f"{canv.getPageNumber()} / {total}")
        canv.restoreState()

    return draw


# --------------------------------------------------------------------------------------
# workbook → flowables
# --------------------------------------------------------------------------------------


def sheet_rows(ws: Any) -> tuple[list[str], list[list[Any]], str]:
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    if not rows:
        return [], [], ""
    header = [str(h) if h is not None else "" for h in rows[0]]
    body: list[list[Any]] = []
    note = ""
    data = [r for r in rows[1:] if any(v not in (None, "") for v in r)]
    for idx, r in enumerate(data):
        single = r[0] not in (None, "") and all(v in (None, "") for v in r[1:])
        # the renderer appends one italic single-cell note row at the end of each tab
        if single and idx == len(data) - 1 and body and isinstance(r[0], str):
            note = r[0]
            continue
        body.append(list(r) + [None] * (len(header) - len(r)))
    return header, body, note


def is_wide(header: list[str], body: list[list[Any]]) -> bool:
    """Cards for genuinely wide tabs; a long cell in a narrow table just wraps."""
    longest = max((len(str(v)) for r in body for v in r if v is not None), default=0)
    return len(header) > WIDE_COLUMNS or (len(header) > 4 and longest > LONG_CELL)


def col_widths(header: list[str], body: list[list[Any]], avail: float) -> list[float]:
    weights = []
    for i, h in enumerate(header):
        lens = [len(str(r[i])) for r in body if i < len(r) and r[i] not in (None, "")]
        avg = sum(lens) / len(lens) if lens else 0
        weights.append(max(len(h), min(90, avg), 6))
    # identifiers in the first column (repositories, marks, domains) should not break mid-word
    first = [len(str(r[0])) for r in body if r and r[0] not in (None, "")]
    if first:
        weights[0] = max(weights[0], min(34, max(first)))
    total = sum(weights)
    widths = [max(0.55 * inch, avail * w / total) for w in weights]
    scale = avail / sum(widths)
    return [w * scale for w in widths]


def grid_flowable(header: list[str], body: list[list[Any]], avail: float) -> Table:
    dense = len(header) > 5
    hs, cs = (S_HEAD_D, S_CELL_D) if dense else (S_HEAD, S_CELL)
    data = [[Paragraph(esc(h), hs) for h in header]]
    for r in body:
        data.append([Paragraph(esc(v), cs) for v in r[: len(header)]])
    t = Table(data, colWidths=col_widths(header, body, avail), repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return t


def card_flowables(header: list[str], body: list[list[Any]], avail: float) -> list[Any]:
    out: list[Any] = []
    for r in body:
        rows = []
        for k, v in zip(header[1:], r[1:], strict=False):
            if v in (None, ""):
                continue
            rows.append([Paragraph(esc(k), S_KEY), Paragraph(esc(v), S_VAL)])
        block: list[Any] = [Paragraph(esc(r[0]), S_H3)]
        if rows:
            t = Table(rows, colWidths=[0.22 * avail, 0.78 * avail])
            t.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                        ("BACKGROUND", (0, 0), (0, -1), KEY_BG),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ]
                )
            )
            block.append(t)
        block.append(Spacer(1, 6))
        # cards taller than a page must be allowed to split; short ones stay together
        out.append(KeepTogether(block) if len(rows) <= 12 else block)
    flat: list[Any] = []
    for item in out:
        flat.extend(item if isinstance(item, list) else [item])
    return flat


def is_internal(title: str) -> bool:
    return INTERNAL_MARK in title.lower()


def workbook_story(xlsx: Path, title: str, avail: float, internal: bool = False) -> list[Any]:
    import openpyxl

    wb = openpyxl.load_workbook(xlsx, read_only=True)
    sheets = [ws for ws in wb.worksheets if internal or not is_internal(ws.title)]
    dropped = {ws.title for ws in wb.worksheets if ws not in sheets}
    story: list[Any] = [Paragraph(esc(title), S_TITLE)]
    s_header, s_body, _ = sheet_rows(wb.worksheets[0])
    kv = {str(r[0]): r[1] for r in s_body if r and r[0] is not None}
    for key in ("Issuer and owner", "Address", "Snapshot date", "Engine commit"):
        if key in kv:
            story.append(Paragraph(f"<b>{esc(key)}:</b> {esc(kv[key])}", S_BODY))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Tabs", S_H3))
    toc = Table([[Paragraph(esc(ws.title), S_VAL)] for ws in sheets], colWidths=[0.5 * avail])
    toc.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(toc)
    for ws in sheets:
        header, body, note = sheet_rows(ws)
        if not header:
            continue
        if ws is wb.worksheets[0] and dropped:
            # the summary's own tab index must not point at tabs this rendition omits
            body = [r for r in body if not (r and isinstance(r[1], str) and r[1] in dropped)]
        story.append(PageBreak())
        story.append(Paragraph(esc(ws.title), S_H2))
        if is_wide(header, body):
            story.extend(card_flowables(header, body, avail))
        else:
            story.append(grid_flowable(header, body, avail))
        if note:
            story.append(Paragraph(esc(note), S_NOTE))
    return story


# --------------------------------------------------------------------------------------
# markdown → flowables
# --------------------------------------------------------------------------------------


def md_table(lines: list[str], avail: float) -> Table:
    rows = [
        [c.strip().replace("\\|", "|") for c in ln.strip().strip("|").split("|")]
        for ln in lines
        if not re.match(r"^\|\s*:?-{3,}", ln)
    ]
    cols = max(len(r) for r in rows)
    data = [
        [Paragraph(md_inline(c), S_HEAD if i == 0 else S_CELL) for c in r + [""] * (cols - len(r))]
        for i, r in enumerate(rows)
    ]
    t = Table(data, colWidths=col_widths(rows[0], rows[1:], avail), repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return t


def markdown_story(md_path: Path, avail: float) -> list[Any]:
    story: list[Any] = []
    lines = md_path.read_text(encoding="utf-8").split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        if ln.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append(lines[i])
                i += 1
            story.append(md_table(block, avail))
            story.append(Spacer(1, 6))
            continue
        h = re.match(r"^(#{1,3})\s+(.*)$", ln)
        if h:
            style = {1: S_DOC_H1, 2: S_DOC_H2, 3: S_DOC_H3}[len(h.group(1))]
            story.append(Paragraph(md_inline(h.group(2)), style))
            i += 1
            continue
        if ln.lstrip().startswith("- "):
            story.append(Paragraph("• " + md_inline(ln.lstrip()[2:]), S_DOC))
            i += 1
            continue
        story.append(Paragraph(md_inline(ln), S_DOC))
        i += 1
    return story


# --------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------


def _doc(target: Any, portrait: bool, title: str) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        target,
        pagesize=letter if portrait else landscape(letter),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title=title,
        author="Seville AI Technologies, Inc. d/b/a Thyn",
    )


def build(out: Path, make_story: Callable[[], list[Any]], title: str, portrait: bool) -> None:
    """Two passes: the first counts pages into a scratch buffer, the second draws 'n / total'."""
    pages = {"n": 0}

    def count(_canv: canvas.Canvas, _doc: Any) -> None:
        pages["n"] += 1

    _doc(io.BytesIO(), portrait, title).build(make_story(), onFirstPage=count, onLaterPages=count)
    footer = _footer(title, pages["n"])
    _doc(str(out), portrait, title).build(make_story(), onFirstPage=footer, onLaterPages=footer)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dir", type=Path, required=True, help="the dated output folder")
    ap.add_argument("--only", choices=("schedule", "docs"), default=None)
    ap.add_argument(
        "--internal",
        action="store_true",
        help="also write <schedule>_internal.pdf with the internal tabs included",
    )
    args = ap.parse_args(argv)
    d = args.dir
    made: list[Path] = []
    land_avail = landscape(letter)[0] - 24 * mm
    port_avail = letter[0] - 24 * mm
    if args.only in (None, "schedule"):
        for xlsx in sorted(d.glob("Thyn_IP_Schedule_*.xlsx")):
            if xlsx.name.startswith("~$") or xlsx.stem.endswith("_internal"):
                continue
            date = xlsx.stem.split("_")[-1]
            title = f"Schedule of Intellectual Property — {date}"
            out = xlsx.with_suffix(".pdf")
            build(out, partial(workbook_story, xlsx, title, land_avail), title, portrait=False)
            made.append(out)
            internal_xlsx = xlsx.with_name(xlsx.stem + "_internal.xlsx")
            if args.internal and internal_xlsx.exists():
                out_i = internal_xlsx.with_suffix(".pdf")
                build(
                    out_i,
                    partial(
                        workbook_story,
                        internal_xlsx,
                        title + " (internal)",
                        land_avail,
                        internal=True,
                    ),
                    title + " (internal)",
                    portrait=False,
                )
                made.append(out_i)
    if args.only in (None, "docs"):
        docs = sorted(
            list(d.glob("Thyn_IP_Narrative_*.md")) + list(d.glob("Valuation_support_internal_*.md"))
        )
        for md in docs:
            out = md.with_suffix(".pdf")
            build(
                out,
                partial(markdown_story, md, port_avail),
                md.stem.replace("_", " "),
                portrait=True,
            )
            made.append(out)
    for p in made:
        sys.stderr.write(f"[ip-schedule] wrote {p}\n")
    return 0 if made else 1


if __name__ == "__main__":
    sys.exit(main())
