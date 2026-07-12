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
    assert report["source"] == "gitbook"
    assert report["summary"]["pages_checked"] >= 120
    assert report["summary"]["links_checked"] >= 200
    assert report["summary"]["snippets_checked"] >= 900
    assert report["agent_readability"]["cursor_ready"] is True
    assert report["agent_readability"]["codex_ready"] is True
    assert report["agent_readability"]["google_ai_ready"] is True
    assert report["snippets"]["static_or_guarded_commands"] > 0
    assert report["summary"]["source_inventory_percent"] == 100.0
    assert report["summary"]["shell_syntax_validation_percent"] == 100.0
    assert report["summary"]["command_execution_percent"] == 0.0
    assert report["openapi_identity"]["algenta_title"] is True
    assert report["openapi_identity"]["cross_product_mentions"] == 0
    assert report["openapi_identity"]["runtime_encapsulation_mentions"] == 0

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
    assert totals["endpoint_mentions"] == len(report["evidence"]["endpoint_mentions"])
    assert totals["shell_commands"] == len(report["evidence"]["shell_commands"])
    assert totals["source_items_inventoried"] == sum(
        len(rows) for rows in report["evidence"].values()
    )
    assert totals["shell_syntax_validated_commands"] == totals["shell_commands"]
    assert totals["failures"] == summary["failures"] == 0
    assert totals["warnings"] == summary["warnings"] == 0
    assert totals["fixes"] == summary["fixes"] == 0
    assert totals["skips"] == summary["skips"]
    assert totals["blockers"] == summary["blockers"] == 0


def test_openapi_audit_rejects_user_managed_runtime_lifecycle_terms(
    monkeypatch, tmp_path: Path
) -> None:
    audit = _load_module()
    schema_dir = tmp_path / "schemas" / "openapi"
    schema_dir.mkdir(parents=True)
    (schema_dir / "openapi.yaml").write_text(
        """openapi: 3.1.0
info:
  title: Algenta API
  version: 1.0.0
paths:
  /v1/metering:
    post:
      description: Called by the local runtime daemon.
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(audit, "ROOT", tmp_path)

    issues, report = audit._audit_openapi_public_identity()

    assert [issue.code for issue in issues] == ["openapi_runtime_encapsulation_leak"]
    assert report["runtime_encapsulation_mentions"] == 1


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


def test_internal_product_identity_is_rejected_from_public_docs(tmp_path: Path) -> None:
    audit = _load_module()
    path = tmp_path / "page.md"

    issues = audit._find_secret_issues(path, "page.md", "Internal product: Codna\n")

    assert [issue.code for issue in issues] == ["private_or_internal_leak"]
    assert issues[0].line == 1


def test_internal_plan_identifiers_are_rejected_from_public_docs(tmp_path: Path) -> None:
    audit = _load_module()
    path = tmp_path / "page.md"

    issues = audit._find_secret_issues(path, "page.md", "| Edition | Internal plan |\n")

    assert [issue.code for issue in issues] == ["private_or_internal_leak"]


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


def test_public_package_scanner_rejects_insecure_cli_secret_fallback(tmp_path: Path) -> None:
    audit = _load_module()
    path = tmp_path / "page.md"

    issues = audit._find_public_package_issues(
        path,
        "page.md",
        "The CLI falls back to a Fernet-encrypted file and stores plaintext only as a last resort.\n",
    )

    assert [issue.code for issue in issues] == [
        "insecure_cli_secret_storage_claim",
        "insecure_cli_secret_storage_claim",
    ]


def test_runtime_encapsulation_scanner_rejects_separate_setup_and_internal_controls() -> None:
    audit = _load_module()
    text = """Run the Mojo engine with de runtime start.
Set MOJO_BINARY_PATH and RUNTIME_FALLBACK_MODE after make build-mojo.
"""

    issues = audit._find_runtime_encapsulation_issues("page.md", text)

    assert len(issues) == 5
    assert {issue.code for issue in issues} == {"public_runtime_encapsulation_violation"}


def test_runtime_encapsulation_scanner_allows_integrated_runtime_language() -> None:
    audit = _load_module()

    issues = audit._find_runtime_encapsulation_issues(
        "page.md",
        "The signed bundled runtime starts with Algenta and needs no separate setup.",
    )

    assert issues == []


def test_pricing_contract_scanner_rejects_stale_live_rate_limit_page() -> None:
    audit = _load_module()
    text = """# Rate limits & quotas
| Edition | Requests/minute | Monthly execution governance | Workers/device |
| Community | 60 | 10,000 | 1 |
When centrally governed execution reaches its monthly ceiling, retry next month.
"""

    issues = audit._find_pricing_contract_issues(
        "live:/http-api/rate-limits.md",
        text,
    )

    assert {issue.code for issue in issues} == {
        "pricing_contract_required_text_missing",
        "pricing_contract_stale_text",
    }
    assert sum(issue.code == "pricing_contract_stale_text" for issue in issues) == 3


def test_pricing_contract_scanner_accepts_current_source_pages() -> None:
    audit = _load_module()

    for path in (
        ROOT / "gitbook" / "api" / "rate-limits.md",
        ROOT / "gitbook" / "licensing.md",
        ROOT / "gitbook" / "billing.md",
    ):
        rel_path = str(path.relative_to(ROOT / "gitbook"))
        assert audit._find_pricing_contract_issues(rel_path, path.read_text()) == []


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


def test_shell_inventory_keeps_multiline_payload_and_loop_as_single_commands() -> None:
    audit = _load_module()
    body = """curl -sS https://api.example/v1/items \\
  -H 'Content-Type: application/json' \\
  -d '{
    "name": "example"
  }'
