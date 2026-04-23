"""
Live TypeScript runtime integration tests against a real API server.

Prerequisites:
  1. API server running and reachable via DE_BASE_URL
  2. Valid API key in DE_API_KEY
  3. TypeScript SDK dependencies installed

Run:
  DE_API_KEY="..." DE_BASE_URL="http://127.0.0.1:8000" \
    python3 tests/integration/test_typescript_runtime_live.py
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TS_SDK_DIR = ROOT / "packages" / "ts-sdk"
TS_DIST_ENTRY_CANDIDATES = (
    TS_SDK_DIR / "dist" / "index.mjs",
    TS_SDK_DIR / "dist" / "index.js",
)

BASE_URL = os.environ.get("DE_BASE_URL", "http://127.0.0.1:8000")
API_KEY = os.environ.get("DE_API_KEY", "")
TEST_FILES = ROOT / "test_files"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ruff: noqa: E402
from tests.integration.runtime_live_db_helpers import (
    postgres_canonical_connector,
    temporary_postgres_fixture,
)

REAL_MARCH_ORDERS = (
    TEST_FILES / "850a28da-a6f7-4ecc-9e7a-51a9cf7f501b-united_states.csv"
)
REAL_MARCH_FINANCIAL = (
    TEST_FILES / "aaeff3ab-19ac-494e-9e58-e507bd7e3893-united_states.csv"
)
REAL_MARCH_INACCURATE = (
    TEST_FILES / "630a0f6c-a250-4bd7-af2e-bed6184619ac_top_inaccurate_items_v3_2026-03-01_2026-03-31.csv"
)

PUBLIC_S3_CONNECTION = {
    "type": "s3",
    "bucket": "noaa-global-hourly-pds",
    "key": "1901/02907099999.csv",
    "region": "us-east-1",
    "anonymous": True,
    "format": "csv",
}
PUBLIC_REST_CONNECTION = {
    "type": "rest",
    "base_url": "https://api.weather.gov",
    "path": "/stations",
    "method": "GET",
    "headers": {
        "User-Agent": "algenta-ts-runtime-live/1.0",
        "Accept": "application/geo+json",
    },
    "params": {"state": "CO"},
    "data_path": "features",
    "timeout": 60,
}

PASS = "✅"
FAIL = "❌"
results: list[tuple[str, str, str]] = []


def check(name: str, fn) -> Any:
    try:
        out = fn()
        results.append((PASS, name, ""))
        print(f"  {PASS} {name}")
        return out
    except AssertionError as exc:
        results.append((FAIL, name, str(exc)))
        print(f"  {FAIL} {name}: {exc}")
        return None
    except Exception as exc:  # noqa: BLE001
        results.append((FAIL, name, f"{type(exc).__name__}: {exc}"))
        print(f"  {FAIL} {name}: {type(exc).__name__}: {exc}")
        return None


def build_ts_sdk() -> None:
    proc = subprocess.run(
        _ts_build_command(),
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "TypeScript SDK build failed.\n"
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )
    if _resolve_ts_dist_entry() is None:
        candidates = ", ".join(str(path) for path in TS_DIST_ENTRY_CANDIDATES)
        raise AssertionError(f"Built TypeScript runtime entry missing. Checked: {candidates}")


def _pnpm_command() -> list[str]:
    if shutil.which("pnpm"):
        return ["pnpm"]
    if shutil.which("corepack"):
        return ["corepack", "pnpm"]
    if shutil.which("npx"):
        return ["npx", "pnpm"]
    raise FileNotFoundError(
        "Unable to find pnpm-compatible package manager. Install pnpm or ensure corepack is available."
    )


def _ts_build_command() -> list[str]:
    tsconfig_path = TS_SDK_DIR / "tsconfig.json"
    try:
        pnpm_cmd = _pnpm_command()
    except FileNotFoundError:
        local_tsc = TS_SDK_DIR / "node_modules" / ".bin" / "tsc"
        if local_tsc.exists():
            return [str(local_tsc), "-p", str(tsconfig_path)]
        node_binary = shutil.which("node")
        bundled_tsc = (
            TS_SDK_DIR / "node_modules" / "typescript" / "bin" / "tsc"
        )
        if node_binary and bundled_tsc.exists():
            return [node_binary, str(bundled_tsc), "-p", str(tsconfig_path)]
        raise
    return [*pnpm_cmd, "--dir", str(TS_SDK_DIR), "build"]


def _resolve_ts_dist_entry() -> Path | None:
    for candidate in TS_DIST_ENTRY_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def write_sqlite_fixture(path: Path) -> None:
    rows = [
        {"product_line": "Electronics", "revenue": 42193221.0, "region": "US"},
        {"product_line": "Apparel", "revenue": 28114992.0, "region": "US"},
        {"product_line": "Electronics", "revenue": 1204000.0, "region": "CA"},
    ]
    connection = sqlite3.connect(path)
    try:
        connection.execute('DROP TABLE IF EXISTS "orders"')
        connection.execute(
            'CREATE TABLE "orders" ("product_line" TEXT, "revenue" REAL, "region" TEXT)'
        )
        connection.executemany(
            'INSERT INTO "orders" ("product_line", "revenue", "region") VALUES (?, ?, ?)',
            [(row["product_line"], row["revenue"], row["region"]) for row in rows],
        )
        connection.commit()
    finally:
        connection.close()


def postgres_fixture_rows() -> list[dict[str, object]]:
    return [
        {"product_line": "Electronics", "revenue": 42193221.0, "region": "US"},
        {"product_line": "Apparel", "revenue": 28114992.0, "region": "US"},
        {"product_line": "Electronics", "revenue": 1204000.0, "region": "CA"},
    ]


def _node_probe(
    sqlite_path: Path,
    postgres_connector: dict[str, Any],
) -> dict[str, Any]:
    if not API_KEY:
        raise RuntimeError("DE_API_KEY is required for live TypeScript runtime integration.")
    dist_entry = _resolve_ts_dist_entry()
    if dist_entry is None:
        candidates = ", ".join(str(path) for path in TS_DIST_ENTRY_CANDIDATES)
        raise RuntimeError(f"TypeScript SDK dist entry missing. Checked: {candidates}")
    script = f"""
