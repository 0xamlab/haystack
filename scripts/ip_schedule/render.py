#!/usr/bin/env python3
"""Render ``snapshot.json`` (from ``collect.py``) into the Schedule of Intellectual Property.

Outputs, next to the snapshot unless ``--out-dir`` says otherwise:

* ``Thyn_IP_Schedule_<date>.xlsx`` — the diligence upload: one tab per schedule, an Owner
  column on every asset row, frozen headers.
* ``Thyn_IP_Schedule_<date>.md`` — the same tables in Markdown for review and diffing.
* ``derived.json`` — figures computed from the snapshot (headline totals and the internal
  COCOMO II replacement-cost estimate), so the narrative document reads numbers from one
  place instead of retyping them.

Nothing here measures anything; every value comes from the snapshot, so re-running
``collect.py`` is the only way a number changes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill("solid", fgColor="1F3A5F")
HEADER_FONT = Font(bold=True, color="FFFFFF")
WRAP = Alignment(wrap_text=True, vertical="top")

Row = list[Any]


# --------------------------------------------------------------------------------------
# Derived figures
# --------------------------------------------------------------------------------------


def fmt(n: Any) -> str:
    if isinstance(n, int):
        return f"{n:,}"
    if isinstance(n, float):
        return f"{n:,.1f}"
    return "" if n is None else str(n)


def grouped_flags(flagged: list[dict[str, Any]]) -> list[str]:
    """Collapse flagged dependencies that share a license and an npm scope (``@theia/*``)."""
    groups: dict[tuple[str, str], list[str]] = {}
    for f in flagged:
        name = f["name"]
        scope = name.split("/", 1)[0] + "/*" if name.startswith("@") and "/" in name else name
        groups.setdefault((scope, str(f.get("license"))), []).append(name)
    out = []
    for (scope, lic), names in groups.items():
        if len(names) == 1:
            out.append(f"{names[0]} ({lic})")
        else:
            out.append(f"{len(names)} {scope} packages ({lic}; e.g. {names[0]})")
    return out


def measured(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in snapshot["repos"] if r.get("measured")]


def core(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in measured(snapshot) if r["role"] == "core"]


def cost_approach(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Replacement-cost floor for the proprietary engine, built from measured facts only.

    Basis: authored Mojo in the engine's product directories and the founder's actual months
    from first commit to snapshot (both from git). Readings: historical cost; replacement by an
    equally equipped team at a fraction of the founder's measured rate; each at a standard and
    at a scarce-skill (Mojo / GPU kernel) rate; then verification allowance and developer's
    profit. No KLOC model: COCOMO-style estimates are meaningless for this codebase.
    """
    v = snapshot.get("valuation_inputs") or {}
    std = float(v.get("loaded_cost_per_person_month_usd", 18000))
    scarce = float(v.get("scarce_skill_loaded_cost_per_person_month_usd", 25000))
    rel = [float(x) for x in v.get("replacement_relative_productivity", [0.5, 0.25])]
    if not rel or any(f <= 0 for f in rel):
        return {
            "available": False,
            "reason": "replacement_relative_productivity must be a non-empty list of positive "
            "factors",
        }
    team = int(v.get("replacement_team_size", 3))
    lead = float(v.get("hiring_lead_months", 4))
    verify = float(v.get("verification_allowance", 0.2))
    profit = float(v.get("developer_profit", 0.25))
    engine = next((r for r in core(snapshot) if r["key"] == "algenta"), None)
    if engine is None:
        return {"available": False, "reason": "engine not measured"}
    code = engine["code"]
    mojo_product = code.get("product_by_language", {}).get("Mojo", {}).get("lines", 0)
    first, snap = engine.get("first_commit"), engine.get("sha_date")
    founder_months = None
    if first and snap:
        y0, m0, d0 = (int(x) for x in first.split("-"))
        y1, m1, d1 = (int(x) for x in snap.split("-"))
        founder_months = max(0.5, round((y1 - y0) * 12 + (m1 - m0) + (d1 - d0) / 30.0, 1))
    if not founder_months:
        return {"available": False, "reason": "no commit dates for the engine"}
    rate_lpm = mojo_product / founder_months  # measured product Mojo lines per founder-month

    def reading(label: str, effort_pm: float, note: str, schedule: float | None) -> dict[str, Any]:
        return {
            "label": label,
            "effort_person_months": round(effort_pm, 1),
            "effort_person_years": round(effort_pm / 12, 2),
            "schedule_months": None if schedule is None else round(schedule, 1),
            "cost_standard_usd": round(effort_pm * std, -3),
            "cost_scarce_skill_usd": round(effort_pm * scarce, -3),
            "note": note,
        }

    readings = [
        reading(
            "Historical (actual)",
            founder_months,
            f"one founder, {founder_months} months, {first} → {snap}",
            founder_months,
        )
    ]
    for f in rel:
        pm = founder_months / f
        readings.append(
            reading(
                f"Replacement team at {f:g}x founder rate",
                pm,
                f"{team} engineers; schedule includes {lead:g} months hiring lead",
                pm / team + lead,
            )
        )
    loaded = []
    for rd in readings[1:]:
        base_s, base_k = rd["cost_standard_usd"], rd["cost_scarce_skill_usd"]
        loaded.append(
            {
                "label": rd["label"] + " + verification + developer's profit",
                "cost_standard_usd": round(base_s * (1 + verify) * (1 + profit), -3),
                "cost_scarce_skill_usd": round(base_k * (1 + verify) * (1 + profit), -3),
            }
        )
    floor_low = min(x["cost_standard_usd"] for x in loaded)
    floor_high = max(x["cost_scarce_skill_usd"] for x in loaded)
    return {
        "available": True,
        "basis": {
            "description": "authored Mojo in the engine's product directories, and the "
            "founder's actual months from first commit to snapshot",
            "mojo_product_lines": mojo_product,
            "product_lines_all_languages": code.get("product_lines", 0),
            "authored_by_area": code.get("authored_by_area", {}),
            "product_by_language": code.get("product_by_language", {}),
            "founder_months": founder_months,
            "measured_rate_mojo_lines_per_founder_month": round(rate_lpm),
        },
        "assumptions": {
            "loaded_cost_per_person_month_usd": std,
            "loaded_cost_note": v.get("loaded_cost_note"),
            "scarce_skill_loaded_cost_per_person_month_usd": scarce,
            "scarce_skill_note": v.get("scarce_skill_note"),
            "replacement_relative_productivity": rel,
            "replacement_team_size": team,
            "hiring_lead_months": lead,
            "verification_allowance": verify,
            "developer_profit": profit,
            "notes": v.get("cost_notes", []),
        },
        "readings": readings,
        "loaded_readings": loaded,
        "floor_range_usd": [floor_low, floor_high],
        "market_comparables": v.get("market_comparables", []),
        "caveats": [
            "Cost is a floor and a sanity check, not the valuation: it prices what the code cost "
            "or would cost to rebuild, not what it earns, what it displaces, or what buyers pay.",
            "No KLOC or COCOMO figure is used: those models are calibrated on pre-AI, "
            "human-written projects and produce effort numbers with no relation to how this "
            "codebase was built.",
            "Obsolescence is not deducted (the code is months old); a valuation analyst would "
            "check functional and technological obsolescence.",
            "Talent scarcity cuts both ways: it raises a buyer's replacement cost (the "
            "scarce-skill column and the hiring lead time) and it is a key-person and hiring "
            "risk for the company (risk factor C.4).",
            "The offering's valuation should rest on the market approach (comparables below) and "
            "an independent valuation report; none of these figures belongs in the Form C.",
        ],
    }


def headline(snapshot: dict[str, Any]) -> dict[str, Any]:
    engine = next(
        (r for r in snapshot["repos"] if r["key"] == "algenta" and r.get("measured")), None
    )
    langs: dict[str, int] = {}
    for r in measured(snapshot):
        for lang, v in r["code"]["authored"].items():
            langs[lang] = langs.get(lang, 0) + v["lines"]
    out: dict[str, Any] = {
        "repos_measured": len(measured(snapshot)),
        "repos_core": len(core(snapshot)),
        "authored_lines_all_measured": sum(r["code"]["authored_lines"] for r in measured(snapshot)),
        "authored_lines_by_language": dict(sorted(langs.items(), key=lambda kv: -kv[1])),
        "packages": len(snapshot.get("packages", [])),
        "domains": len(snapshot.get("domains", [])),
        "marks_core": sum(1 for m in snapshot["marks"] if m.get("scope") == "core"),
        "human_contributors": sorted(
            {h["name"] for r in measured(snapshot) for h in r["contributors"]["humans"]}
        ),
        "unmapped_contributors": [
            (r["org_repo"], u) for r in measured(snapshot) for u in r["contributors"]["unmapped"]
        ],
    }
    if engine:
        gpu = (engine.get("contract") or {}).get("gpu_kernels") or {}
        out["engine"] = {
            "sha": engine["sha_short"],
            "sha_date": engine["sha_date"],
            "ref": engine["ref"],
            "mojo_tracked_lines": engine["code"].get("mojo_tracked", {}).get("lines"),
            "mojo_tracked_files": engine["code"].get("mojo_tracked", {}).get("files"),
            "mojo_authored_lines": engine["code"]["authored"].get("Mojo", {}).get("lines"),
            "function_count": (engine.get("contract") or {}).get("function_count"),
            "module_count": (engine.get("contract") or {}).get("module_count"),
            "gpu_kernel_count": gpu.get("kernel_count"),
            "gpu_backend_counts": gpu.get("backend_counts"),
            "gpu_kernel_modules": gpu.get("module_count"),
        }
    return out


# --------------------------------------------------------------------------------------
# Tables (shared by xlsx and markdown)
# --------------------------------------------------------------------------------------


def tables(
    snapshot: dict[str, Any], derived: dict[str, Any]
) -> list[tuple[str, list[str], list[Row], str]]:
    """Return ``(title, headers, rows, note)`` per tab, in filing order."""
    owner = snapshot["issuer"]["owner"]
    issuer = snapshot["issuer"]
    h = derived["headline"]
    eng = h.get("engine") or {}
    t: list[tuple[str, list[str], list[Row], str]] = []

    # 0 Summary
    rows0: list[Row] = [
        [
            "Issuer and owner",
            f"{issuer['legal_name']} d/b/a {issuer['dba']} ({issuer['jurisdiction']})",
        ],
        ["Address", issuer["address"]],
        ["Snapshot date", snapshot["generated_on"]],
        [
            "Engine commit",
            f"{eng.get('ref', '')} @ {eng.get('sha', '')} ({eng.get('sha_date', '')})",
        ],
        ["Repositories measured", h["repos_measured"]],
        ["Authored lines, all measured repositories", h["authored_lines_all_measured"]],
        [
            "Engine: tracked Mojo lines / files",
            f"{fmt(eng.get('mojo_tracked_lines'))} / {fmt(eng.get('mojo_tracked_files'))}",
        ],
        ["Engine: authored Mojo lines (generated excluded)", eng.get("mojo_authored_lines")],
        [
            "Engine: runtime functions / modules (packaged contract)",
            f"{fmt(eng.get('function_count'))} / {fmt(eng.get('module_count'))}",
        ],
        [
            "Engine: GPU kernels (packaged contract)",
            f"{fmt(eng.get('gpu_kernel_count'))} ("
            + ", ".join(
                f"{k.upper()} {v}" for k, v in (eng.get("gpu_backend_counts") or {}).items()
            )
            + f") in {fmt(eng.get('gpu_kernel_modules'))} kernel modules",
        ],
        ["Published packages", h["packages"]],
        ["Domains", h["domains"]],
        ["Unregistered marks (core)", h["marks_core"]],
        ["Registered patents / trademarks / copyrights", "none / none / none"],
        [
            "Human contributors across all measured repositories",
            "; ".join(h["human_contributors"]) or "none",
        ],
        ["Method", snapshot["method"]["counting"]],
    ]
    for title, *_rest in TAB_TITLES:
        rows0.append([f"Tab {title.split(' ', 1)[0]}", title])
    t.append(
        (
            "0 Summary",
            ["Item", "Value"],
            rows0,
            "One dated, reproducible snapshot; every figure traces to a commit, registry "
            "response, or WHOIS record.",
        )
    )

    # 1 Registered IP
    t.append(
        (
            "1 Registered IP",
            [
                "Type",
                "Title / mark",
                "Jurisdiction",
                "Application no.",
                "Registration no.",
                "Filed",
                "Registered",
                "Status",
                "Owner",
                "Notes",
            ],
            [
                [
                    "Patent",
                    "none",
                    "—",
                    "—",
                    "—",
                    "—",
                    "—",
                    "none filed",
                    owner,
                    "No patent applications have been filed.",
                ],
                [
                    "Trademark registration",
                    "none",
                    "—",
                    "—",
                    "—",
                    "—",
                    "—",
                    "none filed",
                    owner,
                    "Marks are in use unregistered; see tab 2. USPTO filings recommended before "
                    "the offering closes.",
                ],
                [
                    "Copyright registration",
                    "none",
                    "—",
                    "—",
                    "—",
                    "—",
                    "—",
                    "none filed",
                    owner,
                    "Copyright subsists automatically; registration recommended for the engine "
                    "and the three applications (Circular 61, trade-secret deposit).",
                ],
            ],
            "As of the snapshot date.",
        )
    )

    # 2 Marks
    rows2: list[Row] = []
    for m in snapshot["marks"]:
        ev = "; ".join(f"{e['kind']} {e['what']} {e['date']}" for e in m.get("evidence", [])[:4])
        rows2.append(
            [
                m["mark"],
                m["kind"],
                m["goods"],
                m.get("first_use_evidence") or "",
                ev,
                m["status"],
                owner,
                m.get("logo_assets"),
                m.get("scope"),
            ]
        )
    t.append(
        (
            "2 Unregistered marks",
            [
                "Mark",
                "Kind",
                "Goods / services",
                "Earliest use evidence",
                "Evidence (dated)",
                "Status",
                "Owner",
                "Logo assets",
                "Scope",
            ],
            rows2,
            "Common-law marks. Earliest-use evidence is the earliest dated public record "
            "found (domain registration, first package release, first commit, repository "
            "creation).",
        )
    )

    # 3 Domains
    rows3: list[Row] = []
    for d in snapshot["domains"]:
        rows3.append(
            [
                d["name"],
                d.get("product"),
                d.get("registrar", ""),
                d.get("created", ""),
                d.get("expires", ""),
                d.get("registrant", "privacy-proxied"),
                ", ".join(d.get("status", []))
                if isinstance(d.get("status"), list)
                else d.get("status", ""),
                d.get("use"),
                owner,
                d.get("note", "") + (f" (error: {d['error']})" if d.get("error") else ""),
                d.get("scope"),
            ]
        )
    t.append(
        (
            "3 Domains",
            [
                "Domain",
                "Product",
                "Registrar",
                "Created",
                "Expires",
                "Registrant (WHOIS)",
                "Status",
                "Use",
                "Owner",
                "Notes",
                "Scope",
            ],
            rows3,
            "WHOIS as of the snapshot date. Registrant shows the registrar's privacy proxy; "
            "the registrar account is held by the company.",
        )
    )

    # 4 Software assets
    rows4: list[Row] = []
    for r in snapshot["repos"]:
        gh = r.get("github") or {}
        vis = "private" if gh.get("private") else ("public" if gh.get("private") is False else "")
        if r.get("measured"):
            code = r["code"]
            langs = "; ".join(
                f"{k} {fmt(v['lines'])} ({fmt(v['files'])} files)"
                for k, v in code["authored"].items()
            )
            contribs = "; ".join(
                f"{x['name']} ({fmt(x['commits'])})" for x in r["contributors"]["humans"]
            ) + (
                " + bots: " + ", ".join(b["name"] for b in r["contributors"]["bots"])
                if r["contributors"]["bots"]
                else ""
            )
            if r["contributors"]["unmapped"]:
                contribs += " + UNMAPPED: " + "; ".join(
                    u["name"] for u in r["contributors"]["unmapped"]
                )
            tp = "; ".join(r.get("third_party") or []) or "none"
            rows4.append(
                [
                    r["asset"],
                    r["product"],
                    r["org_repo"],
                    vis,
                    r["copyright_owner"],
                    r["license"],
                    langs,
                    code["authored_lines"],
                    code["authored_files"],
                    r.get("first_commit"),
                    r.get("last_commit"),
                    r.get("commit_count"),
                    contribs,
                    f"{r['ref']} @ {r['sha_short']} ({r['sha_date']})",
                    r["description"],
                    tp,
                    r.get("generated_note") or "",
                    r["role"],
                ]
            )
        else:
            rows4.append(
                [
                    r["asset"],
                    r["product"],
                    r["org_repo"],
                    vis,
                    r["copyright_owner"],
                    r["license"],
                    "",
                    "",
                    "",
                    gh.get("created_at", ""),
                    gh.get("pushed_at", ""),
                    "",
                    "",
                    "",
                    r["description"],
                    "; ".join(r.get("third_party") or []) or "",
                    "; ".join(r.get("notes") or []),
                    r["role"],
                ]
            )
    t.append(
        (
            "4 Software assets",
            [
                "Asset",
                "Product",
                "Repository",
                "Visibility",
                "Copyright owner",
                "Outbound license",
                "Authored lines by language",
                "Authored lines",
                "Authored files",
                "First commit",
                "Last commit",
                "Commits",
                "Contributors",
                "Snapshot",
                "Description",
                "Third-party code inside",
                "Exclusions",
                "Scope",
            ],
            rows4,
            "Authored counts exclude generated code, vendored third-party code, fixtures, and "
            "datasets (see tab 11). Mention rows carry GitHub dates in the commit columns.",
        )
    )

    # 4b Engine Mojo by directory + contract counts (own tab for the deck shape)
    rows4b: list[Row] = []
    engine = next(
        (r for r in snapshot["repos"] if r["key"] == "algenta" and r.get("measured")), None
    )
    if engine:
        for d, v in engine["code"].get("mojo_by_dir", {}).items():
            rows4b.append([d, v["files"], v["lines"]])
        mt = engine["code"].get("mojo_tracked", {})
        rows4b.append(["TOTAL tracked .mojo", mt.get("files"), mt.get("lines")])
        rows4b.append(
            [
                "Authored Mojo (generated excluded)",
                engine["code"]["authored"].get("Mojo", {}).get("files"),
                engine["code"]["authored"].get("Mojo", {}).get("lines"),
            ]
        )
        c = engine.get("contract") or {}
        rows4b.append(["Runtime functions (packaged contract)", "", c.get("function_count")])
        rows4b.append(["Runtime modules (packaged contract)", "", c.get("module_count")])
        gpu = c.get("gpu_kernels") or {}
        rows4b.append(
            ["GPU kernels (packaged contract)", gpu.get("module_count"), gpu.get("kernel_count")]
        )
        for backend, count in (gpu.get("backend_counts") or {}).items():
            rows4b.append([f"  GPU kernels — {backend.upper()}", "", count])
        rows4b.append(
            ["Snapshot", "", f"{engine['ref']} @ {engine['sha_short']} ({engine['sha_date']})"]
        )
    t.append(
        (
            "4b Engine Mojo by directory",
            ["Directory", "Files", "Lines"],
            rows4b,
            "Same definition as scripts/count_mojo_loc.sh (every tracked .mojo file). Use this "
            "table to correct the investor deck's code-size slide.",
        )
    )

    # 5 Distributions
    rows5: list[Row] = []
    for p in snapshot["packages"]:
        rows5.append(
            [
                p["name"],
                p["registry"],
                p.get("product"),
                p.get("latest", ""),
                p.get("first_published", ""),
                p.get("releases", ""),
                p.get("license", ""),
                p.get("repo"),
                p.get("url", ""),
                owner,
                p.get("error", ""),
            ]
        )
    for d in snapshot.get("distributions", []):
        rows5.append(
            [d["name"], d["kind"], d.get("product"), "", "", "", "", d.get("repo"), "", owner, ""]
        )
    t.append(
        (
            "5 Distributions",
            [
                "Name",
                "Registry / kind",
                "Product",
                "Latest",
                "First published",
                "Releases",
                "License (registry)",
                "Source repository",
                "URL",
                "Owner",
                "Notes",
            ],
            rows5,
            "Registry records as of the snapshot date.",
        )
    )

    # 6 Trade secrets
    rows6: list[Row] = [
        [ts["category"], ts["description"], ts["held_in"], owner]
        for ts in snapshot["trade_secrets"]
    ]
    rows6.append(
        ["Protection measures", " • ".join(snapshot.get("protection_measures", [])), "all", owner]
    )
    if engine:
        gpu = (engine.get("contract") or {}).get("gpu_kernels") or {}
        if gpu:
            roles = ", ".join(f"{k} {v}" for k, v in gpu.get("roles", {}).items())
            backends = ", ".join(
                f"{k.upper()} {v}" for k, v in gpu.get("backend_counts", {}).items()
            )
            rows6.append(
                [
                    "GPU kernel library",
                    f"{fmt(gpu.get('kernel_count'))} pointer-based GPU kernels ({backends}) in "
                    f"{fmt(gpu.get('module_count'))} kernel modules serving the inference path; "
                    f"roles: {roles}",
                    "thyn-ai/algenta (private); compiled into the runtime, never shipped as source",
                    owner,
                ]
            )
            for m in gpu.get("modules", []):
                rows6.append(
                    [
                        f"GPU kernel module: {m.get('name')}",
                        f"{fmt(m.get('kernel_count'))} {str(m.get('backend', '')).upper()} kernels "
                        f"under mojo/engine/{m.get('path', '')}",
                        "thyn-ai/algenta (private)",
                        owner,
                    ]
                )
        fams = engine["code"].get("engine_families", {})
        for fam, v in list(fams.items())[:60]:
            rows6.append(
                [
                    f"Mojo engine family: {fam}",
                    f"{fmt(v['files'])} files, {fmt(v['lines'])} lines under "
                    f"mojo/engine/{'' if fam.startswith('(') else fam + '/'}",
                    "thyn-ai/algenta (private)",
                    owner,
                ]
            )
    t.append(
        (
            "6 Trade secrets",
            ["Category", "Non-revealing description", "Where held", "Owner"],
            rows6,
            "Categories only. Nothing in this tab discloses the content of a trade secret.",
        )
    )

    # 7 Components
    rows7: list[Row] = []
    for r in measured(snapshot):
        deps = r.get("dependencies") or {}
        buckets = deps.get("license_buckets", {})
        flagged = "; ".join(grouped_flags(deps.get("flagged", []))) or "none"
        tpc = r["code"].get("third_party_code", {})
        tpc_txt = (
            "; ".join(
                f"{k}: {fmt(v['lines'])} lines / {fmt(v['files'])} files" for k, v in tpc.items()
            )
            or "none"
        )
        sb = r.get("sbom") or {}
        sb_copyleft = "; ".join(
            f"{k}: " + ", ".join(sorted({str(c["name"]) for c in v.get("copyleft_components", [])}))
            for k, v in sb.items()
            if v.get("copyleft_components")
        )
        sb_txt = (
            "; ".join(
                f"{k}{v.get('artifact', '')}: {v.get('components', '')} components "
                f"{v.get('license_buckets', v.get('status', ''))}"
                for k, v in sb.items()
            )
            or "no CI SBOM artifact"
        )
        rows7.append(
            [
                r["org_repo"],
                deps.get("direct_count", ""),
                len(deps.get("python_direct", [])),
                len(deps.get("javascript_direct", [])),
                buckets.get("permissive", 0),
                buckets.get("weak-copyleft", 0),
                buckets.get("strong-copyleft", 0),
                buckets.get("unknown", 0),
                flagged,
                tpc_txt,
                "; ".join(r.get("third_party") or []) or "none",
                sb_txt + (f" — copyleft in image: {sb_copyleft}" if sb_copyleft else ""),
                "; ".join(deps.get("manifests_read", [])),
            ]
        )
    t.append(
        (
            "7 Third-party components",
            [
                "Repository",
                "Direct deps",
                "Python",
                "JavaScript",
                "Permissive",
                "Weak copyleft",
                "Strong copyleft",
                "Unknown",
                "Flagged (copyleft / proprietary)",
                "Vendored third-party code (excluded from authored)",
                "Notable third-party",
                "CI SBOM",
                "Manifests read",
            ],
            rows7,
            "Direct dependencies from manifests at the snapshot commit; licenses from the "
            "registries. Copyleft or unknown entries need a human look before filing.",
        )
    )

    # 8 Inbound licenses
    rows8: list[Row] = [
        [x["licensor"], x["subject"], x["terms"], x["materiality"]]
        for x in snapshot["inbound_licenses"]
    ]
    t.append(("8 Inbound licenses", ["Licensor", "Subject", "Terms", "Materiality"], rows8, ""))

    # 9 Outbound licenses
    rows9: list[Row] = [
        [x["subject"], x["terms"], x["where"], owner] for x in snapshot["outbound_licenses"]
    ]
    t.append(("9 Outbound licenses", ["Subject", "Terms", "Where recorded", "Licensor"], rows9, ""))

    # 10 Chain of title
    rows10: list[Row] = [["Founder assignment", issuer["founder_assignment"], "", owner]]
    for r in measured(snapshot):
        humans = (
            "; ".join(
                f"{x['name']}: {fmt(x['commits'])} commits" for x in r["contributors"]["humans"]
            )
            or "none"
        )
        bots = (
            ", ".join(f"{b['name']} ({b['commits']})" for b in r["contributors"]["bots"]) or "none"
        )
        unmapped = (
            "; ".join(f"{u['name']} ({u['commits']})" for u in r["contributors"]["unmapped"])
            or "none"
        )
        rows10.append(
            [
                r["org_repo"],
                f"human: {humans}",
                f"bots: {bots}; unmapped: {unmapped}; history complete: {r['history_complete']}",
                owner,
            ]
        )
    rows10.append(
        [
            "Employees and contractors",
            "No commit in any measured repository comes from an employee or contractor "
            "identity; every human commit maps to the founder.",
            "",
            owner,
        ]
    )
    rows10.append(
        [
            "Contributor license agreement",
            "None. Public repositories accept contributions inbound = outbound under GitHub "
            "Terms of Service §D.6.",
            "",
            owner,
        ]
    )
    t.append(
        (
            "10 Chain of title",
            ["Item", "Detail", "Evidence", "Owner"],
            rows10,
            "Contributor identities are collapsed through the identity map in "
            "scripts/ip_schedule/config.toml. An 'unmapped' name means a human identity not "
            "in that map and must be resolved before filing.",
        )
    )

    # 11 Provenance
    m = snapshot["method"]
    rows11: list[Row] = [
        ["Generated at (UTC)", snapshot["generated_at"]],
        ["Mode", json.dumps(snapshot["mode"])],
        ["git", m["git"]],
        ["Counting", m["counting"]],
        ["Excluded directory names", ", ".join(m["excluded_dirs"])],
        ["Languages", ", ".join(f"{k}={v}" for k, v in m["languages"].items())],
        ["Tracked Mojo definition", m["mojo_tracked"]],
        ["Contributors", m["contributors"]],
        ["Registries", m["registries"]],
    ]
    for r in measured(snapshot):
        ex = (
            "; ".join(
                f"{k}: {fmt(v['lines'])} lines / {fmt(v['files'])} files"
                for k, v in r["code"].get("excluded", {}).items()
            )
            or "none"
        )
        rows11.append(
            [
                f"{r['org_repo']} snapshot",
                f"{r['ref']} @ {r['sha']} ({r['sha_date']}); excluded: {ex}",
            ]
        )
    t.append(
        (
            "11 Provenance",
            ["Item", "Value"],
            rows11,
            "Regenerated from the repositories and registries on demand; identical inputs give "
            "identical numbers.",
        )
    )

    # 12 Cleanup (internal)
    rows12: list[Row] = [[i + 1, item] for i, item in enumerate(snapshot.get("cleanup_items", []))]
    for r in measured(snapshot):
        for u in r["contributors"]["unmapped"]:
            rows12.append(
                [
                    "!",
                    f"Unmapped contributor identity in {r['org_repo']}: {u['name']} "
                    f"({u['commits']} commits) — add to the identity map or document the "
                    "assignment.",
                ]
            )
        for item in grouped_flags((r.get("dependencies") or {}).get("flagged", [])):
            rows12.append(
                [
                    "!",
                    f"Copyleft/proprietary direct dependency in {r['org_repo']}: {item} — "
                    "confirm compliance.",
                ]
            )
    t.append(
        (
            "12 Cleanup list (internal)",
            ["#", "Item"],
            rows12,
            "INTERNAL. Not part of the upload.",
        )
    )
    return t


TAB_TITLES = [
    ("0 Summary",),
    ("1 Registered IP",),
    ("2 Unregistered marks",),
    ("3 Domains",),
    ("4 Software assets",),
    ("4b Engine Mojo by directory",),
    ("5 Distributions",),
    ("6 Trade secrets",),
    ("7 Third-party components",),
    ("8 Inbound licenses",),
    ("9 Outbound licenses",),
    ("10 Chain of title",),
    ("11 Provenance",),
    ("12 Cleanup list (internal)",),
]


# --------------------------------------------------------------------------------------
# Writers
# --------------------------------------------------------------------------------------


INTERNAL_MARK = "(internal"


def external_tabs(
    tabs: list[tuple[str, list[str], list[Row], str]],
) -> list[tuple[str, list[str], list[Row], str]]:
    """Drop internal tabs and the summary index rows that point at them."""
    internal = {t for t, *_ in tabs if INTERNAL_MARK in t.lower()}
    out = []
    for title, headers, rows, note in tabs:
        if title in internal:
            continue
        if title.startswith("0 "):
            rows = [r for r in rows if not (len(r) > 1 and r[1] in internal)]
        out.append((title, headers, rows, note))
    return out


def write_xlsx(path: Path, tabs: list[tuple[str, list[str], list[Row], str]]) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    for title, headers, rows, note in tabs:
        ws = wb.create_sheet(title[:31])
        ws.append(headers)
        for cell in ws[1]:
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = WRAP
        for row in rows:
            ws.append([("" if v is None else v) for v in row])
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = WRAP
        for idx, header in enumerate(headers, start=1):
            longest = max(
                [len(str(header))]
                + [
                    len(str(r[idx - 1]))
                    for r in rows
                    if idx - 1 < len(r) and r[idx - 1] is not None
                ]
            )
            ws.column_dimensions[get_column_letter(idx)].width = max(12, min(70, longest + 2))
        ws.freeze_panes = "A2"
        if note:
            ws.append([])
            ws.append([note])
            ws.cell(row=ws.max_row, column=1).font = Font(italic=True)
    wb.save(path)


def md_cell(v: Any) -> str:
    return fmt(v).replace("|", "\\|").replace("\n", " ")


def write_markdown(
    path: Path,
    snapshot: dict[str, Any],
    derived: dict[str, Any],
    tabs: list[tuple[str, list[str], list[Row], str]],
) -> None:
    lines: list[str] = [
        f"# Schedule of Intellectual Property — {snapshot['issuer']['owner']}",
        "",
        f"Snapshot {snapshot['generated_on']} · generated {snapshot['generated_at']}",
        "",
    ]
    for title, headers, rows, note in tabs:
        lines += [f"## {title}", ""]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "---|" * len(headers))
        for r in rows:
            lines.append("| " + " | ".join(md_cell(v) for v in r) + " |")
        if note:
            lines += ["", f"_{note}_"]
        lines.append("")
    lines += [
        "## Valuation support",
        "",
        "_Kept out of this schedule; held in a separate internal note._",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_valuation_note(path: Path, snapshot: dict[str, Any], derived: dict[str, Any]) -> None:
    c = derived["cost_approach"]
    date = snapshot["generated_on"]
    out: list[str] = [
        f"# Valuation support (internal) — {snapshot['issuer']['owner']}",
        "",
        f"Snapshot {date}. Not for upload. Numbers from snapshot.json / derived.json.",
        "",
    ]
    if not c.get("available"):
        out += [f"Cost approach unavailable: {c.get('reason')}", ""]
        path.write_text("\n".join(out), encoding="utf-8")
        return
    b, asm = c["basis"], c["assumptions"]
    lo, hi = c["floor_range_usd"]
    out += [
        "## 1. Cost approach — replacement-cost floor for the proprietary engine",
        "",
        f"Basis: {b['description']}. Product Mojo: **{b['mojo_product_lines']:,} lines** "
        f"(product code in all languages {b['product_lines_all_languages']:,}; authored lines by "
        "area: "
        + ", ".join(f"{k} {v['lines']:,}" for k, v in b["authored_by_area"].items())
        + f"). Founder time: **{b['founder_months']} months**, a measured rate of about "
        f"{b['measured_rate_mojo_lines_per_founder_month']:,} product Mojo lines per "
        "founder-month.",
        "",
        "| Reading | Effort (person-months) | Schedule (months) | Cost, standard rate (USD) | "
        "Cost, Mojo/GPU-kernel rate (USD) | Note |",
        "|---|---|---|---|---|---|",
    ]
    for r in c["readings"]:
        out.append(
            f"| {r['label']} | {r['effort_person_months']:,} | "
            f"{'' if r['schedule_months'] is None else r['schedule_months']} | "
            f"{r['cost_standard_usd']:,.0f} | {r['cost_scarce_skill_usd']:,.0f} | {r['note']} |"
        )
    for r in c["loaded_readings"]:
        out.append(
            f"| {r['label']} | | | {r['cost_standard_usd']:,.0f} | "
            f"{r['cost_scarce_skill_usd']:,.0f} | verification "
            f"{asm['verification_allowance']:.0%}, developer's profit "
            f"{asm['developer_profit']:.0%} |"
        )
    out += [
        "",
        f"**Cost-approach floor: about USD {lo / 1e6:,.1f}M to USD {hi / 1e6:,.1f}M.** It cannot "
        "carry a USD 50M valuation and should not be asked to; it establishes that the asset is "
        "real, recent, and cheap to have built relative to what it does.",
        "",
        f"Rates: {asm['loaded_cost_note']} {asm['scarce_skill_note']}",
        "",
    ]
    out += [f"- {n}" for n in asm["notes"]]
    out += ["", "## 2. Market approach (what carries the valuation)", ""]
    out += [f"- {m}" for m in c["market_comparables"]]
    out += [
        "",
        "The valuation paragraph of the Form C should cite the board's method and these "
        "comparables together with the published, reproducible benchmark results against the "
        "same engines (16.9x vLLM, 19.2x SGLang, 1.54x past MAX's published cell), not a cost "
        "figure.",
        "",
        "## 3. Caveats",
        "",
    ]
    out += [f"- {x}" for x in c["caveats"]] + [""]
    path.write_text("\n".join(out), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--basename", default=None, help="defaults to Thyn_IP_Schedule_<date>")
    args = ap.parse_args(argv)

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    out_dir = args.out_dir or args.snapshot.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    base = args.basename or f"Thyn_IP_Schedule_{snapshot['generated_on']}"

    derived = {"headline": headline(snapshot), "cost_approach": cost_approach(snapshot)}
    tabs = tables(snapshot, derived)
    # The upload set never carries internal tabs; the _internal files carry everything.
    write_xlsx(out_dir / f"{base}.xlsx", external_tabs(tabs))
    write_markdown(out_dir / f"{base}.md", snapshot, derived, external_tabs(tabs))
    write_xlsx(out_dir / f"{base}_internal.xlsx", tabs)
    write_markdown(out_dir / f"{base}_internal.md", snapshot, derived, tabs)
    (out_dir / "derived.json").write_text(json.dumps(derived, indent=2) + "\n", encoding="utf-8")
    write_valuation_note(
        out_dir / f"Valuation_support_internal_{snapshot['generated_on']}.md", snapshot, derived
    )
    sys.stderr.write(f"[ip-schedule] wrote {out_dir / base}.xlsx, .md and derived.json\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
