from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
TEST_FILES = ROOT / "test_files"


def _pythonpath() -> str:
    return os.pathsep.join([str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)])


def test_algenta_cli_import_runs_cleanly(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text(
        "product_line,revenue,region\nElectronics,42193221,US\nApparel,28114992,US\n",
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["PYTHONPATH"] = _pythonpath()
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "algenta.cli", "import", str(source), "--name", "orders"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "Algenta Source Import" in proc.stdout
    assert "Source: orders" in proc.stdout
    assert "Import preview complete." in proc.stdout
    assert "Use Python Runtime() for a persistent local session:" in proc.stdout


def test_algenta_cli_import_missing_file_exits_non_zero() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = _pythonpath()
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "algenta.cli", "import", "missing_orders.csv"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "Error: file not found" in proc.stdout


def test_algenta_cli_import_bundle_runs_cleanly_for_real_march_corpus() -> None:
    orders = TEST_FILES / "850a28da-a6f7-4ecc-9e7a-51a9cf7f501b-united_states.csv"
    financial = TEST_FILES / "aaeff3ab-19ac-494e-9e58-e507bd7e3893-united_states.csv"
    inaccurate = (
        TEST_FILES
        / "630a0f6c-a250-4bd7-af2e-bed6184619ac_top_inaccurate_items_v3_2026-03-01_2026-03-31.csv"
    )
    ratings = (
        TEST_FILES
        / "3d9b2e55-c7ea-4e31-90ea-ca5797a69c2b_restaurant_rating_sku_local_2026-03-01_2026-03-31.csv"
    )
    empty_export = (
        TEST_FILES / "549c63c8-3300-416c-8b45-55fec4c6529a_store_pause_2026-03-01_2026-03-31.csv"
    )

    env = dict(os.environ)
    env["PYTHONPATH"] = _pythonpath()
    proc = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "algenta.cli",
            "import",
            str(orders),
            str(financial),
            str(inaccurate),
            str(ratings),
            str(empty_export),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "Algenta Source Bundle" in proc.stdout
    assert "Imported: 4 | Failures: 1" in proc.stdout
    assert "store_pause" in proc.stdout
    assert "empty_source" in proc.stdout
    assert "rt.connect_many([" in proc.stdout
