"""measure_progexec_finqa.mojo — run `progexec.exec` over every scored real FinQA gold
program and print each program's result. Scoring against `exe_ans` and against the naive
baselines happens in `benchmarks/external_baselines/finqa_exec/score.py`, in the SAME
process that reads the dataset's own gold answers — never here, for the identical reason
`measure_exactnum_strd.mojo` keeps scoring out of the Mojo side: two implementations of a
comparison is no way to know which one flattered which side.

Input is `finqa_progexec.spec` (produced by `emit_specs.py`), every float a 16-hex-digit
IEEE-754 bit pattern — no ASCII decimal round trip, so the arithmetic this file measures
is provably fed the same bits `score.py`'s naive baselines were built from.

Reproduce:

    cd mojo_env
    pixi run mojo run -I ../mojo/engine \\
        ../benchmarks/mojo_benchmarks/measure_progexec_finqa.mojo <spec_file>
"""
from sys import argv

from memory import bitcast

from progexec.exec import progexec_run_flat


fn hex_to_f64(s: StringSlice) raises -> Float64:
    var acc: UInt64 = 0
    var raw = s.as_bytes()
    if len(raw) != 16:
        raise Error("hex token must be 16 digits")
    for i in range(16):
        var c = Int(raw[i])
        var d: Int
        if c >= 48 and c <= 57:
            d = c - 48
        elif c >= 97 and c <= 102:
            d = c - 87
        elif c >= 65 and c <= 70:
            d = c - 55
        else:
            raise Error("bad hex digit")
        acc = (acc << 4) | UInt64(d)
    return bitcast[DType.float64, 1](acc)


fn f64_to_hex(v: Float64) -> String:
    var u = v.to_bits()
    var out = String("")
    for i in range(16):
        var shift = (15 - i) * 4
        var nib = Int((u >> shift) & 0xF)
        out += chr(nib + 48) if nib < 10 else chr(nib + 87)
    return out


fn read_all(path: String) raises -> String:
    var f = open(path, "r")
    var s = f.read()
    f.close()
    return s^


fn main() raises:
    var args = argv()
    if len(args) < 2:
        print("usage: measure_progexec_finqa <spec_file>")
        return
    var text = read_all(String(args[1]))
    var lines = text.split("\n")
    var total = Int(lines[0])

    var line_idx = 1
    var n_ok = 0
    var n_absent = 0
    for _ in range(total):
        var header = lines[line_idx].split(" ")
        line_idx += 1
        var prog_id = header[0]
        var n_steps = Int(header[1])
        var n_table_values = Int(header[2])

        var table_values = List[Float64]()
        var table_line = lines[line_idx]
        line_idx += 1
        if n_table_values > 0:
            var toks = table_line.split(" ")
            for i in range(n_table_values):
                table_values.append(hex_to_f64(toks[i]))

        var ops = List[Int]()
        var a1k = List[Int]()
        var a1n = List[Float64]()
        var a2k = List[Int]()
        var a2n = List[Float64]()
        var toff = List[Int]()
        var tlen = List[Int]()
        for _ in range(n_steps):
            var toks = lines[line_idx].split(" ")
            line_idx += 1
            ops.append(Int(toks[0]))
            a1k.append(Int(toks[1]))
            a1n.append(hex_to_f64(toks[2]))
            a2k.append(Int(toks[3]))
            a2n.append(hex_to_f64(toks[4]))
            toff.append(Int(toks[5]))
            tlen.append(Int(toks[6]))

        var res = progexec_run_flat(ops, a1k, a1n, a2k, a2n, table_values, toff, tlen, n_steps)
        if res.present:
            n_ok += 1
        else:
            n_absent += 1

        if res.is_bool:
            print("RESULT", prog_id, res.status, "1" if res.present else "0", "bool", "yes" if res.bool_value else "no")
        else:
            print("RESULT", prog_id, res.status, "1" if res.present else "0", "num", f64_to_hex(res.value))

    print("TOTAL", total, "PRESENT", n_ok, "ABSENT", n_absent)