for item in one two \\
  three; do
  echo "$item"
done
{"status": "response, not a command"}
"""

    commands = audit._logical_shell_commands(body, start_line=10)

    assert len(commands) == 2
    assert [command.line for command in commands] == [10, 15]
    assert commands[0].command.startswith("curl -sS")
    assert commands[1].command.startswith("for item")
    assert all(audit._validate_shell_command("page.md", command) is None for command in commands)


def test_shell_classifier_guards_environment_references_and_command_substitutions() -> None:
    audit = _load_module()
    cases = {
        'export ALGENTA_BASE_URL="https://api.algenta.ai"': "safe_static",
        "echo '{\"org_name\": \"Acme\"}' > rename.json": "safe_static",
        "echo 'safe & literal' > safe.txt": "safe_static",
        "cat > request.json <<'JSON'\n{\"ok\": true}\nJSON": "safe_static",
        'export ALGENTA_API_KEY="$ALGENTA_API_KEY"': "requires_environment",
        'echo "confidence=$confidence"': "requires_environment",
        'export GATEWAY_URL="$(az deployment group show)"': "requires_environment",
        'export KEY="$(openssl rand -hex 32)"': "requires_environment",
        "echo unsafe > /tmp/out": "static_only",
        "echo unsafe & touch escaped": "static_only",
        "echo unsafe > >(touch escaped)": "static_only",
        "cat > ../out <<'TXT'\nunsafe\nTXT": "static_only",
        (
            "cat > out.json <<'JSON'\n{}\nJSON\n"
            "echo escaped > escaped.txt\nJSON"
        ): "static_only",
        "curl -X POST https://api.example/v1/items": "external_or_mutating",
        "curl https://api.example/v1/items --json '{}'": "external_or_mutating",
        "curl https://api.example/v1/items -d '{}'": "external_or_mutating",
        "de keys create CI": "external_or_mutating",
        "de data refresh dataset_123": "external_or_mutating",
        "rm -rf build": "destructive_mutation",
        "sudo rm -rf build": "destructive_mutation",
    }

    assert {command: audit._classify_shell_command(command) for command in cases} == cases


def test_safe_shell_executor_isolated_file_generation() -> None:
    audit = _load_module()
    command = "cat > request.json <<'JSON'\n{\"ok\": true}\nJSON"

    issue, execution = audit._execute_safe_shell_command(command, "page.md", 12)

    assert issue is None
    assert execution["execution_attempted"] is True
    assert execution["executed"] is True
    assert execution["execution_status"] == "pass"
    assert execution["execution_exit_code"] == 0
    assert execution["files_created"] == [
        {
            "path": "request.json",
            "bytes": 13,
            "sha256": "55f66c2c5aeb275ff5b1ae26b321d5c0b8ceda8c034b19c2643e046d024919f3",
        }
    ]


def test_safe_shell_executor_refuses_environment_dependent_command() -> None:
    audit = _load_module()

    issue, execution = audit._execute_safe_shell_command(
        'export ALGENTA_API_KEY="$ALGENTA_API_KEY"', "page.md", 12
    )

    assert issue is not None
    assert issue.code == "unsafe_command_execution_refused"
    assert execution == {
        "execution_attempted": False,
        "executed": False,
        "execution_status": "refused",
    }


def test_endpoint_inventory_scopes_external_urls_and_route_families() -> None:
    audit = _load_module()
    text = """POST /v1/repositories/{repository_id}/triage
