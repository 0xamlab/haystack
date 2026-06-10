// Algenta engine plugin — the "engine behind" tool seam: Cline drives the loop, this
// plugin contributes the Algenta tools (localize / graph_query / simulate_patch). Loaded
// via the start config's `pluginPaths` (see adapter.ts), only when ALGENTA_ENGINE_URL is
// set. The runtime calls setup(api) and the registered tools become available to the loop.
//
// NOTE: the govern hook (mojo-gate) is wired via the start config's `config.hooks` in
// adapter.ts, NOT here. In backendMode "local" a pluginPaths plugin contributes its
// setup()/tools but its top-level `hooks` are not merged into the agent loop — only
// config.hooks is. So this plugin declares the "tools" capability only.
import type { AgentPlugin } from "@cline/core";
import { algentaTools } from "./tools";

const plugin: AgentPlugin = {
	name: "algenta-engine",
	manifest: { capabilities: ["tools"] },
	setup(api) {
		// `api` is contextually typed as AgentExtensionApi from the AgentPlugin annotation.
		for (const tool of algentaTools) api.registerTool(tool);
	},
};

export default plugin;
