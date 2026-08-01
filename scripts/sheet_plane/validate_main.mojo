"""Corpus-validation binary: one extracted workbook in, one report out.

Compiled (never JIT — rule 1b) via:
    cd mojo_env && pixi run mojo build -I../mojo/engine \
        ../scripts/sheet_plane/validate_main.mojo -o ../build/sheet_validate

Usage: sheet_validate <workbook.swt> [budget_ops]

Prints tab-separated key/value lines; free-text values are %-escaped by the
same convention the loader reads, so the Python harness can unescape.
"""

from sys import argv

from sheet.api import sheet_recalc_report
from sheet.numio import _bs_str


fn _esc(s: String) -> String:
    var bs = s.as_bytes()
    var buf = List[UInt8]()
    for i in range(len(bs)):
        var b = Int(bs[i])
        if b == 37 or b == 9 or b == 10 or b == 13:
            buf.append(UInt8(37))
            var hexd = String("0123456789ABCDEF").as_bytes()
            buf.append(hexd[b // 16])
            buf.append(hexd[b % 16])
        else:
            buf.append(UInt8(b))
    return _bs_str(buf)


fn main() raises:
    var args = argv()
    if len(args) < 2:
        print("usage: sheet_validate <workbook.swt> [budget_ops]")
        return
    var budget = 0
    if len(args) >= 3:
        var b = String(args[2])
        var acc = 0
        var ok = len(b) > 0
        for i in range(len(b.as_bytes())):
            var ch = Int(b.as_bytes()[i])
            if ch < 48 or ch > 57:
                ok = False
                break
            acc = acc * 10 + (ch - 48)
        if ok:
            budget = acc
    var text = String("")
    try:
        with open(String(args[1]), "r") as f:
            text = f.read()
    except:
        # a non-UTF-8 payload refuses like any other malformed workbook
        # (found by fuzzing: String construction validates UTF-8 and raises)
        print("status\t1302")
        print("load_line\t0")
        return
    var rep = sheet_recalc_report(text, budget)
    print("status\t", rep.status, sep="")
    print("load_line\t", rep.load_line, sep="")
    print("sheets\t", rep.sheets, sep="")
    print("cells\t", rep.cells, sep="")
    print("formula_cells\t", rep.formula_cells, sep="")
    print("evaluated\t", rep.evaluated, sep="")
    print("not_evaluated\t", rep.not_evaluated, sep="")
    print("no_cached\t", rep.no_cached, sep="")
    print("matched_exact\t", rep.matched_exact, sep="")
    print("matched_tol\t", rep.matched_tol, sep="")
    print("matched_snap\t", rep.matched_snap, sep="")
    print("error_matched\t", rep.error_matched, sep="")
    print("mismatched\t", rep.mismatched, sep="")
    print("error_mismatched\t", rep.error_mismatched, sep="")
    print("unsupported\t", rep.unsupported, sep="")
    print("volatile_cells\t", rep.volatile_cells, sep="")
    print("cycle_cells\t", rep.cycle_cells, sep="")
    print("cycle_count\t", rep.cycle_count, sep="")
    print("unsupported_compare\t", rep.unsupported_compare, sep="")
    print("ops\t", rep.ops, sep="")
    print("max_chain\t", rep.max_chain, sep="")
    print("cycle_names\t", _esc(rep.cycle_names), sep="")
    print("unsupported_names\t", _esc(rep.unsupported_names), sep="")
    print("mismatch_samples\t", _esc(rep.mismatch_samples), sep="")