All routes live under /v1/repositories.
External URL: https://metrics.example.com/v1/series
"""

    mentions = audit._extract_endpoint_mentions(text)

    assert [(item.path, item.scope) for item in mentions] == [
        ("/v1/repositories/{}/triage", "algenta"),
        ("/v1/repositories", "algenta"),
        ("/v1/series", "external"),
    ]
    operations = {"/v1/repositories/{}/triage": {"POST"}}
    assert audit._validate_endpoint_mentions("page.md", mentions, operations) == []


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


def test_summary_expected_sitemap_urls_maps_gitbook_navigation(tmp_path: Path) -> None:
    audit = _load_module()
    (tmp_path / "SUMMARY.md").write_text(
        """# Table of contents

* [What Algenta is](overview.md)

## Getting Started

* [Install](install.md)

## Engine runtime

* [Verify the bundled engine](engine/bundled-runtime.md)
* [How the engine works](concepts/engine.md)

## SDKs

* [TypeScript client reference](sdk/typescript/overview.md)
* [MCP server](sdk/mcp.md)

## Microsoft & Azure

* [Algenta for Microsoft Cloud](integrations/microsoft/overview.md)
* [Deploy the decision gateway to your Azure](integrations/azure/gateway.md)

## Deploy & Operate

* [Device key store](operate/device-key-store.md)
""",
        encoding="utf-8",
    )

    assert audit._summary_expected_sitemap_urls(tmp_path, "https://docs.example/") == [
        "https://docs.example",
        "https://docs.example/getting-started/install",
        "https://docs.example/engine-runtime/bundled-runtime",
        "https://docs.example/engine-runtime/engine",
        "https://docs.example/sdks/typescript/overview",
        "https://docs.example/sdks/mcp",
        "https://docs.example/microsoft-and-azure/overview",
        "https://docs.example/microsoft-and-azure/gateway",
        "https://docs.example/deploy-and-operate/device-key-store",
    ]


def test_package_registry_audit_accepts_current_public_sdk_packages(monkeypatch) -> None:
    audit = _load_module()

    def fake_fetch_json(url: str, *, timeout: float = 20.0):
        del timeout
        if url.startswith("https://pypi.org/pypi/"):
            package = url.split("/pypi/", 1)[1].split("/", 1)[0]
            if package in {"algenta-sdk", "algenta-mcp"}:
                return 200, {"info": {"version": "1.0.2", "summary": f"{package} summary"}}
            return 404, None
        if url == "https://registry.npmjs.org/algenta-sdk/latest":
            return 200, {
                "version": "1.0.2",
                "description": "TypeScript SDK for Algenta",
                "license": "Apache-2.0",
            }
        return 500, None

    monkeypatch.setattr(audit, "_fetch_json", fake_fetch_json)

    issues, report = audit._audit_package_registries("pip install algenta-sdk")

    assert issues == []
    assert report["pypi"]["algenta-sdk"]["status"] == 200
    assert report["pypi"]["algenta-mcp"]["status"] == 200
    assert report["pypi"]["algenta"]["status"] == 404
    assert report["npm"]["algenta-sdk"]["version"] == "1.0.2"
    assert report["public_runtime_install_claims"] == 0


def test_package_registry_audit_rejects_public_runtime_install_before_pypi_live(
    monkeypatch,
) -> None:
    audit = _load_module()

    def fake_fetch_json(url: str, *, timeout: float = 20.0):
        del timeout
        if url.startswith("https://pypi.org/pypi/"):
            package = url.split("/pypi/", 1)[1].split("/", 1)[0]
            if package in {"algenta-sdk", "algenta-mcp"}:
                return 200, {"info": {"version": "1.0.2", "summary": f"{package} summary"}}
            return 404, None
        if url == "https://registry.npmjs.org/algenta-sdk/latest":
            return 200, {
                "version": "1.0.2",
                "description": "TypeScript SDK",
                "license": "Apache-2.0",
            }
        return 500, None

    monkeypatch.setattr(audit, "_fetch_json", fake_fetch_json)

    issues, report = audit._audit_package_registries("python3 -m pip install algenta\n")

    assert [issue.code for issue in issues] == ["runtime_package_install_not_live"]
    assert report["public_runtime_install_claims"] == 1


def test_package_registry_audit_rejects_stale_runtime_caveat_after_pypi_live(
    monkeypatch,
) -> None:
    audit = _load_module()

    def fake_fetch_json(url: str, *, timeout: float = 20.0):
        del timeout
        if url.startswith("https://pypi.org/pypi/"):
            package = url.split("/pypi/", 1)[1].split("/", 1)[0]
            if package in {"algenta-sdk", "algenta-mcp", "algenta"}:
                return 200, {"info": {"version": "1.0.2", "summary": f"{package} summary"}}
            return 404, None
        if url == "https://registry.npmjs.org/algenta-sdk/latest":
            return 200, {
                "version": "1.0.2",
                "description": "TypeScript SDK",
                "license": "Apache-2.0",
            }
        return 500, None

    monkeypatch.setattr(audit, "_fetch_json", fake_fetch_json)

    issues, report = audit._audit_package_registries(
        "The runtime distribution is not public on PyPI yet."
    )

    assert [issue.code for issue in issues] == ["stale_runtime_registry_caveat"]
    assert report["pypi"]["algenta"]["status"] == 200


def test_live_audit_checks_every_sitemap_markdown_route(monkeypatch, tmp_path: Path) -> None:
    audit = _load_module()
    fetched_urls: list[str] = []
    (tmp_path / "SUMMARY.md").write_text(
        """# Table of contents

