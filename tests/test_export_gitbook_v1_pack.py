from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "export_gitbook_v1_pack.py"
MAKEFILE = ROOT / "Makefile"
PUBLISHING_GUIDE = ROOT / "apps" / "docs" / "GITBOOK_V1_PUBLISHING.md"


def test_export_gitbook_v1_pack_creates_bundle(tmp_path: Path) -> None:
    output_dir = tmp_path / "gitbook-pack"
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), "--output-dir", str(output_dir)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert output_dir.exists()
    assert (output_dir / "navigation.json").exists()
    assert (output_dir / "IMPORT_ORDER.md").exists()
    assert (output_dir / "README.md").exists()
    assert (output_dir / "excluded-from-primary-nav.txt").exists()
    assert (output_dir / "GITBOOK_V1_PUBLISHING.md").exists()

    pages_dir = output_dir / "pages"
    assert (pages_dir / "01-overview" / "01-overview.md").exists()
    assert (pages_dir / "02-quickstart" / "01-quickstart.md").exists()
    assert (pages_dir / "03-operations" / "02-setup-configuration.md").exists()
    assert (pages_dir / "04-operations-advanced" / "02-backup-recovery.md").exists()
    assert (pages_dir / "05-api-authentication" / "01-api-authentication.md").exists()
    assert (pages_dir / "06-sdks" / "01-python-sdk.md").exists()
    assert (pages_dir / "06-sdks" / "02-typescript-sdk.md").exists()

    readme = (output_dir / "README.md").read_text(encoding="utf-8")
    assert "GitBook v1 Export Pack" in readme
    assert "🧭 Overview" in readme
    assert "⚡ Quickstart" in readme


def test_makefile_and_publishing_guide_reference_gitbook_pack_export() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")
    guide = PUBLISHING_GUIDE.read_text(encoding="utf-8")

    assert "docs-gitbook-pack:" in makefile
    assert "docs-gitbook-verify: docs-gitbook-status docs-gitbook-pack" in makefile
    assert "scripts/export_gitbook_v1_pack.py" in makefile
    assert "make docs-gitbook-verify" in guide
    assert "scripts/export_gitbook_v1_pack.py" in guide
