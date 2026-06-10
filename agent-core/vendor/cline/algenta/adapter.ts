// Algenta Repositories — real agent-core adapter over the vendored Cline SDK.
//
// runAgent() drives a headless, auto-approved, single-shot ClineCore run against ANY
// provider Cline supports (key resolved from .env via the SDK provider catalog), edits
// files under working_dir, and returns the run status + which files changed. Proven
// live against Anthropic. See ../CLINE_SDK_INTERFACE.md for the full surface.
import { ClineCore, Llms } from "@cline/core";

export interface RunAgentArgs {
  working_dir: string;
  prompt: string; // the task
  injected_context?: string; // token-compressed evidence bundle (repo intelligence)
  provider?: string; // default "anthropic"
  model?: string; // default = provider's defaultModelId
  suppress_exploration?: boolean; // legacy token-reduction flag: block read/search/fetch tools
  tool_profile?: string; // AR-OPT-4 tool profile (takes precedence over suppress_exploration)
  limits?: { maxIterations?: number; timeoutMs?: number };
}

export interface RunAgentResult {
  status: string; // AgentFinishReason: completed | max_iterations | aborted | mistake_limit | error
  agent_run_id: string;
  text: string;
  iterations: number;
  files_changed: string[];
  usage?: { inputTokens: number; outputTokens: number; totalCost?: number };
  provider: string;
  model: string;
}

const EXPLORATION_TOOLS = ["read_files", "search_codebase", "fetch_web_content", "ask_question"];
const SHELL_TOOLS = ["run_commands"];
const WRITE_TOOLS = new Set(["editor", "apply_patch"]);

// AR-OPT-4 tool profiles — trim the agent's tool surface to cut exploration tokens.
//   no_exploration_no_shell         -> block exploration AND the shell (most token-frugal;
//                                       the agent edits purely from the injected bundle).
//   no_exploration_local_validation -> block exploration; keep the shell so the agent may
//                                       validate its patch in-sandbox after editing.
// Falls back to the legacy suppress_exploration flag when no profile is given.
function suppressedTools(args: RunAgentArgs): string[] {
  switch (args.tool_profile) {
    case "no_exploration_no_shell":
      return [...EXPLORATION_TOOLS, ...SHELL_TOOLS];
    case "no_exploration_local_validation":
      return [...EXPLORATION_TOOLS];
    default:
      return args.suppress_exploration ? [...EXPLORATION_TOOLS] : [];
  }
}

export async function runAgent(args: RunAgentArgs): Promise<RunAgentResult> {
  // 1) Resolve provider/model/apiKey from .env via the SDK catalog — any provider.
  const requested = args.provider || "anthropic";
  const providerId =
    (Llms as { normalizeProviderId?: (p: string) => string }).normalizeProviderId?.(requested) ??
    requested;
  const collection = await Llms.getProviderCollection(providerId);
  const envNames: string[] = collection?.provider?.env ?? [];
  const apiKey = envNames.map((k) => process.env[k]?.trim()).find(Boolean);
  const modelId = args.model || collection?.provider?.defaultModelId;
  if (!modelId) throw new Error(`no model id for provider '${providerId}'`);
  if (!apiKey) {
    throw new Error(`no API key in env for '${providerId}' (tried: ${envNames.join(", ") || "none"})`);
  }

  // 2) Auto-approve everything (headless); optionally hard-suppress exploration tools.
  const toolPolicies: Record<string, { enabled?: boolean; autoApprove?: boolean }> = {
    "*": { enabled: true, autoApprove: true },
  };
  for (const t of suppressedTools(args)) toolPolicies[t] = { enabled: false };

  const systemPrompt =
    "You are Algenta's automated repository-fixing agent. Apply the requested change using " +
    "your file-editing tools, then stop. Do not ask questions." +
    (args.injected_context
      ? `\n\n[REPOSITORY EVIDENCE BUNDLE — authoritative; prefer it over exploring the repo]\n${args.injected_context}`
      : "");

  const cline = await ClineCore.create({
    clientName: "algenta-agent-core",
    backendMode: "local",
    toolPolicies,
  } as Parameters<typeof ClineCore.create>[0]);

  let agentRunId = "";
  try {
    const started = await cline.start({
      config: {
        providerId,
        modelId,
        apiKey,
        cwd: args.working_dir,
        workspaceRoot: args.working_dir,
        systemPrompt,
        enableTools: true,
        enableSpawnAgent: false,
        enableAgentTeams: false,
        ...(args.limits?.maxIterations
          ? { execution: { maxIterations: args.limits.maxIterations } }
          : {}),
      },
      source: "terminal",
      interactive: false,
    } as Parameters<typeof cline.start>[0]);
    agentRunId = started.sessionId;

    const result = await (cline as unknown as {
      send: (i: unknown) => Promise<
        | {
            finishReason?: string;
            text?: string;
            iterations?: number;
            usage?: { inputTokens?: number; outputTokens?: number; totalCost?: number };
            toolCalls?: { name: string; input?: unknown; error?: string }[];
          }
        | undefined
      >;
    }).send({
      sessionId: agentRunId,
      prompt: args.prompt,
      mode: "act",
      timeoutMs: args.limits?.timeoutMs ?? 150000,
    });

    const filesChanged = new Set<string>();
    for (const call of result?.toolCalls ?? []) {
      if (!WRITE_TOOLS.has(call.name) || call.error) continue;
      const input = call.input as { path?: string; file?: string; files?: unknown } | undefined;
      const candidates = [input?.path, input?.file, ...(Array.isArray(input?.files) ? input!.files : [])];
      for (const p of candidates) if (typeof p === "string") filesChanged.add(p);
    }

    const usage = result?.usage;
    return {
      status: result?.finishReason ?? "unknown",
      agent_run_id: agentRunId,
      text: result?.text ?? "",
      iterations: result?.iterations ?? 0,
      files_changed: [...filesChanged],
      usage: usage
        ? {
            inputTokens: usage.inputTokens ?? 0,
            outputTokens: usage.outputTokens ?? 0,
            totalCost: usage.totalCost,
          }
        : undefined,
      provider: providerId,
      model: modelId,
    };
  } finally {
    const anyCline = cline as unknown as { dispose?: (r?: string) => Promise<void> };
    if (typeof anyCline.dispose === "function") {
      await anyCline.dispose("run_complete").catch(() => {});
    }
  }
}
