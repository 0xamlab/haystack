from __future__ import annotations

from pathlib import Path

import pytest

import benchmarks.repository_intelligence_public_repo_stability_matrix as stability_matrix
from benchmarks import repository_intelligence_real_repo_probe_collection_support as collection_support
from benchmarks.repository_intelligence_public_repo_matrix import PublicRepositoryCase


def test_select_rank_stratified_public_repository_cases_evenly_samples_ranks() -> None:
    cases = [
        PublicRepositoryCase(
            language=f"lang-{index}",
            repository_url=f"https://github.com/example/repo-{index}.git",
            expected_primary_ecosystem=f"lang-{index}",
        )
        for index in range(5)
    ]

    selected = stability_matrix.select_rank_stratified_public_repository_cases(
        cases=cases,
        sample_size=3,
    )

    assert [case.language for case in selected] == ["lang-0", "lang-2", "lang-4"]


def test_select_rank_stratified_public_repository_cases_returns_all_when_sample_exceeds_count() -> None:
    cases = [
        PublicRepositoryCase(
            language=f"lang-{index}",
            repository_url=f"https://github.com/example/repo-{index}.git",
            expected_primary_ecosystem=f"lang-{index}",
        )
        for index in range(3)
    ]

    selected = stability_matrix.select_rank_stratified_public_repository_cases(
        cases=cases,
        sample_size=5,
    )

    assert [case.language for case in selected] == ["lang-0", "lang-1", "lang-2"]


def test_limit_public_repository_cases_by_rank_clamps_ordered_cases() -> None:
    cases = [
        PublicRepositoryCase(
            language=f"lang-{index}",
            repository_url=f"https://github.com/example/repo-{index}.git",
            expected_primary_ecosystem=f"lang-{index}",
        )
        for index in range(5)
    ]

    selected = stability_matrix.limit_public_repository_cases_by_rank(
        cases=cases,
        rank_limit=3,
    )

    assert [case.language for case in selected] == ["lang-0", "lang-1", "lang-2"]


def test_summarize_stability_attempts_tracks_stable_flaky_and_failing_cases() -> None:
    cases = [
        PublicRepositoryCase(
            language="stable",
            repository_url="https://github.com/example/stable.git",
            expected_primary_ecosystem="stable",
        ),
        PublicRepositoryCase(
            language="flaky",
            repository_url="https://github.com/example/flaky.git",
            expected_primary_ecosystem="flaky",
        ),
        PublicRepositoryCase(
            language="failing",
            repository_url="https://github.com/example/failing.git",
            expected_primary_ecosystem="failing",
        ),
    ]
    attempts = [
        {
            "repeat_index": 0,
            "case": {"language": "stable"},
            "case_key": "stable:https://github.com/example/stable.git",
            "primary_match": True,
            "clone_elapsed_s": 0.5,
            "probe_elapsed_s": 1.0,
        },
        {
            "repeat_index": 1,
            "case": {"language": "stable"},
            "case_key": "stable:https://github.com/example/stable.git",
            "primary_match": True,
            "clone_elapsed_s": 0.6,
            "probe_elapsed_s": 1.1,
        },
        {
            "repeat_index": 0,
            "case": {"language": "flaky"},
            "case_key": "flaky:https://github.com/example/flaky.git",
            "primary_match": True,
            "clone_elapsed_s": 0.4,
            "probe_elapsed_s": 1.2,
        },
        {
            "repeat_index": 1,
            "case": {"language": "flaky"},
            "case_key": "flaky:https://github.com/example/flaky.git",
            "primary_match": False,
            "clone_elapsed_s": 0.7,
            "probe_elapsed_s": 2.0,
            "error": {"code": "PublicRepositoryCaseTimeoutError", "message": "timeout", "details": {}},
        },
        {
            "repeat_index": 0,
            "case": {"language": "failing"},
            "case_key": "failing:https://github.com/example/failing.git",
            "primary_match": False,
        },
        {
            "repeat_index": 1,
            "case": {"language": "failing"},
            "case_key": "failing:https://github.com/example/failing.git",
            "primary_match": False,
        },
    ]

    result = stability_matrix.summarize_stability_attempts(
        attempts=attempts,
        selected_cases=cases,
        repeat_count=2,
    )

    assert result["case_count"] == 3
    assert result["repeat_count"] == 2
    assert result["total_runs"] == 6
    assert result["passing_runs"] == 3
    assert result["stable_case_count"] == 1
    assert result["flaky_case_count"] == 1
    assert result["failing_case_count"] == 1
    case_statuses = {
        case_summary["case"]["language"]: case_summary["stability_status"]
        for case_summary in result["cases"]
    }
    assert case_statuses == {
        "stable": "stable",
        "flaky": "flaky",
        "failing": "failing",
    }


