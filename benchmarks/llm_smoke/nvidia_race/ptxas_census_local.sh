#!/usr/bin/env bash
# ptxas_census_local.sh — produce the per-kernel register / spill census for a CUDA source file
# with NO GPU and NO VM, at zero cloud cost.
#
# WHY. The register census is the cheapest refutation gate this campaign owns: it killed round 7's
# primary lever (v3 RT=2 row-tiles sharing one B-fragment stream) in ~30 s of build time, before an
# hour of gated cells, because RT=2 needs 255/255 registers and spills where the shipped v2 does
# not. But `ptxas` ships with the CUDA toolkit and the H200 race box is spot capacity that has
# repeatedly gone to STOCKOUT — so gating authoring on having the GPU back inverts the point.
# It does not have to: **ptxas is a HOST cross-compiler.** `-arch=sm_90a` needs a CUDA 12.x
# toolkit, not an sm_90 device, so an arm64 Linux container produces the same census the box would.
#
# VERSION MUST MATCH THE RACE BOX. Register allocation is a ptxas property and it moves between
# toolkit releases, so IMAGE pins CUDA 12.6 — the box runs V12.6.85 (Built
# Wed_Oct_30_00:04:50_PDT_2024) and `nvidia/cuda:12.6.0-devel-ubuntu22.04` reports the same. If the
# box's toolkit changes, change IMAGE and RE-CALIBRATE before trusting any new number.
#
# CALIBRATION IS MANDATORY, NOT OPTIONAL, AND IT PASSED. A local census is only evidence if it
# reproduces numbers the box already produced. Run `--calibrate` : it compiles tc_shim.cu and
# compares the six `_fa_g3_window2_kernel` BN=64 instantiations the VM's round-7 log printed
# against this toolchain's output. On 2026-09-17 that comparison was **6/6 EXACT** (165, 172, 165,
# 172, 166, 166 registers, zero spill in both), and v3's 36 instantiations reproduced too (peak
# 255, 24 spilling). Until a calibration like that passes, quote no local census as evidence.
#
# GOTCHAS FOUND THE HARD WAY, so they are encoded here rather than rediscovered:
#   * The pip `nvidia-cuda-nvcc-cu12` arm64 wheel ships ONLY ptxas — no nvcc/cicc — so it cannot
#     take a .cu to PTX. Use the full devel image.
#   * That devel image has NO python3, so the embedded-PTX header is generated with coreutils
#     (od/tr/paste), not python. tc_shim.cu #includes "tc_rt_ptx.h" and dies without it — the same
#     fresh-box trap that killed chain5c, chain5d and round 6's re-stage.
#
# Usage:
#   bash ptxas_census_local.sh --calibrate                # MUST pass before quoting anything
#   bash ptxas_census_local.sh FILE.cu --arch sm_90a --kernel SUBSTR [--gen-ptx-header]
set -uo pipefail

IMAGE=${IMAGE:-nvidia/cuda:12.6.0-devel-ubuntu22.04}
WORK=${WORK:-/tmp/ptxas_census}
ARCH=sm_90a
KERNEL_FILTER=""
CALIBRATE=0
GEN_HDR=0
SRC=""
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

while (( $# > 0 )); do
  case "$1" in
    --arch) ARCH="$2"; shift 2 ;;
    --kernel) KERNEL_FILTER="$2"; shift 2 ;;
    --calibrate) CALIBRATE=1; shift ;;
    --gen-ptx-header) GEN_HDR=1; shift ;;
    -*) echo "unknown flag $1" >&2; exit 2 ;;
    *) SRC="$1"; shift ;;
  esac
done
command -v docker >/dev/null || { echo "docker is required (colima is fine)" >&2; exit 2; }

if (( CALIBRATE == 1 )); then
  SRC="$HERE/tc_shim.cu"; ARCH=sm_90; GEN_HDR=1; KERNEL_FILTER="_fa_g3_window"
fi
[[ -n "$SRC" && -f "$SRC" ]] || { echo "no source file (pass one, or --calibrate)" >&2; exit 2; }

