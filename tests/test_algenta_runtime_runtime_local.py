"""Tests for test_algenta_runtime: runtime_local.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-3/tests/test_algenta_runtime.py during modularization.
"""
from __future__ import annotations

from tests._test_algenta_runtime_helpers import *  # noqa: F401,F403


def test_runtime_local_resolve_query_happy_path() -> None:
    runtime = Runtime()
    registration = runtime.connect(_sample_rows(), name="orders")

    plan = runtime.resolve(
        {"source_name": "orders", "metric": "revenue", "group_by": "product_line"}
    )
    result = runtime.query(plan)

    assert registration.status == "ready"
    assert isinstance(plan, ResolveOutput)
    assert plan.resolved_plan is not None
    assert plan.resolved_plan.metric_column == "revenue"
    assert plan.resolved_plan.group_column == "product_line"
    assert isinstance(result, QueryOutput)
    assert result.result_type == "table"
    assert result.result[0]["product_line"] == "Electronics"
    assert result.result[0]["revenue"] == 43397221.0


def test_runtime_local_verify_happy_path() -> None:
    runtime = Runtime()
    runtime.connect(_sample_rows(), name="orders")
    plan = runtime.resolve(
        {"source_name": "orders", "metric": "revenue", "group_by": "product_line"}
    )

    verification = runtime.verify(plan)

    assert verification.valid is True
    assert verification.verified is True
    assert verification.resolved["metric_column"] == "revenue"


def test_runtime_local_query_with_metadata_derives_stable_metadata() -> None:
    runtime = Runtime()
    runtime.connect(_sample_rows(), name="orders")
    plan = runtime.resolve(
        {"source_name": "orders", "metric": "revenue", "group_by": "product_line"}
    )

    result = runtime.query_with_metadata(plan)

    assert isinstance(result, QueryWithMetadataOutput)
    assert isinstance(result.data, QueryOutput)
    assert result.data.result_type == "table"
    assert result.metadata.latency_ms == result.data.latency_ms
    assert result.headers == {}


def test_runtime_local_import_preview_and_query_real_csv_file() -> None:
    runtime = Runtime()

    imported = runtime.import_preview(
        REAL_MARCH_ORDERS,
        name="orders_detail",
        source_ref=REAL_MARCH_ORDERS.name,
    )
    plan = runtime.resolve(
        {
            "source_name": "orders_detail",
            "metric": "Sales (incl. tax)",
            "group_by": "Order Channel",
        }
    )
    result = runtime.query(plan)

    assert imported.registration.row_count == 6097
    assert imported.registration.name == "orders_detail"
    assert "Algenta Source Import" in imported.preview
    assert "850a28da-a6f7-4ecc-9e7a-51a9cf7f501b-united_states" in imported.preview
    assert plan.resolved_plan is not None
    assert plan.resolved_plan.metric_column == "Sales (incl. tax)"
    assert plan.resolved_plan.group_column == "Order Channel"
    assert result.result_type == "table"
    assert result.row_count > 0


def test_runtime_local_connect_real_csv_skips_alias_header_row() -> None:
    runtime = Runtime()

    registration = runtime.connect(REAL_MARCH_FINANCIAL, name="orders_financial")

    assert registration.row_count == 2026


def test_runtime_local_connect_rejects_real_empty_export() -> None:
    runtime = Runtime()

    with pytest.raises(RuntimeValidationError, match="empty"):
        runtime.connect(REAL_MARCH_EMPTY, name="store_pause")


def test_runtime_local_connect_sqlite_descriptor_happy_path(tmp_path: Path) -> None:
    db_path = tmp_path / "orders.db"
    _write_sqlite_fixture(db_path, _sample_rows())

    runtime = Runtime()
    registration = runtime.connect(
        {
            "provider": "sqlite",
            "path": str(db_path),
            "table": "orders",
        }
    )
    plan = runtime.resolve(
        {"source_name": registration.name, "metric": "revenue", "group_by": "product_line"}
    )
    result = runtime.query(plan)

    assert registration.status == "ready"
    assert registration.row_count == 3
    assert registration.name == "orders_orders"
    assert result.result[0]["product_line"] == "Electronics"
    assert result.result[0]["revenue"] == 43397221.0


