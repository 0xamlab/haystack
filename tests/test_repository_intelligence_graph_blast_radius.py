"""AR-OPT-7: graph signals split into localization (proximity) vs blast-radius
(dependents), with utility-hub damping so centrality doesn't rank hubs as suspects.
"""
from __future__ import annotations

from types import SimpleNamespace

from apps.api_server.services import repository_intelligence_graph as graph


def _manifest(files_deps: dict[str, list[str]]) -> dict:
    files = []
    for path, deps in files_deps.items():
        files.append(
            {
                "file_path": path,
                "language": "python",
                "symbols": [],
                "dependencies": [
                    {"target_file": target, "dependency_type": "imports"} for target in deps
                ],
                "symbol_references": [],
            }
        )
    return {"files": files}


def test_blast_radius_counts_dependents() -> None:
    manifest = _manifest(
        {
            "hub.py": [],
            "leaf.py": [],
            "imp1.py": ["hub.py"],
            "imp2.py": ["hub.py"],
            "imp3.py": ["hub.py"],
            "seed.py": ["leaf.py"],
        }
    )
    blast = graph._graph_blast_radius_scores(manifest)
    assert blast.get("hub.py") == 3.0  # imported by imp1/imp2/imp3
    assert blast.get("leaf.py") == 1.0  # imported by seed


def test_localization_damps_utility_hubs() -> None:
    # seed imports hub + leaf; hub is also imported by imp1/imp2/imp3 (high fan-in).
    manifest = _manifest(
        {
            "hub.py": [],
            "leaf.py": [],
            "seed.py": ["hub.py", "leaf.py"],
            "imp1.py": ["hub.py"],
            "imp2.py": ["hub.py"],
            "imp3.py": ["hub.py"],
        }
    )
    signals = SimpleNamespace(diagnostics=[], changed_files=["seed.py"], failing_tests=[])
    scores = graph._graph_proximity_scores(manifest, signals)
    # hub and leaf get equal RAW proximity (both are seed's out-deps), but the
    # high-fan-in hub is damped below the focused leaf; the seed stays on top.
    assert scores["seed.py"] > scores["leaf.py"]
    assert scores["hub.py"] < scores["leaf.py"]
