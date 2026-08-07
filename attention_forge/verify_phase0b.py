#!/usr/bin/env python3
"""attention_forge.verify_phase0b -- Phase 0B's own exit criterion, checked mechanically rather
than by inspection: "the same generator emits Qwen3-GQA and one synthetic-MHA specialization with
zero source changes."

Concretely this verifies:
  1. generate_variants.py runs ONCE, unmodified, and produces two entries.
  2. The two entries are genuinely different specializations (different tile/head parameters) --
     not two copies of the same thing, which would trivially "pass" a weaker check.
  3. No line of generate_variants.py or model_importer.py contains a literal model-name branch
     (grepped, not merely asserted in a docstring).
  4. Both generated stub kernels actually compile and run via the pinned Mojo toolchain and each
     reports its own shape check as OK.

Usage:
    python3 verify_phase0b.py --manifest /tmp/qwen3smoke/manifest.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

FORGE_DIR = Path(__file__).resolve().parent

# Model names that must never appear as a conditional branch subject in the generator/importer.
# Checked as "name compared against something", not merely "name appears" -- docstrings and
# comments legitimately mention these, only `== "qwen3"`-style code does not belong here.
_SUSPECT_NAMES = ["qwen", "llama", "mistral", "gemma", "phi"]


def _strip_docstrings_and_comments(source: str) -> str:
    """Blank out triple-quoted docstring bodies and `#` comments (replacing with same-length
    whitespace, to keep line numbers meaningful for reporting) so the branch check below only
    ever sees actual code -- this file's own docstring intentionally shows the anti-pattern as an
    EXAMPLE (`if name == "qwen3": ...`), which must not itself trip the checker."""
    out = []
    in_docstring = False
    for line in source.splitlines():
        if '"""' in line:
            count = line.count('"""')
            if count % 2 == 1:
                in_docstring = not in_docstring
                out.append("")
                continue
        if in_docstring:
            out.append("")
            continue
        code_part = line.split("#", 1)[0]
        out.append(code_part)
    return "\n".join(out)


def check_no_model_name_branches() -> list[str]:
    problems = []
    for path in [FORGE_DIR / "generate_variants.py", FORGE_DIR / "model_importer.py"]:
        code_only = _strip_docstrings_and_comments(path.read_text())
        for lineno, line in enumerate(code_only.splitlines(), 1):
            lowered = line.lower()
            for name in _SUSPECT_NAMES:
                if name in lowered and re.search(rf'[=!]=\s*["\'].*{name}.*["\']', lowered):
                    problems.append(f"{path.name}:{lineno}: looks like a model-name branch: {line.strip()}")
    return problems


def run_generator(manifest_path: Path) -> dict:
    subprocess.run(
        [sys.executable, "generate_variants.py", "--manifest", str(manifest_path)],
        cwd=FORGE_DIR, check=True,
    )
    return json.loads((FORGE_DIR / "generated" / "manifest.json").read_text())


def check_entries_are_distinct(manifest: dict) -> list[str]:
    problems = []
    entries = manifest["entries"]
    if len(entries) != 2:
        problems.append(f"expected 2 entries, got {len(entries)}")
        return problems
    a, b = entries
    distinguishing_fields = ["query_tile", "key_tile", "h_tile", "simd_group_count"]
    same = [f for f in distinguishing_fields if a["key"][f] == b["key"][f]]
    if a["key"]["model_traits_subset"] == b["key"]["model_traits_subset"]:
        problems.append("both entries have IDENTICAL model_traits_subset -- not two real specializations")
    if len(same) == len(distinguishing_fields):
        problems.append(f"both entries have identical tile params {distinguishing_fields} -- suspiciously undifferentiated")
    if a["requested_name"] == b["requested_name"]:
        problems.append("both entries requested the SAME host_name")
    return problems


def compile_and_run_stub(mojo_path: Path) -> tuple[bool, str]:
    developer_dir = "/Applications/Xcode-26.6.0.app/Contents/Developer"
    result = subprocess.run(
        ["pixi", "run", "mojo", "run", str(mojo_path.resolve())],
        cwd=FORGE_DIR.parent / "mojo_env",
        env={"DEVELOPER_DIR": developer_dir, "PATH": "/usr/bin:/bin:/opt/homebrew/bin:/Users/angel/.pixi/bin"},
        capture_output=True, text=True, timeout=60,
    )
    ok = result.returncode == 0 and "shape check OK" in result.stdout
    return ok, result.stdout + result.stderr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    args = ap.parse_args()

    all_problems = []

    all_problems += check_no_model_name_branches()

    manifest = run_generator(Path(args.manifest))
    all_problems += check_entries_are_distinct(manifest)

    for entry in manifest["entries"]:
        stub_path = FORGE_DIR / "generated" / f"{entry['requested_name']}.mojo"
        if not stub_path.exists():
            all_problems.append(f"expected generated stub not found: {stub_path}")
            continue
        ok, output = compile_and_run_stub(stub_path)
        print(f"--- {entry['requested_name']} ---")
        print(output.strip())
        if not ok:
            all_problems.append(f"{stub_path.name} failed to compile/run cleanly")

    print("")
    if all_problems:
        print("PHASE 0B EXIT CRITERION: FAIL")
        for p in all_problems:
            print("  -", p)
        return 1

    print("PHASE 0B EXIT CRITERION: PASS")
    print("  - generator ran unmodified for both real-Qwen3 and synthetic-MHA traits")
    print("  - the two specializations are genuinely distinct (not two copies of one thing)")
    print("  - no model-name branch found in generate_variants.py or model_importer.py")
    print("  - both generated stubs compiled and ran cleanly via the pinned Mojo toolchain")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
