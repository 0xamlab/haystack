from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from statistics import mean
import time
from typing import Any

import benchmarks.repository_intelligence_public_repo_matrix as public_repo_matrix
from benchmarks import (
    repository_intelligence_real_repo_probe_collection_support as collection_support,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "build" / "repository_intelligence_public_repo_stability_matrix.json"
)


def _public_repository_case_key(case: public_repo_matrix.PublicRepositoryCase | dict[str, Any]) -> str:
    language = str(case["language"] if isinstance(case, dict) else case.language)
    repository_url = str(
        case["repository_url"] if isinstance(case, dict) else case.repository_url
    ).rstrip("/")
    return f"{language}:{repository_url}"


def select_rank_stratified_public_repository_cases(
    *,
    cases: list[public_repo_matrix.PublicRepositoryCase],
    sample_size: int | None,
) -> list[public_repo_matrix.PublicRepositoryCase]:
    if sample_size is None or sample_size >= len(cases):
        return list(cases)
    if sample_size <= 0 or not cases:
        return []
    if sample_size == 1:
        return [cases[0]]

    indexed_selection: list[int] = []
    seen_indexes: set[int] = set()
    max_index = len(cases) - 1
    for position in range(sample_size):
        case_index = round(position * max_index / float(sample_size - 1))
        normalized_index = max(0, min(max_index, int(case_index)))
        if normalized_index in seen_indexes:
            continue
        indexed_selection.append(normalized_index)
        seen_indexes.add(normalized_index)

    if len(indexed_selection) < sample_size:
        for case_index in range(len(cases)):
            if case_index in seen_indexes:
                continue
            indexed_selection.append(case_index)
            seen_indexes.add(case_index)
            if len(indexed_selection) >= sample_size:
                break

    indexed_selection.sort()
    return [cases[index] for index in indexed_selection]


def limit_public_repository_cases_by_rank(
    *,
    cases: list[public_repo_matrix.PublicRepositoryCase],
    rank_limit: int | None,
) -> list[public_repo_matrix.PublicRepositoryCase]:
    if rank_limit is None:
        return list(cases)
    if rank_limit <= 0:
        return []
    return list(cases[:rank_limit])


def collapse_public_repository_cases_to_unique_languages(
    *,
    cases: list[public_repo_matrix.PublicRepositoryCase],
) -> list[public_repo_matrix.PublicRepositoryCase]:
    unique_cases: list[public_repo_matrix.PublicRepositoryCase] = []
    seen_languages: set[str] = set()
    for case in cases:
        canonical_language = (
            public_repo_matrix.canonical_repository_language(case.language) or case.language
        )
        if canonical_language in seen_languages:
            continue
        seen_languages.add(canonical_language)
        unique_cases.append(case)
    return unique_cases


def _run_stability_case_attempt(
    *,
    case: public_repo_matrix.PublicRepositoryCase,
    rank: int,
    repeat_index: int,
    checkout_root: Path,
    runtime_root: Path,
    refresh: bool,
    case_timeout_seconds: int | None,
    preserve_case_probe_caches: bool = False,
    prime_runtime: bool = False,
) -> dict[str, Any]:
    clone_started = time.perf_counter()
    repo_path = public_repo_matrix.clone_public_repository_case(
        case,
        checkout_root=checkout_root,
        refresh=refresh,
    )
    clone_elapsed_seconds = round(time.perf_counter() - clone_started, 3)
    _reset_stability_attempt_state(
        case=case,
        runtime_root=runtime_root,
        preserve_case_probe_caches=preserve_case_probe_caches,
    )
    if prime_runtime:
        public_repo_matrix.prime_public_repository_probe_runtime()
    probe_started = time.perf_counter()
    probe_result = public_repo_matrix._run_with_case_timeout(
        timeout_seconds=case_timeout_seconds,
        callback=lambda: public_repo_matrix._run_public_repository_probe_for_checkout(
            case,
            repo_path=repo_path,
            runtime_root=runtime_root,
        ),
    )
    probe_elapsed_seconds = round(time.perf_counter() - probe_started, 3)
    return {
        "rank": rank,
        "repeat_index": repeat_index,
        "case": asdict(case),
        "case_key": _public_repository_case_key(case),
        "primary_match": bool(probe_result.get("primary_match") is True),
        "primary_ecosystem": probe_result.get("primary_ecosystem"),
        "planner_status": probe_result.get("planner_status"),
        "clone_elapsed_s": clone_elapsed_seconds,
        "probe_elapsed_s": probe_elapsed_seconds,
        "snapshot_file_count": probe_result.get("snapshot_file_count"),
        "connected_file_count": probe_result.get("connected_file_count"),
    }