* [What Algenta is](overview.md)

## SDKs

* [MCP server](sdk/mcp.md)

## Help

* [Using these docs with AI](help/ai-access.md)
""",
        encoding="utf-8",
    )
    sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://docs.example</loc></url>
  <url><loc>https://docs.example/sdks/mcp</loc></url>
  <url><loc>https://docs.example/help/ai-access</loc></url>
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
        if (
            url.endswith("/.md")
            or url.endswith("/sdks/mcp.md")
            or url.endswith("/help/ai-access.md")
        ):
            return 200, b"# Algenta page\n", "text/markdown; charset=utf-8"
        return 404, b"not found", "text/plain"

    monkeypatch.setattr(audit, "_fetch", fake_fetch)

    def fake_post_jsonrpc(url: str, payload: dict, **kwargs):
        del url, kwargs
        request_id = payload["id"]
        method = payload["method"]
        if method == "initialize":
            result = {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {"listChanged": True}},
            }
        elif method == "tools/list":
            result = {
                "tools": [
                    _docs_mcp_tool("searchDocumentation", "query"),
                    _docs_mcp_tool("getPage", "url"),
                ]
            }
        elif payload["params"]["name"] == "searchDocumentation":
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": "Install Algenta with algenta-mcp and configure Codex.",
                    }
                ]
            }
        else:
            result = {
                "content": [
                    {"type": "text", "text": "# MCP server\nInstall algenta-mcp for Cursor."}
                ]
            }
        return 200, {"jsonrpc": "2.0", "id": request_id, "result": result}, {}

    monkeypatch.setattr(audit, "_post_jsonrpc", fake_post_jsonrpc)

    issues, report = audit._audit_live("https://docs.example", public_page_count=3, source=tmp_path)

    assert issues == []
    assert report["sitemap_urls"] == 3
    assert report["source_navigation_urls"] == 3
    assert report["sitemap_matches_source_navigation"] is True
    assert report["markdown_pages_checked"] == 3
    assert report["llms_full_pages"] == 1
    assert report["llms_full_complete"] is True
    assert report["docs_mcp"] == {
        "initialize_status": 200,
        "protocol_version": "2025-03-26",
        "tools_status": 200,
        "tools": ["getPage", "searchDocumentation"],
        "tool_url_aliases": [],
        "search_status": 200,
        "page_status": 200,
    }
    assert "https://docs.example/.md" in fetched_urls
    assert "https://docs.example/sdks/mcp.md" in fetched_urls
    assert "https://docs.example/help/ai-access.md" in fetched_urls


def _docs_mcp_tool(name: str, required_input: str) -> dict:
    return {
        "name": name,
        "inputSchema": {
            "type": "object",
            "properties": {required_input: {"type": "string"}},
            "required": [required_input],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    }


def test_parse_jsonrpc_body_accepts_sse_and_json() -> None:
    audit = _load_module()
    payload = {"jsonrpc": "2.0", "id": 7, "result": {"ok": True}}

    assert (
        audit._parse_jsonrpc_body(
            b'event: message\ndata: {"jsonrpc":"2.0","id":7,"result":{"ok":true}}\n\n',
            "text/event-stream; charset=utf-8",
        )
        == payload
    )
    assert audit._parse_jsonrpc_body(json.dumps(payload).encode(), "application/json") == payload


def test_validate_docs_mcp_tools_rejects_mutating_or_untyped_contracts() -> None:
    audit = _load_module()
    search = _docs_mcp_tool("searchDocumentation", "query")
    page = _docs_mcp_tool("getPage", "url")
    search["annotations"]["destructiveHint"] = True
    page["inputSchema"]["properties"]["url"]["type"] = "integer"

    issues, names = audit._validate_docs_mcp_tools([search, page])

    assert names == ["getPage", "searchDocumentation"]
    assert [issue.code for issue in issues] == [
        "docs_mcp_tool_contract_invalid",
        "docs_mcp_tool_contract_invalid",
    ]


def test_validate_docs_mcp_tool_url_aliases_accepts_canonical_redirect(monkeypatch) -> None:
    audit = _load_module()
    search = _docs_mcp_tool("searchDocumentation", "query")
    page = _docs_mcp_tool("getPage", "url")
    page["description"] = "Example: https://docs.algenta.ai//getting-started"
    monkeypatch.setattr(
        audit,
        "_fetch_redirect_target",
        lambda url: (307, "https://docs.algenta.ai/getting-started"),
    )
    monkeypatch.setattr(
        audit,
        "_fetch",
        lambda url: (200, b"canonical page", "text/html"),
    )

    issues, aliases = audit._validate_docs_mcp_tool_url_aliases(
        "https://docs.algenta.ai", [search, page]
    )

    assert issues == []
    assert aliases == [
        {
            "tool": "getPage",
            "example": "https://docs.algenta.ai//getting-started",
            "canonical": "https://docs.algenta.ai/getting-started",
            "redirect_status": 307,
            "redirect_target": "https://docs.algenta.ai/getting-started",
            "canonical_status": 200,
            "equivalent": True,
        }
    ]


def test_validate_docs_mcp_tool_url_aliases_rejects_broken_redirect(monkeypatch) -> None:
    audit = _load_module()
    page = _docs_mcp_tool("getPage", "url")
    page["description"] = "Example: https://docs.algenta.ai//getting-started"
    monkeypatch.setattr(audit, "_fetch_redirect_target", lambda url: (307, "/wrong"))
    monkeypatch.setattr(audit, "_fetch", lambda url: (404, b"missing", "text/html"))

    issues, aliases = audit._validate_docs_mcp_tool_url_aliases("https://docs.algenta.ai", [page])

    assert [issue.code for issue in issues] == ["docs_mcp_noncanonical_tool_url"]
    assert aliases[0]["equivalent"] is False


def test_fetch_llms_full_pages_follows_bounded_pagination(monkeypatch) -> None:
    audit = _load_module()
    fetched_urls: list[str] = []

    def fake_fetch(url: str, *, max_bytes: int = 2_000_000, timeout: float = 30.0):
        del max_bytes, timeout
        fetched_urls.append(url)
        if url.endswith("/llms-full.txt"):
            return (
                200,
                b"# Algenta\nUsing these docs with AI\n\n[Next Page](/llms-full.txt/1)\n",
                "text/plain; charset=utf-8",
            )
        if url.endswith("/llms-full.txt/1"):
            return 200, b"# Oracle Database\nBundled Thin mode.\n", "text/plain"
        return 404, b"not found", "text/plain"

    monkeypatch.setattr(audit, "_fetch", fake_fetch)

    issues, pages, report = audit._fetch_llms_full_pages("https://docs.example")

    assert issues == []
    assert pages == [
        (
            "/llms-full.txt",
            "# Algenta\nUsing these docs with AI\n\n[Next Page](/llms-full.txt/1)\n",
        ),
        ("/llms-full.txt/1", "# Oracle Database\nBundled Thin mode.\n"),
    ]
    assert report == {
        "root_status": 200,
        "pages": 2,
        "bytes": 103,
        "routes": ["/llms-full.txt", "/llms-full.txt/1"],
        "complete": True,
    }
    assert fetched_urls == [
        "https://docs.example/llms-full.txt",
        "https://docs.example/llms-full.txt/1",
    ]


def test_fetch_llms_full_pages_rejects_pagination_cycle(monkeypatch) -> None:
    audit = _load_module()

    def fake_fetch(url: str, *, max_bytes: int = 2_000_000, timeout: float = 30.0):
        del max_bytes, timeout
        if url.endswith("/llms-full.txt"):
            return 200, b"[Next Page](/llms-full.txt/1)\n", "text/plain"
        return 200, b"[Next Page](/llms-full.txt/1)\n", "text/plain"

    monkeypatch.setattr(audit, "_fetch", fake_fetch)

    issues, pages, report = audit._fetch_llms_full_pages("https://docs.example")

    assert len(pages) == 2
    assert [issue.code for issue in issues] == ["llms_full_pagination_cycle"]
    assert report["complete"] is False


def test_fetch_llms_full_pages_rejects_oversized_page(monkeypatch) -> None:
    audit = _load_module()
    monkeypatch.setattr(audit, "_LLMS_FULL_MAX_PAGE_BYTES", 10)

    def fake_fetch(url: str, *, max_bytes: int = 2_000_000, timeout: float = 30.0):
        del url, max_bytes, timeout
        return 200, b"x" * 11, "text/plain"

    monkeypatch.setattr(audit, "_fetch", fake_fetch)

    issues, pages, report = audit._fetch_llms_full_pages("https://docs.example")

    assert pages == []
    assert [issue.code for issue in issues] == ["llms_full_page_too_large"]
    assert report["complete"] is False
