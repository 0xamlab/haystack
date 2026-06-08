from types import SimpleNamespace

from apps.api_server.services.auto_planner_mojo import (
    call_planner_mojo,
    find_mojo_binary,
    should_use_resident_planner_mojo,
)


def test_should_use_resident_planner_mojo_respects_engine_and_payload_size():
    small_payload = {"engine_type": "field_map", "data": {"x": [1.0, 2.0]}}
    large_payload = {
        "engine_type": "field_map",
        "data": {"blob": "x" * 256},
    }

    assert should_use_resident_planner_mojo(
        engine_type="field_map",
        payload=small_payload,
        resident_engines=frozenset({"field_map"}),
        max_payload_bytes=128,
    )
    assert not should_use_resident_planner_mojo(
        engine_type="column_match",
        payload=small_payload,
        resident_engines=frozenset({"field_map"}),
        max_payload_bytes=128,
    )
    assert not should_use_resident_planner_mojo(
        engine_type="field_map",
        payload=large_payload,
        resident_engines=frozenset({"field_map"}),
        max_payload_bytes=128,
    )


def test_find_mojo_binary_skips_non_executable_repo_candidate_and_uses_cwd_candidate(
    tmp_path,
    monkeypatch,
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    repo_candidate = repo_root / "mojo_build" / "simulate"
    repo_candidate.parent.mkdir(parents=True)
    repo_candidate.write_text("")
    repo_candidate.chmod(0o644)

    cwd_candidate = tmp_path / "mojo_build" / "simulate"
    cwd_candidate.parent.mkdir(parents=True)
    cwd_candidate.write_text("")
    cwd_candidate.chmod(0o755)

    monkeypatch.chdir(tmp_path)

    assert find_mojo_binary(repo_root) == cwd_candidate.resolve()


def test_call_planner_mojo_pool_mode_fails_closed_without_legacy_fallback(tmp_path):
    binary = tmp_path / "simulate"
    binary.write_text("")
    binary.chmod(0o755)
    logs: list[tuple[str, dict[str, object]]] = []
    logger = SimpleNamespace(debug=lambda event, **kwargs: logs.append((event, kwargs)))

    def _pool_unavailable(_payload, *, timeout=None):
        assert timeout == 5.0
        raise RuntimeError("pool unavailable")

    def _unexpected_resident(*_args, **_kwargs):
        raise AssertionError("resident transport should not run in explicit pool mode")

    def _unexpected_subprocess(*_args, **_kwargs):
        raise AssertionError("subprocess transport should not run in explicit pool mode")

    result = call_planner_mojo(
        mojo_binary=binary,
        payload={"engine_type": "field_map"},
        timeout=5,
        transport="pool",
        shared_engines=frozenset({"field_map"}),
        should_use_resident_fn=lambda *_args: False,
        invoke_engine_sync_fn=_pool_unavailable,
        invoke_planner_mojo_fn=_unexpected_resident,
        subprocess_run_fn=_unexpected_subprocess,
        logger=logger,
    )

    assert result is None
    assert logs == [
        (
            "auto_planner_mojo_error",
            {
                "error": "pool unavailable",
                "engine": "field_map",
                "transport": "pool",
            },
        )
    ]
