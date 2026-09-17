#!/usr/bin/env bash
# audit_tc_flags.sh — the FRONT-3 flag/banner audit: prove, from the SHIPPED BINARY, which
# numeric-path build flags an arm actually carries.
#
# WHY THIS EXISTS. The gemma-3-27b H200 TensorRT-LLM column was voided because the arm it was
# measured with (`~/a2a/correctness_ctx8192_tc_attn`) had been rebuilt WITHOUT
# `-D ALGENTA_G3_STREAM` — a comptime flag that changes the numeric path, not just the speed.
# That arm was wrong at oracle index 0 on 5/6 prompts, was 2-12% SLOWER on every prompt, and
# nothing in the published cells said so: the "token-identical" validation compared a key the
# driver never emits, so `[] == []` passed unconditionally. A benchmark cell is only as good as
# the proof of which binary produced it.
#
# WHAT IT DOES. The sessions print one banner line per numeric-path flag from INSIDE that
# flag's own `@parameter if` (`residentk.session_cuda_p3._tc_stage_weights` for the 7B family,
# `residentk.session_cuda_gemma3_f16._print_round5_flag_audit` for the gemma-3 family), so the
# literal only exists in a binary that has the flag. `strings` on the binary is therefore a
# positive audit, and an absent line means OFF — a build cannot print a line it does not
# contain. This script greps exactly those literals, cross-checks them against the flags the
# build was invoked with, and writes both plus the runtime flag banner (captured from a real
# session open, if a log is given) to JSON.
#
# FAMILIES. A binary's family is decided by which POSITIVE CONTROL literal it carries, not by
# its filename, so a mis-named arm cannot be audited against the wrong flag table:
#   7B        "TC: prefill f16 dual residency STAGED |"   -> ALGENTA_7B_* / ALGENTA_PF_* flags
#   gemma-3   "G3 FLAGS: TCATTN ="                        -> ALGENTA_G3_* flags
# A binary carrying NEITHER aborts the audit (exit 3) rather than reporting an empty flag set.
#
# Usage:
#   bash scripts/audit_tc_flags.sh --bin-dir ~/front3/bin --out ~/trtllm/front3/flag_audit.json
#   bash scripts/audit_tc_flags.sh --bin-dir ~/lever5 --glob 'R5_*' --logs ~/lever5/logs --out ...
set -uo pipefail

BIN_DIR="$HOME/front3/bin"
LOG_DIR=""
OUT="$HOME/trtllm/front3/flag_audit.json"
GLOBS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --bin-dir) BIN_DIR="$2"; shift 2 ;;
        --logs) LOG_DIR="$2"; shift 2 ;;
        --out) OUT="$2"; shift 2 ;;
        --glob) GLOBS+=("$2"); shift 2 ;;
        *) echo "unknown arg $1" >&2; exit 2 ;;
    esac
