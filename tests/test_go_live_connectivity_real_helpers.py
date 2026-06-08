from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration import test_go_live_connectivity_real as connectivity_real


def test_with_invalid_redis_password_rewrites_only_credentials() -> None:
    invalid = connectivity_real._with_invalid_redis_password(
        "redis://default:secret@redis.example.com:15638/0?ssl_cert_reqs=required"
    )

    assert invalid == (
        "redis://default:algenta-invalid-password@redis.example.com:15638/0?ssl_cert_reqs=required"
    )


def test_with_invalid_redis_password_preserves_username_less_auth() -> None:
    invalid = connectivity_real._with_invalid_redis_password("rediss://:secret@redis.example.com/0")

    assert invalid == "rediss://:algenta-invalid-password@redis.example.com/0"


def test_with_invalid_redis_password_returns_none_without_embedded_auth() -> None:
    assert connectivity_real._with_invalid_redis_password("redis://localhost:6379/0") is None


def test_parse_redis_endpoint_defaults_port() -> None:
    assert connectivity_real._parse_redis_endpoint("redis://localhost/0") == ("localhost", 6379)


def test_is_loopback_host_accepts_loopback_variants() -> None:
    assert connectivity_real._is_loopback_host("localhost") is True
    assert connectivity_real._is_loopback_host("127.0.0.1") is True
    assert connectivity_real._is_loopback_host("::1") is True
    assert connectivity_real._is_loopback_host("redis.example.com") is False


def test_ensure_local_redis_available_returns_none_when_port_is_open(monkeypatch) -> None:
    monkeypatch.setattr(connectivity_real, "ensure_port_open", lambda host, port, label: None)

    assert connectivity_real.ensure_local_redis_available("redis://127.0.0.1:6379/0") is None


def test_ensure_local_redis_available_rejects_non_loopback_bootstrap(monkeypatch) -> None:
    def _refuse(host: str, port: int, label: str) -> None:
        raise ConnectionRefusedError(61, "connection refused")

    monkeypatch.setattr(connectivity_real, "ensure_port_open", _refuse)

    with pytest.raises(connectivity_real.LocalRedisBootstrapError) as excinfo:
        connectivity_real.ensure_local_redis_available("redis://redis.example.com:6379/0")

    assert "automatic bootstrap is allowed only for loopback Redis URLs" in str(excinfo.value)


def test_ensure_local_redis_available_bootstraps_loopback(monkeypatch, tmp_path: Path) -> None:
    launches: list[list[str]] = []
    redis_dir = tmp_path / "redis"

    def _refuse_once(host: str, port: int, label: str) -> None:
        raise ConnectionRefusedError(61, "connection refused")

    class _FakeProcess:
        def __init__(self) -> None:
            self.returncode = None
            self.terminated = False
            self.killed = False

        def poll(self) -> int | None:
            return self.returncode

        def terminate(self) -> None:
            self.terminated = True
            self.returncode = 0

        def wait(self, timeout: float | None = None) -> int:
            return 0 if self.returncode is not None else 0

        def kill(self) -> None:
            self.killed = True
            self.returncode = -9

    fake_process = _FakeProcess()

    def _fake_popen(cmd: list[str], **kwargs):
        launches.append(cmd)
        return fake_process

    monkeypatch.setattr(connectivity_real, "ensure_port_open", _refuse_once)
    monkeypatch.setattr(connectivity_real.shutil, "which", lambda name: "/opt/homebrew/bin/redis-server")
    def _fake_mkdtemp(prefix: str) -> str:
        redis_dir.mkdir()
        return str(redis_dir)

    monkeypatch.setattr(connectivity_real.tempfile, "mkdtemp", _fake_mkdtemp)
    monkeypatch.setattr(connectivity_real.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(connectivity_real, "_wait_for_port_open", lambda *args, **kwargs: None)

    handle = connectivity_real.ensure_local_redis_available("redis://127.0.0.1:6379/0")

    assert handle is not None
    assert launches == [
        [
            "/opt/homebrew/bin/redis-server",
            "--save",
            "",
            "--appendonly",
            "no",
            "--bind",
            "127.0.0.1",
            "--port",
            "6379",
            "--dir",
            str(redis_dir),
            "--loglevel",
            "warning",
        ]
    ]

    handle.stop()
    assert fake_process.terminated is True


def test_assert_behavior_sla_summary_keeps_p1_budget_drift_advisory_only(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        connectivity_real,
        "behavior_case_summaries",
        [
            {
                "metrics": {
                    "fetch_budget_key": "fetch_ms.rest_single_dataset",
                    "fetch_ms": [459.369],
                    "resolve_hit_ms": 0.1,
                    "exact_hit_ms": 0.1,
                    "total_request_ms": 40.0,
                    "first_query_total_ms": 8.0,
                }
            }
        ],
    )
    monkeypatch.setattr(connectivity_real, "behavior_p1_failures", [])

    connectivity_real.assert_behavior_sla_summary()

    assert connectivity_real.behavior_p1_failures == []


def test_assert_behavior_sla_summary_still_fails_closed_on_p0_budget_breach(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        connectivity_real,
        "behavior_case_summaries",
        [
            {
                "metrics": {
                    "resolve_hit_ms": 10.0,
                    "exact_hit_ms": 0.1,
                    "total_request_ms": 40.0,
                    "first_query_total_ms": 8.0,
                }
            }
        ],
    )
    monkeypatch.setattr(connectivity_real, "behavior_p1_failures", [])

    with pytest.raises(AssertionError, match="resolve_hit_ms exceeded P0 budget"):
        connectivity_real.assert_behavior_sla_summary()
