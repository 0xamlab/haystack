/**
 * Multi-hop local runtime-library flow example.
 *
 * This module demonstrates the local runtime-library path. It defaults to a
 * local daemon and does not silently fall back to Algenta cloud. If you
 * provide `ALGENTA_BASE_URL` / `DE_BASE_URL` / `ALGENTA_API_URL` or
 * `ALGENTA_API_KEY` / `DE_API_KEY` for daemon bootstrap or self-hosted control
 * surfaces, point them at your self-hosted operator deployment instead of
 * Algenta cloud in `self_hosted` and `air_gapped`.
 */

import { MojoRuntime, libraries } from "algenta-sdk";

async function main(): Promise<void> {
  const config = {
    mode: "local" as const,
    tcpAddress: process.env.ALGENTA_DAEMON_TCP ?? "127.0.0.1:50099",
  };

  const runtime = new MojoRuntime(config);

  // Mission get_algenta_library_health -> public MojoRuntime.health()
  const health = await runtime.health();
  console.log("runtime health:", health);

  // Mission list_algenta_libraries -> public listModules() / catalog.names()
  const modules = await runtime.listModules();
  console.log("module count:", modules.length);
  console.log(
    "first modules:",
    modules.slice(0, 5).map((module) => module.name),
  );

  const catalog = await libraries(config);
  console.log("catalog names:", catalog.names().slice(0, 5));

  // Mission inspect_algenta_library / get_algenta_library_module
  console.log("text.tokenizer functions:", await runtime.listFunctions("text.tokenizer"));
  const textTokenizer = catalog.module("text.tokenizer");
  console.log("text.tokenizer proxy name:", textTokenizer.name);

  // Mission execute_algenta_library -> direct execute() or module proxy calls
  const direct = await runtime.execute("rerank_eval", "precision_at_k", {
    relevance: [1, 0, 1, 1],
    k: 3,
  });
  console.log("direct execute result:", direct.result);

  const tokens = await textTokenizer.word_tokenize("delay correlation route");
  console.log("proxy execute result:", tokens);
}

void main();
