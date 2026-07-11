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

    totals = report["totals"]
    summary = report["summary"]
    assert totals["pages"] == summary["pages_checked"]
    assert totals["links"] == summary["links_checked"]
    assert totals["code_fences"] == summary["snippets_checked"]
    assert totals["shell_commands"] == summary["commands_classified"]
    assert totals["runnable_commands"] == report["snippets"]["runnable_safe_commands"]
    assert totals["static_or_guarded_commands"] == report["snippets"]["static_or_guarded_commands"]
    assert totals["claim_mentions"] == summary["claim_mentions"]
    assert totals["claim_mentions"] == sum(totals["product_claims"].values())
    assert totals["failures"] == summary["failures"] == 0
    assert totals["warnings"] == summary["warnings"] == 0
    assert totals["fixes"] == summary["fixes"] == 0
    assert totals["skips"] == summary["skips"]
    assert totals["blockers"] == summary["blockers"] == 0


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
    text = "\n".join(
        [
            '"access_token": "ghp_example_token"',
            'export ALGENTA_API_KEY="sk_live_..."',
            "STRIPE_PUBLISHABLE_KEY=pk_test_replace_me",
            "STRIPE_WEBHOOK_SECRET=whsec_replace_me",
            "",
        ]
    )

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


def test_public_package_scanner_rejects_wrong_scoped_typescript_sdk(tmp_path: Path) -> None:
    audit = _load_module()
    path = tmp_path / "page.md"

    issues = audit._find_public_package_issues(
        path,
        "page.md",
        'import { AlgentaClient } from "@algenta/sdk";\n',
    )

    assert [issue.code for issue in issues] == ["wrong_typescript_sdk_package"]
    assert issues[0].line == 1


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


def test_sitemap_url_to_markdown_route_maps_gitbook_urls() -> None:
    audit = _load_module()

    assert (
        audit._sitemap_url_to_markdown_route("https://docs.example", "https://docs.example")
        == "/.md"
    )
    assert (
        audit._sitemap_url_to_markdown_route("https://docs.example", "https://docs.example/")
        == "/.md"
    )
    assert (
        audit._sitemap_url_to_markdown_route("https://docs.example", "https://docs.example/sdk/mcp")
        == "/sdk/mcp.md"
    )
    assert (
        audit._sitemap_url_to_markdown_route(
            "https://docs.example", "https://docs.example/sdk/mcp/"
        )
        == "/sdk/mcp.md"
    )
    assert (
        audit._sitemap_url_to_markdown_route(
            "https://docs.example", "https://other.example/sdk/mcp"
        )
        is None
    )


def test_live_audit_checks_every_sitemap_markdown_route(monkeypatch) -> None:
    audit = _load_module()
    fetched_urls: list[str] = []
    sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://docs.example</loc></url>
  <url><loc>https://docs.example/sdk/mcp</loc></url>
  <url><loc>https://docs.example/guides/ai-access/</loc></url>
</urlset>
"""

    def fake_fetch(url: str, *, max_bytes: int = 2_000_000, timeout: float = 30.0):
        del max_bytes, timeout
        fetched_urls.append(url)
        if url.endswith("/sitemap-pages.xml"):
            return 200, sitemap.encode(), "application/xml"
        if url.endswith("/robots.txt"):
            return 200, b"User-agent: *\nAllow: /\n", "text/plain"
        if url.endswith("/llms.txt"):
            return 200, b"# Algenta\nhttps://docs.algenta.ai\n", "text/markdown"
        if url.endswith("/llms-full.txt"):
            return 200, b"# Algenta\nUsing these docs with AI\n", "text/markdown"
        if url.endswith("/~gitbook/mcp"):
            return 405, b'{"jsonrpc":"2.0","error":{"code":-32000}}', "application/json"
        if (
            url.endswith("/.md")
            or url.endswith("/sdk/mcp.md")
            or url.endswith("/guides/ai-access.md")
        ):
            return 200, b"# Algenta page\n", "text/markdown; charset=utf-8"
        return 404, b"not found", "text/plain"

    monkeypatch.setattr(audit, "_fetch", fake_fetch)

    issues, report = audit._audit_live("https://docs.example", public_page_count=3)

    assert issues == []
    assert report["sitemap_urls"] == 3
    assert report["markdown_pages_checked"] == 3
    assert "https://docs.example/.md" in fetched_urls
    assert "https://docs.example/sdk/mcp.md" in fetched_urls
    assert "https://docs.example/guides/ai-access.md" in fetched_urls
