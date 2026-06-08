from pathlib import Path


def test_go_live_validation_doc_mentions_root_js_operator_gate() -> None:
    text = Path("tests/integration/GO_LIVE_VALIDATION.md").read_text()

    assert "make test-go-live-full" in text
    assert "make js-check" in text
    assert "build/go_live_verify_summary.json" in text
    assert "build/go_live_verify_report.md" in text
    assert "make go-live-report" in text
    assert "DE_ENABLE_SLOW_PUBLIC_REST_CASES" in text
    assert "planned step commands for that run" in text
    assert "static_operational_gaps" in text
    assert "operational_gaps" in text
    assert "live_connectivity_skips" in text
    assert "gap_source_summary" in text
    assert "gap_action_summary" in text
    assert "gap_connector_summary" in text
    assert "gap_env_summary" in text
    assert "gap_env_resolution_summary" in text
    assert "gap_env_template_summary" in text
    assert "tier/source/connector breakdowns" in text
    assert "per-action env and connector coverage" in text
    assert "env -> case/action/connector/tier routing" in text
    assert "keys.txt alias/manual-only" in text
    assert "template-coverage routing" in text
    assert "next_actions" in text
    assert "`source`, `sources`, `static_reason`, and `live_reason`" in text
    assert "keeps a synced Markdown artifact at" in text
    assert "static matrix gaps" in text
    assert "operational gap list" in text
    assert "live connectivity skips" in text
    assert "next actions" in text
    assert "repo-root JavaScript workspace operator gate" in text
    assert "TypeScript package/build surface" in text
    assert "repo-root JS bootstrap path" in text
