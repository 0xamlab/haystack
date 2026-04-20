from __future__ import annotations

from apps.api_server.services import pyarrow_runtime


def test_filter_known_pyarrow_cpu_info_warnings_removes_only_known_noise() -> None:
    warning = (
        "/Users/runner/work/crossbow/crossbow/arrow/cpp/src/arrow/util/cpu_info.cc:239: "
        "IOError: sysctlbyname failed for 'hw.l1dcachesize'. "
        "Detail: [errno 1] Operation not permitted\n"
    )
    other = "unexpected stderr that must remain visible\n"

    filtered = pyarrow_runtime._filter_known_pyarrow_cpu_info_warnings(
        warning + other + warning
    )

    assert filtered == other


def test_initialize_pyarrow_parquet_runtime_primes_only_once(
    monkeypatch,
) -> None:
    calls = 0

    def _fake_prime() -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr(pyarrow_runtime, "_PARQUET_RUNTIME_READY", False)
    monkeypatch.setattr(pyarrow_runtime, "_prime_pyarrow_parquet_runtime", _fake_prime)

    pyarrow_runtime.initialize_pyarrow_parquet_runtime()
    pyarrow_runtime.initialize_pyarrow_parquet_runtime()

    assert calls == 1