def test_summarize_stability_attempts_keeps_duplicate_language_cases_separate() -> None:
    cases = [
        PublicRepositoryCase(
            language="rebol",
            repository_url="https://github.com/example/rebol-a.git",
            expected_primary_ecosystem="rebol",
        ),
        PublicRepositoryCase(
            language="rebol",
            repository_url="https://github.com/example/rebol-b.git",
            expected_primary_ecosystem="rebol",
        ),
    ]
    attempts = [
        {
            "repeat_index": 0,
            "case": {
                "language": "rebol",
                "repository_url": "https://github.com/example/rebol-a.git",
            },
            "case_key": "rebol:https://github.com/example/rebol-a.git",
            "primary_match": True,
            "clone_elapsed_s": 0.1,
            "probe_elapsed_s": 0.2,
        },
        {
            "repeat_index": 0,
            "case": {
                "language": "rebol",
                "repository_url": "https://github.com/example/rebol-b.git",
            },
            "case_key": "rebol:https://github.com/example/rebol-b.git",
            "primary_match": False,
            "clone_elapsed_s": 0.3,
            "probe_elapsed_s": 0.4,
        },
    ]

    result = stability_matrix.summarize_stability_attempts(
        attempts=attempts,
        selected_cases=cases,
        repeat_count=1,
    )

    assert result["stable_case_count"] == 1
    assert result["failing_case_count"] == 1
    assert result["selected_case_keys"] == [
        "rebol:https://github.com/example/rebol-a.git",
        "rebol:https://github.com/example/rebol-b.git",
    ]
    assert [case_summary["case"]["repository_url"] for case_summary in result["cases"]] == [
        "https://github.com/example/rebol-a.git",
        "https://github.com/example/rebol-b.git",
    ]


def test_run_stability_case_attempt_clones_before_probe(
    tmp_path: Path, monkeypatch
) -> None:
    case = PublicRepositoryCase(
        language="python",
        repository_url="https://github.com/pallets/click.git",
        expected_primary_ecosystem="python",
    )
    repo_path = tmp_path / "click"
    repo_path.mkdir()
    events: list[str] = []

    monkeypatch.setattr(
        stability_matrix.public_repo_matrix,
        "clone_public_repository_case",
        lambda *_args, **_kwargs: events.append("clone") or repo_path,
    )
    monkeypatch.setattr(
        stability_matrix.public_repo_matrix,
        "_run_with_case_timeout",
        lambda **kwargs: kwargs["callback"](),
    )

    def fake_probe(*_args, **kwargs):
        assert kwargs["repo_path"] == repo_path
        events.append("probe")
        return {
            "primary_match": True,
            "primary_ecosystem": "python",
            "planner_status": "ready",
            "snapshot_file_count": 4,
            "connected_file_count": 3,
        }

    monkeypatch.setattr(
        stability_matrix.public_repo_matrix,
        "_run_public_repository_probe_for_checkout",
        fake_probe,
    )

    result = stability_matrix._run_stability_case_attempt(
        case=case,
        rank=1,
        repeat_index=0,
        checkout_root=tmp_path / "checkouts",
        runtime_root=tmp_path / "runtime",
        refresh=False,
        case_timeout_seconds=60,
    )

    assert events == ["clone", "probe"]


