from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.emit_start_local_env_exports import emit_start_local_env_exports

ROOT = Path(__file__).resolve().parents[1]


def test_emit_start_local_env_exports_filters_to_startup_relevant_keys(tmp_path: Path) -> None:
    env_file = tmp_path / "mission.env"
    env_file.write_text(
        "\n".join(
            [
                "ALGENTA_API_KEY=de_live_test",
                'ANTHROPIC_API_KEY="anthropic-secret"',
                "DATABASE_URL=postgresql+psycopg2://should-not-pass",
                "NEXT_PUBLIC_SITE_URL=https://mission.example",
                "ALGENTA_LOCAL_ANTHROPIC_MODEL=claude-custom",
            ]
        ),
        encoding="utf-8",
    )

    exports = emit_start_local_env_exports(env_file)

    assert exports == [
        "export ALGENTA_API_KEY=de_live_test",
        "export ANTHROPIC_API_KEY=anthropic-secret",
        "export ALGENTA_LOCAL_ANTHROPIC_MODEL=claude-custom",
    ]


def test_emit_start_local_env_exports_cli_executes_as_script(tmp_path: Path) -> None:
    env_file = tmp_path / "mission.env"
    env_file.write_text(
        "\n".join(
            [
                "ALGENTA_API_KEY=de_live_test",
                "DATABASE_URL=postgresql+psycopg2://should-not-pass",
                "ALGENTA_LOCAL_ANTHROPIC_MODEL=claude-custom",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "emit_start_local_env_exports.py"), str(env_file)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        "export ALGENTA_API_KEY=de_live_test",
        "export ALGENTA_LOCAL_ANTHROPIC_MODEL=claude-custom",
    ]
    assert "DATABASE_URL" not in result.stdout
