#!/usr/bin/env python3
"""Write the narrative that accompanies the IP schedule, with every number taken from the snapshot.

Sections, in the order an offering document uses them:

A. "Intellectual Property" — the subsection of *The Company and its Business* in a Regulation
   Crowdfunding offering memorandum (StartEngine's Form C exhibit format): what is owned, what
   is not, how it is protected, the open-source posture, material third-party dependencies,
   and the litigation sentence.
B. The same text extended for a Regulation A offering circular (Form 1-A, Part II, Item 7),
   which additionally asks for the material terms and duration of licenses.
C. Draft intellectual-property risk factors.
D. A pointer to the internal valuation note (no cost figure appears in the narrative).

Output is Markdown (``Thyn_IP_Narrative_<date>.md``) plus ``narrative_numbers.json`` listing
every figure the text used and where in the snapshot it came from, so a test can prove the
prose and the schedule agree. Bracketed ``[confirm: …]`` markers flag the statements only the
company can attest to.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def n(value: Any) -> str:
    return f"{value:,}" if isinstance(value, int) else str(value)


def engine_row(snapshot: dict[str, Any]) -> dict[str, Any]:
    row = next((r for r in snapshot["repos"] if r["key"] == "algenta" and r.get("measured")), None)
    if row is None:
        raise SystemExit(
            "narrative: the snapshot has no measured 'algenta' repository; run collect.py with the "
            "engine included (it is the subject of the narrative)"
        )
    return row


def join_and(names: list[str]) -> str:
    """'A', 'A and B', 'A, B and C' — never a leading ' and '."""
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" and {names[-1]}"


def core_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in snapshot["repos"] if r["role"] == "core" and r.get("measured")]


def build(snapshot: dict[str, Any], derived: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    issuer = snapshot["issuer"]
    owner = issuer["owner"]
    eng = engine_row(snapshot)
    cores = core_rows(snapshot)
    c = eng["contract"] or {}
    gpu = c.get("gpu_kernels") or {}
    backends = gpu.get("backend_counts") or {}
    mojo_tracked = eng["code"]["mojo_tracked"]
    mojo_authored = eng["code"]["authored"].get("Mojo", {"lines": 0, "files": 0})
    core_authored = sum(r["code"]["authored_lines"] for r in cores)
    marks = [m for m in snapshot["marks"] if m.get("scope") == "core"]
    mark_names = join_and([m["mark"].upper() for m in marks]) or "[marks]"
    mark_dates = "; ".join(
        f"{m['mark'].upper()} {m['first_use_evidence'] or '[date]'}" for m in marks
    )
    first_use = sorted(m["first_use_evidence"] for m in marks if m.get("first_use_evidence"))
    domains_core = [d["name"] for d in snapshot["domains"] if d.get("scope") == "core"]
    domains_mention = [d["name"] for d in snapshot["domains"] if d.get("scope") != "core"]
    expiries = sorted(d["expires"] for d in snapshot["domains"] if d.get("expires"))
    humans = {h["name"] for r in cores for h in r["contributors"]["humans"]}
    unmapped = [u for r in cores for u in r["contributors"]["unmapped"]]
    date = snapshot["generated_on"]

    numbers = {
        "snapshot_date": date,
        "engine_ref": f"{eng['ref']} @ {eng['sha_short']}",
        "engine_mojo_tracked_lines": mojo_tracked["lines"],
        "engine_mojo_tracked_files": mojo_tracked["files"],
        "engine_mojo_authored_lines": mojo_authored["lines"],
        "engine_function_count": c.get("function_count"),
        "engine_module_count": c.get("module_count"),
        "engine_gpu_kernel_count": gpu.get("kernel_count"),
        "engine_gpu_backend_counts": backends,
        "engine_gpu_kernel_modules": gpu.get("module_count"),
        "core_repositories": len(cores),
        "core_authored_lines": core_authored,
        "core_marks": len(marks),
        "earliest_mark_use": first_use[0] if first_use else None,
        "domain_expiry_min": expiries[0] if expiries else None,
        "domain_expiry_max": expiries[-1] if expiries else None,
        "human_contributors": sorted(humans),
        "unmapped_contributors": unmapped,
    }

    founder = (
        "All of this code was written by the Company's founder, whose rights in it have been "
        "assigned to the Company; based on the repositories' commit history, no employee or "
        "contractor has contributed code."
        if len(humans) == 1 and not unmapped
        else "[confirm: the commit history shows contributor identities beyond the founder — "
        "document their assignments before using this sentence.]"
    )

    a_paragraphs = [
        "**Intellectual Property**",
        (
            "The Company's principal intellectual property is proprietary software developed "
            "in-house. It consists of (i) the Algenta engine, a self-hosted application runtime "
            "for AI systems whose numerical kernels are written in the Mojo programming language "
            "and are shipped only as compiled, signed binaries, together with its API server, "
            "runtime, Python and TypeScript SDKs and MCP server; and (ii) three applications built "
            "on that engine: Codna (governed code review and repair), Telys (an embedded memory "
            "engine for AI agents) and SQAI (governed structured-data access for AI agents). "
            f"As of {date}, the engine repository held {n(mojo_tracked['lines'])} lines of Mojo "
            f"source in {n(mojo_tracked['files'])} files ({n(mojo_authored['lines'])} lines "
            f"excluding generated test code), exposing {n(c.get('function_count'))} runtime "
            f"functions in {n(c.get('module_count'))} modules together with "
            f"{n(gpu.get('kernel_count'))} GPU kernels "
            f"({n(backends.get('cuda'))} for NVIDIA CUDA and {n(backends.get('metal'))} for Apple "
            f"Metal) in {n(gpu.get('module_count'))} kernel modules, and the {len(cores)} core "
            f"repositories together held {n(core_authored)} authored lines of source code. "
            f"{founder}"
        ),
        (
            "The Company does not own any patents and has not filed any patent applications. It "
            f"has not registered any trademarks; it uses the names {mark_names} as unregistered "
            "marks in commerce, with the earliest dated public record for each being "
            f"{mark_dates}. "
            f"The Company owns the domain names {', '.join(domains_core)}"
            + (
                f", together with {' and '.join(domains_mention)} for products in development."
                if domains_mention
                else "."
            )
        ),
        (
            "The Company relies primarily on trade secret protection and copyright for its "
            "software. The source code of the engine's Mojo kernels is held in private "
            "repositories and is never distributed; the engine is licensed under the Algenta "
            "Community License, which prohibits reverse engineering of the compiled engine and "
            "sub-licensing, and under commercial per-device and per-compute-unit tiers. The "
            "Company's client SDKs, framework integrations and open-source kernels, and the source "
            "code of Codna, Telys and SQAI, are made available under the Apache License, Version "
            "2.0, a permissive open-source license, which the Company believes broadens adoption "
            "of the engine without disclosing the engine itself. The Company's websites and hosted "
            "services are provided under its Terms of Service, which reserve all rights in its "
            "software, models, interfaces, workflows, trademarks, logos and documentation."
        ),
        (
            "The Company's software depends on the Mojo compiler and toolchain, developed by "
            "Modular (acquired by Qualcomm in 2026) and licensed to the Company on Modular's "
            "standard terms; Codna incorporates a fork of the open-source Cline SDK under the "
            "Apache License, Version 2.0, and the Codna IDE application is built on the Eclipse "
            "Theia platform under the Eclipse Public License 2.0. The Company believes its use of "
            "third-party and "
            "open-source components complies with their licenses and maintains a component "
            "inventory (Schedule tab 7)."
        ),
        (
            "**Litigation.** The Company is not involved in any litigation, and its management is "
            "not aware of any pending or threatened legal actions relating to its intellectual "
            "property, the conduct of its business activities, or otherwise. [confirm]"
        ),
    ]

    b_extra = [
        (
            "*Material terms and duration of licenses (Form 1-A, Item 7(a)(2)).* The Algenta "
            "Community License has no fixed term and is royalty-free within its community-use "
            "thresholds; commercial licenses are sold monthly per device (Pro and Team tiers) or "
            "per compute unit (Server tier), are verified offline, and lapse to the Community "
            "tier on non-renewal without interrupting the software. Licenses the Company grants "
            "under the "
            "Apache License, Version 2.0 are perpetual, worldwide and royalty-free, and include a "
            "patent license from the Company for the covered code. The Company's inbound license "
            "to the Mojo toolchain is on Modular's standard terms with no fixed term "
            "[confirm: current Modular/Qualcomm license reference]. Domain registrations expire "
            f"between {expiries[0] if expiries else '[date]'} and "
            f"{expiries[-1] if expiries else '[date]'} "
            "and are renewable. No license material to the Company's business is due to expire or "
            "is subject to a pending termination."
        ),
    ]

    risk_factors = [
        (
            "**We may not be able to protect our intellectual property.** We rely on trade "
            "secrets, copyright, contractual restrictions and unregistered trademarks rather than "
            "patents. We have no issued patents or registered marks, and a third party could "
            "independently develop equivalent technology or challenge our use of our product "
            "names. Much of the software surrounding our engine, including the source code of "
            "Codna, Telys and SQAI, is distributed under the Apache License, Version 2.0, and "
            "competitors may use it. Policing infringement is costly, and litigation to protect "
            "our rights or to defend against claims could harm our business regardless of outcome."
        ),
        (
            "**We depend on the Mojo language and toolchain, which we do not control.** Our "
            "engine is written in Mojo, a language created by Modular, which was acquired by "
            "Qualcomm in 2026. Changes to the toolchain's licensing, pricing, availability or "
            "direction, or its discontinuation, could require costly re-engineering. The pool of "
            "engineers experienced in Mojo is small, which may make it harder and more expensive "
            "to hire."
        ),
        (
            "**Our software incorporates open-source components and we distribute much of our own "
            "software under an open-source license.** Failure to comply with third-party license "
            "terms could require us to release source code, re-engineer products or pay damages. "
            "Because the Apache License, Version 2.0 permits anyone to use, modify and "
            "redistribute our SDKs, integrations and application source code, we cannot prevent "
            "others from "
            "building competing products on them; our proprietary engine and its license terms are "
            "our principal protection."
        ),
        (
            "**We depend on our founder, who wrote substantially all of our software.** Our "
            "founder authored our code base and holds the detailed knowledge of its design. The "
            "loss of the founder's services, or an inability to hire senior engineers to share "
            "that knowledge, would materially harm our ability to maintain and extend our products."
        ),
    ]

    lines: list[str] = [
        f"# Intellectual property narrative — {owner}",
        "",
        f"Snapshot {date} · engine {eng['ref']} @ {eng['sha_short']} · numbers from snapshot.json "
        "and derived.json (see narrative_numbers.json). Bracketed [confirm] markers are for the "
        "company to attest before filing.",
        "",
        '## A. "Intellectual Property" — offering memorandum subsection '
        "(Regulation Crowdfunding, Form C exhibit)",
        "",
    ]
    for p in a_paragraphs:
        lines += [p, ""]
    lines += [
        "## B. Offering circular variant (Regulation A, Form 1-A Part II, Item 7)",
        "",
        "Use Section A in full, followed by:",
        "",
    ]
    for p in b_extra:
        lines += [p, ""]
    lines += ["## C. Draft risk factors (intellectual property)", ""]
    for p in risk_factors:
        lines += [p, ""]
    lines += [
        "## D. Valuation support",
        "",
        "Deliberately not part of this narrative. The cost-approach range and market comparables "
        "are in Valuation_support_internal_<date>.md (internal); the Form C valuation paragraph "
        "should cite the board's method and the market comparables, not a cost figure.",
        "",
    ]
    return "\n".join(lines), numbers


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument(
        "--derived", type=Path, default=None, help="defaults to derived.json beside the snapshot"
    )
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--basename", default=None, help="defaults to Thyn_IP_Narrative_<date>")
    args = ap.parse_args(argv)

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    derived_path = args.derived or (args.snapshot.parent / "derived.json")
    derived = json.loads(derived_path.read_text(encoding="utf-8"))
    out_dir = args.out_dir or args.snapshot.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    base = args.basename or f"Thyn_IP_Narrative_{snapshot['generated_on']}"

    text, numbers = build(snapshot, derived)
    (out_dir / f"{base}.md").write_text(text, encoding="utf-8")
    (out_dir / "narrative_numbers.json").write_text(
        json.dumps(numbers, indent=2) + "\n", encoding="utf-8"
    )
    sys.stderr.write(f"[ip-schedule] wrote {out_dir / base}.md and narrative_numbers.json\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
