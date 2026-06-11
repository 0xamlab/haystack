from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_ignored_standalone_runners_do_not_reenter_pytest() -> None:
    targets = (
        ROOT / "tests" / "integration" / "test_go_live_connectivity_real.py",
        ROOT / "tests" / "integration" / "test_exports.py",
        ROOT / "tests" / "integration" / "test_runtime_libraries_http_live.py",
    )

    violations: list[str] = []
    for path in targets:
        text = path.read_text(encoding="utf-8")
        if "pytest.main([__file__" in text:
            violations.append(path.name)

    assert not violations, (
        "Ignored standalone runners must execute their own main() entrypoints "
        f"instead of recursing into pytest: {violations}"
    )
