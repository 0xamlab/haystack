"""
Export API — GET /v1/runs/{run_id}/export.{fmt}

Formats:
  csv   — always available (stdlib only)
  xlsx  — requires openpyxl   (pip install openpyxl)
  pdf   — requires fpdf2      (pip install fpdf2)
  json  — always available (raw DecisionEnvelope JSON)

The endpoint reconstructs the decision envelope from the persisted DB fields
and whatever blob storage URL was saved.  If the run has a result_url (S3/MinIO)
it fetches and re-serves the full payload; otherwise it builds a summary from
the indexed DB columns.
"""

import csv
import io
import json
import textwrap
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select

from apps.api_server.db.session import AsyncSessionDep
from apps.api_server.middleware.auth import AuthContext, get_current_org
from apps.api_server.services.workspace_scope import workspace_scope_clauses
from apps.api_server.models.simulation_run import SimulationRun

router = APIRouter(tags=["Export"])

# ── Format → mime-type ────────────────────────────────────────────────────────
_MIME: dict[str, str] = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
    "json": "application/json",
}

SummaryValue = str | int | float | bool | None
SummaryDict = dict[str, SummaryValue]
ResultBlob = dict[str, Any]


def _pdf_text(value: object) -> str:
    """Normalize text to the latin-1-safe subset supported by core PDF fonts."""
    if value is None:
        return "-"
    text = str(value)
    replacements = {
        "\u2014": "-",
        "\u2013": "-",
        "\u2212": "-",
        "\u2026": "...",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text.encode("latin-1", "replace").decode("latin-1")


def _has_fpdf2() -> bool:
    try:
        from fpdf import FPDF  # noqa: F401
        from fpdf.enums import XPos, YPos  # noqa: F401
    except ImportError:
        return False
    return True


def _build_minimal_pdf(lines: list[str]) -> bytes:
    """Render a minimal single-page PDF using only stdlib bytes assembly."""

    def _escape_pdf_text(text: str) -> str:
        return (
            text.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
            .replace("\r", " ")
            .replace("\n", " ")
        )

    content_lines = ["BT", "/F1 12 Tf", "50 792 Td", "14 TL"]
    for line in lines:
        content_lines.append(f"({_escape_pdf_text(_pdf_text(line))}) Tj")
        content_lines.append("T*")
    content_lines.append("ET")
    content_stream = "\n".join(content_lines).encode("latin-1")

    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n",
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        (
            f"5 0 obj\n<< /Length {len(content_stream)} >>\nstream\n".encode("ascii")
            + content_stream
            + b"\nendstream\nendobj\n"
        ),
    ]

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = [0]
    for obj in objects:
        offsets.append(len(output))
        output.extend(obj)

    xref_start = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def _render_pdf_without_fpdf(summary: SummaryDict, full: ResultBlob | None, run_id: str) -> bytes:
    lines = [
        "Algenta",
        f"Simulation Run Report - {run_id[:16]}...",
        "",
        "Run Metadata",
    ]
    for key, value in summary.items():
        lines.append(f"{key}: {_pdf_text(value)}")

    if full:
        stats = full.get("summary", {})
        pct = full.get("percentiles", {})
        risk = full.get("risk", {})
        if stats or pct or risk:
            lines.extend(["", "Statistics Summary"])
            for key, value in {**stats, **pct, **risk}.items():
                formatted = f"{value:.6f}" if isinstance(value, float) else value
                lines.append(f"{key}: {_pdf_text(formatted)}")

        sens = full.get("sensitivity_analysis", {})
        tornado = sens.get("tornado_chart", []) if sens else []
        if tornado:
            lines.extend(["", "Sensitivity - Top Drivers"])
            for entry in sorted(
                tornado,
                key=lambda item: abs(item.get("range", 0)),
                reverse=True,
            )[:10]:
                lines.append(
                    (
                        f"{entry.get('variable', '')}: "
                        f"range={entry.get('range', 0):.4f} "
                        f"low={entry.get('low_swing', 0):.4f} "
                        f"high={entry.get('high_swing', 0):.4f}"
                    )
                )

        compare = full.get("compare_results", [])
        if compare:
            lines.extend(["", "Scenario Comparison"])
            for index, scenario in enumerate(compare, start=1):
                envelope = scenario.get("envelope", {})
                stats = envelope.get("summary", {})
                lines.append(
                    (
                        f"{scenario.get('name', f'Scenario {index}')}: "
                        f"mean={stats.get('mean', 0):.2f} "
                        f"std={stats.get('std', 0):.2f} "
                        f"score={envelope.get('score', 0):.4f}"
                    )
                )

    return _build_minimal_pdf(lines)


# ── Helper: load run + enforce org ownership ──────────────────────────────────


