#!/usr/bin/env python3
"""Extract one .xlsx into the sheet-plane text format (see sheet/grid.mojo).

This is the STAGED half of the xlsx reader: the frozen mojo/engine/compression
package has no RFC-1951 inflate, so the zip/XML container is opened here with
the Python stdlib while the recalc engine itself stays pure Mojo. Everything
this script emits is verifiable by the Mojo loader, which refuses malformed
lines rather than trusting this code.

Faithfulness notes (verified against the benchmark corpora):
  * sheet order comes from xl/workbook.xml <sheets> + the workbook rels —
    sheetN.xml file numbering does NOT match tab order;
  * shared formulas: masters keep their text + si, followers emit G lines
    with si only (the Mojo engine shifts the master tree by the cell delta);
  * rich-text shared strings concatenate their <r><t> runs;
  * cells with no r= attribute (LibreOffice) advance an implied cursor;
  * formula cells with no cached <v> emit ct=z — they cannot self-validate
    and the report counts them;
  * date1904 emits D 1 and the Mojo loader refuses (zero corpus workbooks).

Usage: extract_xlsx.py <input.xlsx> <output.swt>   (exit 1 + stderr on refusal)
"""

from __future__ import annotations

import sys
import zipfile
from xml.etree import ElementTree as ET

_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def esc(s: str) -> str:
    return s.replace("%", "%25").replace("\t", "%09").replace("\n", "%0A").replace("\r", "%0D")


def _shared_strings(z: zipfile.ZipFile, names: set[str]) -> list[str]:
    out: list[str] = []
    if "xl/sharedStrings.xml" not in names:
        return out
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))  # noqa: S314 — local corpus file
    for si in root:
        if _local(si.tag) != "si":
            continue
        parts: list[str] = []
        for el in si.iter():
            if _local(el.tag) == "t" and el.text is not None:
                parts.append(el.text)
        out.append("".join(parts))
    return out


def _rid_of(el) -> str | None:
    for k, v in el.attrib.items():
        if k == f"{_REL_NS}id" or k.endswith("}id"):
            return v
    return None


def _sheet_parts(
    z: zipfile.ZipFile,
) -> tuple[list[str], list[str | None], bool, list[tuple[int, str, str]]]:
    """(sheet names in tab order, worksheet part path per sheet or None,
    date1904, defined names as (scope, name, refers))."""
    wb = ET.fromstring(z.read("xl/workbook.xml"))  # noqa: S314 — local corpus file
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))  # noqa: S314 — local corpus file
    rid_to_target: dict[str, str] = {}
    for rel in rels:
        rid = rel.get("Id")
        target = rel.get("Target") or ""
        if target.startswith("/"):
            target = target.lstrip("/")
        elif not target.startswith("xl/"):
            target = "xl/" + target
        # normalise ../ inside xl/
        while "/../" in target:
            head, _, tail = target.partition("/../")
            head = head.rsplit("/", 1)[0] if "/" in head else ""
            target = f"{head}/{tail}" if head else tail
        rid_to_target[rid] = target
    names: list[str] = []
    parts: list[str | None] = []
    date1904 = False
    defined: list[tuple[int, str, str]] = []
    for el in wb.iter():
        ln = _local(el.tag)
        if ln == "workbookPr" and el.get("date1904") in ("1", "true"):
            date1904 = True
        elif ln == "sheet":
            names.append(el.get("name") or f"Sheet{len(names) + 1}")
            rid = _rid_of(el)
            parts.append(rid_to_target.get(rid) if rid else None)
        elif ln == "definedName":
            nm = el.get("name") or ""
            scope = el.get("localSheetId")
            refers = el.text or ""
            if nm and refers:
                defined.append((int(scope) if scope is not None else -1, nm, refers))
    return names, parts, date1904, defined


def extract(xlsx_path: str, out_path: str) -> None:
    z = zipfile.ZipFile(xlsx_path)
    znames = set(z.namelist())
    sheet_names, sheet_parts, date1904, defined = _sheet_parts(z)
    sst = _shared_strings(z, znames)
    with open(out_path, "w", encoding="utf-8", newline="\n") as out:
        out.write("SHEETWB\t1\n")
        out.write(f"D\t{1 if date1904 else 0}\n")
        for nm in sheet_names:
            out.write(f"S\t{esc(nm)}\n")
        for scope, nm, refers in defined:
            out.write(f"N\t{scope}\t{esc(nm)}\t{esc(refers)}\n")
        for sheet_idx, part in enumerate(sheet_parts):
            if part is None or part not in znames or "chartsheet" in part:
                continue
            _emit_sheet(z, part, sheet_idx, sst, out)
    z.close()


