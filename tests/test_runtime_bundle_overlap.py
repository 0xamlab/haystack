from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
for path in (str(ALGENTA_CORE), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

runtime_bundle_overlap = importlib.import_module("algenta.runtime_bundle_overlap")
runtime_models = importlib.import_module("algenta.runtime_models")
SourceRegistration = runtime_models.SourceRegistration
bundle_field_tokens = runtime_bundle_overlap.bundle_field_tokens
bundle_overlap_lines = runtime_bundle_overlap.bundle_overlap_lines
field_overlap_score = runtime_bundle_overlap.field_overlap_score


def _registration(name: str, fields: list[str]) -> SourceRegistration:
    return SourceRegistration(
        source_id=f"src_{name}",
        dataset_id=f"ds_{name}",
        name=name,
        status="ready",
        source_schema={"fields": fields},
    )


def test_bundle_field_tokens_ignores_suffixes_and_normalizes_case() -> None:
    assert bundle_field_tokens("Guest_Count__avg") == {"guestcount"}


def test_field_overlap_score_returns_full_and_partial_matches() -> None:
    assert field_overlap_score("revenue__sum", "revenue__avg") == 1.0
    assert field_overlap_score("guest_count", "guest_count_daily") == 0.0
    assert field_overlap_score("gross_revenue", "units") == 0.0


def test_bundle_overlap_lines_reports_top_matches_between_registrations() -> None:
    registrations = [
        _registration("orders", ["revenue__sum", "ticket_count__sum", "units"]),
        _registration("finance", ["revenue__avg", "ticket_count__avg", "units"]),
        _registration("support", ["ticket_count", "satisfaction_score"]),
    ]

    lines = bundle_overlap_lines(registrations)

    assert lines[0].startswith("orders ↔ finance:")
    assert "revenue__sum ~ revenue__avg" in lines[0]
    assert "ticket_count__sum ~ ticket_count__avg" in lines[0]
    assert "units ~ units" in lines[0]