def test_reset_stability_attempt_state_clears_probe_attempt_caches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = PublicRepositoryCase(
        language="python",
        repository_url="https://github.com/pallets/click.git",
        expected_primary_ecosystem="python",
    )
    runtime_root = tmp_path / "runtime"
    runtime_dir = runtime_root / stability_matrix.public_repo_matrix._case_checkout_name(case)
    shared_runtime_dir = stability_matrix.public_repo_matrix._public_repository_case_shared_runtime_dir(
        runtime_root=runtime_root,
        case=case,
    )
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "state.json").write_text("{}", encoding="utf-8")
    shared_runtime_dir.mkdir(parents=True)
    (shared_runtime_dir / "cache.json").write_text("{}", encoding="utf-8")
    calls: list[dict[str, bool]] = []

    monkeypatch.setattr(
        stability_matrix.public_repo_matrix,
        "clear_public_repository_probe_attempt_cache",
        lambda **kwargs: calls.append(kwargs),
    )

    stability_matrix._reset_stability_attempt_state(case=case, runtime_root=runtime_root)

    assert calls == [
        {
            "preserve_prepass_focus_paths": True,
            "preserve_expected_ecosystem_hints": True,
        }
    ]
    assert not runtime_dir.exists()
    assert not shared_runtime_dir.exists()


def test_reset_stability_attempt_state_preserves_case_probe_caches_for_warm_repeat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = PublicRepositoryCase(
        language="objectivec",
        repository_url="https://github.com/AFNetworking/AFNetworking.git",
        expected_primary_ecosystem="objectivec",
    )
    runtime_root = tmp_path / "runtime"
    runtime_dir = runtime_root / stability_matrix.public_repo_matrix._case_checkout_name(case)
    shared_runtime_dir = stability_matrix.public_repo_matrix._public_repository_case_shared_runtime_dir(
        runtime_root=runtime_root,
        case=case,
    )
    runtime_dir.mkdir(parents=True)
    shared_runtime_dir.mkdir(parents=True)
    (shared_runtime_dir / "cache.json").write_text("{}", encoding="utf-8")
    calls: list[dict[str, bool]] = []

    monkeypatch.setattr(
        stability_matrix.public_repo_matrix,
        "clear_public_repository_probe_attempt_cache",
        lambda **kwargs: calls.append(kwargs),
    )

    stability_matrix._reset_stability_attempt_state(
        case=case,
        runtime_root=runtime_root,
        preserve_case_probe_caches=True,
    )

    assert calls == [
        {
            "preserve_prepass_focus_paths": True,
            "preserve_seed_plan_results": True,
            "preserve_path_candidate_ecosystems": True,
            "preserve_expected_ecosystem_hints": True,
        }
    ]
    assert runtime_dir.exists()
    assert shared_runtime_dir.exists()


def test_reset_stability_attempt_state_ignores_missing_cleanup_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = PublicRepositoryCase(
        language="tsql",
        repository_url="https://github.com/BrentOzarULTD/SQL-Server-First-Responder-Kit.git",
        expected_primary_ecosystem="tsql",
    )
    runtime_root = tmp_path / "runtime"
    runtime_dir = runtime_root / stability_matrix.public_repo_matrix._case_checkout_name(case)
    shared_runtime_dir = stability_matrix.public_repo_matrix._public_repository_case_shared_runtime_dir(
        runtime_root=runtime_root,
        case=case,
    )
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "state.json").write_text("{}", encoding="utf-8")
    shared_runtime_dir.mkdir(parents=True)
    (shared_runtime_dir / "cache.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        stability_matrix.public_repo_matrix,
        "clear_public_repository_probe_attempt_cache",
        lambda **_kwargs: None,
    )

    removed_paths: list[Path] = []

    def fake_rmtree(path, *, onexc):
        removed_paths.append(Path(path))
        onexc(None, "missing", (FileNotFoundError, FileNotFoundError("missing"), None))

    monkeypatch.setattr(stability_matrix.shutil, "rmtree", fake_rmtree)

    stability_matrix._reset_stability_attempt_state(case=case, runtime_root=runtime_root)

    assert removed_paths == [runtime_dir, shared_runtime_dir]