def _emit_sheet(z, part: str, sheet_idx: int, sst: list[str], out) -> None:
    implied_row = 0  # 1-based when set by <row r=...>
    implied_col = 0  # 0-based next-column cursor
    with z.open(part) as fh:
        for _, el in ET.iterparse(fh, events=("end",)):  # noqa: S314 — local corpus file
            ln = _local(el.tag)
            if ln == "row":
                r = el.get("r")
                if r is not None and r.isdigit():
                    implied_row = int(r)
                else:
                    implied_row += 1
                implied_col = 0
                el.clear()
                continue
            if ln != "c":
                continue
            ref = el.get("r")
            if ref is None:
                ref = f"{_col_name(implied_col)}{implied_row}"
            implied_col = _col_of(ref) + 1
            t = el.get("t") or "n"
            f_el = None
            v_el = None
            is_el = None
            for ch in el:
                cln = _local(ch.tag)
                if cln == "f":
                    f_el = ch
                elif cln == "v":
                    v_el = ch
                elif cln == "is":
                    is_el = ch
            v_text = v_el.text if (v_el is not None and v_el.text is not None) else None
            if f_el is not None:
                ftype = f_el.get("t") or "normal"
                ftext = f_el.text or ""
                si = f_el.get("si")
                ct, cv = _cached_of(t, v_text, sst, is_el)
                if ftype == "shared" and not ftext:
                    if si is None:
                        raise ValueError(f"{part}:{ref}: shared follower without si")
                    out.write(f"G\t{sheet_idx}\t{ref}\t{si}\t{ct}\t{cv}\n")
                else:
                    if ftype == "shared":
                        fkind = f"m:{si}" if si is not None else "n"
                    elif ftype == "array":
                        fkind = "a"
                    elif ftype == "dataTable":
                        fkind = "d"
                    else:
                        fkind = "n"
                    out.write(f"F\t{sheet_idx}\t{ref}\t{fkind}\t{esc(ftext)}\t{ct}\t{cv}\n")
                el.clear()
                continue
            # constant cell
            if t == "s":
                if v_text is None:
                    el.clear()
                    continue
                idx = int(v_text)
                if idx < 0 or idx >= len(sst):
                    raise ValueError(f"{part}:{ref}: shared string index {idx}")
                out.write(f"C\t{sheet_idx}\t{ref}\ts\t{esc(sst[idx])}\n")
            elif t == "inlineStr":
                text = ""
                if is_el is not None:
                    text = "".join(e.text for e in is_el.iter() if _local(e.tag) == "t" and e.text)
                out.write(f"C\t{sheet_idx}\t{ref}\ts\t{esc(text)}\n")
            elif t == "str":
                if v_text is not None:
                    out.write(f"C\t{sheet_idx}\t{ref}\ts\t{esc(v_text)}\n")
            elif t == "b":
                if v_text is not None:
                    b = "1" if v_text.strip() in ("1", "true", "TRUE") else "0"
                    out.write(f"C\t{sheet_idx}\t{ref}\tb\t{b}\n")
            elif t == "e":
                if v_text is not None:
                    out.write(f"C\t{sheet_idx}\t{ref}\te\t{esc(v_text)}\n")
            elif t == "n":
                if v_text is not None and v_text.strip():
                    out.write(f"C\t{sheet_idx}\t{ref}\tn\t{v_text.strip()}\n")
            else:
                raise ValueError(f"{part}:{ref}: unsupported cell type t={t!r}")
            el.clear()


def _cached_of(t: str, v_text: str | None, sst: list[str], is_el) -> tuple[str, str]:
    """Cached-value (ct, cv) fields for a formula cell."""
    if v_text is None:
        return "z", ""
    if t == "s":  # cached shared string (rare but legal)
        idx = int(v_text)
        if 0 <= idx < len(sst):
            return "s", esc(sst[idx])
        return "z", ""
    if t == "str":
        return "s", esc(v_text)
    if t == "inlineStr":
        text = ""
        if is_el is not None:
            text = "".join(e.text for e in is_el.iter() if _local(e.tag) == "t" and e.text)
        return "s", esc(text)
    if t == "b":
        return "b", "1" if v_text.strip() in ("1", "true", "TRUE") else "0"
    if t == "e":
        return "e", esc(v_text)
    # t == "n" or absent
    body = v_text.strip()
    if not body:
        return "z", ""
    return "n", body


def _col_of(ref: str) -> int:
    acc = 0
    for ch in ref:
        if ch.isalpha():
            acc = acc * 26 + (ord(ch.upper()) - 64)
        else:
            break
    return acc - 1


def _col_name(col: int) -> str:
    out = ""
    c = col
    while True:
        out = chr(65 + c % 26) + out
        c = c // 26 - 1
        if c < 0:
            return out


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: extract_xlsx.py <input.xlsx> <output.swt>", file=sys.stderr)
        return 2
    try:
        extract(sys.argv[1], sys.argv[2])
    except Exception as exc:  # refusal, named
        print(f"extract-refused: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
