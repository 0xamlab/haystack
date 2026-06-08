from __future__ import annotations

from pathlib import Path

import pytest

from scripts.emit_env_exports import emit_env_exports


def test_emit_env_exports_supports_dotenv_quotes_and_export_prefix(tmp_path: Path) -> None:
    env_file = tmp_path / "mission.env"
    env_file.write_text(
        "\n".join(
            [
                "# comment",
                "ALGENTA_API_KEY=de_live_test",
                'ANTHROPIC_API_KEY="sk-ant&ropic value"',
                "export OPENAI_API_KEY='sk-openai with spaces'",
            ]
        ),
        encoding="utf-8",
    )

    exports = emit_env_exports(env_file)

    assert exports == [
        "export ALGENTA_API_KEY=de_live_test",
        "export ANTHROPIC_API_KEY='sk-ant&ropic value'",
        "export OPENAI_API_KEY='sk-openai with spaces'",
    ]


def test_emit_env_exports_rejects_invalid_lines(tmp_path: Path) -> None:
    env_file = tmp_path / "broken.env"
    env_file.write_text("NOT_VALID\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must use KEY=value syntax"):
        emit_env_exports(env_file)


def test_emit_env_exports_rejects_invalid_variable_names(tmp_path: Path) -> None:
    env_file = tmp_path / "broken.env"
    env_file.write_text("BAD-KEY=value\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid environment variable name"):
        emit_env_exports(env_file)
