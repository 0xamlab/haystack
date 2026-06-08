from __future__ import annotations

import pytest

from apps.api_server.connectors.file_connector import FileConnector, _flatten_dict


def test_flatten_dict_wrapper_preserves_public_export() -> None:
    flattened = _flatten_dict(
        {
            "customer": {"name": "Acme", "city": "NY"},
            "tags": ["a", "b"],
        }
    )

    assert flattened == {
        "customer.name": "Acme",
        "customer.city": "NY",
        "tags": '["a", "b"]',
    }


def test_parse_excel_uses_open_excel_sheet_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str | bytes, int | str, bool]] = []
    workbook_closed = {"value": False}

    class _FakeWorkbook:
        def close(self) -> None:
            workbook_closed["value"] = True

    class _FakeWorksheet:
        @property
        def values(self):  # type: ignore[no-untyped-def]
            return iter(
                (
                    ("part_number", "measure_total"),
                    ("00123", 10),
                    ("00456", 20),
                )
            )

    def _fake_open_excel_sheet(
        content_b64: str | bytes,
        sheet: int | str = 0,
        *,
        apply_styles: bool = False,
    ) -> tuple[object, object]:
        calls.append((content_b64, sheet, apply_styles))
        return _FakeWorkbook(), _FakeWorksheet()

    monkeypatch.setattr(
        FileConnector,
        "_open_excel_sheet",
        staticmethod(_fake_open_excel_sheet),
    )

    records = FileConnector._parse_excel("ignored", sheet=1)

    assert calls == [("ignored", 1, True)]
    assert workbook_closed["value"] is True
    assert records == [
        {"part_number": "00123", "measure_total": 10},
        {"part_number": "00456", "measure_total": 20},
    ]


def test_excel_to_arrow_table_uses_openpyxl_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = object()
    calls: list[tuple[str | bytes, int | str]] = []

    def _fake_openpyxl_excel_to_arrow_table(
        content_b64: str | bytes,
        sheet: int | str = 0,
    ) -> object:
        calls.append((content_b64, sheet))
        return sentinel

    monkeypatch.setattr(
        FileConnector,
        "_openpyxl_excel_to_arrow_table",
        staticmethod(_fake_openpyxl_excel_to_arrow_table),
    )

    assert FileConnector._excel_to_arrow_table("ignored", sheet="Sheet1") is sentinel
    assert calls == [("ignored", "Sheet1")]
