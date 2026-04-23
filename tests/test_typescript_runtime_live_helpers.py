from __future__ import annotations

from tests.integration import test_typescript_runtime_live as live_ts


def test_pnpm_command_prefers_corepack_when_direct_pnpm_missing(monkeypatch) -> None:
    def _fake_which(name: str) -> str | None:
        if name == "corepack":
            return "/usr/bin/corepack"
        return None

    monkeypatch.setattr(live_ts.shutil, "which", _fake_which)

    assert live_ts._pnpm_command() == ["corepack", "pnpm"]


def test_ts_build_command_falls_back_to_local_tsc(monkeypatch, tmp_path) -> None:
    sdk_dir = tmp_path / "ts-sdk"
    tsc_path = sdk_dir / "node_modules" / ".bin" / "tsc"
    tsc_path.parent.mkdir(parents=True)
    tsc_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    monkeypatch.setattr(live_ts, "TS_SDK_DIR", sdk_dir)
    monkeypatch.setattr(live_ts, "_pnpm_command", lambda: (_ for _ in ()).throw(FileNotFoundError("missing")))

    assert live_ts._ts_build_command() == [
        str(tsc_path),
        "-p",
        str(sdk_dir / "tsconfig.json"),
    ]
