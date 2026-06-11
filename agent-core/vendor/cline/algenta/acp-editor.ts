const DEFAULT_SERVER_NAME = "algenta";
const DEFAULT_COMMAND = "python";
const DEFAULT_ARGS = ["-m", "apps.mcp_server.server"] as const;
const DEFAULT_API_KEY_PLACEHOLDER =
	"<SET ALGENTA_API_KEY OR DE_API_KEY BEFORE LAUNCH>";

export type EditorIntegrationName =
	| "cursor"
	| "zed"
	| "claude_desktop";

export interface EditorEnvInput {
	apiKeyPlaceholder?: string;
	baseUrl?: string;
	extraEnv?: Readonly<Record<string, string>>;
}

export interface EditorServerInput extends EditorEnvInput {
	serverName?: string;
	command?: string;
	args?: readonly string[];
}

export interface EditorIntegrationSurface {
	editor: EditorIntegrationName;
	config_path: string;
	transport: "mcp_stdio";
	entrypoint_tools: string[];
	example_prompts: string[];
	config: Record<string, unknown>;
}

function requiredString(value: string | undefined, field: string): string {
	if (typeof value !== "string" || value.trim().length === 0) {
		throw new Error(`${field} must be a non-empty string.`);
	}
	return value.trim();
}

function optionalString(value: string | undefined): string | undefined {
	if (typeof value !== "string") return undefined;
	const trimmed = value.trim();
	return trimmed.length > 0 ? trimmed : undefined;
}

function normalizeArgs(args: readonly string[] | undefined): string[] {
	if (!args || args.length === 0) return [...DEFAULT_ARGS];
	return args.map((arg, index) => requiredString(arg, `args[${index}]`));
}

function normalizeEnv(input: EditorEnvInput | undefined): Record<string, string> {
	const env: Record<string, string> = {
		ALGENTA_API_KEY:
			optionalString(input?.apiKeyPlaceholder) || DEFAULT_API_KEY_PLACEHOLDER,
	};
	const baseUrl = optionalString(input?.baseUrl);
	if (baseUrl) {
		env.ALGENTA_BASE_URL = baseUrl;
	}
	for (const [key, value] of Object.entries(input?.extraEnv ?? {})) {
		env[requiredString(key, "extraEnv key")] = requiredString(
			value,
			`extraEnv.${key}`,
		);
	}
	return env;
}

function normalizeServerInput(input: EditorServerInput | undefined): {
	serverName: string;
	command: string;
	args: string[];
	env: Record<string, string>;
} {
	return {
		serverName:
			optionalString(input?.serverName) || DEFAULT_SERVER_NAME,
		command: optionalString(input?.command) || DEFAULT_COMMAND,
		args: normalizeArgs(input?.args),
		env: normalizeEnv(input),
	};
}

export function buildCursorMcpConfig(
	input: EditorServerInput = {},
): Record<string, unknown> {
	const server = normalizeServerInput(input);
	return {
		mcpServers: {
			[server.serverName]: {
				command: server.command,
				args: server.args,
				env: server.env,
			},
		},
	};
}

export function buildZedContextServerConfig(
	input: EditorServerInput = {},
): Record<string, unknown> {
	const server = normalizeServerInput(input);
	return {
		context_servers: {
			[server.serverName]: {
				command: {
					path: server.command,
					args: server.args,
					env: server.env,
				},
			},
		},
	};
}

export function buildClaudeDesktopMcpConfig(
	input: EditorServerInput = {},
): Record<string, unknown> {
	return buildCursorMcpConfig({
		...input,
		baseUrl: optionalString(input.baseUrl) || "http://localhost:8000",
	});
}

function repositoryFixPrompt(serverName: string): string {
	return `@${serverName} run_repository_fix repository_id='repo_123' pipeline={"signals":{"issue_text":"Null dereference in src/service.py"}} apply={"mode":"patch_only"}`;
}

function pipelinePrompt(serverName: string): string {
	return `@${serverName} run_repository_pipeline repository_id='repo_123' pipeline={"signals":{"issue_text":"Investigate elevated p95 latency in src/runtime.ts"}}`;
}

export function buildEditorIntegrationManifest(
	input: EditorServerInput = {},
): EditorIntegrationSurface[] {
	const server = normalizeServerInput(input);
	const tools = [
		"run_repository_pipeline",
		"simulate_repository_patch",
		"run_repository_fix",
	];
	const prompts = [
		repositoryFixPrompt(server.serverName),
		pipelinePrompt(server.serverName),
	];
	return [
		{
			editor: "cursor",
			config_path: "~/.cursor/mcp.json",
			transport: "mcp_stdio",
			entrypoint_tools: tools,
			example_prompts: prompts,
			config: buildCursorMcpConfig(input),
		},
		{
			editor: "zed",
			config_path: "~/.config/zed/settings.json",
			transport: "mcp_stdio",
			entrypoint_tools: tools,
			example_prompts: prompts,
			config: buildZedContextServerConfig(input),
		},
		{
			editor: "claude_desktop",
			config_path: "~/Library/Application Support/Claude/claude_desktop_config.json",
			transport: "mcp_stdio",
			entrypoint_tools: tools,
			example_prompts: prompts,
			config: buildClaudeDesktopMcpConfig(input),
		},
	];
}

export function renderEditorConfigJson(value: unknown): string {
	return `${JSON.stringify(value, null, 2)}\n`;
}