def _reset_stability_attempt_state(
    *,
    case: public_repo_matrix.PublicRepositoryCase,
    runtime_root: Path,
    preserve_case_probe_caches: bool = False,
) -> None:
    if preserve_case_probe_caches:
        public_repo_matrix.clear_public_repository_probe_attempt_cache(
            preserve_prepass_focus_paths=True,
            preserve_seed_plan_results=True,
            preserve_path_candidate_ecosystems=True,
            preserve_expected_ecosystem_hints=True,
        )
    else:
        # Preserve clone-time checkout metadata so first attempts can reuse the
        # same tracked-file/prepass inputs available during real checkout setup.
        # Expected-ecosystem hint metadata is static per ecosystem, so keep it
        # warm across attempts to avoid recomputing the same suffix/pathspec
        # caches for every public-repo rerun.
        public_repo_matrix.clear_public_repository_probe_attempt_cache(
            preserve_prepass_focus_paths=True,
            preserve_expected_ecosystem_hints=True,
        )
    runtime_dir = runtime_root / public_repo_matrix._case_checkout_name(case)
    shared_runtime_dir = public_repo_matrix._public_repository_case_shared_runtime_dir(
        runtime_root=runtime_root,
        case=case,
    )

    def _ignore_missing_cleanup_path(function, path, excinfo) -> None:
        if isinstance(excinfo[1], FileNotFoundError):
            return
        raise excinfo[1]

    # Warm repeats should retain the case-local runtime so snapshot lookups and
    # previously materialized artifacts can be reused. Cold attempts still start
    # from a clean slate below.
    if runtime_dir.exists() and not preserve_case_probe_caches:
        shutil.rmtree(runtime_dir, onexc=_ignore_missing_cleanup_path)
    if not preserve_case_probe_caches and shared_runtime_dir.exists():
        shutil.rmtree(shared_runtime_dir, onexc=_ignore_missing_cleanup_path)


def summarize_stability_attempts(
    *,
    attempts: list[dict[str, Any]],
    selected_cases: list[public_repo_matrix.PublicRepositoryCase],
    repeat_count: int,
) -> dict[str, Any]:
    grouped_attempts: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        grouped_attempts[
            str(attempt.get("case_key") or _public_repository_case_key(attempt["case"]))
        ].append(attempt)

    case_summaries: list[dict[str, Any]] = []
    stable_case_count = 0
    flaky_case_count = 0
    failing_case_count = 0
    passing_runs = 0

    for case in selected_cases:
        case_key = _public_repository_case_key(case)
        case_attempts = grouped_attempts.get(case_key, [])
        case_attempts.sort(key=lambda item: int(item["repeat_index"]))
        pass_count = sum(1 for item in case_attempts if item.get("primary_match") is True)
        passing_runs += pass_count
        probe_elapsed_values = [
            float(item["probe_elapsed_s"])
            for item in case_attempts
            if item.get("probe_elapsed_s") is not None
        ]
        clone_elapsed_values = [
            float(item["clone_elapsed_s"])
            for item in case_attempts
            if item.get("clone_elapsed_s") is not None
        ]
        if pass_count == len(case_attempts) == repeat_count:
            stability_status = "stable"
            stable_case_count += 1
        elif pass_count == 0 and len(case_attempts) == repeat_count:
            stability_status = "failing"
            failing_case_count += 1
        else:
            stability_status = "flaky"
            flaky_case_count += 1
        case_summaries.append(
            {
                "case": asdict(case),
                "case_key": case_key,
                "stability_status": stability_status,
                "run_count": len(case_attempts),
                "pass_count": pass_count,
                "clone_elapsed_s": {
                    "min": min(clone_elapsed_values) if clone_elapsed_values else None,
                    "max": max(clone_elapsed_values) if clone_elapsed_values else None,
                    "mean": round(mean(clone_elapsed_values), 3)
                    if clone_elapsed_values
                    else None,
                },
                "probe_elapsed_s": {
                    "min": min(probe_elapsed_values) if probe_elapsed_values else None,
                    "max": max(probe_elapsed_values) if probe_elapsed_values else None,
                    "mean": round(mean(probe_elapsed_values), 3)
                    if probe_elapsed_values
                    else None,
                },
                "attempts": case_attempts,
            }
        )

    return {
        "case_count": len(selected_cases),
        "repeat_count": repeat_count,
        "total_runs": len(attempts),
        "passing_runs": passing_runs,
        "stable_case_count": stable_case_count,
        "flaky_case_count": flaky_case_count,
        "failing_case_count": failing_case_count,
        "selected_languages": [case.language for case in selected_cases],
        "selected_case_keys": [_public_repository_case_key(case) for case in selected_cases],
        "cases": case_summaries,
    }


