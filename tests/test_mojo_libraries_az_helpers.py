from __future__ import annotations

from pathlib import Path

from tests.integration import test_mojo_libraries_az as mojo_az


def test_mojo_run_command_prefers_direct_binary_when_pixi_missing(monkeypatch) -> None:
    monkeypatch.setattr(mojo_az.shutil, "which", lambda name: None)
    monkeypatch.setattr(mojo_az.Path, "home", classmethod(lambda cls: Path("/missing-home")))
    monkeypatch.setattr(mojo_az, "MOJO_BIN", Path("/tmp/mojo"))
    monkeypatch.setattr(mojo_az, "ENGINE_DIR", Path("/tmp/engine"))

    command = mojo_az._mojo_run_command(Path("/tmp/test_lib.mojo"))

    assert command == [
        "/tmp/mojo",
        "run",
        "-I/tmp/engine",
        "/tmp/test_lib.mojo",
    ]


def test_mojo_run_command_prefers_pixi_when_available(monkeypatch) -> None:
    monkeypatch.setattr(
        mojo_az.shutil,
        "which",
        lambda name: "/usr/bin/pixi" if name == "pixi" else None,
    )
    monkeypatch.setattr(mojo_az, "ENGINE_DIR", Path("/tmp/engine"))

    command = mojo_az._mojo_run_command(Path("/tmp/test_lib.mojo"))

    assert command == [
        "/usr/bin/pixi",
        "run",
        "mojo",
        "run",
        "-I/tmp/engine",
        "/tmp/test_lib.mojo",
    ]


def test_pixi_binary_falls_back_to_home_install(monkeypatch, tmp_path) -> None:
    pixi_path = tmp_path / ".pixi" / "bin" / "pixi"
    pixi_path.parent.mkdir(parents=True)
    pixi_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(mojo_az.shutil, "which", lambda name: None)
    monkeypatch.setattr(mojo_az.Path, "home", classmethod(lambda cls: tmp_path))

    assert mojo_az._pixi_binary() == str(pixi_path)