import {{ Runtime }} from {json.dumps(dist_entry.resolve().as_uri())};

const runtime = new Runtime({{
  mode: "api",
  apiKey: process.env.DE_API_KEY,
  baseUrl: process.env.DE_BASE_URL,
}});

const publicRest = {json.dumps(PUBLIC_REST_CONNECTION)};
const publicS3 = {json.dumps(PUBLIC_S3_CONNECTION)};
const sqliteDescriptor = {{
  type: "sqlite",
  path: {json.dumps(str(sqlite_path.resolve()))},
  table: "orders",
}};
const postgresDescriptor = {json.dumps(postgres_connector)};
const localOrdersCsv = {json.dumps(str(REAL_MARCH_ORDERS.resolve()))};
const localFinancialCsv = {json.dumps(str(REAL_MARCH_FINANCIAL.resolve()))};
const localInaccurateCsv = {json.dumps(str(REAL_MARCH_INACCURATE.resolve()))};

async function datasetSchema(registration) {{
  const datasetId = registration.dataset_id ?? registration.source_id;
  if (!datasetId) {{
    throw new Error(`No dataset id available for ${{registration?.name ?? "unknown"}}`);
  }}
  const response = await fetch(`${{process.env.DE_BASE_URL}}/v1/data/${{datasetId}}`, {{
    headers: {{
      "X-API-Key": String(process.env.DE_API_KEY ?? ""),
    }},
  }});
  if (!response.ok) {{
    throw new Error(`Schema fetch failed for ${{registration?.name ?? "unknown"}}: ${{response.status}}`);
  }}
  return await response.json();
}}

async function step(name, fn) {{
  try {{
    return await fn();
  }} catch (error) {{
    const code = error && typeof error === "object" && "code" in error ? String(error.code) : "";
    const details = error && typeof error === "object" && "details" in error
      ? JSON.stringify(error.details)
      : "";
    const message = error instanceof Error ? error.message : String(error);
    const suffix = details ? ` :: ${{details}}` : "";
    throw new Error(`${{name}} failed${{code ? ` [${{code}}]` : ""}}: ${{message}}${{suffix}}`);
  }}
}}

async function metricField(registration) {{
  const schema = registration?.source_schema ?? registration?.schema ?? await datasetSchema(registration);
  if (schema && typeof schema === "object" && "source_schema" in schema) {{
    const nested = schema.source_schema;
    if (nested && typeof nested === "object") {{
      return metricField({{ ...registration, source_schema: nested }});
    }}
  }}
  const rawSchema = schema && typeof schema === "object" ? schema : {{}};
  const fields = Array.isArray(rawSchema.fields)
    ? rawSchema.fields
    : Array.isArray(rawSchema.columns)
      ? rawSchema.columns.map((column) => column?.name).filter((name) => typeof name === "string" && name.length > 0)
      : [];
  if (fields.length > 0) {{
    return String(fields[0]);
  }}
  throw new Error(`No metric field available for ${{registration?.name ?? "unknown"}}`);
}}