done
if (( ${#GLOBS[@]} == 0 )); then GLOBS=("qwen25_7b_p3_graph_cuda*"); fi

# flag literal in the binary  ->  the -D that must have produced it
FLAGS_7B=(
    "ALGENTA_PF_ONEPASS_B1=1|ALGENTA_PF_ONEPASS_B1"
    "ALGENTA_PF_ATTN_FLASH_B1=1|ALGENTA_PF_ATTN_FLASH_B1"
    "ALGENTA_PF_ATTN_FLASH2_B1=1|ALGENTA_PF_ATTN_FLASH2_B1"
    "ALGENTA_TC_NOSEAM=1|ALGENTA_TC_NOSEAM"
    "ALGENTA_7B_PF_TCATTN=1|ALGENTA_7B_PF_TCATTN"
    "ALGENTA_7B_PF_SM1P=1|ALGENTA_7B_PF_SM1P"
    "ALGENTA_7B_PF_F16NORM=1|ALGENTA_7B_PF_F16NORM"
    "ALGENTA_7B_PF_F16MLP=1|ALGENTA_7B_PF_F16MLP"
    "ALGENTA_7B_PF_FA=1|ALGENTA_7B_PF_FA"
    "ALGENTA_7B_PF_FASTEXP=1|ALGENTA_7B_PF_FASTEXP"
    "ALGENTA_7B_PF_BIASROPE=1|ALGENTA_7B_PF_BIASROPE"
    # FRONT 4 (2026-09-16, the RAG-4096 flip round). FA2 and FA2DB are separate literals with
    # their own `=1` suffixes, so the substring test above cannot confuse `ALGENTA_7B_PF_FA=1`
    # with `ALGENTA_7B_PF_FA2=1`; FA2/FA2DB both REQUIRE PF_FA, so a binary carrying either
    # necessarily also carries the FA literal.
    "ALGENTA_7B_PF_FA2=1|ALGENTA_7B_PF_FA2"
    "ALGENTA_7B_PF_FA2DB=1|ALGENTA_7B_PF_FA2DB"
    "ALGENTA_7B_PF_KVTWIN=1|ALGENTA_7B_PF_KVTWIN"
    # FRONT 5 (2026-09-16, the second RAG-4096 flip round). ROPEVEC requires BIASROPE — it
    # replaces that kernel's dispatch slot — so a binary carrying ROPEVEC necessarily also
    # carries the BIASROPE literal, and the two are distinct strings with their own `=1`
    # suffixes, so neither substring test can light up the other.
    "ALGENTA_7B_PF_ROPEVEC=1|ALGENTA_7B_PF_ROPEVEC"
    # FRONT 6 (2026-09-16, the third RAG-4096 flip round). Neither of these adds a kernel, so
    # the kernel inventory does not move and `strings` on a *kernel* name would prove nothing:
    # PASS4096 changes a comptime SHAPE (the prefill pass cap) and LTALGO changes which cuBLAS
    # algorithm a shape dispatches. Both are audited by their own banner literal AND by a
    # runtime field, because for both the literal alone can be true while the effect is absent
    # — a pass cap no prompt exceeds, or an Lt arm whose shapes all declined (-320) and ran the
    # shipped GemmEx path anyway.
    "ALGENTA_PF_PASS4096=1|ALGENTA_PF_PASS4096"
    "ALGENTA_7B_PF_LTALGO=1|ALGENTA_7B_PF_LTALGO"
    # FRONT 7 (2026-09-16, the margin-widening round). O16TWIN DOES add a kernel (a copy of FA2
    # whose epilogue writes the f16 O twin), so unlike FRONT 6's two levers a `strings` hit on
    # `_fa2_causal_o16_kernel` is real evidence — and it is still not sufficient: the twin entry
    # can DECLINE at runtime (-301/-304/-305/-306/-311), in which case the arm measures the
    # shipped convert path while carrying both the flag and the kernel name. So this lever is
    # audited three ways: the banner literal, the runtime `o16_twin = armed` field, and the
    # absence of a `f16 O twin DECLINED` line in the cell's own log.
    # O16VERIFY is the PROOF arm (writes both O pointers, compares every element as bits) and is
    # deliberately never a raced arm — the audit records which binaries carried it so a proof
    # binary cannot be mistaken for a ship one.
    "ALGENTA_7B_PF_O16TWIN=1|ALGENTA_7B_PF_O16TWIN"
    "ALGENTA_7B_PF_O16VERIFY=1|ALGENTA_7B_PF_O16VERIFY"
    "ALGENTA_7B_PF_FAREV=1|ALGENTA_7B_PF_FAREV"
    "ALGENTA_7B_PF_LTINSITU=1|ALGENTA_7B_PF_LTINSITU"
)
# The gemma-3 family (residentk.session_cuda_gemma3_f16). ALGENTA_G3_PF_FA is the round-5
# fused windowed tensor-core flash attention; FA2 is its round-6 raw-mma v2 kernel (a separate
# literal with its own `=1` suffix, so the substring test cannot confuse `ALGENTA_G3_PF_FA=1`
# with `ALGENTA_G3_PF_FA2=1`; FA2 REQUIRES FA, so a binary carrying FA2 necessarily also
# carries the FA literal). BN32/BN128 override the fused kernel's key-block width (a summation
# order, i.e. numeric-path, change). F16NORM/F16MLP/F16ATTN are the pre-staged-A companions;
# TCATTN is the five-pass chain FA replaces (kept in the table because an arm that carries BOTH
# is the fallback-correct arm and the banner says which one ran); STREAM is the legacy-stream
# seam whose silent absence voided the first H200 column.
FLAGS_G3=(
    "ALGENTA_G3_PF_FA=1|ALGENTA_G3_PF_FA"
    "ALGENTA_G3_PF_FA2=1|ALGENTA_G3_PF_FA2"
    "ALGENTA_G3_PF_KV16=1|ALGENTA_G3_PF_KV16"
    "ALGENTA_G3_PF_BN32=1|ALGENTA_G3_PF_BN32"
    "ALGENTA_G3_PF_BN128=1|ALGENTA_G3_PF_BN128"
    "ALGENTA_G3_PF_F16NORM=1|ALGENTA_G3_PF_F16NORM"
    "ALGENTA_G3_PF_F16MLP=1|ALGENTA_G3_PF_F16MLP"
    "ALGENTA_G3_PF_F16ATTN=1|ALGENTA_G3_PF_F16ATTN"
    "ALGENTA_G3_PF_ROPE2=1|ALGENTA_G3_PF_ROPE2"
    "ALGENTA_G3_PF_TCATTN=1|ALGENTA_G3_PF_TCATTN"
    "ALGENTA_G3_STREAM=1|ALGENTA_G3_STREAM"
)
# ALGENTA_7B_CTX8192 has no banner of its own (it only widens MAX_CTX); it is audited through
# the runtime `TC FLAGS:` banner's `max_ctx =` field, which the session prints at open. The
# gemma-3 driver's context width is its own `max_ctx =` field in the `G3 FLAGS:` banner.
CTX_PAT="ALGENTA_7B_CTX8192"
# The two FRONT 6 runtime fields: `pass_max =` in the `TC FLAGS:` banner must read 4096 for a
# PASS4096 arm and 1024 for every other arm, and `lt_shapes_tuned = N of 4` (printed with the
# LTALGO literal) must read 4 — 0 means the lever compiled in and then declined everywhere, so
# the cell was measured on cublasGemmEx DEFAULT while still claiming the flag.
PASS_MAX_PAT="pass_max = 4096"
LT_TUNED_PAT="lt_shapes_tuned = 4 of 4"
# The FRONT 7 runtime fields. Each of these four flags can be present in a binary while the
# effect is absent, and three of them can be absent while the binary still LOOKS like the lever
# (the twin kernel's name is in the string table either way):
#   o16_twin = armed        the session will attempt the twin (and PF_O16LIVE's correctness gate
#                           held: LTALGO on, rung 0). Without it the flag compiled in but the
#                           f32 O is still written and still converted.
#   NO "f16 O twin DECLINED" the attempt did not fall back at runtime. A declined twin means the
#                           cell measured the shipped convert path.
#   O16 VERIFY RESULT: PASS  the full-element bit-identity proof (411,041,792 elements per RAG
#                           prefill, compared as bits) actually ran and passed. Only the _hv
#                           proof arm carries it; a ship arm has no verify line and that is
#                           correct — the JSON says which is which.
#   LT INSITU: FROZEN 4      the in-situ search completed and froze all four shapes before the
#                           timed loop. State 1 (still exploring) during a measured cell would
#                           rotate algorithms between that cell's own samples.
O16_ARMED_PAT="o16_twin = armed"
O16_DECLINED_PAT="f16 O twin DECLINED"
O16_VERIFY_PAT="O16 VERIFY RESULT: PASS"
LT_INSITU_FROZEN_PAT="LT INSITU: FROZEN 4"

# POSITIVE CONTROLS. A literal every driver of the family carries regardless of flags. If
# neither is found, the audit is broken (not the binary) and must abort rather than report an
# empty flag set — the first version of this script did exactly that: `grep -q` exits on the
# first match, `printf` then dies of SIGPIPE, and `set -o pipefail` turned the pipeline
# non-zero, so every flag in every arm read as ABSENT. An audit that fails in the "nothing is
# enabled" direction is worse than no audit, because it looks like a clean result.
CONTROL_7B="TC: prefill f16 dual residency STAGED |"
CONTROL_G3="G3 FLAGS: TCATTN ="

# bash pattern match, NOT a pipe into grep: no SIGPIPE, no pipefail interaction.
has_lit() { [[ "$1" == *"$2"* ]]; }

mkdir -p "$(dirname "$OUT")"
TMP=$(mktemp)
: > "$TMP"

n_bins=0
for pat in "${GLOBS[@]}"; do
for bin in "$BIN_DIR"/$pat; do
    [[ -f "$bin" ]] || continue
    case "$bin" in *.o|*.txt|*.log|*.json|*.sh) continue ;; esac
    n_bins=$((n_bins + 1))
    name=$(basename "$bin")
    sha=$(shasum -a 256 "$bin" 2>/dev/null | cut -c1-16)
    [[ -z "$sha" ]] && sha=$(sha256sum "$bin" | cut -c1-16)
    size=$(stat -c %s "$bin" 2>/dev/null || stat -f %z "$bin")
    mtime=$(date -u -r "$bin" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")
    str=$(strings -a "$bin")
    family=""
    control=""
    if has_lit "$str" "$CONTROL_G3"; then
        family="gemma3"; control="$CONTROL_G3"
    elif has_lit "$str" "$CONTROL_7B"; then
        family="7b"; control="$CONTROL_7B"
    fi
    if [[ -z "$family" ]]; then
        echo "FATAL: no family positive control literal found in $name — this audit cannot read" >&2
        echo "       the binary's string table (strings=${#str} bytes) or the binary is not a" >&2
        echo "       TC-shim driver at all. Refusing to report an empty flag set as a result." >&2
        rm -f "$TMP"
        exit 3
    fi
    FLAGS=("${FLAGS_7B[@]}")
    [[ "$family" == "gemma3" ]] && FLAGS=("${FLAGS_G3[@]}")
    present=()
    absent=()
    for entry in "${FLAGS[@]}"; do
        pat2="${entry%%|*}"
        if has_lit "$str" "$pat2"; then
            present+=("${entry##*|}")
        else
            absent+=("${entry##*|}")
        fi
    done
    # the runtime banner, when a session-open log for this arm is available
    rt=""
    armed=""
    armed2=""
    ltline=""
    o16line=""
    o16dec=""
    o16ver=""
    o16shimver=""
    ltins=""
    if [[ -n "$LOG_DIR" ]]; then
        lg=$(grep -rl -m1 -F "$name" "$LOG_DIR" 2>/dev/null | head -1)
        if [[ -n "${lg:-}" && -f "$lg" ]]; then
            # the resolved-bool banner is per-family: "TC FLAGS:" for the 7B session,
            # "G3 FLAGS:" for gemma-3 (session_cuda_gemma3_f16._print_round5_flag_audit)
            rt=$(grep -m1 -E "^(TC|G3) FLAGS:" "$lg" 2>/dev/null | head -1)
            # FRONT 3's FA verdict and FRONT 4's v2 verdict are DIFFERENT lines; an arm that
            # carries FA2 must show the v2 line too, or the v2 kernel declined at runtime and
            # the cell measured FRONT 3's kernel. Capturing only the first match would hide
            # exactly that. `armed` is the family-generic pattern so it also catches gemma-3's
            # "fused windowed TC flash attention ARMED/DECLINED"; `armed2` is the v2 pattern,
            # family-generic the same way since round 6 (it matches the 7B lane's "fused causal
            # flash attention v2" and gemma-3's "fused windowed TC flash attention v2").
            armed=$(grep -m1 -E "flash attention (ARMED|DECLINED)" "$lg" 2>/dev/null | head -1)
            armed2=$(grep -m1 -E "flash attention v2 (ARMED|DECLINED)" "$lg" 2>/dev/null | head -1)
            # the tuned-shape count rides the LTALGO TCFLAG line, NOT the `TC FLAGS:` banner:
            # the banner is printed unconditionally and calling _tc_lt_count() from it would make
            # every flag-off build reference a cublasLt symbol and fail to link against the stock
            # shim object. So the effect field has to be read from its own line.
            ltline=$(grep -m1 "lt_shapes_tuned" "$lg" 2>/dev/null | head -1)
            # FRONT 7's runtime-effect lines. The O16 twin's own banner line carries the `armed`
            # field and the row-order it will run; the DECLINED line is per-prefill and only
            # appears if the twin entry fell back, so its PRESENCE is the bad case; the verify
            # verdict and the in-situ freeze count come from the proof arm and the driver.
            o16line=$(grep -m1 "ALGENTA_7B_PF_O16TWIN=1" "$lg" 2>/dev/null | head -1)
            o16dec=$(grep -m1 "$O16_DECLINED_PAT" "$lg" 2>/dev/null | head -1)
            o16ver=$(grep -m1 "O16 VERIFY RESULT" "$lg" 2>/dev/null | head -1)
            o16shimver=$(grep -m1 "TC O16 VERIFY" "$lg" 2>/dev/null | head -1)
            ltins=$(grep -m1 "LT INSITU: FROZEN" "$lg" 2>/dev/null | head -1)
        fi
    fi
    {
        echo "  {"
        echo "   \"arm\": \"$name\","
        echo "   \"family\": \"$family\","
        echo "   \"positive_control\": $(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$control"),"
        echo "   \"path\": \"$bin\","
        echo "   \"sha256_16\": \"$sha\","
        echo "   \"bytes\": $size,"
        echo "   \"mtime_utc\": \"$mtime\","
        echo -n "   \"flags_in_binary\": ["
        first=1
        for f in ${present+"${present[@]}"}; do
            [[ $first -eq 0 ]] && echo -n ", "
            echo -n "\"$f\""; first=0
        done
        echo "],"
        echo -n "   \"flags_absent\": ["
        first=1
        for f in ${absent+"${absent[@]}"}; do
            [[ $first -eq 0 ]] && echo -n ", "
            echo -n "\"$f\""; first=0
        done
        echo "],"
        echo "   \"runtime_banner\": $( [[ -n "$rt" ]] && python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$rt" || echo null ),"
        echo "   \"fa_verdict\": $( [[ -n "$armed" ]] && python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$armed" || echo null ),"
        echo "   \"fa2_verdict\": $( [[ -n "$armed2" ]] && python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$armed2" || echo null ),"
        # FRONT 6: the two levers whose flag literal can be present while the EFFECT is absent.
        # A pass cap no prompt exceeds, or an Lt arm whose four shapes all declined (-320) and
        # ran cublasGemmEx DEFAULT anyway, would both audit as "flag in binary" and measure the
        # shipped path. These read the runtime banner, so the JSON records whether the effect
        # actually happened, not merely whether the flag was passed.
        echo "   \"pass_max_4096\": $( [[ "$rt" == *"$PASS_MAX_PAT"* ]] && echo true || echo false ),"
        echo "   \"lt_tuned_4_of_4\": $( [[ "$ltline" == *"$LT_TUNED_PAT"* ]] && echo true || echo false ),"
        echo "   \"lt_line\": $( [[ -n "$ltline" ]] && python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$ltline" || echo null ),"
        # FRONT 7: the twin's runtime effect, its decline, the bit-identity verdict and the
        # in-situ freeze. `o16_declined_at_runtime` is the one whose TRUE value is bad: it means
        # the binary carries the lever, the session armed it, and the shim still fell back — so
        # the cell measured the shipped convert path.
        echo "   \"o16_twin_armed\": $( [[ "$o16line" == *"$O16_ARMED_PAT"* ]] && echo true || echo false ),"
        echo "   \"o16_declined_at_runtime\": $( [[ -n "$o16dec" ]] && echo true || echo false ),"
        echo "   \"o16_verify_pass\": $( [[ "$o16ver" == *"$O16_VERIFY_PAT"* ]] && echo true || echo false ),"
        echo "   \"lt_insitu_frozen_4\": $( [[ "$ltins" == *"$LT_INSITU_FROZEN_PAT"* ]] && echo true || echo false ),"
        echo "   \"o16_line\": $( [[ -n "$o16line" ]] && python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$o16line" || echo null ),"
        echo "   \"o16_decline_line\": $( [[ -n "$o16dec" ]] && python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$o16dec" || echo null ),"
        echo "   \"o16_verify_line\": $( [[ -n "$o16ver" ]] && python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$o16ver" || echo null ),"
        echo "   \"o16_shim_verify_line\": $( [[ -n "$o16shimver" ]] && python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$o16shimver" || echo null ),"
        echo "   \"lt_insitu_line\": $( [[ -n "$ltins" ]] && python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$ltins" || echo null )"
        echo "  },"
    } >> "$TMP"