def test_runtime_local_connect_sqlite_descriptor_supports_connection_string_and_query(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "orders.db"
    _write_sqlite_fixture(db_path, _sample_rows())

    runtime = Runtime()
    registration = runtime.connect(
        {
            "type": "sqlite",
            "connection_string": f"sqlite+pysqlite:///{db_path}",
            "query": "SELECT product_line, revenue FROM orders WHERE region = 'US'",
        },
    )

    assert registration.status == "ready"
    assert registration.row_count == 2
    assert registration.name == "orders_query"


def test_runtime_local_connect_parquet_file_happy_path(tmp_path: Path) -> None:
    parquet_path = tmp_path / "orders.parquet"
    _write_parquet_fixture(parquet_path, _sample_rows())

    runtime = Runtime()
    registration = runtime.connect(parquet_path, name="orders_parquet")
    plan = runtime.resolve(
        {"source_name": registration.name, "metric": "revenue", "group_by": "product_line"}
    )
    result = runtime.query(plan)

    assert registration.status == "ready"
    assert registration.row_count == 3
    assert registration.name == "orders_parquet"
    assert result.result[0]["product_line"] == "Electronics"
    assert result.result[0]["revenue"] == 43397221.0


def test_runtime_local_connect_excel_file_happy_path(tmp_path: Path) -> None:
    workbook_path = tmp_path / "orders.xlsx"
    _write_excel_fixture(workbook_path, _sample_rows())

    runtime = Runtime()
    registration = runtime.connect(workbook_path, name="orders_excel")
    plan = runtime.resolve(
        {"source_name": registration.name, "metric": "revenue", "group_by": "product_line"}
    )
    result = runtime.query(plan)

    assert registration.status == "ready"
    assert registration.row_count == 3
    assert registration.name == "orders_excel"
    assert result.result[0]["product_line"] == "Electronics"
    assert result.result[0]["revenue"] == 43397221.0


def test_runtime_local_import_preview_uses_descriptor_origin_for_sqlite_sources(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "orders.db"
    _write_sqlite_fixture(db_path, _sample_rows())
    runtime = Runtime()

    imported = runtime.import_preview(
        {
            "provider": "sqlite",
            "path": str(db_path),
            "table": "orders",
        },
    )

    assert imported.registration.name == "orders_orders"
    assert imported.preview.startswith(" █████╗")
    assert f"{db_path.name}#orders" in imported.preview


def test_runtime_local_connect_sqlite_descriptor_requires_table_or_query(tmp_path: Path) -> None:
    db_path = tmp_path / "orders.db"
    _write_sqlite_fixture(db_path, _sample_rows())
    runtime = Runtime()

    with pytest.raises(RuntimeValidationError, match="table or query"):
        runtime.connect({"provider": "sqlite", "path": str(db_path)})


def test_runtime_local_import_bundle_preview_reports_successes_and_failures_for_real_march_corpus() -> (
    None
):
    runtime = Runtime()

    bundle = runtime.import_bundle_preview(
        [
            REAL_MARCH_ORDERS,
            REAL_MARCH_FINANCIAL,
            REAL_MARCH_INACCURATE,
            REAL_MARCH_RATINGS,
            REAL_MARCH_EMPTY,
        ],
        source_refs=[
            REAL_MARCH_ORDERS.name,
            REAL_MARCH_FINANCIAL.name,
            REAL_MARCH_INACCURATE.name,
            REAL_MARCH_RATINGS.name,
            REAL_MARCH_EMPTY.name,
        ],
    )

    assert len(bundle.registrations) == 4
    assert len(bundle.failures) == 1
    assert bundle.failures[0].code == "empty_source"
    assert bundle.failures[0].source_ref == REAL_MARCH_EMPTY.name
    assert "Algenta Source Bundle" in bundle.preview
    assert "Imported: 4 | Failures: 1" in bundle.preview
    assert "orders_financial" in bundle.preview or REAL_MARCH_FINANCIAL.stem in bundle.preview
    assert "Shared fields:" in bundle.preview


def test_runtime_local_import_bundle_preview_supports_mixed_csv_and_sqlite_sources(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "orders.db"
    _write_sqlite_fixture(db_path, _sample_rows())
    runtime = Runtime()

    bundle = runtime.import_bundle_preview(
        [
            REAL_MARCH_ORDERS,
            {
                "provider": "sqlite",
                "path": str(db_path),
                "table": "orders",
            },
            REAL_MARCH_EMPTY,
        ],
        source_refs=[
            REAL_MARCH_ORDERS.name,
            "orders.db#orders",
            REAL_MARCH_EMPTY.name,
        ],
    )

    assert len(bundle.registrations) == 2
    assert len(bundle.failures) == 1
    assert bundle.registrations[0].name == "united_states"
    assert bundle.registrations[1].name == "orders_orders"
    assert bundle.failures[0].code == "empty_source"
    assert "Imported: 2 | Failures: 1" in bundle.preview
    assert "orders_orders" in bundle.preview


def test_runtime_local_hosted_limits_work_offline_with_stored_license(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("ALGENTA_RUNTIME_DEV_MODE", raising=False)
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "jwt-signing-seed")
    # plan="developer" is Codna-style, the one product still verifying HS256 by design.
    monkeypatch.setenv("ALGENTA_RUNTIME_PRODUCT", "codna")
    get_settings.cache_clear()

    license_mod = _reload_runtime_license_module()
    credits_mod = _reload_runtime_credits_module()
    token = _issue_license_jwt(
        device_id="device-runtime-offline-123",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_runtime_test",
    )
    license_mod._save_license(token)
    credits_mod.get_store().initialize_sync(credits_granted=2, billing_period="2026-04")

    runtime = Runtime(api_key="de_live_test_key")
    runtime.connect(REAL_MARCH_ORDERS, name="orders_detail")
    plan = runtime.resolve(
        {
            "source_name": "orders_detail",
            "metric": "Sales (incl. tax)",
            "group_by": "Order Channel",
        }
    )

    with patch.object(
        license_mod,
        "_exchange_api_key_for_license",
        side_effect=AssertionError("stored offline license must not hit control plane"),
    ):
        first = runtime.query(plan)
        second = runtime.query(plan)
        with pytest.raises(RuntimeValidationError, match="quota"):
            runtime.query(plan)

    state = credits_mod.get_store()._read()
    assert first.row_count > 0
    assert second.row_count > 0
    assert state is not None
    assert state.credits_remaining == 0
    get_settings.cache_clear()


def test_runtime_local_hosted_limits_allow_key_bound_offline_execution_without_credit_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("ALGENTA_RUNTIME_DEV_MODE", raising=False)
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "jwt-signing-seed")
    # plan="developer" is Codna-style, the one product still verifying HS256 by design.
    monkeypatch.setenv("ALGENTA_RUNTIME_PRODUCT", "codna")
    get_settings.cache_clear()

    license_mod = _reload_runtime_license_module()
    _reload_runtime_credits_module()
    future_expiry = datetime.now(UTC).timestamp() + 86_400
    token = _issue_license_jwt(
        device_id="device-runtime-keybound-123",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_runtime_test",
        api_key_expires_at=datetime.fromtimestamp(future_expiry, UTC),
    )
    license_mod._save_license(token)

    runtime = Runtime(api_key="de_live_test_key")
    runtime.connect(REAL_MARCH_ORDERS, name="orders_detail")
    plan = runtime.resolve(
        {
            "source_name": "orders_detail",
            "metric": "Sales (incl. tax)",
            "group_by": "Order Channel",
        }
    )

    with patch.object(
        license_mod,
        "_exchange_api_key_for_license",
        side_effect=AssertionError("stored offline license must not hit control plane"),
    ):
        first = runtime.query(plan)
        second = runtime.query(plan)

    assert first.row_count > 0
    assert second.row_count > 0
    assert (tmp_path / "credits.json").exists() is False
    get_settings.cache_clear()


def test_runtime_local_hosted_limits_block_first_time_offline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("ALGENTA_RUNTIME_DEV_MODE", raising=False)
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "jwt-signing-seed")
    get_settings.cache_clear()

    license_mod = _reload_runtime_license_module()
    _reload_runtime_credits_module()

    runtime = Runtime(api_key="de_live_test_key")
    runtime.connect(REAL_MARCH_ORDERS, name="orders_detail")
    plan = runtime.resolve(
        {
            "source_name": "orders_detail",
            "metric": "Sales (incl. tax)",
            "group_by": "Order Channel",
        }
    )

    with patch.object(license_mod, "_exchange_api_key_for_license", return_value=None):
        with pytest.raises(RuntimeConfigurationError, match="control plane"):
            runtime.query(plan)
    get_settings.cache_clear()


def test_runtime_local_hosted_limits_recheck_offline_license_with_monotonic_time(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("ALGENTA_RUNTIME_DEV_MODE", raising=False)
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "jwt-signing-seed")
    # plan="developer" is Codna-style, the one product still verifying HS256 by design.
    monkeypatch.setenv("ALGENTA_RUNTIME_PRODUCT", "codna")
    get_settings.cache_clear()

    license_mod = _reload_runtime_license_module()
    credits_mod = _reload_runtime_credits_module()
    trusted_time_mod = _reload_runtime_trusted_time_module()

    issued_at = 1_950_000_000
    wall_now = float(issued_at)
    monotonic_now = 10.0
    monkeypatch.setattr(trusted_time_mod.time, "time", lambda: wall_now)
    monkeypatch.setattr(trusted_time_mod.time, "monotonic", lambda: monotonic_now)

    token = _issue_license_jwt(
        device_id="device-runtime-monotonic-123",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_runtime_test",
        api_key_expires_at=datetime.fromtimestamp(issued_at + 1, UTC),
    )
    license_mod._save_license(token)
    trusted_time_mod.observe_time(float(issued_at), source="control-plane-register")
    credits_mod.get_store().initialize_sync(credits_granted=2, billing_period="2026-04")

    runtime = Runtime(api_key="de_live_test_key")
    runtime.connect(REAL_MARCH_ORDERS, name="orders_detail")
    plan = runtime.resolve(
        {
            "source_name": "orders_detail",
            "metric": "Sales (incl. tax)",
            "group_by": "Order Channel",
        }
    )

    with patch.object(
        license_mod,
        "_exchange_api_key_for_license",
        side_effect=AssertionError("stored offline license must not hit control plane"),
    ), patch.object(license_mod, "renew_license", lambda *a, **k: None):  # renewal unreachable offline
        first = runtime.query(plan)
        assert first.row_count > 0
        # NEW model: past hard-expiry with no reachable renewal, the offline license DOWNGRADES to
        # Community (free-forever) rather than hard-blocking. Verify at the license layer — the engine
        # keeps a valid license and serves at Community limits; paid caps/features resume on renewal.
        # A previously valid Enterprise air-gapped term follows the same Community fallback.
        monotonic_now = 10.0 + (14 * 86_400) + 5.0
        downgraded = license_mod.load_license("de_live_test_key")

    assert downgraded.valid is True
    assert downgraded.plan == "algenta_free"
    assert downgraded.source == "community-fallback"
    get_settings.cache_clear()


def test_runtime_local_without_enforced_limits_skips_runtime_license_path() -> None:
    runtime = Runtime()
    runtime.connect(REAL_MARCH_ORDERS, name="orders_detail")
    plan = runtime.resolve(
        {
            "source_name": "orders_detail",
            "metric": "Sales (incl. tax)",
            "group_by": "Order Channel",
        }
    )

    with patch(
        "apps.runtime.license.load_license",
        side_effect=AssertionError("plain local runtime must not load hosted license"),
    ):
        result = runtime.query(plan)

    assert result.row_count > 0


def test_runtime_local_self_hosted_private_profile_skips_hosted_license_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")

    runtime = Runtime(api_key="de_live_private_key")
    runtime.connect(REAL_MARCH_ORDERS, name="orders_detail")
    plan = runtime.resolve(
        {
            "source_name": "orders_detail",
            "metric": "Sales (incl. tax)",
            "group_by": "Order Channel",
        }
    )

    with patch(
        "apps.runtime.license.load_license",
        side_effect=AssertionError("self_hosted private runtime must not hit hosted license flow"),
    ):
        result = runtime.query(plan)

    assert result.row_count > 0


def test_runtime_local_air_gapped_profile_requires_local_license(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "air_gapped")
    monkeypatch.delenv("ALGENTA_RUNTIME_DEV_MODE", raising=False)

    runtime = Runtime()
    runtime.connect(REAL_MARCH_ORDERS, name="orders_detail")
    plan = runtime.resolve(
        {
            "source_name": "orders_detail",
            "metric": "Sales (incl. tax)",
            "group_by": "Order Channel",
        }
    )

    with pytest.raises(RuntimeConfigurationError, match="local signed license"):
        runtime.query(plan)


def test_runtime_local_air_gapped_profile_accepts_offline_local_license(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "air_gapped")
    monkeypatch.delenv("ALGENTA_RUNTIME_DEV_MODE", raising=False)
    private_key, public_key = _offline_license_keypair()
    monkeypatch.setenv("ALGENTA_LOCAL_LICENSE_PUBLIC_KEY", public_key)

    token = jwt.encode(
        {
            "api_key_prefix": "offline",
            "device_id": "device-airgap-runtime",
            "plan": "enterprise",
            "device_limit": 0,
            "permitted_modules": ["*"],
            "issued_at": 1_900_000_000,
            "expires_at": 1_999_999_999,
            "key_expires_at": 1_999_999_999,
            "grace_days": 14,
            "iss": "algenta-offline-license",
            "sub": "device-license",
            "ver": 2,
        },
        private_key,
        algorithm="RS256",
    )
    runtime_license = _reload_runtime_license_module()
    runtime_license._save_license(token)

    runtime = Runtime()
    runtime.connect(REAL_MARCH_ORDERS, name="orders_detail")
    plan = runtime.resolve(
        {
            "source_name": "orders_detail",
            "metric": "Sales (incl. tax)",
            "group_by": "Order Channel",
        }
    )

    result = runtime.query(plan)
    assert result.row_count > 0


def test_runtime_local_requires_connected_source() -> None:
    runtime = Runtime()

    with pytest.raises(RuntimeConfigurationError, match="No local sources are connected"):
        runtime.resolve({"metric": "revenue"})


def test_runtime_local_connect_accepts_canonical_csv_connector(tmp_path: Path) -> None:
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text("product_line,revenue\nElectronics,10\nApparel,20\n", encoding="utf-8")
    runtime = Runtime()

    registration = runtime.connect(
        {
            "type": "csv",
            "location": {"path": str(csv_path)},
            "options": {"delimiter": ","},
        },
        name="orders_detail",
    )
    plan = runtime.resolve(
        {
            "source_name": registration.name,
            "metric": "revenue",
            "aggregation": "count",
        }
    )
    result = runtime.query(plan)

    assert registration.status == "ready"
    assert registration.row_count == 2
    assert plan.resolved_plan is not None
    assert float(_result_scalar_value(result.result)) == 2.0


def test_runtime_local_connect_rejects_remote_canonical_connector() -> None:
    runtime = Runtime()

    with pytest.raises(RuntimeValidationError) as exc:
        runtime.connect(
            {
                "type": "postgres",
                "location": {
                    "host": "localhost",
                    "port": 5432,
                    "database": "orders",
                    "schema": "public",
                    "table": "orders",
                },
                "auth": {
                    "credentials": {
                        "user": "analytics",
                        "password": "secret",
                    }
                },
            },
            name="orders_pg",
        )

    assert exc.value.code == "unsupported_local_connector"