async def _get_run(run_id: UUID, auth: AuthContext, db: AsyncSessionDep) -> SimulationRun:
    # Scope by org AND workspace (when X-Workspace-Id is set), matching runs.py get_run —
    # export must not let a workspace-scoped key read a sibling workspace's run.
    result = await db.execute(
        select(SimulationRun).where(
            SimulationRun.id == run_id,
            *workspace_scope_clauses(SimulationRun, auth),
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


# ── Helper: fetch full JSON blob if available ─────────────────────────────────


async def _fetch_result_blob(run: SimulationRun) -> ResultBlob | None:
    """Fetch the full result payload from S3/MinIO if a result_url exists."""
    url = getattr(run, "result_url", None)
    blob_ref = getattr(run, "output_blob_ref", None)
    if not url and not blob_ref:
        return None
    if not url:
        from apps.api_server.services.storage_service import generate_presigned_download_url

        url = generate_presigned_download_url(run.org_id, run.id)
    if not url:
        return None
    from apps.api_server.services.storage_service import get_result

    return await get_result(url, org_id=run.org_id)


# ── Helper: build summary dict from DB indexed fields ────────────────────────


def _run_to_summary(run: SimulationRun) -> SummaryDict:
    return {
        "run_id": str(run.id),
        "status": run.status.value if hasattr(run.status, "value") else str(run.status),
        "mode": run.mode.value if hasattr(run.mode, "value") else str(run.mode),
        "simulation_model": getattr(run, "simulation_model", "monte_carlo"),
        "scenarios_run": run.scenarios_run,
        "duration_ms": run.duration_ms,
        "recommended_action": getattr(run, "recommended_action", None),
        "confidence": getattr(run, "confidence", None),
        "expected_value": getattr(run, "expected_value", None),
        "probability_of_loss": getattr(run, "probability_of_loss", None),
        "std_deviation": getattr(run, "std_deviation", None),
        "rationale": getattr(run, "rationale", None),
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "engine_version": getattr(run, "engine_version", None),
        "result_hash": getattr(run, "result_hash", None),
        "request_hash": getattr(run, "request_hash", None),
    }


# ── Helpers: render each format ───────────────────────────────────────────────


def _render_csv(summary: SummaryDict, full: ResultBlob | None) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)

    # ── Section 1: run metadata ───────────────────────────────────────────────
    w.writerow(["# Algenta — Simulation Run Export"])
    w.writerow([])
    w.writerow(["Field", "Value"])
    for k, v in summary.items():
        w.writerow([k, v if v is not None else ""])

    if full:
        # ── Section 2: statistics summary ────────────────────────────────────
        w.writerow([])
        w.writerow(["# Statistics Summary"])
        stats = full.get("summary", {})
        if stats:
            w.writerow(["Metric", "Value"])
            for k, v in stats.items():
                w.writerow([k, v])

        # ── Section 3: percentiles ────────────────────────────────────────────
        pct = full.get("percentiles", {})
        if pct:
            w.writerow([])
            w.writerow(["# Percentiles"])
            w.writerow(["Percentile", "Value"])
            for k, v in pct.items():
                w.writerow([k, v])

        # ── Section 4: risk metrics ───────────────────────────────────────────
        risk = full.get("risk", {})
        if risk:
            w.writerow([])
            w.writerow(["# Risk Metrics"])
            w.writerow(["Metric", "Value"])
            for k, v in risk.items():
                w.writerow([k, v])

        # ── Section 5: sensitivity / scenario ────────────────────────────────
        sens = full.get("sensitivity_analysis", {})
        if sens and "tornado_chart" in sens:
            w.writerow([])
            w.writerow(["# Sensitivity — Tornado Chart"])
            w.writerow(["Variable", "Low Swing", "High Swing", "Range", "Variance Contribution"])
            for entry in sens["tornado_chart"]:
                w.writerow(
                    [
                        entry.get("variable"),
                        entry.get("low_swing"),
                        entry.get("high_swing"),
                        entry.get("range"),
                        entry.get("variance_contribution"),
                    ]
                )

        sc = full.get("scenario_analysis", {})
        if sc and "scenarios" in sc:
            w.writerow([])
            w.writerow(["# Scenario Analysis"])
            w.writerow(["Scenario", "Probability", "Outcome", "Contribution"])
            for s in sc["scenarios"]:
                w.writerow(
                    [
                        s.get("name"),
                        s.get("probability"),
                        s.get("outcome"),
                        s.get("contribution"),
                    ]
                )

    return buf.getvalue().encode("utf-8")


def _render_xlsx(summary: SummaryDict, full: ResultBlob | None) -> bytes:
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="xlsx export requires openpyxl — install it with: pip install openpyxl",
        ) from exc

    workbook: Any = openpyxl.Workbook()
    header_fill = PatternFill("solid", fgColor="1A1A2E")
    header_font = Font(bold=True, color="FFFFFF")
    alt_fill = PatternFill("solid", fgColor="F0F4FF")

    def _sheet_header(ws: Any, titles: list[str]) -> None:
        ws.append(titles)
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")
        ws.freeze_panes = "A2"

    def _autowidth(ws: Any) -> None:
        for col in ws.columns:
            max_len = max((len(str(cell.value or "")) for cell in col), default=0)
            ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 4, 60)

    # ── Sheet 1: Run Metadata ─────────────────────────────────────────────────
    ws1: Any = workbook.active
    ws1.title = "Run Metadata"
    _sheet_header(ws1, ["Field", "Value"])
    for i, (k, v) in enumerate(summary.items(), start=2):
        ws1.append([k, str(v) if v is not None else ""])
        if i % 2 == 0:
            for cell in ws1[i]:
                cell.fill = alt_fill
    _autowidth(ws1)

    if full:
        # ── Sheet 2: Statistics ───────────────────────────────────────────────
        stats = full.get("summary", {})
        pct = full.get("percentiles", {})
        risk = full.get("risk", {})
        if stats or pct or risk:
            ws2: Any = workbook.create_sheet("Statistics")
            _sheet_header(ws2, ["Metric", "Value"])
            for k, v in {**stats, **pct, **risk}.items():
                ws2.append([k, round(v, 6) if isinstance(v, float) else v])
            _autowidth(ws2)

        # ── Sheet 3: Sensitivity ──────────────────────────────────────────────
        sens = full.get("sensitivity_analysis", {})
        if sens and "tornado_chart" in sens:
            ws3: Any = workbook.create_sheet("Sensitivity")
            _sheet_header(ws3, ["Variable", "Low Swing", "High Swing", "Range", "Var Contribution"])
            for e in sens["tornado_chart"]:
                ws3.append(
                    [
                        e.get("variable"),
                        round(e.get("low_swing", 0), 4),
                        round(e.get("high_swing", 0), 4),
                        round(e.get("range", 0), 4),
                        round(e.get("variance_contribution", 0), 6),
                    ]
                )
            _autowidth(ws3)

        # ── Sheet 4: Scenarios ────────────────────────────────────────────────
        sc = full.get("scenario_analysis", {})
        if sc and "scenarios" in sc:
            ws4: Any = workbook.create_sheet("Scenarios")
            _sheet_header(ws4, ["Scenario", "Probability", "Outcome", "Contribution"])
            for s in sc["scenarios"]:
                ws4.append(
                    [
                        s.get("name"),
                        s.get("probability"),
                        s.get("outcome"),
                        s.get("contribution"),
                    ]
                )
            _autowidth(ws4)

        # ── Sheet 5: Compare Results ──────────────────────────────────────────
        compare = full.get("compare_results", [])
        if compare:
            ws5: Any = workbook.create_sheet("Compare")
            _sheet_header(
                ws5,
                ["Scenario", "Mean", "Std", "P5", "P50", "P95", "VaR 95", "CVaR 95", "Score"],
            )
            for sc_r in compare:
                env = sc_r.get("envelope", {})
                s = env.get("summary", {})
                p = env.get("percentiles", {})
                r = env.get("risk", {})
                ws5.append(
                    [
                        sc_r.get("name"),
                        round(s.get("mean", 0), 4),
                        round(s.get("std", 0), 4),
                        round(p.get("p5", 0), 4),
                        round(p.get("p50", 0), 4),
                        round(p.get("p95", 0), 4),
                        round(r.get("var_95", 0), 4),
                        round(r.get("cvar_95", 0), 4),
                        round(env.get("score", 0), 4),
                    ]
                )
            _autowidth(ws5)

    buf = io.BytesIO()
    workbook.save(buf)
    return buf.getvalue()


