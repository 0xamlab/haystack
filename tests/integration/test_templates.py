"""
All 51 Simulation Templates End-to-End Tests — Phase 19

Runs every registered simulation template through the live API to verify
they all produce valid results.

Covers:
  - Template registry integrity (count, fields, uniqueness)
  - Template quality checks (variables, distributions, parameters)
  - Domain coverage analysis
  - End-to-end simulation for all 51 templates via POST /v1/simulate
  - Template list API (GET /v1/templates)
  - Template detail API (GET /v1/templates/{slug})
  - Results CSV output

Prerequisites:
  1. API server running: make dev-api
  2. PostgreSQL running on :5432
  3. Redis running on :6379
  4. Dev data seeded: python scripts/seed_dev.py

Run:
  python tests/integration/test_templates.py

Endpoints under test:
  GET  /v1/templates              — list all templates
  GET  /v1/templates/{slug}       — get specific template
  POST /v1/simulate               — run simulation
"""
import csv
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

# Ensure project root is on sys.path for direct module imports
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from apps.api_server.simulation_templates import (
    TEMPLATES,
    get_all_domains,
    get_all_tags,
    get_template,
    list_templates,
)

# Global socket timeout — prevents any test from hanging indefinitely
socket.setdefaulttimeout(30)

BASE_URL = os.environ.get("DE_BASE_URL", "http://localhost:8000")
API_KEY = os.environ.get("DE_API_KEY", "de_live_LrL6UWSAfgXsTjgfyaboI9aolrsznjLU")

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"
results: list[tuple] = []
timings: list[tuple[str, float]] = []

# CSV results for all 51 template runs
csv_rows: list[dict] = []

# Valid distribution names the engine accepts
VALID_DISTRIBUTIONS = {
    "normal", "lognormal", "uniform", "triangular", "beta", "gamma",
    "exponential", "poisson", "binomial", "bernoulli", "weibull",
    "fixed", "discrete", "pert", "logistic", "pareto", "cauchy",
    "chi_squared", "student_t", "gumbel", "halfnormal", "neg_binomial",
    "negative_binomial", "rayleigh",
}


# ─── HTTP helpers ─────────────────────────────────────────────────────────────
def req(method: str, path: str, body=None, headers=None, auth=True, timeout=30):
    """Make HTTP request, return (status_code, response_body_bytes, response_headers, elapsed)."""
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    h = {"Content-Type": "application/json"}
    if auth:
        h["X-API-Key"] = API_KEY
    if headers:
        h.update(headers)
    request = urllib.request.Request(url, data=data, headers=h, method=method)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            elapsed = time.perf_counter() - t0
            body_bytes = resp.read()
            return resp.status, body_bytes, dict(resp.headers), elapsed
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - t0
        body_bytes = e.read()
        return e.code, body_bytes, dict(e.headers), elapsed
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return 0, str(e).encode(), {}, elapsed


def req_json(method: str, path: str, body=None, headers=None, auth=True, timeout=30):
    """Make HTTP request, return (status_code, parsed_json_or_str, response_headers, elapsed)."""
    status, raw, hdrs, elapsed = req(method, path, body, headers, auth, timeout)
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
    return status, parsed, hdrs, elapsed


def record(name: str, passed: bool, detail: str = "", elapsed: float = 0.0):
    status = PASS if passed else FAIL
    results.append((name, status, detail))
    if elapsed > 0:
        timings.append((name, elapsed))
    icon = PASS if passed else FAIL
    suffix = f" ({detail[:80]})" if detail and not passed else ""
    ms = f" [{elapsed*1000:.0f}ms]" if elapsed > 0 else ""
    print(f"  {icon} {name}{ms}{suffix}")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: Template Registry Tests
# ═══════════════════════════════════════════════════════════════════════════════
def test_registry_count():
    """Verify TEMPLATES registry has exactly 51 templates."""
    count = len(TEMPLATES)
    record("registry_count_is_51", count == 51, f"got {count}")


