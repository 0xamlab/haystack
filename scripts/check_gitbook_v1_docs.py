from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = ROOT / "apps" / "docs" / "docs"
MANIFEST_PATH = ROOT / "apps" / "docs" / "gitbook_v1_navigation.json"

EXPECTED_SECTION_LABELS = [
    "🧭 Overview",
    "⚡ Quickstart",
    "⚙️ Operations",
    "🛠️ Operations (Advanced)",
    "🔐 API Authentication",
    "📦 SDKs",
]

EXPECTED_SUPPORT_BOUNDARIES = """| Area | Status |
| --- | --- |
| Single VM + Compose | ✅ Supported |
| API + Worker | ✅ Supported |
| Backup/Restore | ✅ Supported |
| SDK usage | ⚠️ Best effort / secondary |
| Kubernetes | ❌ Not supported |
| UI/Portal | ❌ Not included |"""


class GitBookValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ManifestPage:
    title: str
    path: Path
    slug: str


def _load_manifest() -> dict[str, object]:
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GitBookValidationError(f"Missing manifest: {MANIFEST_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise GitBookValidationError(f"Invalid manifest JSON: {exc}") from exc


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise GitBookValidationError(f"Missing docs page: {path}") from exc


def _extract_h1(text: str, path: Path) -> str:
    match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if not match:
        raise GitBookValidationError(f"Missing H1 in {path}")
    return match.group(1).strip()


def _validate_manifest_pages(manifest: dict[str, object]) -> list[ManifestPage]:
    sections = manifest.get("sections")
    if not isinstance(sections, list):
        raise GitBookValidationError("Manifest sections must be a list")

    labels = []
    pages: list[ManifestPage] = []
    for section in sections:
        if not isinstance(section, dict):
            raise GitBookValidationError("Manifest section entries must be objects")
        label = section.get("label")
        if not isinstance(label, str):
            raise GitBookValidationError("Each manifest section must have a string label")
        labels.append(label)
        section_pages = section.get("pages")
        if not isinstance(section_pages, list) or not section_pages:
            raise GitBookValidationError(f"Section {label!r} must contain pages")
        for page in section_pages:
            if not isinstance(page, dict):
                raise GitBookValidationError(f"Section {label!r} contains an invalid page entry")
            title = page.get("title")
            raw_path = page.get("path")
            slug = page.get("slug")
            if (
                not isinstance(title, str)
                or not isinstance(raw_path, str)
                or not isinstance(slug, str)
            ):
                raise GitBookValidationError(
                    f"Section {label!r} contains a page with invalid fields"
                )
            pages.append(ManifestPage(title=title, path=ROOT / raw_path, slug=slug))

    if labels != EXPECTED_SECTION_LABELS:
        raise GitBookValidationError(f"Unexpected manifest labels: {labels!r}")
    return pages


def _validate_manifest_exclusions(manifest: dict[str, object], included_paths: set[Path]) -> None:
    excluded = manifest.get("exclude_from_primary_nav")
    if not isinstance(excluded, list):
        raise GitBookValidationError("Manifest exclude_from_primary_nav must be a list")

    required_exclusions = {
        ROOT / "apps" / "docs" / "docs" / "integrations" / "local-runtime.md",
        ROOT / "apps" / "docs" / "docs" / "mcp.md",
        ROOT / "apps" / "docs" / "docs" / "api-reference" / "capability-plane.md",
        ROOT / "apps" / "docs" / "docs" / "direct-api-client.md",
        ROOT / "apps" / "docs" / "docs" / "supported-secondary-modes.md",
    }
    excluded_paths = {ROOT / raw for raw in excluded if isinstance(raw, str)}
    missing = sorted(str(path) for path in required_exclusions - excluded_paths)
    if missing:
        raise GitBookValidationError(f"Missing required exclusions: {missing}")

    overlap = included_paths & excluded_paths
    if overlap:
        rendered = ", ".join(sorted(str(path) for path in overlap))
        raise GitBookValidationError(f"Excluded pages appear in primary nav: {rendered}")


def _validate_title_contract(pages: list[ManifestPage]) -> None:
    for page in pages:
        text = _read_text(page.path)
        heading = _extract_h1(text, page.path)
        if heading != page.title:
            raise GitBookValidationError(
                "Manifest title mismatch for "
                f"{page.path}: expected {page.title!r}, found {heading!r}"
            )
        if any(icon in heading for icon in "🧭⚡⚙️🛠️🔐📦"):
            raise GitBookValidationError(f"Page title must not contain sidebar icons: {page.path}")


def _validate_overview() -> None:
    text = _read_text(DOCS_ROOT / "index.md")
    if "curl -sSL https://codna.ai/install.sh | bash" not in text:
        raise GitBookValidationError("Overview must contain the install command")
    if "Open [Quickstart](/quickstart)." not in text:
        raise GitBookValidationError("Overview must link directly to Quickstart")
    if "from algenta import Runtime" in text:
        raise GitBookValidationError("Overview must not lead with the local runtime")
    if "Backup & Recovery" in text:
        raise GitBookValidationError("Overview must not mention backup and recovery")


def _validate_quickstart() -> None:
    text = _read_text(DOCS_ROOT / "quickstart.md")
    required_snippets = [
        "In this guide you will:",
        "curl -sSL https://codna.ai/install.sh | bash",
        "curl http://localhost:8000/v1/health",
        "export ALGENTA_API_KEY='<SELF_HOST_BOOTSTRAP_KEY>'",
        "curl -X POST http://localhost:8000/v1/simulate \\",
        '"objective": "maximize_net_value"',
        "No SDK or Python install is required to use Algenta.",
        "Next: Configure production setup -> [Operations](/operations)",
    ]
    for snippet in required_snippets:
        if snippet not in text:
            raise GitBookValidationError(f"Quickstart is missing required content: {snippet}")

    forbidden = [
        "Backup & Recovery",
        "pip install algenta-sdk",
        "pip install algenta-core",
        "TLS & Reverse Proxy",
    ]
    for snippet in forbidden:
        if snippet in text:
            raise GitBookValidationError(f"Quickstart contains forbidden content: {snippet}")


def _validate_operations_and_advanced() -> None:
    backup = _read_text(DOCS_ROOT / "operations-advanced" / "backup-and-recovery.md")
    troubleshooting = _read_text(DOCS_ROOT / "operations-advanced" / "troubleshooting.md")
    support = _read_text(DOCS_ROOT / "operations-advanced" / "support-boundaries.md")
    logs = _read_text(DOCS_ROOT / "operations" / "logs-and-metrics.md")

    required_backup_text = (
        "This section is for operators managing backup, restore, and disaster recovery. "
        "It is not required for first-time setup. "
        "Configure backups after initial deployment and validation."
    )
    if required_backup_text not in backup:
        raise GitBookValidationError("Backup & Recovery is missing the operator-only warning")

    troubleshooting_checks = [
        "docker info",
        "docker compose -f infra/docker/docker-compose.selfhosted.yml ps",
        "curl http://localhost:8000/v1/health",
        "logs --tail=200 api",
        "logs --tail=200 worker",
    ]
    for snippet in troubleshooting_checks:
        if snippet not in troubleshooting:
            raise GitBookValidationError(
                f"Troubleshooting is missing command-first entry: {snippet}"
            )

    if EXPECTED_SUPPORT_BOUNDARIES not in support:
        raise GitBookValidationError("Support Boundaries table does not match the required format")

    if "curl http://localhost:8000/metrics" not in logs:
        raise GitBookValidationError("Logs & Metrics must document the local metrics endpoint")
    if "X-Metrics-Secret" not in logs:
        raise GitBookValidationError("Logs & Metrics must document the remote metrics header")


def _validate_sdk_crosslinks() -> None:
    for path in [
        DOCS_ROOT / "sdks" / "python.md",
        DOCS_ROOT / "sdks" / "typescript.md",
        DOCS_ROOT / "api-reference" / "authentication.md",
    ]:
        text = _read_text(path)
        if "[Quickstart](/quickstart)" not in text:
            raise GitBookValidationError(f"{path} must link back to Quickstart")
        if (
            path.name != "authentication.md"
            and "[API Authentication](/api-reference/authentication)" not in text
        ):
            raise GitBookValidationError(f"{path} must link to API Authentication")


def _validate_secondary_docs_do_not_override_primary_path() -> None:
    api_reference = _read_text(DOCS_ROOT / "api-reference" / "index.md")
    direct_client = _read_text(DOCS_ROOT / "direct-api-client.md")

    if "## First-run decision endpoints" not in api_reference:
        raise GitBookValidationError(
            "API Reference must identify the first-run decision endpoints section"
        )
    if "## Structured data runtime endpoints" not in api_reference:
        raise GitBookValidationError(
            "API Reference must identify the structured data runtime endpoints section"
        )
    if "secondary to the runtime-first docs story" in api_reference:
        raise GitBookValidationError(
            "API Reference must not describe the first-run path as secondary"
        )
    if "The primary published development/runtime path is:" in direct_client:
        raise GitBookValidationError("Direct API Client must not redefine the primary product path")


def main() -> int:
    manifest = _load_manifest()
    if manifest.get("scope") != "self_hosted_v1":
        raise GitBookValidationError("Manifest scope must be self_hosted_v1")

    pages = _validate_manifest_pages(manifest)
    _validate_manifest_exclusions(manifest, {page.path for page in pages})
    _validate_title_contract(pages)
    _validate_overview()
    _validate_quickstart()
    _validate_operations_and_advanced()
    _validate_sdk_crosslinks()
    _validate_secondary_docs_do_not_override_primary_path()

    print("GitBook v1 docs contract is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
