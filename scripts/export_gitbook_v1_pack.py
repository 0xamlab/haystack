from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "apps" / "docs" / "gitbook_v1_navigation.json"
PUBLISHING_GUIDE_PATH = ROOT / "apps" / "docs" / "GITBOOK_V1_PUBLISHING.md"
DEFAULT_OUTPUT_DIR = ROOT / "build" / "gitbook-v1"


class ExportError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExportPage:
    title: str
    source_path: Path
    slug: str


@dataclass(frozen=True)
class ExportSection:
    label: str
    pages: list[ExportPage]


def _slugify(value: str) -> str:
    cleaned = re.sub(r"^[^\w]+", "", value, flags=re.UNICODE)
    asciiish = re.sub(r"[^A-Za-z0-9]+", "-", cleaned).strip("-").lower()
    return asciiish or "page"


def _load_manifest() -> tuple[list[ExportSection], list[str]]:
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ExportError(f"Missing manifest: {MANIFEST_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise ExportError(f"Invalid manifest JSON: {exc}") from exc

    raw_sections = manifest.get("sections")
    raw_exclusions = manifest.get("exclude_from_primary_nav")
    if not isinstance(raw_sections, list):
        raise ExportError("Manifest sections must be a list")
    if not isinstance(raw_exclusions, list):
        raise ExportError("Manifest exclude_from_primary_nav must be a list")

    sections: list[ExportSection] = []
    for section in raw_sections:
        if not isinstance(section, dict):
            raise ExportError("Manifest section entries must be objects")
        label = section.get("label")
        raw_pages = section.get("pages")
        if not isinstance(label, str) or not isinstance(raw_pages, list):
            raise ExportError("Manifest section entries must contain label and pages")

        pages: list[ExportPage] = []
        for page in raw_pages:
            if not isinstance(page, dict):
                raise ExportError(f"Section {label!r} contains an invalid page entry")
            title = page.get("title")
            raw_path = page.get("path")
            slug = page.get("slug")
            if (
                not isinstance(title, str)
                or not isinstance(raw_path, str)
                or not isinstance(slug, str)
            ):
                raise ExportError(f"Section {label!r} contains a page with invalid fields")
            pages.append(ExportPage(title=title, source_path=ROOT / raw_path, slug=slug))

        sections.append(ExportSection(label=label, pages=pages))

    exclusions = [str(path) for path in raw_exclusions if isinstance(path, str)]
    return sections, exclusions


def _write_import_order(output_dir: Path, sections: list[ExportSection]) -> None:
    lines = ["# GitBook v1 Import Order", ""]
    for section_index, section in enumerate(sections, start=1):
        lines.append(f"{section_index}. {section.label}")
        for page_index, page in enumerate(section.pages, start=1):
            lines.append(f"   {section_index}.{page_index} {page.title} -> {page.slug}")
        lines.append("")
    (output_dir / "IMPORT_ORDER.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _write_bundle_readme(output_dir: Path, sections: list[ExportSection]) -> None:
    lines = [
        "# GitBook v1 Export Pack",
        "",
        "This bundle is generated from `apps/docs/gitbook_v1_navigation.json`.",
        "",
        "Use it when configuring the external GitBook workspace.",
        "",
        "## Contents",
        "",
        "- `navigation.json` — canonical section/page ordering",
        "- `IMPORT_ORDER.md` — copy order for GitBook page creation",
        "- `excluded-from-primary-nav.txt` — pages that must stay out of the launch sidebar",
        "- `pages/` — copied markdown files grouped by top-level section",
        "- `GITBOOK_V1_PUBLISHING.md` — publishing rules and checklist",
        "",
        "## Sections",
        "",
    ]
    for section in sections:
        lines.append(f"- {section.label}")
        for page in section.pages:
            lines.append(f"  - {page.title}")
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_bundle(output_dir: Path) -> Path:
    sections, exclusions = _load_manifest()

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(MANIFEST_PATH, output_dir / "navigation.json")
    shutil.copy2(PUBLISHING_GUIDE_PATH, output_dir / "GITBOOK_V1_PUBLISHING.md")
    (output_dir / "excluded-from-primary-nav.txt").write_text(
        "\n".join(exclusions) + "\n", encoding="utf-8"
    )

    pages_root = output_dir / "pages"
    pages_root.mkdir(parents=True, exist_ok=True)

    for section_index, section in enumerate(sections, start=1):
        section_dir = pages_root / f"{section_index:02d}-{_slugify(section.label)}"
        section_dir.mkdir(parents=True, exist_ok=True)
        for page_index, page in enumerate(section.pages, start=1):
            page_name = f"{page_index:02d}-{_slugify(page.title)}.md"
            shutil.copy2(page.source_path, section_dir / page_name)

    _write_import_order(output_dir, sections)
    _write_bundle_readme(output_dir, sections)
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the GitBook v1 publishing pack.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Destination directory. Default: {DEFAULT_OUTPUT_DIR}",
    )
    args = parser.parse_args()

    output_dir = export_bundle(args.output_dir)
    print(f"Exported GitBook v1 pack to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