done
done

{
    echo "{"
    echo " \"meta\": {"
    echo "  \"tool\": \"scripts/audit_tc_flags.sh (strings-based comptime banner audit)\","
    echo "  \"date_utc\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
    echo "  \"host\": \"$(hostname)\","
    echo "  \"bin_dir\": \"$BIN_DIR\","
    echo "  \"n_bins\": $n_bins,"
    echo "  \"globs\": $(python3 -c 'import json,sys;print(json.dumps(sys.argv[1:]))' "${GLOBS[@]}"),"
    echo "  \"method\": \"the session prints one 'TCFLAG <name>=1 ...' line per numeric-path flag from inside that flag's own @parameter if (session_cuda_p3._tc_stage_weights for the 7B family, session_cuda_gemma3_f16._print_round5_flag_audit for gemma-3), so the literal exists ONLY in a binary built with the flag. strings -a is therefore a positive audit and an absent literal is proof of OFF. Family is decided by which positive-control literal the binary carries, never by its filename.\","
    echo "  \"why\": \"the gemma-3-27b H200 column was voided by a rebuild that silently dropped -D ALGENTA_G3_STREAM; no published cell recorded which flags the measured binary carried. This audit makes that unrepresentable.\","
    echo "  \"ctx8192_note\": \"ALGENTA_7B_CTX8192 widens MAX_CTX only and has no TCFLAG literal; it is audited via the runtime banner's 'max_ctx =' field (1600 = off, 8192 = on). The gemma-3 driver's context width is the same field of its 'G3 FLAGS:' banner.\","
    echo "  \"branch\": \"$(git -C "$(dirname "${BASH_SOURCE[0]}")/.." rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)\","
    echo "  \"head\": \"$(git -C "$(dirname "${BASH_SOURCE[0]}")/.." rev-parse --short HEAD 2>/dev/null || echo unknown)\""
    echo " },"
    echo " \"arms\": ["
    sed '$ s/},$/}/' "$TMP"
    echo " ]"
    echo "}"
} > "$OUT"
rm -f "$TMP"

