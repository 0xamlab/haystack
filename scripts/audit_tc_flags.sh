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
# WHAT IT DOES. `residentk.session_cuda_p3._tc_stage_weights` prints one banner line per
# numeric-path flag from INSIDE that flag's own `@parameter if`, so the literal only exists in a
# binary that has the flag. `strings` on the binary is therefore a positive audit, and an absent
# line means OFF — a build cannot print a line it does not contain. This script greps exactly
# those literals, cross-checks them against the flags the build was invoked with, and writes
# both plus the runtime `TC FLAGS:` banner (captured from a real session open, if a log is
# given) to JSON.
#
# Usage:
#   bash scripts/audit_tc_flags.sh --bin-dir ~/front3/bin --out ~/trtllm/front3/flag_audit.json
#   bash scripts/audit_tc_flags.sh --bin-dir ~/front3/bin --logs ~/trtllm/front3 --out ...
set -uo pipefail

BIN_DIR="$HOME/front3/bin"
LOG_DIR=""
OUT="$HOME/trtllm/front3/flag_audit.json"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --bin-dir) BIN_DIR="$2"; shift 2 ;;
        --logs) LOG_DIR="$2"; shift 2 ;;
        --out) OUT="$2"; shift 2 ;;
        *) echo "unknown arg $1" >&2; exit 2 ;;
    esac
done

# flag literal in the binary  ->  the -D that must have produced it
FLAGS=(
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
)
# ALGENTA_7B_CTX8192 has no banner of its own (it only widens MAX_CTX); it is audited through
# the runtime `TC FLAGS:` banner's `max_ctx =` field, which the session prints at open.
CTX_PAT="ALGENTA_7B_CTX8192"

# POSITIVE CONTROL. A literal every one of these drivers carries regardless of flags. If this
# is not found, the audit is broken (not the binary) and must abort rather than report an
# empty flag set — the first version of this script did exactly that: `grep -q` exits on the
# first match, `printf` then dies of SIGPIPE, and `set -o pipefail` turned the pipeline
# non-zero, so every flag in every arm read as ABSENT. An audit that fails in the "nothing is
# enabled" direction is worse than no audit, because it looks like a clean result.
CONTROL="TC: prefill f16 dual residency STAGED |"

# bash pattern match, NOT a pipe into grep: no SIGPIPE, no pipefail interaction.
has_lit() { [[ "$1" == *"$2"* ]]; }

mkdir -p "$(dirname "$OUT")"
TMP=$(mktemp)
: > "$TMP"

n_bins=0
for bin in "$BIN_DIR"/qwen25_7b_p3_graph_cuda*; do
    [[ -f "$bin" ]] || continue
    case "$bin" in *.o|*.txt|*.log) continue ;; esac
    n_bins=$((n_bins + 1))
    name=$(basename "$bin")
    sha=$(shasum -a 256 "$bin" 2>/dev/null | cut -c1-16)
    [[ -z "$sha" ]] && sha=$(sha256sum "$bin" | cut -c1-16)
    size=$(stat -c %s "$bin" 2>/dev/null || stat -f %z "$bin")
    mtime=$(date -u -r "$bin" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")
    str=$(strings -a "$bin")
    if ! has_lit "$str" "$CONTROL"; then
        echo "FATAL: positive control literal not found in $name — this audit cannot read" >&2
        echo "       the binary's string table (strings=${#str} bytes). Refusing to report" >&2
        echo "       an empty flag set as if it were a result." >&2
        rm -f "$TMP"
        exit 3
    fi
    present=()
    absent=()
    for entry in "${FLAGS[@]}"; do
        pat="${entry%%|*}"
        if has_lit "$str" "$pat"; then
            present+=("${entry##*|}")
        else
            absent+=("${entry##*|}")
        fi
    done
    # the runtime banner, when a session-open log for this arm is available
    rt=""
    armed=""
    if [[ -n "$LOG_DIR" ]]; then
        lg=$(ls -1t "$LOG_DIR"/*"${name##qwen25_7b_p3_graph_cuda}"*.log 2>/dev/null | head -1)
        if [[ -n "${lg:-}" && -f "$lg" ]]; then
            rt=$(grep -m1 "^TC FLAGS:" "$lg" 2>/dev/null | head -1)
            armed=$(grep -m1 -E "flash attention (ARMED|DECLINED)" "$lg" 2>/dev/null | head -1)
        fi
    fi
    {
        echo "  {"
        echo "   \"arm\": \"$name\","
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
        echo "   \"fa_verdict\": $( [[ -n "$armed" ]] && python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$armed" || echo null )"
        echo "  },"
    } >> "$TMP"
done

{
    echo "{"
    echo " \"meta\": {"
    echo "  \"tool\": \"scripts/audit_tc_flags.sh (strings-based comptime banner audit)\","
    echo "  \"date_utc\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
    echo "  \"host\": \"$(hostname)\","
    echo "  \"bin_dir\": \"$BIN_DIR\","
    echo "  \"n_bins\": $n_bins,"
    echo "  \"method\": \"session_cuda_p3._tc_stage_weights prints one 'TCFLAG <name>=1 ...' line per numeric-path flag from inside that flag's own @parameter if, so the literal exists ONLY in a binary built with the flag. strings -a is therefore a positive audit and an absent literal is proof of OFF.\","
    echo "  \"why\": \"the gemma-3-27b H200 column was voided by a rebuild that silently dropped -D ALGENTA_G3_STREAM; no published cell recorded which flags the measured binary carried. This audit makes that unrepresentable.\","
    echo "  \"ctx8192_note\": \"ALGENTA_7B_CTX8192 widens MAX_CTX only and has no TCFLAG literal; it is audited via the runtime banner's 'max_ctx =' field (1600 = off, 8192 = on).\","
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
" || { echo "AUDIT JSON INVALID" >&2; exit 1; }