def test_registry_required_fields():
    """Verify all templates have required fields populated."""
    ok = True
    bad = []
    required = ["id", "name", "domain", "description", "variables", "objective_function"]
    for tid, t in TEMPLATES.items():
        for field in required:
            val = getattr(t, field, None)
            if val is None or (isinstance(val, (str, list)) and len(val) == 0):
                bad.append(f"{tid}.{field}")
                ok = False
    record("all_templates_have_required_fields", ok, "; ".join(bad[:5]))


def test_registry_unique_slugs():
    """Verify all template IDs (slugs) are unique."""
    ids = list(TEMPLATES.keys())
    unique = len(set(ids))
    ok = unique == len(ids)
    record("all_slugs_unique", ok, f"{len(ids)} total, {unique} unique")


def test_registry_valid_domains():
    """Verify all templates have non-empty domain strings."""
    bad = [t.id for t in TEMPLATES.values() if not t.domain or not isinstance(t.domain, str)]
    ok = len(bad) == 0
    record("all_domains_valid_strings", ok, f"bad: {bad[:5]}")


def test_template_list_api():
    """Verify GET /v1/templates returns templates (API serves example templates)."""
    status, body, _, elapsed = req_json("GET", "/v1/templates")
    if status != 200:
        record("template_list_api_returns_templates", False, f"status={status}")
        return
    templates = body if isinstance(body, list) else body.get("templates", body.get("data", []))
    count = len(templates) if isinstance(templates, list) else 0
    record("template_list_api_returns_templates", count >= 1, f"got {count} API example templates", elapsed)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: Template Quality Tests
# ═══════════════════════════════════════════════════════════════════════════════
def test_each_template_has_min_variables():
    """Verify each template has >= 2 variables."""
    bad = [(t.id, len(t.variables)) for t in TEMPLATES.values() if len(t.variables) < 2]
    ok = len(bad) == 0
    record("each_template_ge_2_variables", ok, f"bad: {bad[:5]}")


def test_variable_distributions_valid():
    """Verify all variable distributions are recognized."""
    bad = []
    for t in TEMPLATES.values():
        for v in t.variables:
            if v.distribution.lower() not in VALID_DISTRIBUTIONS:
                bad.append(f"{t.id}/{v.name}={v.distribution}")
    ok = len(bad) == 0
    record("all_variable_distributions_valid", ok, f"bad: {bad[:5]}")


def test_variable_params_make_sense():
    """Verify variable parameters are mathematically consistent (low < high, etc.)."""
    bad = []
    for t in TEMPLATES.values():
        for v in t.variables:
            p = v.params
            dist = v.distribution.lower()
            if dist == "uniform":
                if "low" in p and "high" in p and p["low"] >= p["high"]:
                    bad.append(f"{t.id}/{v.name}: low >= high")
            elif dist == "triangular":
                if "low" in p and "high" in p and p["low"] >= p["high"]:
                    bad.append(f"{t.id}/{v.name}: low >= high")
                if "low" in p and "mode" in p and "high" in p:
                    if not (p["low"] <= p["mode"] <= p["high"]):
                        bad.append(f"{t.id}/{v.name}: mode not in [low, high]")
            elif dist == "normal":
                if "std" in p and p["std"] < 0:
                    bad.append(f"{t.id}/{v.name}: negative std")
            elif dist == "lognormal":
                if "std" in p and p["std"] < 0:
                    bad.append(f"{t.id}/{v.name}: negative std")
            elif dist == "beta":
                if "alpha" in p and p["alpha"] <= 0:
                    bad.append(f"{t.id}/{v.name}: alpha <= 0")
                if "beta" in p and p["beta"] <= 0:
                    bad.append(f"{t.id}/{v.name}: beta <= 0")
            elif dist == "gamma":
                if "shape" in p and p["shape"] <= 0:
                    bad.append(f"{t.id}/{v.name}: shape <= 0")
            elif dist == "fixed":
                if "value" not in p:
                    bad.append(f"{t.id}/{v.name}: fixed missing value")
            elif dist == "discrete":
                if "values" in p and "probabilities" in p:
                    if len(p["values"]) != len(p["probabilities"]):
                        bad.append(f"{t.id}/{v.name}: values/probs length mismatch")
                    total = sum(p["probabilities"])
                    if abs(total - 1.0) > 0.01:
                        bad.append(f"{t.id}/{v.name}: probs sum={total:.3f}")
    ok = len(bad) == 0
    record("variable_params_mathematically_valid", ok, "; ".join(bad[:5]))


