"""The IP-schedule generator must reproduce the canonical code-size figures, not approximate them.

`scripts/count_mojo_loc.sh` is the number the investor deck, the site and the scorecard quote
for "lines of Mojo". `scripts/ip_schedule/collect.py` re-derives that figure from
`git ls-tree` + `git cat-file` without a checkout, and adds per-language authored counts,
contributors and the packaged function/module counts. If the two ever disagree, the schedule
is citing a number nobody can reproduce, which is exactly the defect this generator exists to
remove. These tests run offline against the local HEAD so they pass on any clone, shallow or
not, with no network.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
COLLECT = REPO / "scripts" / "ip_schedule" / "collect.py"
RENDER = REPO / "scripts" / "ip_schedule" / "render.py"
NARRATIVE = REPO / "scripts" / "ip_schedule" / "narrative.py"
COUNT = REPO / "scripts" / "count_mojo_loc.sh"
OWNER = "Seville AI Technologies, Inc. d/b/a Thyn"


@pytest.fixture(scope="module")
def snapshot(tmp_path_factory: pytest.TempPathFactory) -> dict:
    out = tmp_path_factory.mktemp("ip_schedule") / "snapshot.json"
    subprocess.run(
        [
            sys.executable,
            str(COLLECT),
            "--offline",
            "--self",
            "--ref",
            "head",
            "--only",
            "algenta",
            "--out",
            str(out),
        ],
        check=True,
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    return json.loads(out.read_text(encoding="utf-8"))


def _engine(snapshot: dict) -> dict:
    return next(r for r in snapshot["repos"] if r["key"] == "algenta")


def test_tracked_mojo_matches_count_mojo_loc(snapshot: dict) -> None:
    script = subprocess.run(
        ["bash", str(COUNT), str(REPO)], check=True, capture_output=True, text=True
    ).stdout
    total_files = int(re.search(r"^Mojo files: (\d+)$", script, re.M).group(1))
    total_lines = int(re.search(r"^Total lines: (\d+)$", script, re.M).group(1))
    by_dir = {
        m.group(1).strip(): (int(m.group(2)), int(m.group(3)))
        for m in re.finditer(r"^\s{2}(\S.*?)\s+(\d+) files\s+(\d+) lines$", script, re.M)
    }

    code = _engine(snapshot)["code"]
    assert code["mojo_tracked"]["files"] == total_files
    assert code["mojo_tracked"]["lines"] == total_lines
    ours = {k: (v["files"], v["lines"]) for k, v in code["mojo_by_dir"].items()}
    assert ours == by_dir


def test_generated_mojo_is_excluded_from_authored_but_present_in_tracked(snapshot: dict) -> None:
    code = _engine(snapshot)["code"]
    generated = code["excluded"].get("generated:mojo/tests/libs/")
    assert generated and generated["files"] > 0, "the generated test tree must be recognised"
    excluded_mojo = code["excluded_by_language"].get("Mojo", {"lines": 0, "files": 0})
    # authored + excluded == tracked, per language: nothing is dropped on the floor
    assert (
        code["authored"]["Mojo"]["lines"] + excluded_mojo["lines"] == code["mojo_tracked"]["lines"]
    )
    assert (
        code["authored"]["Mojo"]["files"] + excluded_mojo["files"] == code["mojo_tracked"]["files"]
    )
    assert excluded_mojo["lines"] >= generated["lines"]


def test_contract_counts_and_single_human_owner(snapshot: dict) -> None:
    engine = _engine(snapshot)
    contract = json.loads(
        (REPO / "packages/algenta/algenta/runtime_library_contract.json").read_text()
    )
    assert engine["contract"]["function_count"] == contract["function_count"]
    assert engine["contract"]["module_count"] == contract["module_count"]
    gpu = engine["contract"]["gpu_kernels"]
    assert gpu["kernel_count"] == contract["engine_kernels"]["kernel_count"]
    assert gpu["backend_counts"] == contract["engine_kernels"]["backend_counts"]
    assert gpu["module_count"] == contract["engine_kernels"]["module_count"]
    assert sum(gpu["roles"].values()) == gpu["kernel_count"]
    assert engine["copyright_owner"] == OWNER == snapshot["issuer"]["owner"]
    # root-level TOML arrays must not be swallowed by the last [[table]] above them
    assert len(snapshot["cleanup_items"]) >= 5
    assert len(snapshot["protection_measures"]) >= 3
    assert len(snapshot["trade_secrets"]) >= 5 and len(snapshot["outbound_licenses"]) >= 3
    humans = engine["contributors"]["humans"]
    # a shallow CI checkout may hold only a synthetic merge commit (skipped by --no-merges),
    # so the invariant is "never more than the founder, never an unmapped human"
    if engine["history_complete"]:
        assert len(humans) == 1, humans
    else:
        assert len(humans) <= 1, humans
    assert engine["contributors"]["unmapped"] == [], engine["contributors"]["unmapped"]
    assert all(re.search(r"\[bot\]$|-bot$", b["name"]) for b in engine["contributors"]["bots"])


def test_render_builds_the_workbook(snapshot: dict, tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    snap_path = tmp_path / "snapshot.json"
    snap_path.write_text(json.dumps(snapshot), encoding="utf-8")
    subprocess.run(
        [sys.executable, str(RENDER), "--snapshot", str(snap_path), "--basename", "schedule"],
        check=True,
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    wb = openpyxl.load_workbook(tmp_path / "schedule.xlsx", read_only=True)
    assert wb.sheetnames[:3] == ["0 Summary", "1 Registered IP", "2 Unregistered marks"]
    # the upload workbook carries no internal tab and does not list one in its index
    assert wb.sheetnames[-1] == "11 Provenance"
    assert not any("(internal" in n for n in wb.sheetnames)
    summary = list(wb["0 Summary"].iter_rows(values_only=True))
    assert not any(r and isinstance(r[1], str) and "(internal" in r[1] for r in summary)
    wb_i = openpyxl.load_workbook(tmp_path / "schedule_internal.xlsx", read_only=True)
    assert wb_i.sheetnames[-1] == "12 Cleanup list (internal)"
    assert all(len(name) <= 31 for name in wb_i.sheetnames)
    assets = wb["4 Software assets"]
    rows = list(assets.iter_rows(values_only=True))
    owner_col = rows[0].index("Copyright owner")
    repo_col = rows[0].index("Repository")
    # data rows only: the sheet ends with a blank line and an italic note row
    owners = {r[owner_col] for r in rows[1:] if r and r[repo_col]}
    assert owners == {OWNER}
    derived = json.loads((tmp_path / "derived.json").read_text())
    assert (
        derived["headline"]["engine"]["mojo_tracked_lines"]
        == _engine(snapshot)["code"]["mojo_tracked"]["lines"]
    )
    ca = derived["cost_approach"]
    code = _engine(snapshot)["code"]
    assert ca["basis"]["mojo_product_lines"] == code["product_by_language"]["Mojo"]["lines"]
    assert 0 < ca["basis"]["mojo_product_lines"] < code["authored"]["Mojo"]["lines"]
    assert sum(v["lines"] for v in code["authored_by_area"].values()) == code["authored_lines"]
    assert (tmp_path / f"Valuation_support_internal_{snapshot['generated_on']}.md").exists()
    md = (tmp_path / "schedule.md").read_text(encoding="utf-8")
    assert "decision engine" not in md.lower()


def test_narrative_numbers_trace_to_the_snapshot(snapshot: dict, tmp_path: Path) -> None:
    pytest.importorskip("openpyxl")
    snap_path = tmp_path / "snapshot.json"
    snap_path.write_text(json.dumps(snapshot), encoding="utf-8")
    for script in (RENDER, NARRATIVE):
        subprocess.run(
            [sys.executable, str(script), "--snapshot", str(snap_path), "--basename", "out"],
            check=True,
            cwd=REPO,
            capture_output=True,
            text=True,
        )
    numbers = json.loads((tmp_path / "narrative_numbers.json").read_text())
    engine = _engine(snapshot)
    assert numbers["engine_mojo_tracked_lines"] == engine["code"]["mojo_tracked"]["lines"]
    assert numbers["engine_mojo_authored_lines"] == engine["code"]["authored"]["Mojo"]["lines"]
    assert numbers["engine_function_count"] == engine["contract"]["function_count"]
    assert numbers["engine_module_count"] == engine["contract"]["module_count"]
    assert numbers["engine_gpu_kernel_count"] == engine["contract"]["gpu_kernels"]["kernel_count"]
    assert engine["dependencies"]["license_lookup"].startswith("skipped: --offline")
    assert engine["dependencies"]["flagged"] == []
    assert engine["dependencies"]["licenses"] == {}
    assert numbers["human_contributors"] == sorted(
        h["name"] for h in engine["contributors"]["humans"]
    )
    text = (tmp_path / "out.md").read_text(encoding="utf-8")
    # every headline figure appears in the prose, formatted with thousands separators
    for key in (
        "engine_mojo_tracked_lines",
        "engine_function_count",
        "engine_module_count",
        "engine_gpu_kernel_count",
    ):
        assert f"{numbers[key]:,}" in text, key
    assert "decision engine" not in text.lower()
    assert "Seville AI Technologies, Inc. d/b/a Thyn" in text


def test_join_and_never_produces_a_dangling_conjunction() -> None:
    # load the module by path; no sys.path mutation leaks into the rest of the suite
    spec = importlib.util.spec_from_file_location("ip_schedule_narrative", NARRATIVE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    join_and = module.join_and

    assert join_and([]) == ""
    assert join_and(["THYN"]) == "THYN"
    assert join_and(["THYN", "ALGENTA"]) == "THYN and ALGENTA"
    assert join_and(["A", "B", "C"]) == "A, B and C"
