"""Phase 5A live verification: quota, usage recording, rate limiting."""
import json
import sys
import urllib.request

BASE = "http://localhost:8000"
KEY = "de_live_mqY1soUd-ZUzv6cOXHZOmbPw_LEGQUvz"
HDR = {"Content-Type": "application/json", "X-API-Key": KEY}

PASSED = []
FAILED = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(label)
        print(f"  ✓ {label}{' — ' + detail if detail else ''}")
    else:
        FAILED.append(label)
        print(f"  ✗ {label}{' — ' + detail if detail else ''}")


def http(method: str, path: str, body=None, headers=HDR):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read()), resp.headers
    except urllib.request.HTTPError as e:
        return e.code, json.loads(e.read()), None


print("\n── Phase 5A: Quota + Usage Recording live verification ──\n")

# ── 1. Simulate ───────────────────────────────────────────────────────────────
print("1. POST /v1/simulate")
status, body, headers = http(
    "POST", "/v1/simulate",
    {
        "mode": "auto",
        "scenario": {
            "variables": {
                "revenue": {"low": 80000, "high": 200000},
                "cost":    {"low": 30000, "high": 90000},
            },
            "objective": "maximize_net_value",
        },
        "seed": 42,
    }
)
check("status=200", status == 200, str(status))
result_hash = body.get("result_hash", "")
check("result_hash in body (64 chars)", bool(result_hash) and len(result_hash) == 64, result_hash[:16] + "...")
x_hash_hdr = headers["X-Decision-Hash"] if headers else "MISSING"
check("X-Decision-Hash header present", x_hash_hdr != "MISSING", x_hash_hdr[:30] + "...")
check("header contains hash", bool(result_hash) and result_hash in x_hash_hdr)
run_id = body.get("run_id")
action = body.get("recommended_action")
print(f"  run_id={run_id}, action={action}")

# ── 2. Usage endpoint ─────────────────────────────────────────────────────────
print("\n2. GET /v1/usage")
status2, usage, _ = http("GET", "/v1/usage")
check("status=200", status2 == 200, str(status2))
sims_run = usage.get("simulations_run", 0)
check("simulations_run >= 1", sims_run >= 1, str(sims_run))
check("billing_period present", bool(usage.get("billing_period")), usage.get("billing_period", ""))

# ── 3. DB check via psycopg2 ──────────────────────────────────────────────────
print("\n3. DB: usage_records table")
try:
    import psycopg2
    conn = psycopg2.connect("postgresql://angel@localhost:5432/decision_engine")
    cur = conn.cursor()
    cur.execute(
        "SELECT id, endpoint, billing_units, scenarios_run, billing_period "
        "FROM usage_records ORDER BY created_at DESC LIMIT 1"
    )
    row = cur.fetchone()
    conn.close()
    if row:
        check("usage_record exists in DB", True, f"endpoint={row[1]} billing_units={row[2]} scenarios={row[3]}")
        check("endpoint=simulate", row[1] == "simulate", str(row[1]))
        check("billing_units=1", row[2] == 1, str(row[2]))
    else:
        check("usage_record exists in DB", False, "NO ROWS FOUND")
except ImportError:
    print("  (psycopg2 not available — skipping DB check)")
except Exception as e:
    print(f"  DB check error: {e}")

# ── 4. Limits endpoint ────────────────────────────────────────────────────────
print("\n4. GET /v1/limits")
status4, limits, _ = http("GET", "/v1/limits")
check("status=200", status4 == 200, str(status4))
check("plan present", bool(limits.get("plan")), limits.get("plan", ""))
check("max_simulations_per_month present", "max_simulations_per_month" in limits)

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n── Results: {len(PASSED)} passed, {len(FAILED)} failed ──")
if FAILED:
    print(f"FAILED: {', '.join(FAILED)}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED ✓")
    sys.exit(0)
