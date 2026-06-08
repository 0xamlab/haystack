/**
 * Algenta SDK client — TypeScript implementation.
 *
 * Originally a single 6603-line file. Now split into per-domain sub-files
 * for maintainability; this barrel re-exports the public API so external
 * imports continue to work unchanged.
 */

export * from "./_client_constants.js";
export * from "./_client_contract_validators.js";
export * from "./_client_platform_validators_a1.js";
export * from "./_client_platform_validators_a2.js";
export * from "./_client_platform_validators_b1.js";
export * from "./_client_platform_validators_b2.js";
export * from "./_client_platform_validators_c.js";
export * from "./_client_runtime_manifest.js";
export * from "./_client_runtime_admin.js";
export * from "./_client_runtime_release.js";
export * from "./_client_errors.js";
export * from "./_client_class.js";
// Side-effect imports register methods on DecisionEngineClient.prototype via
// TypeScript declaration merging. They must be imported AFTER the class is
// defined and BEFORE any consumer calls instance methods.
import "./_client_class_methods_simulate_decision.js";
import "./_client_class_methods_agent_capability.js";
import "./_client_class_methods_llm_data.js";
import "./_client_class_methods_admin.js";