mkdir -p "$WORK"
rm -f "$WORK"/cal.log "$WORK"/*.o
cp "$SRC" "$WORK/probe.cu"
if (( GEN_HDR == 1 )); then
  cp "$HERE/tc_rt_kernels.cu" "$WORK/" 2>/dev/null || true
fi

echo "=== nvcc -arch=$ARCH -Xptxas -v (container $IMAGE, no GPU) ==="
docker run --rm --platform linux/arm64 -v "$WORK:/w" "$IMAGE" bash -c '
  cd /w
  if [[ -f tc_rt_kernels.cu && ! -f tc_rt_ptx.h ]]; then
    nvcc -ptx -arch=compute_90 tc_rt_kernels.cu -o tc_rt_kernels.ptx 2>/dev/null || true
    if [[ -f tc_rt_kernels.ptx ]]; then
      # no python3 in this image -> coreutils byte array
      od -An -tu1 -v tc_rt_kernels.ptx | tr -s " " "\n" | sed "/^$/d" | paste -sd, - > b.txt
      { printf "/* generated locally for the ptxas census */\nstatic const unsigned char g_tc_rt_ptx[] = {\n"
        cat b.txt; printf ",0};\n"; } > tc_rt_ptx.h
      echo "tc_rt_ptx.h generated: $(stat -c %s tc_rt_ptx.h) bytes from $(stat -c %s tc_rt_kernels.ptx) PTX bytes"
    fi
  fi
  nvcc -O3 -arch='"$ARCH"' -Xcompiler -fPIC -I/w -Xptxas -v -c probe.cu -o probe.o 2>/w/cal.log
  echo "NVCC_RC=$?"
  grep -cE "error" /w/cal.log | sed "s/^/error_lines=/"
' 2>&1 | grep -E "NVCC_RC|error_lines|tc_rt_ptx.h generated"

if grep -qE "error:" "$WORK/cal.log" 2>/dev/null; then
  echo "=== COMPILE FAILED — no census can be quoted for this source ===" >&2
  grep -E "error:" "$WORK/cal.log" | head -15 >&2
  exit 1
fi

# The devel image has no python3, so the log is parsed on the HOST. That is deliberate: the
# container's only job is to be a faithful ptxas, and keeping the parser here means the calibration
# expectations live next to the script that asserts them.
python3 - "$WORK/cal.log" "$KERNEL_FILTER" "$CALIBRATE" <<'PY'
import re, sys
log, filt, calib = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
txt = open(log, errors="replace").read()
ents = re.split(r"Compiling entry function ", txt)
rows = []
for e in ents[1:]:
    name = e.split("'")[1] if "'" in e else "?"
    if filt and filt not in name:
        continue
    r = re.search(r"Used (\d+) registers", e)
    s = re.search(r"(\d+) bytes spill stores", e)
    l = re.search(r"(\d+) bytes spill loads", e)
    t = re.search(r"ILi(\d+)ELb(\d)ELb(\d)ELi(\d)E", name)
    rows.append((name, int(r.group(1)) if r else -1, int(s.group(1)) if s else 0,
                 int(l.group(1)) if l else 0, t.groups() if t else None))
if not rows:
    print(f"NO ENTRY FUNCTIONS matched {filt!r} — INCONCLUSIVE, not a pass")
    sys.exit(2)
sp = [r for r in rows if r[2] > 0 or r[3] > 0]
print(f"{len(rows)} instantiation(s); peak {max(r[1] for r in rows)}/255 registers; "
      f"{len(sp)} spilling")
bybn = {}
for n, regs, ss, sl, t in rows:
    bybn.setdefault(t[0] if t else "?", []).append((regs, ss))
for bn in sorted(bybn, key=lambda x: (x == "?", x)):
    v = bybn[bn]
    print(f"  BN={bn:>4}  n={len(v):>3}  regs {min(x[0] for x in v)}-{max(x[0] for x in v)}"
          f"  spilling {sum(1 for x in v if x[1] > 0)}/{len(v)}")
if calib:
    # The six v2 BN=64 instantiations the VM's round-7 log actually printed.
    vm = {"ILi64ELb0ELb0ELi0E": 165, "ILi64ELb0ELb0ELi1E": 172, "ILi64ELb0ELb1ELi0E": 165,
          "ILi64ELb0ELb1ELi1E": 172, "ILi64ELb1ELb0ELi0E": 166, "ILi64ELb1ELb1ELi0E": 166}
    got, ok = {}, True
    for n, regs, ss, sl, t in rows:
        if "_fa_g3_window2_kernel" not in n:
            continue
        m = re.search(r"(ILi64ELb\dELb\dELi\dE)", n)
        if m and m.group(1) in vm:
            got[m.group(1)] = regs
    print("CALIBRATION vs the VM's round-7 log (v2, BN=64):")
    for k, want in vm.items():
        have = got.get(k)
        good = have == want
        ok &= good
        print(f"  {k}  VM={want}  LOCAL={have}  {'MATCH' if good else 'MISMATCH'}")
    print("CALIBRATION VERDICT: " + ("LOCAL TOOLCHAIN REPRODUCES THE VM — census is EVIDENCE"
                                     if ok and len(got) == len(vm) else
                                     "FAILED — quote NO local census as evidence"))
    sys.exit(0 if ok else 4)
sys.exit(3 if sp else 0)
PY
rc=$?
echo "CENSUS_RC=$rc  (0 = no spills; 3 = something spills; 4 = calibration failed)"
exit 0