def test_run_public_repository_stability_matrix_keeps_outer_collection_cache_scope(
    tmp_path: Path, monkeypatch
) -> None:
    cases = [
        PublicRepositoryCase(
            language="python",
            repository_url="https://github.com/pallets/click.git",
            expected_primary_ecosystem="python",
        ),
        PublicRepositoryCase(
            language="rust",
            repository_url="https://github.com/rust-lang/cargo.git",
            expected_primary_ecosystem="rust",
        ),
    ]
    events: list[str] = []

    monkeypatch.setattr(
        collection_support,
        "begin_git_repo_relative_files_cache_scope",
        lambda: events.append("begin"),
    )
    monkeypatch.setattr(
        collection_support,
        "end_git_repo_relative_files_cache_scope",
        lambda: events.append("end"),
    )

    def fake_attempt(**kwargs):
        case = kwargs["case"]
        return {
            "rank": kwargs["rank"],
            "repeat_index": kwargs["repeat_index"],
            "case": {"language": case.language, "repository_url": case.repository_url},
            "case_key": f"{case.language}:{case.repository_url}",
            "primary_match": True,
            "clone_elapsed_s": 0.01,
            "probe_elapsed_s": 0.02,
            "primary_ecosystem": case.expected_primary_ecosystem,
            "planner_status": "not_attempted_no_diagnostics",
            "snapshot_file_count": 1,
            "connected_file_count": 1,
        }

    monkeypatch.setattr(
        stability_matrix,
        "_run_stability_case_attempt",
        fake_attempt,
    )

    result = stability_matrix.run_public_repository_stability_matrix(
        checkout_root=tmp_path / "checkouts",
        runtime_root=tmp_path / "runtime",
        repeats=2,
        sample_size=None,
        cases=cases,
        refresh=False,
        case_timeout_seconds=60,
    )

    assert events == ["begin", "end"]
    assert result["total_runs"] == 4
    assert result["stable_case_count"] == 2


def test_run_stability_case_attempt_resets_probe_attempt_cache_before_probe(
    tmp_path: Path, monkeypatch
) -> None:
    case = PublicRepositoryCase(
        language="freebasic",
        repository_url="https://github.com/freebasic/fbc.git",
        expected_primary_ecosystem="freebasic",
    )
    repo_path = tmp_path / "fbc"
    repo_path.mkdir()
    runtime_root = tmp_path / "runtime"
    runtime_dir = runtime_root / stability_matrix.public_repo_matrix._case_checkout_name(case)
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "stale.json").write_text("{}", encoding="utf-8")
    events: list[str] = []

    monkeypatch.setattr(
        stability_matrix.public_repo_matrix,
        "clone_public_repository_case",
        lambda *_args, **_kwargs: repo_path,
    )
    monkeypatch.setattr(
        stability_matrix.public_repo_matrix,
        "clear_public_repository_probe_attempt_cache",
        lambda preserve_prepass_focus_paths=False, preserve_seed_plan_results=False, preserve_path_candidate_ecosystems=False, preserve_expected_ecosystem_hints=False: events.append(
            "clear:"
            f"{preserve_prepass_focus_paths}:"
            f"{preserve_seed_plan_results}:"
            f"{preserve_path_candidate_ecosystems}:"
            f"{preserve_expected_ecosystem_hints}"
        ),
    )
    monkeypatch.setattr(
        stability_matrix.public_repo_matrix,
        "_run_with_case_timeout",
        lambda **kwargs: kwargs["callback"](),
    )

    def fake_probe(*_args, **kwargs):
        events.append("probe")
        assert kwargs["repo_path"] == repo_path
        assert not runtime_dir.exists()
        return {
            "primary_match": True,
            "primary_ecosystem": "freebasic",
            "planner_status": "ready",
            "snapshot_file_count": 4,
            "connected_file_count": 4,
        }

    monkeypatch.setattr(
        stability_matrix.public_repo_matrix,
        "_run_public_repository_probe_for_checkout",
        fake_probe,
    )

    stability_matrix._run_stability_case_attempt(
        case=case,
        rank=1,
        repeat_index=0,
        checkout_root=tmp_path / "checkouts",
        runtime_root=runtime_root,
        refresh=False,
        case_timeout_seconds=60,
    )

    assert events == ["clear:True:False:False:True", "probe"]