echo "flag audit written to $OUT ($n_bins binaries)"
python3 -c "
import json,sys
d=json.load(open('$OUT'))
print('%-38s %s' % ('arm','flags_in_binary'))
for a in d['arms']:
    print('%-38s %s' % (a['arm'], ' '.join(f.replace('ALGENTA_','') for f in a['flags_in_binary']) or '(none)'))
    if a.get('runtime_banner'): print('%-38s   %s' % ('', a['runtime_banner']))
    if a.get('fa_verdict'): print('%-38s   %s' % ('', a['fa_verdict']))
    if a.get('fa2_verdict'): print('%-38s   %s' % ('', a['fa2_verdict']))
    print('%-38s   pass_max_4096=%s lt_tuned_4_of_4=%s' % ('', a.get('pass_max_4096'), a.get('lt_tuned_4_of_4')))
    if a.get('o16_line') or a.get('o16_twin_armed'):
        print('%-38s   o16_twin_armed=%s declined_at_runtime=%s verify_pass=%s'
              % ('', a.get('o16_twin_armed'), a.get('o16_declined_at_runtime'),
                 a.get('o16_verify_pass')))
        if a.get('o16_shim_verify_line'):
            print('%-38s   %s' % ('', a['o16_shim_verify_line']))
        if a.get('o16_decline_line'):
            print('%-38s   DECLINED: %s' % ('', a['o16_decline_line']))
    if a.get('lt_insitu_line'):
        print('%-38s   lt_insitu_frozen_4=%s | %s'
              % ('', a.get('lt_insitu_frozen_4'), a['lt_insitu_line']))
" || { echo "AUDIT JSON INVALID" >&2; exit 1; }
