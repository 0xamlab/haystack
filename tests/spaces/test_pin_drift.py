"""apps/spaces/tools/pin_drift.py — pins, pre-releases, hashes and cross-Space drift."""

from __future__ import annotations

from pathlib import Path

import pin_drift as pd
import pytest

WHEEL = "https://github.com/thyn-ai/mojo-kernels/releases/download/arena-wheels-v0.1.1-dev/bm25_mojo-0.1.4.dev1-py3-none-manylinux_2_35_x86_64.whl"
WHEEL_OK = "https://github.com/thyn-ai/mojo-kernels/releases/download/arena-wheels-v0.1.0/cclib_mojo-0.1.2-py3-none-manylinux_2_35_x86_64.whl"


def _write(d: Path, name: str, text: str) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(text, encoding="utf-8")
    return p


def test_parse_specs_urls_and_options(tmp_path: Path) -> None:
    f = _write(
        tmp_path / "a",
        "requirements.txt",
        "\n".join(
            [
                "# comment",
                "--index-url https://pypi.org/simple",
                "-r base.txt",
                "gradio>=6.0,<7.0",
                "numpy",
                "algenta==1.0.18  # inline comment",
                "Algenta_SDK[extra]==1.0.18 ; python_version >= '3.12'",
                "pkg===1.0",
                "wild==1.0.*",
                WHEEL,
                WHEEL_OK,
                "https://example.com/not-a-wheel.tar.gz",
                "mypkg @ https://example.com/mypkg.whl",
                "torch==2.9.1 \\",
                "    --hash=sha256:abc \\",
                "    --hash=sha256:def",
                "",
            ]
        ),
    )
    reqs = {r.raw: r for r in pd.parse_requirements(f)}
    assert set(reqs) == {
        "gradio>=6.0,<7.0",
        "numpy",
        "algenta==1.0.18",
        "Algenta_SDK[extra]==1.0.18 ; python_version >= '3.12'",
        "pkg===1.0",
        "wild==1.0.*",
        WHEEL,
        WHEEL_OK,
        "https://example.com/not-a-wheel.tar.gz",
        "mypkg @ https://example.com/mypkg.whl",
        "torch==2.9.1 --hash=sha256:abc --hash=sha256:def",
    }
    assert not reqs["gradio>=6.0,<7.0"].pinned and reqs["gradio>=6.0,<7.0"].name == "gradio"
    assert not reqs["numpy"].pinned
    assert reqs["algenta==1.0.18"].pinned and reqs["algenta==1.0.18"].version == "1.0.18"
    sdk = reqs["Algenta_SDK[extra]==1.0.18 ; python_version >= '3.12'"]
    assert sdk.name == "algenta-sdk" and sdk.pinned and sdk.version == "1.0.18"
    assert reqs["pkg===1.0"].pinned and reqs["pkg===1.0"].version == "1.0"
    assert not reqs["wild==1.0.*"].pinned
    wheel = reqs[WHEEL]
    assert (
        wheel.name == "bm25-mojo"
        and wheel.version == "0.1.4.dev1"
        and wheel.pinned
        and wheel.prerelease
    )
    assert reqs[WHEEL_OK].version == "0.1.2" and not reqs[WHEEL_OK].prerelease
    assert not reqs["https://example.com/not-a-wheel.tar.gz"].pinned
    assert not reqs["mypkg @ https://example.com/mypkg.whl"].pinned
    torch = reqs["torch==2.9.1 --hash=sha256:abc --hash=sha256:def"]
    assert torch.pinned and torch.hashed and torch.line == 14
    assert reqs["algenta==1.0.18"].line == 6


@pytest.mark.parametrize(
    ("version", "pre"),
    [
        ("1.0.18", False),
        ("0.1.4.dev1", True),
        ("2.0rc1", True),
        ("2.0.0a1", True),
        ("2.0.0b3", True),
        ("1.0.0-beta.2", True),
        ("2024.8.26", False),
        ("1.2.3+cu128", False),
        ("0.60.2", False),
        ("3.0.2", False),
        ("1.0.0.post1", False),
    ],
)
def test_prerelease_detection(version: str, pre: bool) -> None:
    r = pd.Requirement("x", version, True, False, Path("r.txt"), 1, "x")
    assert r.prerelease is pre


def test_check_requirements_codes(tmp_path: Path) -> None:
    f = _write(tmp_path / "s", "requirements.txt", f"gradio>=6\nalgenta==1.0.18\n{WHEEL}\n")
    reqs = pd.parse_requirements(f)
    codes = [(x.line, x.code) for x in pd.check_requirements(reqs, require_hashes=False)]
    assert codes == [(1, "unpinned"), (3, "prerelease")]
    codes = [(x.line, x.code) for x in pd.check_requirements(reqs, require_hashes=True)]
    assert codes == [(1, "unpinned"), (2, "unhashed"), (3, "prerelease"), (3, "unhashed")]


def test_drift_across_spaces(tmp_path: Path) -> None:
    _write(tmp_path / "algenta", "requirements.txt", "algenta==1.0.18\nnumpy==2.2.0\n")
    _write(tmp_path / "algenta", "arena-requirements.txt", "numpy==2.2.0\n")
    _write(tmp_path / "governed-agent", "requirements.txt", "algenta==1.0.17\n")
    _write(tmp_path / "governed-agent" / "tests", "requirements.txt", "algenta==0.0.1\n")
    findings = pd.check_spaces([tmp_path / "algenta", tmp_path / "governed-agent"])
    assert [f.code for f in findings] == ["drift", "drift"]
    assert {f.file.parent.name for f in findings} == {"algenta", "governed-agent"}
    assert all(
        "algenta: 1.0.17 (requirements.txt) vs 1.0.18 (requirements.txt)" == f.message
        for f in findings
    )
    assert pd.requirement_files(tmp_path / "governed-agent") == [
        tmp_path / "governed-agent" / "requirements.txt"
    ]


def test_normalize() -> None:
    assert pd.normalize("Algenta_SDK") == "algenta-sdk"
    assert pd.normalize("nuscenes.devkit") == "nuscenes-devkit"


def test_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(tmp_path / "ok", "requirements.txt", "algenta==1.0.18\n")
    assert pd.main([str(tmp_path / "ok")]) == 0
    assert "0 finding(s) (clean)" in capsys.readouterr().out
    _write(tmp_path / "bad", "requirements.txt", "gradio>=6\n")
    assert pd.main(["--require-hashes", str(tmp_path / "bad"), str(tmp_path / "ok")]) == 1
    out = capsys.readouterr().out
    assert "[unpinned] gradio" in out and "[unhashed] algenta==1.0.18" in out
    assert "2 finding(s) (unhashed=1, unpinned=1)" in out


def test_current_spaces_report_the_known_split_and_prerelease(apps_spaces_dir: Path) -> None:
    """The baseline the plan names, after M2 moved the flagship to 1.0.24: the algenta split
    between the flagship and the two other Spaces (1.0.17) and the bm25_mojo dev wheel."""
    findings = pd.check_spaces(
        [
            apps_spaces_dir / "algenta",
            apps_spaces_dir / "speed-arena",
            apps_spaces_dir / "governed-agent",
        ]
    )
    messages = {f.message for f in findings}
    assert any(m.startswith("algenta: 1.0.17 (requirements.txt) vs 1.0.24") for m in messages)
    flagship = pd.check_spaces([apps_spaces_dir / "algenta"], require_hashes=False)
    assert flagship == [], "the flagship pins every requirement exactly and ships no pre-release"
    assert "bm25-mojo 0.1.4.dev1 is a pre-release" in messages
