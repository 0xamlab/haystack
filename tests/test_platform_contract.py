from __future__ import annotations

import json
from pathlib import Path

from apps.api_server.main import app

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "apps" / "docs" / "integration_manifest.v1.json"


def test_manifest_declares_canonical_contract() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    assert manifest["brand"] == "Algenta"
    assert manifest["api_base_url"] == "https://api.algenta.ai"
    assert manifest["mcp_endpoint"] == "https://api.algenta.ai/mcp/sse"
    assert manifest["auth_scheme"] == "bearer_api_key"
    assert manifest["api_key_prefixes"] == {"live": "de_live_", "test": "de_test_"}
    assert manifest["compatibility"]["deprecation_window_days"] == 90


def test_manifest_integrations_have_required_fields() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    required = {
        "name",
        "description",
        "icon",
        "capabilities",
        "auth_scheme",
        "required_scopes",
        "read_only_default",
        "write_actions",
        "admin_controls",
        "docs_url",
        "privacy_url",
        "terms_url",
        "support_url",
        "regions",
        "status",
    }
    integrations = manifest["integrations"]
    assert integrations
    for integration in integrations:
        assert required.issubset(integration)


def test_openapi_uses_canonical_bearer_contract() -> None:
    schema = app.openapi()
    security = schema["components"]["securitySchemes"]
    assert schema["servers"] == [{"url": "https://api.algenta.ai"}]
    assert schema["x-canonical-mcp-endpoint"] == "https://api.algenta.ai/mcp/sse"
    assert "BearerAuth" in security
    assert security["BearerAuth"]["scheme"] == "bearer"
    assert "LegacyApiKey" in security
    protected = schema["paths"]["/v1/jobs"]["post"]["security"]
    assert protected == [{"BearerAuth": []}]
    decision_params = {
        param["name"]
        for param in schema["paths"]["/v1/decisions"]["get"]["parameters"]
    }
    assert "page" in decision_params
    assert "limit" in decision_params
    for path in [
        "/v1/data",
        "/v1/datasets",
        "/v1/sources",
        "/v1/triggers",
        "/v1/connectors",
        "/v1/team",
        "/v1/api-keys",
        "/v1/distributions",
        "/v1/templates",
        "/v1/device/list",
        "/v1/engines",
        "/v1/simulate/templates",
    ]:
        param_names = {param["name"] for param in schema["paths"][path]["get"]["parameters"]}
        assert "page" in param_names
        assert "limit" in param_names


def test_docs_use_canonical_urls_and_bearer_examples() -> None:
    doc_paths = [
        ROOT / "apps" / "docs" / "docs" / "index.md",
        ROOT / "apps" / "docs" / "docs" / "quickstart.md",
        ROOT / "apps" / "docs" / "docs" / "api-reference" / "index.md",
        ROOT / "apps" / "docs" / "docs" / "api-reference" / "authentication.md",
        ROOT / "apps" / "docs" / "docs" / "integrations" / "chatgpt-actions.md",
        ROOT / "apps" / "docs" / "docs" / "integrations" / "claude-codex.md",
        ROOT / "apps" / "docs" / "docs" / "integrations" / "n8n.md",
        ROOT / "apps" / "docs" / "docs" / "integrations" / "azure-ai-studio.md",
        ROOT / "apps" / "docs" / "docs" / "integrations" / "local-runtime.md",
        ROOT / "apps" / "docs" / "docs" / "integrations" / "overview.md",
        ROOT / "apps" / "docs" / "docs" / "integrations" / "make.md",
        ROOT / "apps" / "docs" / "docusaurus.config.js",
        ROOT / "apps" / "docs" / "sidebars.js",
        ROOT / "apps" / "mcp_server" / "README.md",
        ROOT / "apps" / "mcp_server" / "server.py",
        ROOT / "apps" / "mcp_server" / "config.py",
    ]
    for path in doc_paths:
        text = path.read_text()
        assert "api.decisionengine.io" not in text, path
        assert "api.algenta.io" not in text, path
    assert "Authorization: Bearer" in (ROOT / "apps" / "docs" / "docs" / "quickstart.md").read_text()


def test_public_docs_and_examples_have_no_stale_hosts_or_key_prefixes() -> None:
    targets = [
        ROOT / "apps" / "docs" / "docs",
        ROOT / "examples",
        ROOT / "apps" / "mcp_server",
    ]
    forbidden = ["api.decisionengine.io", "api.algenta.io", "docs.decisionengine.io", "alg_live_"]
    suffixes = {".md", ".json", ".yaml", ".yml", ".py", ".js", ".ts"}

    files: list[Path] = []
    for target in targets:
        if target.is_file():
            files.append(target)
            continue
        for path in target.rglob("*"):
            if path.is_file() and path.suffix in suffixes:
                files.append(path)

    offenders: list[str] = []
    for path in files:
        text = path.read_text()
        for needle in forbidden:
            if needle in text:
                offenders.append(f"{path}: {needle}")
    assert not offenders, "\n".join(offenders)


def test_error_docs_cover_scope_and_idempotency_contract() -> None:
    auth_text = (ROOT / "apps" / "docs" / "docs" / "api-reference" / "authentication.md").read_text()
    errors_text = (ROOT / "apps" / "docs" / "docs" / "api-reference" / "errors.md").read_text()
    assert "access_scope_denied" in auth_text
    assert "access_scope_denied" in errors_text
    assert "resource_write_conflict" in errors_text
    assert "idempotency_key_conflict" in errors_text


def test_integration_docs_cover_primary_surfaces() -> None:
    sidebar = (ROOT / "apps" / "docs" / "sidebars.js").read_text()
    overview = (ROOT / "apps" / "docs" / "docs" / "integrations" / "overview.md").read_text()

    required_ids = [
        "integrations/chatgpt-actions",
        "integrations/claude-codex",
        "integrations/n8n",
        "integrations/azure-ai-studio",
        "integrations/local-runtime",
    ]
    for entry in required_ids:
        assert entry in sidebar

    required_paths = [
        ROOT / "apps" / "docs" / "docs" / "integrations" / "claude-codex.md",
        ROOT / "apps" / "docs" / "docs" / "integrations" / "azure-ai-studio.md",
        ROOT / "apps" / "docs" / "docs" / "integrations" / "local-runtime.md",
        ROOT / "examples" / "chatgpt-actions" / "README.md",
        ROOT / "examples" / "n8n" / "README.md",
        ROOT / "examples" / "local-runtime" / "README.md",
    ]
    for path in required_paths:
        assert path.exists(), path

    assert "/integrations/claude-codex" in overview
    assert "/integrations/azure-ai-studio" in overview
    assert "/integrations/local-runtime" in overview