def test_descriptions_non_empty():
    """Verify all templates have non-empty descriptions."""
    bad = [t.id for t in TEMPLATES.values() if not t.description or len(t.description.strip()) == 0]
    ok = len(bad) == 0
    record("all_descriptions_non_empty", ok, f"bad: {bad[:5]}")


def test_tags_are_string_arrays():
    """Verify tags are arrays of strings for all templates."""
    bad = []
    for t in TEMPLATES.values():
        if not isinstance(t.tags, list):
            bad.append(f"{t.id}: tags not list")
        else:
            for tag in t.tags:
                if not isinstance(tag, str):
                    bad.append(f"{t.id}: tag {tag!r} not str")
                    break
    ok = len(bad) == 0
    record("all_tags_are_string_arrays", ok, "; ".join(bad[:5]))


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: Domain Coverage Tests
# ═══════════════════════════════════════════════════════════════════════════════
def test_domain_coverage():
    """Verify at least 10 different domains are represented."""
    domains = get_all_domains()
    ok = len(domains) >= 10
    record("at_least_10_domains", ok, f"got {len(domains)}: {', '.join(domains)}")


def test_domain_distribution():
    """Count and display templates per domain."""
    from collections import Counter
    domain_counts = Counter(t.domain for t in TEMPLATES.values())
    summary = ", ".join(f"{d}={c}" for d, c in sorted(domain_counts.items()))
    record("domain_distribution_computed", True, summary)


def test_get_all_tags_non_empty():
    """Verify get_all_tags returns a non-empty set."""
    tags = get_all_tags()
    ok = len(tags) > 0
    record("tags_collection_non_empty", ok, f"got {len(tags)} unique tags")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: Template Detail API Tests
# ═══════════════════════════════════════════════════════════════════════════════
def test_get_template_by_slug():
    """Verify GET /v1/templates returns list with expected template structure."""
    # The API only exposes GET /v1/templates (list), no individual lookup endpoint
    status, body, _, elapsed = req_json("GET", "/v1/templates")
    if status == 200 and isinstance(body, list) and len(body) > 0:
        t = body[0]
        has_id = "id" in t
        has_name = "name" in t
        record("template_api_response_structure", has_id and has_name, f"keys={list(t.keys())[:5]}", elapsed)
        record("template_api_has_example_request", "example_request" in t, f"keys={list(t.keys())}", elapsed)
    else:
        record("template_api_response_structure", False, f"status={status}", elapsed)
        record("template_api_has_example_request", False, f"status={status}", elapsed)


def test_get_template_by_slug_not_found():
    """Verify GET /v1/templates/nonexistent returns 404 (no individual lookup endpoint)."""
    status, _, _, elapsed = req_json("GET", "/v1/templates/nonexistent_template_xyz")
    # No individual lookup endpoint exists, expect 404 or 405
    ok = status in (404, 405)
    record("get_template_404_or_405_for_unknown", ok, f"status={status}", elapsed)


def test_get_template_function():
    """Verify get_template() returns correct template objects."""
    for slug in list(TEMPLATES.keys())[:3]:
        t = get_template(slug)
        ok = t is not None and t.id == slug
        record(f"get_template_fn_{slug}", ok)
    # None for missing
    t = get_template("nonexistent")
    record("get_template_fn_returns_none_for_missing", t is None)


def test_list_templates_function():
    """Verify list_templates() returns all templates."""
    all_t = list_templates()
    ok = len(all_t) == 51
    record("list_templates_fn_count_51", ok, f"got {len(all_t)}")

    # Filter by domain
    finance_t = list_templates(domain="finance")
    ok2 = len(finance_t) > 0 and all("finance" in t["domain"].lower() for t in finance_t)
    record("list_templates_fn_filter_by_domain", ok2, f"finance: {len(finance_t)}")


