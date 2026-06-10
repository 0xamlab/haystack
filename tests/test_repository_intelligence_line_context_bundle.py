"""AR-OPT-4: full line-context bundle for the verified_agentic tier.

The bundle must hand the agent the actual numbered source of the top suspect
symbols (diagnostic-touching first) so it can edit without re-reading the repo,
while staying bounded by top-K / per-symbol-line / total-token caps.
"""
from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_planner_generation import (
    _build_line_context_bundle,
)


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _manifest(files: list[dict]) -> dict:
    return {"files": files}


def test_bundle_numbered_source_diagnostic_ranking_and_imports(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "pkg/svc.py",
        "def alpha(x):\n"  # 1
        "    return x + 1\n"  # 2
        "\n"  # 3
        "def beta(y):\n"  # 4
        "    return y - 1\n",  # 5
    )
    files = [
        {
            "file_path": "pkg/svc.py",
            "language": "python",
            "symbols": [
                {"symbol_id": "s1", "symbol_name": "alpha", "symbol_kind": "function",
                 "start_line": 1, "end_line": 2, "parent_symbol_id": None},
                {"symbol_id": "s2", "symbol_name": "beta", "symbol_kind": "function",
                 "start_line": 4, "end_line": 5, "parent_symbol_id": None},
            ],
            "dependencies": [{"target_file": "pkg/util.py", "dependency_type": "imports"}],
        }
    ]
    triage = {
        "suspect_files": ["pkg/svc.py"],
        "signals": {
            "diagnostics": [
                {"path": "pkg/svc.py", "line": 5, "severity": "error", "message": "beta off by one"}
            ]
        },
    }

    bundle = _build_line_context_bundle(
        snapshot_manifest=_manifest(files), triage_manifest=triage, root_path=tmp_path
    )

    assert bundle
    # diagnostic-touched symbol (beta spans line 5) ranks ahead of alpha
    assert bundle[0]["symbol_name"] == "beta"
    assert bundle[0]["touching_diagnostics"] == ["beta off by one"]
    # numbered source uses 1-based line numbers + a tab + the real line
    assert "     5\t    return y - 1" in bundle[0]["numbered_source"]
    assert bundle[0]["nearest_imports"] == ["pkg/util.py"]
    # deterministic
    assert _build_line_context_bundle(
        snapshot_manifest=_manifest(files), triage_manifest=triage, root_path=tmp_path
    ) == bundle


def test_bundle_respects_top_k_files_and_line_caps(tmp_path: Path) -> None:
    files, suspect = [], []
    for index in range(5):
        rel = f"f{index}.py"
        body = "\n".join(f"# line {n}" for n in range(1, 201))
        _write(tmp_path, rel, "def fn():\n" + body + "\n")
        files.append(
            {
                "file_path": rel,
                "language": "python",
                "symbols": [
                    {"symbol_id": f"s{index}", "symbol_name": f"fn{index}",
                     "symbol_kind": "function", "start_line": 1, "end_line": 201,
                     "parent_symbol_id": None}
                ],
                "dependencies": [],
            }
        )
        suspect.append(rel)
    triage = {"suspect_files": suspect, "signals": {"diagnostics": []}}

    bundle = _build_line_context_bundle(
        snapshot_manifest=_manifest(files),
        triage_manifest=triage,
        root_path=tmp_path,
        top_k_files=3,
        max_lines_per_symbol=120,
        max_total_context_tokens=10**9,
    )

    assert len({entry["file_path"] for entry in bundle}) <= 3
    for entry in bundle:
        assert (entry["end_line"] - entry["start_line"] + 1) <= 120
        assert len(entry["numbered_source"].splitlines()) <= 120
    # file order follows the suspect ranking
    assert bundle[0]["file_path"] == "f0.py"


def test_bundle_total_token_budget_stops_early(tmp_path: Path) -> None:
    files, suspect = [], []
    for index in range(3):
        rel = f"big{index}.py"
        body = "\n".join("x = " + "a" * 80 for _ in range(100))
        _write(tmp_path, rel, "def fn():\n" + body + "\n")
        files.append(
            {
                "file_path": rel,
                "language": "python",
                "symbols": [
                    {"symbol_id": f"s{index}", "symbol_name": f"fn{index}",
                     "symbol_kind": "function", "start_line": 1, "end_line": 101,
                     "parent_symbol_id": None}
                ],
                "dependencies": [],
            }
        )
        suspect.append(rel)
    triage = {"suspect_files": suspect, "signals": {"diagnostics": []}}

    bundle = _build_line_context_bundle(
        snapshot_manifest=_manifest(files),
        triage_manifest=triage,
        root_path=tmp_path,
        max_total_context_tokens=500,
    )
    # the first entry is always included; the budget then halts further entries
    assert 1 <= len(bundle) < 3


def test_bundle_enclosing_symbol_resolved_from_parent(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "c.py",
        "class Foo:\n"  # 1
        "    def method(self):\n"  # 2
        "        return 1\n",  # 3
    )
    files = [
        {
            "file_path": "c.py",
            "language": "python",
            "symbols": [
                {"symbol_id": "cls", "symbol_name": "Foo", "symbol_kind": "class",
                 "start_line": 1, "end_line": 3, "parent_symbol_id": None},
                {"symbol_id": "m", "symbol_name": "method", "symbol_kind": "method",
                 "start_line": 2, "end_line": 3, "parent_symbol_id": "cls"},
            ],
            "dependencies": [],
        }
    ]
    triage = {"suspect_files": ["c.py"], "signals": {"diagnostics": []}}

    bundle = _build_line_context_bundle(
        snapshot_manifest=_manifest(files),
        triage_manifest=triage,
        root_path=tmp_path,
        top_k_symbols_per_file=3,
    )
    by_name = {entry["symbol_name"]: entry for entry in bundle}
    assert by_name["method"]["enclosing_symbol"] == "Foo"
    assert by_name["Foo"]["enclosing_symbol"] is None
