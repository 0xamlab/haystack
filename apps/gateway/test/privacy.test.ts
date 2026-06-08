import assert from "node:assert/strict";
import test from "node:test";

import {
  GatewayPrivacyConfigurationError,
  resolveGatewayApiOrigin,
} from "../src/privacy.js";

test("gateway private profiles require an explicit api origin", () => {
  assert.throws(
    () =>
      resolveGatewayApiOrigin({
        ALGENTA_DEPLOYMENT_MODE: "self_hosted",
      }),
    (error) =>
      error instanceof GatewayPrivacyConfigurationError &&
      /require API_ORIGIN to be configured explicitly/.test(error.message),
  );
});

test("gateway private profiles reject algenta cloud origin", () => {
  assert.throws(
    () =>
      resolveGatewayApiOrigin({
        ALGENTA_DEPLOYMENT_MODE: "self_hosted",
        API_ORIGIN: "https://api.algenta.ai",
      }),
    (error) =>
      error instanceof GatewayPrivacyConfigurationError &&
      /Algenta-owned cloud URLs/.test(error.message),
  );
});

test("gateway private profiles allow allowlisted customer origin", () => {
  const resolved = resolveGatewayApiOrigin({
    ALGENTA_DEPLOYMENT_MODE: "self_hosted",
    API_ORIGIN: "https://api.customer.example",
    ALGENTA_EGRESS_ALLOWLIST: "api.customer.example",
  });

  assert.equal(resolved, "https://api.customer.example");
});

test("gateway private profiles allow corp-suffixed internal origin without allowlist", () => {
  const resolved = resolveGatewayApiOrigin({
    ALGENTA_DEPLOYMENT_MODE: "self_hosted",
    API_ORIGIN: "https://api.customer.corp",
  });

  assert.equal(resolved, "https://api.customer.corp");
});

test("gateway private profiles reject unallowlisted public customer origin", () => {
  assert.throws(
    () =>
      resolveGatewayApiOrigin({
        ALGENTA_DEPLOYMENT_MODE: "self_hosted",
        API_ORIGIN: "https://api.customer.example",
      }),
    (error) =>
      error instanceof GatewayPrivacyConfigurationError &&
      /allowlisted customer origin/.test(error.message),
  );
});
