/**
 * Algenta SDK client — TypeScript implementation.
 *
 * Originally a single 6603-line file. Now split into per-domain sub-files
 * for maintainability; this barrel re-exports the public API so external
 * imports continue to work unchanged.
 */

export * from "./_client_constants.js";
export * from "./_client_contract_validators.js";
export * from "./_client_platform_validators_a.js";
export * from "./_client_platform_validators_b.js";
export * from "./_client_platform_validators_c.js";
export * from "./_client_runtime_manifest.js";
export * from "./_client_runtime_admin.js";
export * from "./_client_runtime_release.js";
export * from "./_client_errors.js";
export * from "./_client_class.js";