def _render_pdf(summary: SummaryDict, full: ResultBlob | None, run_id: str) -> bytes:
    """Render a clean PDF report using fpdf2 (soft import)."""
    try:
        from fpdf import FPDF
        from fpdf.enums import XPos, YPos
    except ImportError:
        return _render_pdf_without_fpdf(summary, full, run_id)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(26, 26, 46)
    pdf.cell(0, 12, "Algenta", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(80, 80, 120)
    pdf.cell(
        0,
        8,
        _pdf_text(f"Simulation Run Report - {run_id[:16]}..."),
        align="C",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(6)

    def section_header(title: str) -> None:
        pdf.set_fill_color(26, 26, 46)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, _pdf_text(f"  {title}"), fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(30, 30, 30)
        pdf.set_font("Helvetica", "", 10)
        pdf.ln(1)

    def kv_row(k: str, v: object, alt: bool = False) -> None:
        if alt:
            pdf.set_fill_color(240, 244, 255)
        else:
            pdf.set_fill_color(255, 255, 255)
        pdf.cell(80, 6, _pdf_text(f"  {k}"), border=0, fill=True)
        pdf.cell(0, 6, _pdf_text(v), border=0, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── Run Metadata ─────────────────────────────────────────────────────────
    section_header("Run Metadata")
    for i, (k, v) in enumerate(summary.items()):
        kv_row(k, v, i % 2 == 1)
    pdf.ln(4)

    if full:
        # ── Statistics Summary ────────────────────────────────────────────────
        stats = full.get("summary", {})
        pct = full.get("percentiles", {})
        risk = full.get("risk", {})
        if stats or pct or risk:
            section_header("Statistics Summary")
            all_stats = {**stats, **pct, **risk}
            for i, (k, v) in enumerate(all_stats.items()):
                kv_row(k, f"{v:.6f}" if isinstance(v, float) else str(v), i % 2 == 1)
            pdf.ln(4)

        # ── Sensitivity ───────────────────────────────────────────────────────
        sens = full.get("sensitivity_analysis", {})
        tornado = sens.get("tornado_chart", []) if sens else []
        if tornado:
            section_header("Sensitivity - Top Drivers")
            sorted_tornado = sorted(tornado, key=lambda x: abs(x.get("range", 0)), reverse=True)
            for i, e in enumerate(sorted_tornado[:10]):
                kv_row(
                    e.get("variable", ""),
                    (
                        f"range={e.get('range', 0):.4f}  "
                        f"low={e.get('low_swing', 0):.4f}  "
                        f"high={e.get('high_swing', 0):.4f}"
                    ),
                    i % 2 == 1,
                )
            pdf.ln(4)

        # ── Compare Results ───────────────────────────────────────────────────
        compare = full.get("compare_results", [])
        if compare:
            section_header("Scenario Comparison")
            for i, sc_r in enumerate(compare):
                env = sc_r.get("envelope", {})
                s = env.get("summary", {})
                kv_row(
                    sc_r.get("name", f"Scenario {i + 1}"),
                    (
                        f"mean={s.get('mean', 0):.2f}  "
                        f"std={s.get('std', 0):.2f}  "
                        f"score={env.get('score', 0):.4f}"
                    ),
                    i % 2 == 1,
                )
            pdf.ln(4)

    return bytes(pdf.output())


# ── Main export endpoint ──────────────────────────────────────────────────────


@router.get(
    "/v1/runs/{run_id}/export.{fmt}",
    summary="Export simulation run results",
    description=textwrap.dedent("""
        Export a simulation run in the requested format.

        | Format | Content-Type | Dependency |
        |--------|-------------|------------|
        | `csv`  | text/csv    | stdlib — always available |
        | `xlsx` | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet | `openpyxl` |
        | `pdf`  | application/pdf | `fpdf2` |
        | `json` | application/json | stdlib — always available |

        If the optional dependency is not installed the endpoint returns **503**.
    """),
    responses={
        200: {"description": "Export file bytes"},
        404: {"description": "Run not found"},
        400: {"description": "Unsupported format"},
        503: {"description": "Export dependency not installed"},
    },
)
async def export_run(
    run_id: Annotated[UUID, Path(description="Simulation run UUID")],
    fmt: Annotated[str, Path(description="Export format: csv | xlsx | pdf | json")],
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> Response:
    fmt = fmt.lower()
    if fmt not in _MIME:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{fmt}'. Use: csv, xlsx, pdf, json",
        )

    run = await _get_run(run_id, auth, db)
    summary = _run_to_summary(run)
    full = await _fetch_result_blob(run)

    filename_date = run.created_at.strftime("%Y%m%d") if run.created_at else "export"
    filename = f"run_{str(run_id)[:8]}_{filename_date}.{fmt}"

    if fmt == "json":
        payload = full if full else summary
        content = json.dumps(payload, indent=2, default=str).encode("utf-8")
        return Response(
            content=content,
            media_type=_MIME["json"],
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    if fmt == "csv":
        content = _render_csv(summary, full)
        return StreamingResponse(
            io.BytesIO(content),
            media_type=_MIME["csv"],
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    if fmt == "xlsx":
        content = _render_xlsx(summary, full)
        return Response(
            content=content,
            media_type=_MIME["xlsx"],
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    if fmt == "pdf":
        if not _has_fpdf2():
            raise HTTPException(
                status_code=503,
                detail="pdf export requires fpdf2 — install it with: pip install fpdf2",
            )
        content = _render_pdf(summary, full, str(run_id))
        return Response(
            content=content,
            media_type=_MIME["pdf"],
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    raise HTTPException(status_code=400, detail="Unknown format")