def run_public_repository_stability_matrix(
    *,
    checkout_root: Path,
    runtime_root: Path,
    repeats: int,
    sample_size: int | None = None,
    rank_limit: int | None = None,
    languages: tuple[str, ...] = (),
    cases: list[public_repo_matrix.PublicRepositoryCase] | None = None,
    unique_languages: bool = False,
    refresh: bool = False,
    case_timeout_seconds: int | None = 60,
) -> dict[str, Any]:
    if repeats <= 0:
        raise ValueError("repeats must be a positive integer")

    ordered_cases = (
        list(cases)
        if cases is not None
        else public_repo_matrix.ordered_public_repository_cases(languages=languages)
    )
    if unique_languages:
        ordered_cases = collapse_public_repository_cases_to_unique_languages(cases=ordered_cases)
    ranked_cases = limit_public_repository_cases_by_rank(
        cases=ordered_cases,
        rank_limit=rank_limit,
    )
    selected_cases = select_rank_stratified_public_repository_cases(
        cases=ranked_cases,
        sample_size=sample_size,
    )
    case_ranks = {
        _public_repository_case_key(case): index + 1 for index, case in enumerate(ordered_cases)
    }
    attempts: list[dict[str, Any]] = []
    probe_runtime_primed = False
    # Establish one outer git-relative-files cache scope around the whole matrix so the
    # per-case scopes nest within it and the clone-time tracked listings stay warm across the
    # repeated runs (the nested scopes are depth-counted, so this is a safe outer wrapper).
    collection_support.begin_git_repo_relative_files_cache_scope()
    try:
        for case in selected_cases:
            for repeat_index in range(repeats):
                rank = case_ranks[_public_repository_case_key(case)]
                try:
                    attempts.append(
                        _run_stability_case_attempt(
                            case=case,
                            rank=rank,
                            repeat_index=repeat_index,
                            checkout_root=checkout_root,
                            runtime_root=runtime_root,
                            refresh=refresh and repeat_index == 0,
                            case_timeout_seconds=case_timeout_seconds,
                            preserve_case_probe_caches=repeat_index > 0,
                            prime_runtime=not probe_runtime_primed,
                        )
                    )
                    probe_runtime_primed = True
                except Exception as exc:  # noqa: BLE001
                    attempts.append(
                        {
                            "rank": rank,
                            "repeat_index": repeat_index,
                            "case": asdict(case),
                            "case_key": _public_repository_case_key(case),
                            "primary_match": False,
                            "error": {
                                "code": exc.__class__.__name__,
                                "message": str(exc),
                                "details": {},
                            },
                        }
                    )
    finally:
        collection_support.end_git_repo_relative_files_cache_scope()
    return summarize_stability_attempts(
        attempts=attempts,
        selected_cases=selected_cases,
        repeat_count=repeats,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a repeated stratified public GitHub repository stability matrix."
    )
    parser.add_argument(
        "--checkout-root",
        type=Path,
        default=PROJECT_ROOT / "build" / "repository_intelligence_public_repo_stability_repos",
    )
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=PROJECT_ROOT / "build" / "repository_intelligence_public_repo_stability_runtime",
    )
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--sample-size", type=int, default=24)
    parser.add_argument(
        "--rank-limit",
        type=int,
        default=None,
        help="Optional maximum ordered rank to include before stratified sampling.",
    )
    parser.add_argument(
        "--language",
        dest="languages",
        action="append",
        default=[],
        help="Optional language/ecosystem filter. May be passed multiple times.",
    )
    parser.add_argument(
        "--unique-languages",
        action="store_true",
        help="Collapse duplicate language variants so each canonical language is selected once.",
    )
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--case-timeout-seconds", type=int, default=60)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = run_public_repository_stability_matrix(
        checkout_root=args.checkout_root,
        runtime_root=args.runtime_root,
        repeats=int(args.repeats),
        sample_size=args.sample_size,
        rank_limit=args.rank_limit,
        languages=tuple(args.languages),
        unique_languages=bool(args.unique_languages),
        refresh=bool(args.refresh),
        case_timeout_seconds=args.case_timeout_seconds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
