from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "docs" / "audit_gitbook_claims.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("audit_gitbook_claims", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_gitbook_a_z_source_audit_passes_without_live_network(tmp_path: Path) -> None:
    audit = _load_module()
    report = audit.run_audit(ROOT / "gitbook", live_url=None, skip_live=True)
    output = tmp_path / "gitbook-a-z.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    assert report["status"] == "pass"
    assert report["summary"]["pages_checked"] >= 120
    assert report["summary"]["links_checked"] >= 200
    assert report["summary"]["snippets_checked"] >= 900
    assert report["agent_readability"]["cursor_ready"] is True
    assert report["agent_readability"]["codex_ready"] is True
    assert report["agent_readability"]["google_ai_ready"] is True
    assert report["snippets"]["static_or_guarded_commands"] > 0


def test_secret_scanner_rejects_concrete_bearer_tokens(tmp_path: Path) -> None:
    audit = _load_module()
    path = tmp_path / "page.md"
    token = "de_live_1234567890abcdef1234567890abcdef"
    issues = audit._find_secret_issues(path, "page.md", f"export ALGENTA_API_KEY={token}\n")

    assert [issue.code for issue in issues] == ["secret_like_value"]
    assert issues[0].line == 1


def test_secret_scanner_rejects_provider_specific_placeholder_prefixes(tmp_path: Path) -> None:
    audit = _load_module()
    path = tmp_path / "page.md"
    text = '\n'.join([
        '"access_token": "ghp_example_token"',
        'export ALGENTA_API_KEY="sk_live_..."',
        'STRIPE_PUBLISHABLE_KEY=pk_test_replace_me',
        'STRIPE_WEBHOOK_SECRET=whsec_replace_me',
        '',
    ])

    issues = audit._find_secret_issues(path, "page.md", text)

    assert [issue.code for issue in issues] == [
        "secret_like_placeholder_prefix",
        "secret_like_placeholder_prefix",
        "secret_like_placeholder_prefix",
        "secret_like_placeholder_prefix",
    ]
    assert [issue.line for issue in issues] == [1, 2, 3, 4]


def test_secret_scanner_allows_redacted_algenta_placeholders(tmp_path: Path) -> None:
    audit = _load_module()
    path = tmp_path / "page.md"

    issues = audit._find_secret_issues(path, "page.md", 'export ALGENTA_API_KEY="de_live_..."\n')

    assert issues == []


def test_machine_snippet_validator_rejects_malformed_json(tmp_path: Path) -> None:
    audit = _load_module()
    fence = audit.CodeFence(
        path=tmp_path / "page.md",
        rel_path="page.md",
        line=12,
        info="json",
        language="json",
        body='{"unterminated": true',
    )

    issues = audit._validate_machine_snippet(fence)
    assert [issue.code for issue in issues] == ["invalid_json_snippet"]
    assert issues[0].line == 12