def test_run_stability_case_attempt_preserves_case_probe_caches_on_warm_repeat(
    tmp_path: Path, monkeypatch
) -> None:
    case = PublicRepositoryCase(
        language="objectivec",
        repository_url="https://github.com/AFNetworking/AFNetworking.git",
        expected_primary_ecosystem="objectivec",
    )
    repo_path = tmp_path / "afnetworking"
    repo_path.mkdir()
    events: list[str] = []

    monkeypatch.setattr(
        stability_matrix.public_repo_matrix,
        "clone_public_repository_case",
        lambda *_args, **_kwargs: repo_path,
    )
    monkeypatch.setattr(
        stability_matrix.public_repo_matrix,
        "clear_public_repository_probe_attempt_cache",
        lambda preserve_prepass_focus_paths=False, preserve_seed_plan_results=False, preserve_path_candidate_ecosystems=False, preserve_expected_ecosystem_hints=False: events.append(
            "clear:"
            f"{preserve_prepass_focus_paths}:"
            f"{preserve_seed_plan_results}:"
            f"{preserve_path_candidate_ecosystems}:"
            f"{preserve_expected_ecosystem_hints}"
        ),
    )
    monkeypatch.setattr(
        stability_matrix.public_repo_matrix,
        "_run_with_case_timeout",
        lambda **kwargs: kwargs["callback"](),
    )
    monkeypatch.setattr(
        stability_matrix.public_repo_matrix,
        "_run_public_repository_probe_for_checkout",
        lambda *_args, **_kwargs: {
            "primary_match": True,
            "primary_ecosystem": "objectivec",
            "planner_status": "ready",
            "snapshot_file_count": 7,
            "connected_file_count": 7,
        },
    )

    stability_matrix._run_stability_case_attempt(
        case=case,
        rank=1,
        repeat_index=1,
        checkout_root=tmp_path / "checkouts",
        runtime_root=tmp_path / "runtime",
        refresh=False,
        case_timeout_seconds=60,
        preserve_case_probe_caches=True,
    )

    assert events == ["clear:True:True:True:True"]


def test_run_public_repository_stability_matrix_uses_rank_stratified_selection(
    tmp_path: Path, monkeypatch
) -> None:
    ordered_cases = [
        PublicRepositoryCase(
            language=f"lang-{index}",
            repository_url=f"https://github.com/example/repo-{index}.git",
            expected_primary_ecosystem=f"lang-{index}",
        )
        for index in range(6)
    ]
    attempt_log: list[tuple[str, int, int]] = []

    monkeypatch.setattr(
        stability_matrix.public_repo_matrix,
        "ordered_public_repository_cases",
        lambda languages=(): ordered_cases,
    )
    monkeypatch.setattr(
        stability_matrix,
        "_run_stability_case_attempt",
        lambda **kwargs: (
            attempt_log.append(
                (
                    kwargs["case"].language,
                    kwargs["rank"],
                    kwargs["repeat_index"],
                )
            )
            or {
                "rank": kwargs["rank"],
                "repeat_index": kwargs["repeat_index"],
                "case": {"language": kwargs["case"].language},
                "case_key": stability_matrix._public_repository_case_key(kwargs["case"]),
                "primary_match": True,
                "clone_elapsed_s": 0.1,
                "probe_elapsed_s": 0.2,
            }
        ),
    )

    result = stability_matrix.run_public_repository_stability_matrix(
        checkout_root=tmp_path / "checkouts",
        runtime_root=tmp_path / "runtime",
        repeats=2,
        sample_size=3,
    )

    assert attempt_log == [
        ("lang-0", 1, 0),
        ("lang-0", 1, 1),
        ("lang-2", 3, 0),
        ("lang-2", 3, 1),
        ("lang-5", 6, 0),
        ("lang-5", 6, 1),
    ]
    assert result["stable_case_count"] == 3


