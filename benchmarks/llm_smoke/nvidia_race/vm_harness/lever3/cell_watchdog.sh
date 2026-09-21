#!/bin/bash
# cell_watchdog.sh -- sourceable drop-in implementing the parent's directive (d): a DEAD-CHAIN
# WATCHDOG. Wraps one timed cell so a wedged driver can never silently burn an hour.
#
# Usage in a battery script:
#   source /home/angel/lever3/cell_watchdog.sh
#   cw_init "$RUNS" "$LOGS" "$CLK" "$GPU"        # once, after mkdir
#   cw_cell "label" "$BIN" "$CKPT" --tokens-file ... --max-new 1 --f16 --prefill
#
# Semantics: after CELL START, if no exit within CW_TIMEOUT_S (default 600 = 10 min) the cell is
# logged as STALL, the whole process group is SIGKILLed, and the battery CONTINUES to the next
# cell. A stalled cell writes no driver JSON line, so summarisers skip it (n drops) rather than
# silently reporting a partial run.
#
# Why this exists: on 2026-09-16 a lever-2 gate cell was killed mid-blob-load during a
# deliberate reprioritisation, and its truncated .out (2 banner lines, no JSON) was later
# misread as a crashed/demoted arm. A watchdog makes that state explicit in the log instead of
# leaving an ambiguous truncated artifact.
CW_TIMEOUT_S=${CW_TIMEOUT_S:-600}
# THE PIN IS A GPU-SKU FACT. 1410 MHz is what the campaign pinned on H200 and on A100-SXM4-40GB;
# another SKU may not honour that exact request (`nvidia-smi -lgc` clamps to the supported range),
# and a watchdog that hardcodes the number would then count EVERY sample as off-pin and refuse a
# window that was in fact perfectly pinned. Callers that pin a different clock set CW_PIN_MHZ and
# the drift check, the re-pin and the off-pin count all follow it. Default unchanged for the
# campaign's own boxes.
CW_PIN_MHZ=${CW_PIN_MHZ:-1410}

cw_init() { CW_RUNS=$1; CW_LOGS=$2; CW_CLK=$3; CW_GPU=${4:-1}; }

cw_ts() { date -u +%FT%TZ; }
cw_log() { echo "[$(cw_ts)] $*" | tee -a "${CW_LOGFILE:-/home/angel/lever3/watchdog.log}"; }
cw_ck() { nvidia-smi --query-gpu=clocks.current.sm,temperature.gpu,power.draw,memory.used,utilization.gpu --format=csv,noheader -i "${CW_GPU:-1}"; }
cw_smi_raw() { nvidia-smi --query-gpu=clocks.current.sm --format=csv,noheader,nounits -i "${CW_GPU:-1}"; }

cw_ensure_clocks() {
  local c; c=$(cw_smi_raw)
  if [[ "$c" != "$CW_PIN_MHZ" ]]; then
    cw_log "CLOCK_DRIFT ($c MHz, want $CW_PIN_MHZ) -> re-pinning"
    sudo -n nvidia-smi -pm 1 >/dev/null 2>&1
    sudo -n nvidia-smi -lgc "$CW_PIN_MHZ" >/dev/null 2>&1
    sleep 2; c=$(cw_smi_raw)
  fi
  echo "$c"
}

cw_cell() { # $1=label ; rest=command
  local label=$1; shift
  local before after rc nsamp nonpin t0 pid
  before=$(cw_ensure_clocks)
  cw_log "CELL $label START clocks_before=${before}MHz smi=[$(cw_ck)]"
  ( while true; do
      printf '%s %s\n' "$(date -u +%FT%TZ)" \
        "$(nvidia-smi --query-gpu=clocks.current.sm,utilization.gpu,utilization.memory,memory.used,power.draw,temperature.gpu --format=csv,noheader -i "${CW_GPU:-1}")"
      sleep 1
    done > "$CW_CLK/clocks_${label}.csv" 2>/dev/null ) &
  local sampler=$!
  # run in its own process group so the watchdog can kill the driver AND any children
  setsid "$@" > "$CW_RUNS/$label.out" 2> "$CW_LOGS/$label.err" &
  pid=$!
  t0=$SECONDS
  while kill -0 "$pid" 2>/dev/null; do
    if (( SECONDS - t0 > CW_TIMEOUT_S )); then
      cw_log "CELL $label STALL -- no exit within ${CW_TIMEOUT_S}s; killing process group and continuing"
      kill -9 -- "-$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null
      sleep 3
      echo "{\"label\": \"$label\", \"stalled\": true, \"timeout_s\": $CW_TIMEOUT_S}" >> "$CW_RUNS/$label.out"
      break
    fi
    sleep 5
  done
  wait "$pid" 2>/dev/null; rc=$?
  kill "$sampler" 2>/dev/null; wait "$sampler" 2>/dev/null
  after=$(cw_ensure_clocks)
  nsamp=$(wc -l < "$CW_CLK/clocks_${label}.csv" 2>/dev/null || echo 0)
  nonpin=$(awk '{print $2}' "$CW_CLK/clocks_${label}.csv" 2>/dev/null | grep -vc "^${CW_PIN_MHZ}$" || true)
  cw_log "CELL $label END rc=$rc clocks_after=${after}MHz samples=$nsamp offpin=$nonpin smi=[$(cw_ck)]"
  return $rc
}