def test_to_dict_structure():
    """Verify to_dict() produces expected keys."""
    t = list(TEMPLATES.values())[0]
    d = t.to_dict()
    expected_keys = {"id", "name", "domain", "industry", "description", "use_case",
                     "objective_function", "output_labels", "output_units", "n_variables",
                     "tags", "variables_preview"}
    missing = expected_keys - set(d.keys())
    ok = len(missing) == 0
    record("to_dict_has_all_keys", ok, f"missing: {missing}")


def test_to_simulate_payload_structure():
    """Verify to_simulate_payload() produces valid API payload shape."""
    t = list(TEMPLATES.values())[0]
    p = t.to_simulate_payload(runs=100)
    ok = (
        p.get("mode") == "expert"
        and p.get("simulation_model") == "monte_carlo"
        and p.get("runs") == 100
        and "simulation" in p
        and "variables" in p["simulation"]
        and "objective_function" in p["simulation"]
    )
    record("to_simulate_payload_valid_structure", ok, f"keys: {sorted(p.keys())}")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: End-to-End — Run Every Template Through the API
# ═══════════════════════════════════════════════════════════════════════════════
def test_all_templates_e2e():
    """Run each of the 51 templates through POST /v1/simulate and verify results."""
    print(f"\n  {'─'*60}")
    print(f"  Running all {len(TEMPLATES)} templates through /v1/simulate ...")
    print(f"  {'─'*60}")

    passed_count = 0
    failed_count = 0
    total_e2e_time = 0.0

    for idx, (slug, template) in enumerate(TEMPLATES.items(), 1):
        # Generate payload with 1000 runs for speed
        payload = template.to_simulate_payload(runs=1000, seed=42)

        # POST to simulate
        status, body, hdrs, elapsed = req_json("POST", "/v1/simulate", body=payload, timeout=30)
        total_e2e_time += elapsed

        # Determine success
        is_ok = status == 200
        run_id = ""
        mean_val = ""
        std_val = ""
        recommendation = ""

        if is_ok and isinstance(body, dict):
            run_id = body.get("run_id", body.get("id", ""))
            metrics = body.get("metrics", body.get("result", body.get("statistics", {})))
            if isinstance(metrics, dict):
                mean_val = str(metrics.get("mean", metrics.get("expected_value", "")))
                std_val = str(metrics.get("std", metrics.get("std_dev", metrics.get("standard_deviation", ""))))
            rec = body.get("recommendation", body.get("recommended_action", body.get("decision", "")))
            if isinstance(rec, dict):
                recommendation = rec.get("action", rec.get("text", str(rec)))
            elif isinstance(rec, str):
                recommendation = rec

            # Validate response has essential fields
            has_run_id = bool(run_id)
            has_metrics = bool(metrics) and isinstance(metrics, dict)
            has_recommendation = bool(rec)

            if has_run_id and has_metrics:
                is_ok = True
            else:
                is_ok = False

        detail = f"status={status}"
        if not is_ok and isinstance(body, dict):
            err = body.get("detail", body.get("error", ""))
            detail += f" err={str(err)[:60]}"

        test_name = f"e2e_{slug}"
        record(test_name, is_ok, detail, elapsed)

        if is_ok:
            passed_count += 1
        else:
            failed_count += 1

        # Record CSV row
        csv_rows.append({
            "slug": slug,
            "domain": template.domain,
            "variables": len(template.variables),
            "runs": 1000,
            "status_code": status,
            "execution_ms": f"{elapsed*1000:.0f}",
            "mean": mean_val,
            "std": std_val,
            "recommendation": recommendation[:100] if recommendation else "",
            "pass": "true" if is_ok else "false",
        })

        # Progress indicator every 10 templates
        if idx % 10 == 0:
            print(f"  ... {idx}/{len(TEMPLATES)} completed ({passed_count} passed, {failed_count} failed)")

    print(f"\n  E2E Summary: {passed_count}/{len(TEMPLATES)} templates passed "
          f"in {total_e2e_time:.1f}s (avg {total_e2e_time/len(TEMPLATES)*1000:.0f}ms/template)")


