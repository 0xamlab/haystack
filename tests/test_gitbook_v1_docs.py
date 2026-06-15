from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_gitbook_v1_docs.py"
MAKEFILE = ROOT / "Makefile"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
README = ROOT / "README.md"
API_REFERENCE_INDEX = ROOT / "apps" / "docs" / "docs" / "api-reference" / "index.md"
DIRECT_API_CLIENT = ROOT / "apps" / "docs" / "docs" / "direct-api-client.md"
PUBLISHING_GUIDE = ROOT / "apps" / "docs" / "GITBOOK_V1_PUBLISHING.md"


def test_gitbook_v1_validator_script_passes() -> None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "GitBook v1 docs contract is valid." in proc.stdout


def test_makefile_exposes_gitbook_docs_targets() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")

    assert "docs-gitbook-status:" in text
    assert "docs-gitbook-pack:" in text
    assert "docs-gitbook-verify: docs-gitbook-status docs-gitbook-pack" in text
    assert "scripts/check_gitbook_v1_docs.py" in text


def test_gitbook_publishing_guide_exists_and_tracks_manifest() -> None:
    text = PUBLISHING_GUIDE.read_text(encoding="utf-8")

    assert "GitBook v1 Publishing Guide" in text
    assert "apps/docs/gitbook_v1_navigation.json" in text
    assert "`🧭 Overview`" in text
    assert "`⚡ Quickstart`" in text
    assert "`⚙️ Operations`" in text
    assert "`🛠️ Operations (Advanced)`" in text
    assert "`🔐 API Authentication`" in text
    assert "`📦 SDKs`" in text
    assert "Exclude from the primary nav" in text
    assert "`apps/docs/docs/api-reference/capability-plane.md`" in text
    assert "make docs-gitbook-verify" in text


def test_ci_enforces_gitbook_docs_verification() -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "Verify GitBook v1 docs pack" in text
    assert "make docs-gitbook-verify" in text


def test_readme_and_api_reference_point_first_time_users_to_quickstart() -> None:
    readme = README.read_text(encoding="utf-8")
    api_reference = API_REFERENCE_INDEX.read_text(encoding="utf-8")
    direct_api_client = DIRECT_API_CLIENT.read_text(encoding="utf-8")
    docs_index = (ROOT / "apps" / "docs" / "docs" / "index.md").read_text(encoding="utf-8")
    integrations_overview = (
        ROOT / "apps" / "docs" / "docs" / "integrations" / "overview.md"
    ).read_text(encoding="utf-8")

    assert "Start with [Quickstart](./apps/docs/docs/quickstart.md)" in readme
    assert (
        "If you are deploying the product, start with [Quickstart](./apps/docs/docs/quickstart.md)."
        in readme
    )
    assert "POST /v1/capabilities/route" in readme
    assert "./examples/capability-plane/README.md" in readme
    assert "`algenta_managed` routes can execute through Codna" in readme
    assert "`client_managed` routes" in readme
    assert "make capability-plane-verify" in readme
    assert (
        "Start with [Quickstart](/quickstart) if you are bringing up a self-hosted service for the first time."
        in api_reference
    )
    assert "## First-run decision endpoints" in api_reference
    assert "## Structured data runtime endpoints" in api_reference
    assert "## Unified capability-plane endpoints" in api_reference
    assert "/api-reference/capability-plane" in api_reference
    assert "make capability-plane-verify" in api_reference
    assert "secondary to the runtime-first docs story" not in api_reference
    assert "The primary published development/runtime path is:" not in direct_api_client
    assert "POST /v1/capabilities/route" in docs_index
    assert "/api-reference/capability-plane" in docs_index
    assert "`algenta_managed` routes can execute through Codna" in docs_index
    assert "`client_managed` routes" in docs_index
    assert "client.route_capabilities(...)" in direct_api_client
    assert "client.routeCapabilities({ ... })" in direct_api_client
    assert "examples/capability-plane/" in direct_api_client
    assert "POST /v1/capabilities/route" in integrations_overview
    assert "route_capabilities(...)" in integrations_overview
