from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests import go_live_fivetran as cli


def test_strict_failure_messages_collects_summary_and_manifest_errors() -> None:
    payload = {
        "summary": {"pass": 0, "fail": 2, "blocked": 1},
        "suite_failures": ["custom failure"],
        "manifest_error": "selection drift",
    }

    failures = cli._strict_failure_messages(payload)

    assert failures == [
        "custom failure",
        "2 connector(s) failed.",
        "1 connector(s) are blocked.",
        "manifest error: selection drift",
    ]


def test_main_refresh_inventory_writes_baseline_and_prints_json(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    inventory_path = tmp_path / "inventory.lock.json"
    selection_path = tmp_path / "selection.lock.json"
    baseline_path = tmp_path / "baseline.lock.json"
    seen: dict[str, object] = {}

    monkeypatch.setattr(cli, "INVENTORY_LOCK_PATH", inventory_path)
    monkeypatch.setattr(cli, "SELECTION_LOCK_PATH", selection_path)
    monkeypatch.setattr(cli, "BASELINE_LOCK_PATH", baseline_path)
    monkeypatch.setattr(
        cli,
        "refresh_inventory_and_selection_locks",
        lambda: (
            {"inventory_version": "inv"},
            {"selection_version": "sel", "selected_connectors": [{"connector_slug": "salesforce"}]},
        ),
    )
    monkeypatch.setattr(
        cli,
        "sync_example_manifest_from_selection",
        lambda selection_lock: seen.setdefault("selection_lock", selection_lock),
    )
    monkeypatch.setattr(
        cli,
        "build_empty_baseline_lock",
        lambda: {"baseline_version": "base", "entries": []},
    )

    assert cli.main(["refresh-inventory", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["inventory_version"] == "inv"
    assert payload["selection_version"] == "sel"
    assert payload["selected_count"] == 1
    assert seen["selection_lock"] == {
        "selection_version": "sel",
        "selected_connectors": [{"connector_slug": "salesforce"}],
    }
    assert json.loads(baseline_path.read_text(encoding="utf-8")) == {
        "baseline_version": "base",
        "entries": [],
    }


def test_main_refresh_baseline_writes_payload(monkeypatch, tmp_path: Path, capsys) -> None:
    baseline_path = tmp_path / "baseline.lock.json"
    seen: dict[str, object] = {}
    monkeypatch.setattr(cli, "BASELINE_LOCK_PATH", baseline_path)

    def _refresh_baseline_lock(**kwargs):
        seen.update(kwargs)
        return {"baseline_version": "base", "entries": [{"connector_slug": "salesforce"}]}

    monkeypatch.setattr(cli, "refresh_baseline_lock", _refresh_baseline_lock)

    assert cli.main(["refresh-baseline", "--json", "--connector", "salesforce"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["baseline_version"] == "base"
    assert seen == {"connector_slugs": ("salesforce",)}
    assert json.loads(baseline_path.read_text(encoding="utf-8")) == payload


def test_main_hydrate_manifest_prints_summary(monkeypatch, capsys) -> None:
    seen: dict[str, object] = {}

    def _hydrate_manifest_connection_ids_from_live_account(**kwargs):
        seen.update(kwargs)
        return {
            "manifest_path": "/tmp/manifest.json",
            "changed": True,
            "hydrated_paths": ["salesforce.snowflake.connection_id"],
            "unresolved_paths": ["salesforce.bigquery.connection_id missing live match"],
            "remaining_placeholder_fields": [
                "salesforce.snowflake.table",
                "salesforce.bigquery.table",
            ],
        }

    monkeypatch.setattr(
        cli,
        "hydrate_manifest_connection_ids_from_live_account",
        _hydrate_manifest_connection_ids_from_live_account,
    )

    assert cli.main(["hydrate-manifest", "--connector", "salesforce"]) == 0

    rendered = capsys.readouterr().out
    assert seen == {"connector_slugs": ("salesforce",)}
    assert "manifest_path=/tmp/manifest.json" in rendered
    assert "changed=True" in rendered
    assert "hydrated_paths=1" in rendered
    assert "unresolved_paths=1" in rendered
    assert "remaining_placeholder_fields=2" in rendered


def test_main_manifest_connector_prints_entry(monkeypatch, capsys) -> None:
    seen: dict[str, object] = {}
    monkeypatch.setattr(
        cli,
        "build_connector_manifest_view",
        lambda *, connector_slug: seen.setdefault(
            "payload",
            {
                "manifest_path": "/tmp/manifest.json",
                "manifest_version": "manifest-version",
                "connector_slug": connector_slug,
                "manifest_entry": {"connector_slug": connector_slug},
                "remaining_placeholder_fields": [
                    "snowflake.connection_id",
                    "bigquery.table",
                ],
                "next_commands": [
                    f"make go-live-hydrate-fivetran-manifest CONNECTOR={connector_slug}",
                ],
            },
        ),
    )

    assert cli.main(["manifest-connector", "--connector", "github"]) == 0

    rendered = capsys.readouterr().out
    assert "manifest_path=/tmp/manifest.json" in rendered
    assert "manifest_version=manifest-version" in rendered
    assert "connector_slug=github" in rendered
    assert "remaining_placeholder_fields=2" in rendered
    assert '"connector_slug": "github"' in rendered


def test_main_manifest_connector_requires_exactly_one_connector(capsys) -> None:
    with pytest.raises(SystemExit, match="Exactly one connector slug is required"):
        cli.main(["manifest-connector"])

    assert capsys.readouterr().out == ""


def test_main_account_prints_summary(monkeypatch, capsys) -> None:
    seen: dict[str, object] = {}
    monkeypatch.setattr(
        cli,
        "inspect_live_fivetran_account",
        lambda **kwargs: seen.setdefault(
            "payload",
            {
                "summary": {
                    "destinations": 2,
                    "connections": 3,
                    "matched_pairs": 2,
                    "matched_candidates": 2,
                    "unmatched_candidates": 1,
                },
                "connector_filter": list(kwargs.get("connector_slugs") or ()),
            },
        ),
    )

    assert cli.main(["account", "--connector", "github"]) == 0

    rendered = capsys.readouterr().out
    assert "destinations=2" in rendered
    assert "connections=3" in rendered
    assert "matched_pairs=2" in rendered
    assert "unmatched_candidates=1" in rendered


def test_main_status_renders_text(monkeypatch, capsys) -> None:
    seen: dict[str, object] = {}

    def _evaluate_fivetran_wave(**kwargs):
        seen.update(kwargs)
        return {"summary": {"pass": 1, "fail": 0, "blocked": 0}}

    monkeypatch.setattr(cli, "evaluate_fivetran_wave", _evaluate_fivetran_wave)
    monkeypatch.setattr(
        cli, "render_fivetran_status", lambda payload: f"status {payload['summary']['pass']}"
    )

    assert cli.main(["status", "--connector", "salesforce,github"]) == 0
    assert seen == {
        "run_behavior_validation": True,
        "connector_slugs": ("salesforce", "github"),
    }
    assert capsys.readouterr().out.strip() == "status 1"


def test_main_report_writes_markdown_file(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "report.md"
    seen: dict[str, object] = {}
    monkeypatch.setattr(
        cli,
        "ensure_inventory_and_selection_locks_are_consistent",
        lambda: (
            {"inventory_version": "inv"},
            {"selected_connectors": [{"connector_slug": "salesforce"}]},
        ),
    )

    def _evaluate_fivetran_wave(**kwargs):
        seen.update(kwargs)
        return {"summary": {"pass": 0, "fail": 0, "blocked": 1}}

    monkeypatch.setattr(cli, "evaluate_fivetran_wave", _evaluate_fivetran_wave)
    monkeypatch.setattr(
        cli,
        "render_fivetran_markdown_report",
        lambda payload, *, selection_lock: (
            f"report {selection_lock['selected_connectors'][0]['connector_slug']} {payload['summary']['blocked']}"
        ),
    )

    assert cli.main(["report", "--output", str(output_path), "--connector", "salesforce"]) == 0
    assert seen == {
        "run_behavior_validation": True,
        "connector_slugs": ("salesforce",),
    }
    assert output_path.read_text(encoding="utf-8").strip() == "report salesforce 1"


def test_main_verify_returns_non_zero_when_wave_is_not_clean(monkeypatch, capsys) -> None:
    seen: dict[str, object] = {}

    def _evaluate_fivetran_wave(**kwargs):
        seen["kwargs"] = kwargs
        return {
            "summary": {"pass": 0, "fail": 0, "blocked": 1},
            "suite_failures": [],
            "manifest_error": None,
        }

    monkeypatch.setattr(
        cli,
        "evaluate_fivetran_wave",
        _evaluate_fivetran_wave,
    )
    monkeypatch.setattr(cli, "render_fivetran_status", lambda _payload: "blocked")

    assert cli.main(["verify", "--connector", "salesforce"]) == 1
    assert seen["kwargs"] == {
        "run_behavior_validation": True,
        "connector_slugs": ("salesforce",),
    }
    assert capsys.readouterr().out.strip() == "blocked"


def test_main_verify_returns_zero_when_wave_is_clean(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "evaluate_fivetran_wave",
        lambda **_kwargs: {
            "summary": {"pass": 20, "fail": 0, "blocked": 0},
            "suite_failures": [],
            "manifest_error": None,
        },
    )
    monkeypatch.setattr(cli, "render_fivetran_status", lambda _payload: "clean")

    assert cli.main(["verify"]) == 0
    assert capsys.readouterr().out.strip() == "clean"


def test_main_verify_prebaseline_allows_only_missing_baseline_blockers(monkeypatch, capsys) -> None:
    seen: dict[str, object] = {}

    def _evaluate_fivetran_wave(**kwargs):
        seen["kwargs"] = kwargs
        return {
            "summary": {"pass": 0, "fail": 0, "blocked": 1},
            "suite_failures": [],
            "manifest_error": None,
            "connector_results": [
                {
                    "connector_slug": "github",
                    "destinations": [
                        {
                            "destination_name": "snowflake",
                            "state": "blocked",
                            "reasons": ["snowflake baseline entry is missing."],
                        },
                        {
                            "destination_name": "bigquery",
                            "state": "blocked",
                            "reasons": ["bigquery baseline entry is missing."],
                        },
                    ],
                }
            ],
        }

    monkeypatch.setattr(
        cli,
        "evaluate_fivetran_wave",
        _evaluate_fivetran_wave,
    )
    monkeypatch.setattr(cli, "render_fivetran_status", lambda _payload: "prebaseline")

    assert cli.main(["verify", "--pre-baseline", "--connector", "github"]) == 0
    assert seen["kwargs"] == {
        "run_behavior_validation": True,
        "connector_slugs": ("github",),
    }
    assert capsys.readouterr().out.strip() == "prebaseline"


def test_main_verify_prebaseline_rejects_nonbaseline_blockers(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "evaluate_fivetran_wave",
        lambda **_kwargs: {
            "summary": {"pass": 0, "fail": 0, "blocked": 1},
            "suite_failures": [],
            "manifest_error": None,
            "connector_results": [
                {
                    "connector_slug": "github",
                    "destinations": [
                        {
                            "destination_name": "snowflake",
                            "state": "blocked",
                            "reasons": ["snowflake baseline entry is missing."],
                        },
                        {
                            "destination_name": "bigquery",
                            "state": "blocked",
                            "reasons": ["bigquery missing identity columns: id"],
                        },
                    ],
                }
            ],
        },
    )
    monkeypatch.setattr(cli, "render_fivetran_status", lambda _payload: "prebaseline-fail")

    assert cli.main(["verify", "--pre-baseline", "--connector", "github"]) == 1
    assert capsys.readouterr().out.strip() == "prebaseline-fail"
