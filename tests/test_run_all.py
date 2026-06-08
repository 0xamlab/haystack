from __future__ import annotations

from pathlib import Path

from tests import run_all


def test_run_test_forwards_extra_args(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _CompletedProcess:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_subprocess_run(cmd, *, capture_output, text, timeout, env):  # type: ignore[no-untyped-def]
        captured["cmd"] = cmd
        captured["capture_output"] = capture_output
        captured["text"] = text
        captured["timeout"] = timeout
        captured["env"] = env
        return _CompletedProcess()

    monkeypatch.setattr(run_all.subprocess, "run", fake_subprocess_run)

    result = run_all.run_test(
        Path("/tmp/demo.py"),
        42,
        {"DE_BASE_URL": "http://127.0.0.1:8000"},
        extra_args=("--flag", "value"),
    )

    assert result.exit_code == 0
    assert captured["cmd"] == [
        run_all.sys.executable,
        "/tmp/demo.py",
        "--flag",
        "value",
    ]
    assert captured["capture_output"] is True
    assert captured["text"] is True
    assert captured["timeout"] == 42


def test_main_isolates_bursty_modules_and_forwards_module_extra_args(
    monkeypatch, tmp_path: Path
) -> None:
    tests_dir = tmp_path / "integration"
    tests_dir.mkdir(parents=True)
    for filename in ("test_api_live.py", "test_load.py", "test_go_live_full_real.py"):
        (tests_dir / filename).write_text("print('ok')\n", encoding="utf-8")

    recorded_sleeps: list[int] = []
    created_keys: list[tuple[str, str]] = []
    revoked_keys: list[tuple[str, str, str]] = []
    run_calls: list[tuple[str, str, tuple[str, ...]]] = []

    monkeypatch.setattr(
        run_all,
        "TESTS",
        [
            ("test_api_live.py", {"core", "fast"}, 120),
            ("test_load.py", {"load", "slow"}, 300),
            ("test_go_live_full_real.py", {"go_live", "full"}, 1800),
        ],
    )
    monkeypatch.setattr(run_all, "TESTS_DIR", tests_dir)
    monkeypatch.setattr(run_all.time, "sleep", recorded_sleeps.append)
    monkeypatch.setattr(run_all, "_is_loopback_base_url", lambda _base_url: True)

    def fake_create_temporary_api_key(*, base_url: str, bootstrap_api_key: str, module_name: str):
        created_keys.append((base_url, bootstrap_api_key, module_name))
        return run_all.TemporaryAPIKey(id="temp-id", raw_key="de_temp_key")

    def fake_revoke_temporary_api_key(
        *, base_url: str, bootstrap_api_key: str, temp_key_id: str
    ) -> None:
        revoked_keys.append((base_url, bootstrap_api_key, temp_key_id))

    def fake_run_test(
        script: Path,
        timeout: int,
        env: dict[str, str],
        *,
        extra_args: tuple[str, ...] = (),
    ) -> run_all.TestResult:
        run_calls.append((script.name, env["DE_API_KEY"], extra_args))
        return run_all.TestResult(
            name=script.name,
            passed=1,
            failed=0,
            skipped=0,
            duration=0.1,
            exit_code=0,
            output="",
        )

    monkeypatch.setattr(run_all, "_create_temporary_api_key", fake_create_temporary_api_key)
    monkeypatch.setattr(run_all, "_revoke_temporary_api_key", fake_revoke_temporary_api_key)
    monkeypatch.setattr(run_all, "run_test", fake_run_test)
    monkeypatch.setattr(
        run_all.sys,
        "argv",
        [
            "run_all.py",
            "--base-url",
            "http://127.0.0.1:8000",
            "--api-key",
            "de_bootstrap_key",
        ],
    )

    exit_code = run_all.main()

    assert exit_code == 0
    assert recorded_sleeps == [
        run_all.RATE_LIMIT_COOLDOWN_SECONDS,
        run_all.RATE_LIMIT_COOLDOWN_SECONDS,
    ]
    assert created_keys == [
        ("http://127.0.0.1:8000", "de_bootstrap_key", "test_api_live.py"),
        ("http://127.0.0.1:8000", "de_bootstrap_key", "test_load.py"),
        ("http://127.0.0.1:8000", "de_bootstrap_key", "test_go_live_full_real.py"),
    ]
    assert revoked_keys == [
        ("http://127.0.0.1:8000", "de_bootstrap_key", "temp-id"),
        ("http://127.0.0.1:8000", "de_bootstrap_key", "temp-id"),
        ("http://127.0.0.1:8000", "de_bootstrap_key", "temp-id"),
    ]
    assert run_calls == [
        ("test_api_live.py", "de_temp_key", ()),
        ("test_load.py", "de_temp_key", ()),
        (
            "test_go_live_full_real.py",
            "de_temp_key",
            run_all.MODULE_EXTRA_ARGS["test_go_live_full_real.py"],
        ),
    ]


def test_main_retries_rate_limited_module_once_with_fresh_key(monkeypatch, tmp_path: Path) -> None:
    tests_dir = tmp_path / "integration"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_e2e_complete.py").write_text("print('ok')\n", encoding="utf-8")

    recorded_sleeps: list[int] = []
    created_keys: list[tuple[str, str, str]] = []
    revoked_keys: list[tuple[str, str, str]] = []
    run_calls: list[tuple[str, str, tuple[str, ...]]] = []
    key_counter = {"value": 0}
    call_counter = {"value": 0}

    monkeypatch.setattr(
        run_all,
        "TESTS",
        [("test_e2e_complete.py", {"e2e", "core"}, 600)],
    )
    monkeypatch.setattr(run_all, "TESTS_DIR", tests_dir)
    monkeypatch.setattr(run_all.time, "sleep", recorded_sleeps.append)
    monkeypatch.setattr(run_all, "_is_loopback_base_url", lambda _base_url: True)

    def fake_create_temporary_api_key(*, base_url: str, bootstrap_api_key: str, module_name: str):
        key_counter["value"] += 1
        key_id = f"temp-id-{key_counter['value']}"
        raw_key = f"de_temp_key_{key_counter['value']}"
        created_keys.append((base_url, bootstrap_api_key, module_name))
        return run_all.TemporaryAPIKey(id=key_id, raw_key=raw_key)

    def fake_revoke_temporary_api_key(
        *, base_url: str, bootstrap_api_key: str, temp_key_id: str
    ) -> None:
        revoked_keys.append((base_url, bootstrap_api_key, temp_key_id))

    def fake_run_test(
        script: Path,
        timeout: int,
        env: dict[str, str],
        *,
        extra_args: tuple[str, ...] = (),
    ) -> run_all.TestResult:
        call_counter["value"] += 1
        run_calls.append((script.name, env["DE_API_KEY"], extra_args))
        if call_counter["value"] == 1:
            return run_all.TestResult(
                name=script.name,
                passed=81,
                failed=3,
                skipped=3,
                duration=1.0,
                exit_code=1,
                output="rate_limit_exceeded",
            )
        return run_all.TestResult(
            name=script.name,
            passed=84,
            failed=0,
            skipped=3,
            duration=1.1,
            exit_code=0,
            output="",
        )

    monkeypatch.setattr(run_all, "_create_temporary_api_key", fake_create_temporary_api_key)
    monkeypatch.setattr(run_all, "_revoke_temporary_api_key", fake_revoke_temporary_api_key)
    monkeypatch.setattr(run_all, "run_test", fake_run_test)
    monkeypatch.setattr(
        run_all.sys,
        "argv",
        [
            "run_all.py",
            "--base-url",
            "http://127.0.0.1:8000",
            "--api-key",
            "de_bootstrap_key",
        ],
    )

    exit_code = run_all.main()

    assert exit_code == 0
    assert recorded_sleeps == [
        run_all.RATE_LIMIT_COOLDOWN_SECONDS,
        run_all.RATE_LIMIT_COOLDOWN_SECONDS,
    ]
    assert created_keys == [
        ("http://127.0.0.1:8000", "de_bootstrap_key", "test_e2e_complete.py"),
        ("http://127.0.0.1:8000", "de_bootstrap_key", "test_e2e_complete.py"),
    ]
    assert revoked_keys == [
        ("http://127.0.0.1:8000", "de_bootstrap_key", "temp-id-1"),
        ("http://127.0.0.1:8000", "de_bootstrap_key", "temp-id-2"),
    ]
    assert run_calls == [
        ("test_e2e_complete.py", "de_temp_key_1", ()),
        ("test_e2e_complete.py", "de_temp_key_2", ()),
    ]


def test_go_live_connectivity_real_uses_loopback_cooldown(monkeypatch) -> None:
    monkeypatch.setattr(run_all, "_is_loopback_base_url", lambda _base_url: True)

    assert run_all._should_cool_down_before_module(
        filename="test_go_live_connectivity_real.py",
        base_url="http://127.0.0.1:8000",
    )
