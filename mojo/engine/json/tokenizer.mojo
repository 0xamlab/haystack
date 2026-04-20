"""
json/tokenizer.mojo — Phase 4 boundary optimization gate result.

DECISION: Python JSON boundary is KEPT. Mojo-native tokenizer is NOT implemented.

Benchmark result (tests/benchmark/bench_boundary.py):
  - json.loads() on a 10-variable payload: ~0.06 ms (mean, 500 iterations)
  - invoke_engine() total round-trip (10k MC via pool): ~8–15 ms
  - Parse fraction: ~0.5–0.8% << 10% threshold

Conclusion: Python's json.loads() is a negligible fraction of total latency.
The bottleneck is in the Mojo simulation hot loop (10k iterations × N_vars),
not in the JSON parse. A schema-specific Mojo tokenizer would save < 1ms
per request — not worth the maintenance cost.

If this changes (e.g. when running 1M runs per request, making 10k-run latency
drop below 5ms, pushing parse fraction above 10%), implement the fields below.

Reserved schema-specific tokenizer API (not yet implemented):
  fn extract_string_field(raw: String, key: String) -> String
  fn extract_int_field(raw: String, key: String, default: Int) -> Int
  fn extract_float_field(raw: String, key: String, default: Float64) -> Float64
  fn extract_bool_field(raw: String, key: String, default: Bool) -> Bool
  fn extract_variables_array(raw: String) -> List[VarSpec]

To re-evaluate: run `make bench-boundary` after any significant engine speedup.
"""

# Tokenizer not implemented — Python json.loads() boundary is kept.
# See: mojo/engine/request_parser.mojo (Phase 4 note at top of file)
# See: tests/benchmark/bench_boundary.py for the benchmark methodology