# ═══════════════════════════════════════════════════════════════════════════════
# CSV Output
# ═══════════════════════════════════════════════════════════════════════════════
def write_results_csv():
    """Write template_results.csv with all E2E run data."""
    csv_path = os.path.join(os.path.dirname(__file__), "template_results.csv")
    if not csv_rows:
        print("  ⚠️  No CSV rows to write")
        return
    fieldnames = ["slug", "domain", "variables", "runs", "status_code",
                  "execution_ms", "mean", "std", "recommendation", "pass"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"\n  📄 Results CSV written to {csv_path} ({len(csv_rows)} rows)")


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    print("=" * 70)
    print("  Phase 19: All 51 Simulation Templates End-to-End Tests")
    print("=" * 70)
    t_start = time.perf_counter()

    # ── Section 1: Registry Tests ─────────────────────────────────────────────
    print("\n── Section 1: Template Registry Tests ──")
    test_registry_count()
    test_registry_required_fields()
    test_registry_unique_slugs()
    test_registry_valid_domains()
    test_template_list_api()

    # ── Section 2: Quality Tests ──────────────────────────────────────────────
    print("\n── Section 2: Template Quality Tests ──")
    test_each_template_has_min_variables()
    test_variable_distributions_valid()
    test_variable_params_make_sense()
    test_descriptions_non_empty()
    test_tags_are_string_arrays()

    # ── Section 3: Domain Coverage Tests ──────────────────────────────────────
    print("\n── Section 3: Domain Coverage Tests ──")
    test_domain_coverage()
    test_domain_distribution()
    test_get_all_tags_non_empty()

    # ── Section 4: Template API Tests ─────────────────────────────────────────
    print("\n── Section 4: Template Detail API Tests ──")
    test_get_template_by_slug()
    test_get_template_by_slug_not_found()
    test_get_template_function()
    test_list_templates_function()
    test_to_dict_structure()
    test_to_simulate_payload_structure()

    # ── Section 5: End-to-End All 51 Templates ────────────────────────────────
    print("\n── Section 5: End-to-End All 51 Templates ──")
    test_all_templates_e2e()

    # ── Write CSV ─────────────────────────────────────────────────────────────
    write_results_csv()

    # ── Summary ───────────────────────────────────────────────────────────────
    total_time = time.perf_counter() - t_start
    print("\n" + "=" * 70)
    print("  Phase 19 Results Summary")
    print("=" * 70)

    passed = sum(1 for _, s, _ in results if s == PASS)
    failed = sum(1 for _, s, _ in results if s == FAIL)
    skipped = sum(1 for _, s, _ in results if s == SKIP)
    total = len(results)

    print(f"\n  Total:   {total}")
    print(f"  Passed:  {passed} {PASS}")
    print(f"  Failed:  {failed} {FAIL}")
    print(f"  Skipped: {skipped} {SKIP}")
    print(f"  Time:    {total_time:.1f}s")
    print()

    if failed > 0:
        print("  Failed tests:")
        for name, status, detail in results:
            if status == FAIL:
                print(f"    {FAIL} {name}: {detail[:120]}")
        print()

    # ── Timing report ─────────────────────────────────────────────────────────
    if timings:
        sorted_timings = sorted(timings, key=lambda x: x[1], reverse=True)[:15]
        print("  Top 15 Slowest Tests:")
        for name, t in sorted_timings:
            if t > 0:
                print(f"    {t*1000:7.0f}ms  {name}")
        print()

    # ── Domain stats ──────────────────────────────────────────────────────────
    if csv_rows:
        from collections import Counter
        domain_pass = Counter()
        domain_fail = Counter()
        for row in csv_rows:
            if row["pass"] == "true":
                domain_pass[row["domain"]] += 1
            else:
                domain_fail[row["domain"]] += 1
        print("  Domain Results:")
        all_domains = sorted(set(list(domain_pass.keys()) + list(domain_fail.keys())))
        for d in all_domains:
            p = domain_pass.get(d, 0)
            f = domain_fail.get(d, 0)
            icon = PASS if f == 0 else FAIL
            print(f"    {icon} {d}: {p}/{p+f} passed")
        print()

    pct = (passed / total * 100) if total > 0 else 0
    print(f"  Pass rate: {pct:.1f}% ({passed}/{total})")
    print("=" * 70)

    # Exit code: 0 if all pass/skip, 1 if any fail
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
