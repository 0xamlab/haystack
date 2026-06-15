from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from algenta.runtime_errors import RuntimeValidationError  # noqa: E402
from algenta.runtime_import_preview import (  # noqa: E402
    build_import_bundle_preview,
    build_import_preview,
    registration_preview_fields,
)
from algenta.runtime_models import SourceRegistration  # noqa: E402


def _registration(*, name: str = "orders", fields: list[str] | None = None) -> SourceRegistration:
    return SourceRegistration(
        source_id="src_1",
        dataset_id="src_1",
        name=name,
        status="ready",
        source_schema={"fields": fields or ["amount", "customer"]},
        planner_schema_revision="schema_123",
        latency_ms=4.2,
        row_count=3,
    )


def test_registration_preview_fields_falls_back_to_column_metadata() -> None:
    registration = SourceRegistration(
        source_id="src_1",
        dataset_id="src_1",
        name="orders",
        status="ready",
        source_schema={"columns": [{"name": "amount"}, {"name": "customer"}]},
    )

    assert registration_preview_fields(registration) == ["amount", "customer"]


def test_build_import_preview_uses_explicit_source_ref() -> None:
    preview = build_import_preview(
        source={"type": "csv"},
        registration=_registration(),
        mode="local",
        source_ref="explicit://orders.csv",
        local_source_count=1,
        source_ref_label=lambda _source, _index: "computed://ignored",
        runtime_source_name=lambda _source, _index: "computed_name",
    )

    assert preview.registration.name == "orders"
    assert "Codna Source Import" in preview.preview
    assert "Source: orders" in preview.preview
    assert "Origin: explicit://orders.csv" in preview.preview
    assert "Rows: 3 | Fields: 2" in preview.preview


def test_build_import_bundle_preview_collects_successes_and_failures() -> None:
    calls: list[tuple[object, str | None, str | None]] = []

    def _connect(source, *, name=None, description=None):  # type: ignore[no-untyped-def]
        calls.append((source, name, description))
        if source == "bad":
            raise RuntimeValidationError("invalid_source", "bad source")
        return _registration(name=name or "source")

    bundle = build_import_bundle_preview(
        sources=["good", "bad"],
        mode="api",
        names=["warehouse", "broken"],
        source_refs=["good://1", "bad://1"],
        description="shared desc",
        connect=_connect,
        source_ref_label=lambda source, index: f"computed://{index}:{source}",
        bundle_overlap_lines=lambda registrations: [
            f"{registrations[0].name}.amount ~ shared.amount"
        ],
    )

    assert len(bundle.registrations) == 1
    assert len(bundle.failures) == 1
    assert bundle.failures[0].code == "invalid_source"
    assert "Imported: 1 | Failures: 1" in bundle.preview
    assert "warehouse" in bundle.preview
    assert "broken: invalid_source" in bundle.preview
    assert calls == [("good", "warehouse", "shared desc"), ("bad", "broken", "shared desc")]


def test_build_import_bundle_preview_validates_optional_lengths() -> None:
    with pytest.raises(RuntimeValidationError, match="names must match"):
        build_import_bundle_preview(
            sources=["a", "b"],
            mode="local",
            names=["only-one"],
            source_refs=None,
            description=None,
            connect=lambda *_args, **_kwargs: _registration(),
            source_ref_label=lambda _source, index: f"ref:{index}",
            bundle_overlap_lines=lambda _registrations: [],
        )
