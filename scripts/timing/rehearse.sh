#!/usr/bin/env bash
# Gate 4 end-to-end rehearsal — every piece, in order, as one pipeline.
#
# The individual stages are tested. The PIPELINE is not, and a race weekend is exactly the wrong moment to
# discover that stage 3 expects something stage 2 does not emit. The plan is explicit that Monza practice
# and qualifying must not be the first test of the live path, so this runs the whole chain against an
# archived session on any ordinary afternoon:
#
#   live_ingest      archived race -> archive-format .jsonStream, with an injected reconnect
#   build_event_log  -> append-only event log
#   replay_state     -> laps / stints / pits / regime, and a state hash
#   PARITY GATE      the reconstructed state must be BIT-IDENTICAL to the archive's
#   pitwall_tui      -> boards over real as-of state, at the operational replication count
#   decision_outbox  -> hash-chained decisions, chain verified, head printed for publication
#
# Exit non-zero on the first failure. A rehearsal that reports success on a broken chain is worse than no
# rehearsal, so every stage is checked rather than merely run.
#
# Usage:
#   scripts/timing/rehearse.sh                        # picks a 2024 race
#   SESSION=<archived race dir> scripts/timing/rehearse.sh
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO}"

# Gate 0 item 7: fallback denial applies to the rehearsal too, or it is not rehearsing the real thing.
export RUNTIME_FALLBACK_MODE="deny"
export MOJO_ALLOW_SUBPROCESS_FALLBACK="false"

SESSION="${SESSION:-$(find "${HOME}/.algenta/f1/raw/2024" -maxdepth 2 -type d -name '*_Race' | sort | head -1)}"
WORK="${WORK:-/tmp/algenta_rehearsal}"
# Focal defaults to a MIDFIELD car, not the leader. The board needs a target rival ahead on track, so a
# leading focal car produces no board at all -- the first run of this rehearsal picked car 1, got one
# decision from three lap-steps, and printed "board not evaluated" without failing. A rehearsal that
# accepts that is the failure it exists to prevent.
FOCAL="${FOCAL:-}"
REPS="${REPS:-20000}"          # the operational count established by the rung-4 stability study
LAPS="${LAPS:-6}"

[ -d "${SESSION}" ] || { echo "no session at ${SESSION}" >&2; exit 2; }
rm -rf "${WORK}"; mkdir -p "${WORK}"
LIVE="${WORK}/live"

echo "══ Gate 4 rehearsal ═════════════════════════════════════════════════════════"
echo "  source   $(basename "$(dirname "${SESSION}")")/$(basename "${SESSION}")"
echo "  work     ${WORK}"
echo "  reps     ${REPS}  (the rung-4 operational count)"
echo

echo "── 1/6  live ingest, with an injected reconnect ─────────────────────────────"
python3 scripts/timing/live_ingest.py --replay-from "${SESSION}" --out "${LIVE}" \
    --speed 0 --log-every 999 2>&1 | tail -4
# the static keyframes a live subscribe delivers on connect
for f in SessionInfo.json DriverList.json ArchiveStatus.json Index.json; do
    [ -f "${SESSION}/${f}" ] && cp "${SESSION}/${f}" "${LIVE}/${f}"
done

echo
echo "── 2/6  event log ───────────────────────────────────────────────────────────"
python3 scripts/timing/build_event_log.py --dir "${LIVE}" 2>&1 | tail -3

echo
echo "── 3/6  state reconstruction ────────────────────────────────────────────────"
python3 scripts/timing/replay_state.py --dir "${LIVE}" 2>&1 | tail -4

echo
echo "── 4/6  PARITY GATE: live-ingested state must equal the archive ─────────────"
python3 - "$SESSION" "$LIVE" <<'PY'
import sys
sys.path.insert(0, "scripts/timing")
from pathlib import Path
from replay_state import replay
src, live = Path(sys.argv[1]), Path(sys.argv[2])
a, b = replay(src, emit=False), replay(live, emit=False)
for k in ("laps", "stints", "pit_events", "regime_changes", "max_lap"):
    flag = "ok" if a[k] == b[k] else "DIFFER"
    print(f"    {k:<16}{a[k]:>8}{b[k]:>8}   {flag}")
if a["state_hash"] != b["state_hash"]:
    print(f"\n    PARITY FAILED\n      archive {a['state_hash']}\n      live    {b['state_hash']}")
    print("    The live path is not the same path. Everything downstream is now suspect.")
    sys.exit(1)
print(f"\n    state hash IDENTICAL: {a['state_hash'][:32]}")
PY

echo
echo "── 5/6  option boards over real as-of state ─────────────────────────────────"
OUTBOX="${WORK}/decisions.jsonl"
TOTAL=$(python3 -c "
import pyarrow.parquet as pq
t=pq.read_table('${LIVE}/_laps.parquet').to_pydict()
print(max(x for x in t['lap_number'] if x))")
FROM=$(( TOTAL / 3 )); TO=$(( FROM + LAPS ))
if [ -z "${FOCAL}" ]; then
  FOCAL=$(python3 -c "
import pyarrow.parquet as pq
from collections import defaultdict
t=pq.read_table('${LIVE}/_laps.parquet').to_pydict()
at={}
for c,ln,pos in zip(t['car_number'],t['lap_number'],t['position']):
    if ln==${FROM} and pos: at[pos]=c
# P6 if available: far enough back to have a rival ahead, far enough forward to matter
print(at.get(6) or at.get(5) or (sorted(at)[len(at)//2] and at[sorted(at)[len(at)//2]]))")
  echo "  focal car auto-selected: ${FOCAL} (running ~P6 at lap ${FROM}, so a target rival exists)"
fi
python3 scripts/timing/pitwall_tui.py --dir "${LIVE}" --focal "${FOCAL}" \
    --reps "${REPS}" --speed 0 --from-lap "${FROM}" --to-lap "${TO}" --every 2 \
    --outbox "${OUTBOX}" --theta-json docs/timing/calibration.json \
    > "${WORK}/tui.txt" 2>"${WORK}/tui.err" || { tail -5 "${WORK}/tui.err" >&2; exit 1; }
sed 's/\x1b\[[0-9;]*m//g' "${WORK}/tui.txt" | tail -14

EXPECTED=$(( (TO - FROM) / 2 ))
WROTE=$(wc -l < "${OUTBOX}" 2>/dev/null | tr -d ' ' || echo 0)
if [ "${WROTE}" -lt "${EXPECTED}" ]; then
  echo
  echo "    REHEARSAL FAILED: ${WROTE} boards written, expected at least ${EXPECTED}." >&2
  echo "    Silently producing fewer decisions than lap-steps is how a live session ends up with gaps" >&2
  echo "    nobody notices. Check the focal car has a rival ahead at every step." >&2
  exit 1
fi
echo "    ${WROTE} boards written across $(( (TO - FROM) / 2 )) lap-steps"

echo
echo "── 6/6  decision chain ──────────────────────────────────────────────────────"
python3 scripts/timing/decision_outbox.py "${OUTBOX}" 2>&1 | head -4

echo
echo "══ rehearsal complete ═══════════════════════════════════════════════════════"
echo "  Publish the chain head above BEFORE the session it covers has finished."
echo "  A record that could have been written afterwards is not evidence."
