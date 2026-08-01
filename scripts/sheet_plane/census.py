#!/usr/bin/env python3
"""Formula census over benchmark xlsx corpora.

Parses sheet XML directly (zipfile + ElementTree.iterparse) so shared-formula
storage is handled explicitly: a follower cell <f t="shared" si="N"/> carries no
formula text and inherits the master's function set (its resolved formula differs
only in relative references, so the function census is identical).
"""

import json
import multiprocessing as mp
import os
import re
import sys
import zipfile
from collections import Counter
from xml.etree import ElementTree as ET  # noqa: S405 — offline census over local benchmark corpora

# name=path pairs from argv; the shipped census_results.json was produced
# over the four benchmark corpora named in docs/mojo/sheet-plane.md
CORPORA: dict[str, str] = {}

FUNC_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_.]*)\s*\(")


def strip_quoted(s: str) -> str:
    """Remove double-quoted string literals and single-quoted sheet names."""
    out = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == '"':
            i += 1
            while i < n:
                if s[i] == '"':
                    if i + 1 < n and s[i + 1] == '"':
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
        elif c == "'":
            i += 1
            while i < n:
                if s[i] == "'":
                    if i + 1 < n and s[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def funcs_of(formula: str) -> frozenset:
    body = strip_quoted(formula)
    names = set()
    for m in FUNC_RE.finditer(body):
        name = m.group(1).upper()
        for pfx in ("_XLFN.XLWS.", "_XLFN.", "_XLWS.", "_XLPM."):
            if name.startswith(pfx):
                name = name[len(pfx) :]
        if name:
            names.add(name)
    return frozenset(names)


def localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def scan_workbook(path: str) -> dict:
    r = {
        "path": path,
        "ok": False,
        "error": None,
        "sheets": 0,
        "cells": 0,
        "formula_cells": 0,
        "formula_cells_no_cached_value": 0,
        "shared_masters": 0,
        "shared_followers": 0,
        "shared_followers_no_master": 0,
        "array_formulas": 0,
        "datatable_formulas": 0,
        "cell_t": Counter(),
        "func_cells": Counter(),  # function -> #cells using it
        "cell_funcsets": Counter(),  # frozenset(funcs) -> #cells
        "cached_error_values": Counter(),  # #N/A etc. appearing as cached <v> with t="e"
        "date1904": False,
        "defined_names": 0,
        "external_links": 0,
        "has_shared_strings": False,
        "inline_str_cells": 0,
        "macro_or_other": None,
    }
    try:
        z = zipfile.ZipFile(path)
    except Exception as e:
        r["error"] = f"zip: {e}"
        return r
    try:
        names = set(z.namelist())
        r["has_shared_strings"] = "xl/sharedStrings.xml" in names
        r["external_links"] = sum(
            1 for n in names if n.startswith("xl/externalLinks/") and n.endswith(".xml")
        )
        # workbook-level flags
        if "xl/workbook.xml" in names:
            try:
                wb = ET.fromstring(z.read("xl/workbook.xml"))  # noqa: S314 — local corpus file
                for el in wb.iter():
                    ln = localname(el.tag)
                    if ln == "workbookPr" and el.get("date1904") in ("1", "true"):
                        r["date1904"] = True
                    elif ln == "definedName":
                        r["defined_names"] += 1
            except Exception:  # noqa: S110 — a malformed workbook.xml only loses its flags
                pass
        sheet_xmls = sorted(
            n
            for n in names
            if n.startswith("xl/worksheets/") and n.endswith(".xml") and "/_rels/" not in n
        )
        r["sheets"] = len(sheet_xmls)
        for sx in sheet_xmls:
            shared_defs = {}  # si -> funcset
            with z.open(sx) as fh:
                ctx = ET.iterparse(fh, events=("end",))  # noqa: S314 — local corpus file
                for _, el in ctx:
                    if localname(el.tag) != "c":
                        continue
                    r["cells"] += 1
                    t = el.get("t") or "n"
                    r["cell_t"][t] += 1
                    if t == "inlineStr":
                        r["inline_str_cells"] += 1
                    f_el = None
                    v_el = None
                    for ch in el:
                        ln = localname(ch.tag)
                        if ln == "f":
                            f_el = ch
                        elif ln == "v":
                            v_el = ch
                    if f_el is not None:
                        r["formula_cells"] += 1
                        ftype = f_el.get("t") or "normal"
                        text = f_el.text or ""
                        if ftype == "shared":
                            si = f_el.get("si")
                            if text:
                                r["shared_masters"] += 1
                                fs = funcs_of(text)
                                shared_defs[si] = fs
                            else:
                                r["shared_followers"] += 1
                                fs = shared_defs.get(si)
                                if fs is None:
                                    r["shared_followers_no_master"] += 1
                                    fs = frozenset()
                        elif ftype == "array":
                            r["array_formulas"] += 1
                            fs = funcs_of(text)
                        elif ftype == "dataTable":
                            r["datatable_formulas"] += 1
                            fs = frozenset(["__DATATABLE__"])
                        else:
                            fs = funcs_of(text)
                        for fn in fs:
                            r["func_cells"][fn] += 1
                        r["cell_funcsets"][fs] += 1
                        if v_el is None or v_el.text is None:
                            r["formula_cells_no_cached_value"] += 1
                        elif t == "e" and v_el.text:
                            r["cached_error_values"][v_el.text] += 1
                    el.clear()
        r["ok"] = True
    except Exception as e:
        r["error"] = f"{type(e).__name__}: {e}"
    finally:
        z.close()
    return r


def merge(agg: dict, r: dict):
    agg["workbooks"] += 1
    if not r["ok"]:
        agg["failed"] += 1
        agg["failures"].append({"path": r["path"], "error": r["error"]})
        return
    for k in (
        "sheets",
        "cells",
        "formula_cells",
        "formula_cells_no_cached_value",
        "shared_masters",
        "shared_followers",
        "shared_followers_no_master",
        "array_formulas",
        "datatable_formulas",
        "inline_str_cells",
        "defined_names",
        "external_links",
    ):
        agg[k] += r[k]
    agg["date1904_workbooks"] += 1 if r["date1904"] else 0
    agg["shared_strings_workbooks"] += 1 if r["has_shared_strings"] else 0
    agg["cell_t"].update(r["cell_t"])
    agg["func_cells"].update(r["func_cells"])
    agg["cached_error_values"].update(r["cached_error_values"])
    for fs, n in r["cell_funcsets"].items():
        agg["cell_funcsets"][fs] += n


def new_agg() -> dict:
    return {
        "workbooks": 0,
        "failed": 0,
        "failures": [],
        "sheets": 0,
        "cells": 0,
        "formula_cells": 0,
        "formula_cells_no_cached_value": 0,
        "shared_masters": 0,
        "shared_followers": 0,
        "shared_followers_no_master": 0,
        "array_formulas": 0,
        "datatable_formulas": 0,
        "inline_str_cells": 0,
        "defined_names": 0,
        "external_links": 0,
        "date1904_workbooks": 0,
        "shared_strings_workbooks": 0,
        "cell_t": Counter(),
        "func_cells": Counter(),
        "cell_funcsets": Counter(),
        "cached_error_values": Counter(),
    }


def coverage_curve(cell_funcsets: Counter, func_cells: Counter):
    """Cumulative % of formula cells recalcable as functions are added in
    strict frequency order. A cell is covered when every function it uses is
    implemented; function-free cells (refs/arithmetic) are covered by core."""
    total = sum(cell_funcsets.values())
    order = [f for f, _ in func_cells.most_common()]
    implemented = set()
    curve = []
    core = cell_funcsets.get(frozenset(), 0)
    covered = core
    curve.append(("<core: refs+operators, no functions>", core, covered, covered / total * 100))
    remaining = {fs: n for fs, n in cell_funcsets.items() if fs}
    for fn in order:
        implemented.add(fn)
        newly = 0
        done = []
        for fs, n in remaining.items():
            if fs <= implemented:
                newly += n
                done.append(fs)
        for fs in done:
            del remaining[fs]
        covered += newly
        curve.append((fn, func_cells[fn], covered, covered / total * 100))
    return total, curve


def main():
    for spec in sys.argv[1:]:
        name, _, root = spec.partition("=")
        CORPORA[name] = root
    if not CORPORA:
        print("usage: census.py name=/path/to/xlsx/tree ...", file=sys.stderr)
        return
    per_corpus = {}
    overall = new_agg()
    for corpus, root in CORPORA.items():
        files = []
        for dirpath, _, fnames in os.walk(root):
            for fn in fnames:
                if fn.endswith(".xlsx") and not fn.startswith("~$"):
                    files.append(os.path.join(dirpath, fn))
        files.sort()
        agg = new_agg()
        with mp.Pool(8) as pool:
            for r in pool.imap_unordered(scan_workbook, files, chunksize=8):
                merge(agg, r)
                merge(overall, r)
        per_corpus[corpus] = agg
        print(
            f"[{corpus}] {agg['workbooks']} workbooks ({agg['failed']} failed), "
            f"{agg['cells']:,} cells, {agg['formula_cells']:,} formula cells",
            file=sys.stderr,
        )

    out = {"per_corpus": {}, "overall": {}}
    for name, agg in [*per_corpus.items(), ("OVERALL", overall)]:
        total, curve = coverage_curve(agg["cell_funcsets"], agg["func_cells"])
        d = {
            k: v
            for k, v in agg.items()
            if k not in ("cell_funcsets", "cell_t", "func_cells", "cached_error_values")
        }
        d["cell_t"] = dict(agg["cell_t"])
        d["func_cells"] = dict(agg["func_cells"].most_common())
        d["cached_error_values"] = dict(agg["cached_error_values"].most_common())
        d["coverage_curve"] = [
            {"func": f, "cells": c, "cum_covered": cc, "cum_pct": round(p, 4)}
            for f, c, cc, p in curve
        ]
        d["distinct_funcsets"] = len(agg["cell_funcsets"])
        if name == "OVERALL":
            out["overall"] = d
        else:
            out["per_corpus"][name] = d
    with open("census_results.json", "w") as fh:
        json.dump(out, fh, indent=1)
    print("wrote census_results.json", file=sys.stderr)


if __name__ == "__main__":
    main()