def test_run_public_repository_stability_matrix_applies_rank_limit_before_sampling(
    tmp_path: Path, monkeypatch
) -> None:
    ordered_cases = [
        PublicRepositoryCase(
            language=f"lang-{index}",
            repository_url=f"https://github.com/example/repo-{index}.git",
            expected_primary_ecosystem=f"lang-{index}",
        )
        for index in range(6)
    ]
    attempt_log: list[tuple[str, int, int]] = []

    monkeypatch.setattr(
        stability_matrix.public_repo_matrix,
        "ordered_public_repository_cases",
        lambda languages=(): ordered_cases,
    )
    monkeypatch.setattr(
        stability_matrix,
        "_run_stability_case_attempt",
        lambda **kwargs: (
            attempt_log.append(
                (
                    kwargs["case"].language,
                    kwargs["rank"],
                    kwargs["repeat_index"],
                )
            )
            or {
                "rank": kwargs["rank"],
                "repeat_index": kwargs["repeat_index"],
                "case": {"language": kwargs["case"].language},
                "case_key": stability_matrix._public_repository_case_key(kwargs["case"]),
                "primary_match": True,
                "clone_elapsed_s": 0.1,
                "probe_elapsed_s": 0.2,
            }
        ),
    )

    result = stability_matrix.run_public_repository_stability_matrix(
        checkout_root=tmp_path / "checkouts",
        runtime_root=tmp_path / "runtime",
        repeats=1,
        sample_size=3,
        rank_limit=4,
    )

    assert attempt_log == [
        ("lang-0", 1, 0),
        ("lang-2", 3, 0),
        ("lang-3", 4, 0),
    ]
    assert result["stable_case_count"] == 3


def test_run_public_repository_stability_matrix_primes_probe_runtime_once(
    tmp_path: Path, monkeypatch
) -> None:
    ordered_cases = [
        PublicRepositoryCase(
            language="lang-0",
            repository_url="https://github.com/example/repo-0.git",
            expected_primary_ecosystem="lang-0",
        ),
        PublicRepositoryCase(
            language="lang-1",
            repository_url="https://github.com/example/repo-1.git",
            expected_primary_ecosystem="lang-1",
        ),
    ]
    events: list[str] = []

    monkeypatch.setattr(
        stability_matrix.public_repo_matrix,
        "ordered_public_repository_cases",
        lambda languages=(): ordered_cases,
    )
    monkeypatch.setattr(
        stability_matrix.public_repo_matrix,
        "prime_public_repository_probe_runtime",
        lambda: events.append("warm"),
    )
    monkeypatch.setattr(
        stability_matrix,
        "_run_stability_case_attempt",
        lambda **kwargs: (
            stability_matrix.public_repo_matrix.prime_public_repository_probe_runtime()
            if kwargs["prime_runtime"]
            else None
        )
        or (
            events.append(f"attempt:{kwargs['case'].language}:{kwargs['repeat_index']}")
            or {
                "rank": kwargs["rank"],
                "repeat_index": kwargs["repeat_index"],
                "case": {"language": kwargs["case"].language},
                "case_key": stability_matrix._public_repository_case_key(kwargs["case"]),
                "primary_match": True,
                "clone_elapsed_s": 0.1,
                "probe_elapsed_s": 0.2,
            }
        ),
    )

    stability_matrix.run_public_repository_stability_matrix(
        checkout_root=tmp_path / "checkouts",
        runtime_root=tmp_path / "runtime",
        repeats=2,
    )

    assert events == [
        "warm",
        "attempt:lang-0:0",
        "attempt:lang-0:1",
        "attempt:lang-1:0",
        "attempt:lang-1:1",
    ]


def test_run_public_repository_stability_matrix_supports_explicit_duplicate_language_cases(
    tmp_path: Path, monkeypatch
) -> None:
    duplicate_language_cases = [
        PublicRepositoryCase(
            language="rebol",
            repository_url="https://github.com/example/rebol-a.git",
            expected_primary_ecosystem="rebol",
        ),
        PublicRepositoryCase(
            language="rebol",
            repository_url="https://github.com/example/rebol-b.git",
            expected_primary_ecosystem="rebol",
        ),
    ]
    attempt_log: list[tuple[str, str, int, int]] = []

    monkeypatch.setattr(
        stability_matrix,
        "_run_stability_case_attempt",
        lambda **kwargs: (
            attempt_log.append(
                (
                    kwargs["case"].language,
                    kwargs["case"].repository_url,
                    kwargs["rank"],
                    kwargs["repeat_index"],
                )
            )
            or {
                "rank": kwargs["rank"],
                "repeat_index": kwargs["repeat_index"],
                "case": {
                    "language": kwargs["case"].language,
                    "repository_url": kwargs["case"].repository_url,
                },
                "case_key": stability_matrix._public_repository_case_key(kwargs["case"]),
                "primary_match": True,
                "clone_elapsed_s": 0.1,
                "probe_elapsed_s": 0.2,
            }
        ),
    )

    result = stability_matrix.run_public_repository_stability_matrix(
        checkout_root=tmp_path / "checkouts",
        runtime_root=tmp_path / "runtime",
        repeats=1,
        sample_size=None,
        cases=duplicate_language_cases,
    )

    assert attempt_log == [
        ("rebol", "https://github.com/example/rebol-a.git", 1, 0),
        ("rebol", "https://github.com/example/rebol-b.git", 2, 0),
    ]
    assert result["stable_case_count"] == 2
    assert result["selected_case_keys"] == [
        "rebol:https://github.com/example/rebol-a.git",
        "rebol:https://github.com/example/rebol-b.git",
    ]