async function countQuery(registration) {{
  const plan = await runtime.resolve({{
    source_name: registration.name,
    metric: await metricField(registration),
    aggregation: "count",
  }});
  const verified = await runtime.verify(plan);
  const result = await runtime.query(plan);
  const scalar = typeof result.result === "number"
    ? result.result
    : Number(result.result?.value);
  return {{
    planHash: plan.plan_hash ?? plan.resolved_plan?.plan_hash ?? null,
    schemaRevision: plan.schema_revision ?? plan.resolved_plan?.schema_revision ?? null,
    valid: verified.valid,
    rowCount: registration.row_count,
    scalar,
  }};
}}

async function countQueryWithMetric(runtimeInstance, registration, metric) {{
  const plan = await runtimeInstance.resolve({{
    source_name: registration.name,
    metric,
    aggregation: "count",
  }});
  const verified = await runtimeInstance.verify(plan);
  const result = await runtimeInstance.query(plan);
  const scalar = typeof result.result === "number"
    ? result.result
    : Number(result.result?.value);
  return {{
    planHash: plan.plan_hash ?? plan.resolved_plan?.plan_hash ?? null,
    schemaRevision: plan.schema_revision ?? plan.resolved_plan?.schema_revision ?? null,
    valid: verified.valid,
    rowCount: registration.row_count,
    scalar,
  }};
}}

try {{
  const localRuntime = new Runtime();
  const localImported = await step(
    "Local CSV import preview",
    () =>
      localRuntime.importPreview(localOrdersCsv, {{
        name: "orders_detail",
        sourceRef: "850a28da-a6f7-4ecc-9e7a-51a9cf7f501b-united_states.csv",
        color: false,
      }}),
  );
  const localCount = await step(
    "Local CSV count query",
    () => countQueryWithMetric(localRuntime, localImported.registration, "Sales (incl. tax)"),
  );
  const localBundle = await step(
    "Local CSV bundle preview",
    () =>
      localRuntime.importBundlePreview(
        [localOrdersCsv, localFinancialCsv, localInaccurateCsv],
        {{
          names: ["orders_detail_bundle", "orders_financial_bundle", "top_inaccurate_items_bundle"],
          sourceRefs: [
            "850a28da-a6f7-4ecc-9e7a-51a9cf7f501b-united_states.csv",
            "aaeff3ab-19ac-494e-9e58-e507bd7e3893-united_states.csv",
            "630a0f6c-a250-4bd7-af2e-bed6184619ac_top_inaccurate_items_v3_2026-03-01_2026-03-31.csv",
          ],
          color: false,
        }},
      ),
  );

  const restRegistration = await step("REST connect", () => runtime.connect(publicRest, {{ name: "weather_stations" }}));
  const rest = await step("REST count query", () => countQuery(restRegistration));

  const imported = await step(
    "S3 import preview",
    () =>
      runtime.importPreview(publicS3, {{
        name: "noaa_hourly",
        sourceRef: "s3://noaa-global-hourly-pds/1901/02907099999.csv",
        color: false,
      }}),
  );
  const s3 = await step("S3 count query", () => countQuery(imported.registration));

  const sqliteRegistration = await step(
    "SQLite connect",
    () => runtime.connect(sqliteDescriptor, {{ name: "orders_sqlite" }}),
  );
  const sqlite = await step("SQLite count query", () => countQuery(sqliteRegistration));

  const postgresRegistration = await step(
    "Postgres connect",
    () => runtime.connect(postgresDescriptor, {{ name: "orders_postgres" }}),
  );
  const postgres = await step("Postgres count query", () => countQuery(postgresRegistration));

  const apiBundle = await step(
    "API bundle preview",
    () =>
      runtime.importBundlePreview(
        [sqliteDescriptor, postgresDescriptor, publicS3, publicRest],
        {{
          names: ["orders_sqlite_bundle", "orders_postgres_bundle", "noaa_hourly_bundle", "weather_stations_bundle"],
          sourceRefs: [
            {json.dumps(f"{sqlite_path.name}#orders")},
            {json.dumps(f"postgres://{postgres_connector['location']['schema']}.{postgres_connector['location']['table']}")},
            "s3://noaa-global-hourly-pds/1901/02907099999.csv",
            "https://api.weather.gov/stations?state=CO",
          ],
          color: false,
        }},
      ),
  );

  process.stdout.write(JSON.stringify({{
    local: {{
      registration: localImported.registration,
      preview: localImported.preview,
      count: localCount,
    }},
    localBundle: {{
      preview: localBundle.preview,
      registrationCount: localBundle.registrations.length,
      failureCount: localBundle.failures.length,
    }},
    rest,
    s3: {{
      ...s3,
      preview: imported.preview,
    }},
    sqlite,
    postgres,
    apiBundle: {{
      preview: apiBundle.preview,
      registrationCount: apiBundle.registrations.length,
      failureCount: apiBundle.failures.length,
    }},
  }}));
}} catch (error) {{
  const message = error instanceof Error ? `${{error.name}}: ${{error.message}}` : String(error);
  process.stderr.write(message);
  process.exit(1);
}}
"""
    proc = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=str(ROOT),
        env={
            **os.environ,
            "DE_BASE_URL": BASE_URL,
            "DE_API_KEY": API_KEY,
        },
        capture_output=True,
        text=True,
        timeout=240,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "TypeScript runtime probe failed.\n"
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # noqa: PERF203
        raise RuntimeError(f"Failed to parse TypeScript runtime output: {proc.stdout}") from exc
    if not isinstance(payload, dict):
        raise AssertionError(f"Expected dict payload, received {type(payload)!r}")
    return payload


def run_typescript_runtime_connector_matrix() -> None:
    with tempfile.TemporaryDirectory(prefix="algenta-ts-runtime-live-") as tmp_dir:
        sqlite_path = Path(tmp_dir) / "orders.db"
        write_sqlite_fixture(sqlite_path)
        with temporary_postgres_fixture(postgres_fixture_rows(), table="orders") as postgres_descriptor:
            payload = _node_probe(
                sqlite_path,
                postgres_canonical_connector(postgres_descriptor),
            )

    local = payload.get("local")
    local_bundle = payload.get("localBundle")
    rest = payload.get("rest")
    s3 = payload.get("s3")
    sqlite = payload.get("sqlite")
    postgres = payload.get("postgres")
    api_bundle = payload.get("apiBundle")
    assert isinstance(local, dict), "Missing local runtime result block"
    assert isinstance(local_bundle, dict), "Missing local bundle result block"
    assert isinstance(rest, dict), "Missing REST result block"
    assert isinstance(s3, dict), "Missing S3 result block"
    assert isinstance(sqlite, dict), "Missing SQLite result block"
    assert isinstance(postgres, dict), "Missing Postgres result block"
    assert isinstance(api_bundle, dict), "Missing API bundle result block"

    local_registration = local.get("registration")
    local_count = local.get("count")
    assert isinstance(local_registration, dict), "Missing local registration payload"
    assert isinstance(local_count, dict), "Missing local count payload"
    assert local_registration["status"] == "ready"
    assert local_registration["row_count"] > 0
    assert local_count["valid"] is True
    assert float(local_count["scalar"]) == float(local_registration["row_count"])
    assert "Algenta Source Import" in str(local["preview"])
    assert REAL_MARCH_ORDERS.stem in str(local["preview"])

    assert local_bundle["registrationCount"] == 3
    assert local_bundle["failureCount"] == 0
    assert "Algenta Source Bundle" in str(local_bundle["preview"])
    assert "orders_detail_bundle" in str(local_bundle["preview"])
    assert "orders_financial_bundle" in str(local_bundle["preview"])
    assert "top_inaccurate_items_bundle" in str(local_bundle["preview"])

    assert rest["valid"] is True
    assert rest["rowCount"] > 0
    assert float(rest["scalar"]) == float(rest["rowCount"])

    assert s3["valid"] is True
    assert s3["rowCount"] > 0
    assert float(s3["scalar"]) == float(s3["rowCount"])
    assert "Algenta Source Import" in str(s3["preview"])
    assert "s3://noaa-global-hourly-pds/1901/02907099999.csv" in str(s3["preview"])

    assert sqlite["valid"] is True
    assert sqlite["rowCount"] == 3
    assert float(sqlite["scalar"]) == 3.0

    assert postgres["valid"] is True
    assert postgres["rowCount"] == 3
    assert float(postgres["scalar"]) == 3.0

    assert api_bundle["registrationCount"] == 4
    assert api_bundle["failureCount"] == 0
    assert "Algenta Source Bundle" in str(api_bundle["preview"])
    assert "orders_sqlite_bundle" in str(api_bundle["preview"])
    assert "orders_postgres_bundle" in str(api_bundle["preview"])
    assert "noaa_hourly_bundle" in str(api_bundle["preview"])
    assert "weather_stations_bundle" in str(api_bundle["preview"])


def main() -> int:
    print("\n" + "=" * 70)
    print("  LIVE TYPESCRIPT RUNTIME INTEGRATION")
    print("=" * 70)

    check("Build TypeScript SDK", build_ts_sdk)
    check("TypeScript Runtime connector matrix", run_typescript_runtime_connector_matrix)

    failed = [result for result in results if result[0] == FAIL]
    print("\n" + "=" * 70)
    print(f"Passed: {len(results) - len(failed)}")
    print(f"Failed: {len(failed)}")
    if failed:
        print("Failures:")
        for _, name, message in failed:
            print(f"  - {name}: {message}")
    print("=" * 70)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