def test_collapse_public_repository_cases_to_unique_languages_keeps_first_ranked_case() -> None:
    duplicate_language_cases = [
        PublicRepositoryCase(
            language="chapel",
            repository_url="https://github.com/example/chapel-a.git",
            expected_primary_ecosystem="chapel",
        ),
        PublicRepositoryCase(
            language="chapel",
            repository_url="https://github.com/example/chapel-b.git",
            expected_primary_ecosystem="chapel",
        ),
        PublicRepositoryCase(
            language="common workflow language",
            repository_url="https://github.com/example/cwl-a.git",
            expected_primary_ecosystem="common workflow language",
        ),
        PublicRepositoryCase(
            language="cwl",
            repository_url="https://github.com/example/cwl-b.git",
            expected_primary_ecosystem="common workflow language",
        ),
    ]

    collapsed = stability_matrix.collapse_public_repository_cases_to_unique_languages(
        cases=duplicate_language_cases,
    )

    assert [case.repository_url for case in collapsed] == [
        "https://github.com/example/chapel-a.git",
        "https://github.com/example/cwl-a.git",
    ]


def test_run_public_repository_stability_matrix_unique_languages_collapses_duplicates(
    tmp_path: Path, monkeypatch
) -> None:
    duplicate_language_cases = [
        PublicRepositoryCase(
            language="rebol",
            repository_url="https://github.com/example/rebol-a.git",
            expected_primary_ecosystem="rebol",
        ),
        PublicRepositoryCase(
            language="rebol",
            repository_url="https://github.com/example/rebol-b.git",
            expected_primary_ecosystem="rebol",
        ),
        PublicRepositoryCase(
            language="cwl",
            repository_url="https://github.com/example/cwl-a.git",
            expected_primary_ecosystem="common workflow language",
        ),
        PublicRepositoryCase(
            language="common workflow language",
            repository_url="https://github.com/example/cwl-b.git",
            expected_primary_ecosystem="common workflow language",
        ),
    ]
    attempt_log: list[tuple[str, str, int, int]] = []

    monkeypatch.setattr(
        stability_matrix,
        "_run_stability_case_attempt",
        lambda **kwargs: (
            attempt_log.append(
                (
                    kwargs["case"].language,
                    kwargs["case"].repository_url,
                    kwargs["rank"],
                    kwargs["repeat_index"],
                )
            )
            or {
                "rank": kwargs["rank"],
                "repeat_index": kwargs["repeat_index"],
                "case": {
                    "language": kwargs["case"].language,
                    "repository_url": kwargs["case"].repository_url,
                },
                "case_key": stability_matrix._public_repository_case_key(kwargs["case"]),
                "primary_match": True,
                "clone_elapsed_s": 0.1,
                "probe_elapsed_s": 0.2,
            }
        ),
    )

    result = stability_matrix.run_public_repository_stability_matrix(
        checkout_root=tmp_path / "checkouts",
        runtime_root=tmp_path / "runtime",
        repeats=1,
        sample_size=None,
        cases=duplicate_language_cases,
        unique_languages=True,
    )

    assert attempt_log == [
        ("rebol", "https://github.com/example/rebol-a.git", 1, 0),
        ("cwl", "https://github.com/example/cwl-a.git", 2, 0),
    ]
    assert result["stable_case_count"] == 2
    assert result["selected_case_keys"] == [
        "rebol:https://github.com/example/rebol-a.git",
        "cwl:https://github.com/example/cwl-a.git",
    ]
