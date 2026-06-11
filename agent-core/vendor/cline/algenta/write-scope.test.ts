// B7/PR10c: the write-scope beforeTool guard blocks out-of-scope writes pre-disk.
import { expect, test } from "bun:test";
import { scopeViolation, writeScopeBeforeTool } from "./write-scope";

const ctx = (toolName: string, input: unknown) => ({ toolCall: { toolName }, input }) as never;

test("in-repo relative writes are allowed", () => {
	expect(scopeViolation("src/foo/bar.py")).toBeNull();
	expect(writeScopeBeforeTool(ctx("editor", { path: "src/foo/bar.py" }))).toBeUndefined();
});

test("absolute paths and traversal are blocked (stop)", () => {
	expect(writeScopeBeforeTool(ctx("editor", { path: "/etc/passwd" }))?.stop).toBe(true);
	expect(writeScopeBeforeTool(ctx("apply_patch", { files: ["../../escape.txt"] }))?.stop).toBe(true);
});

test("protected paths are hard-denied regardless of profile", () => {
	expect(writeScopeBeforeTool(ctx("editor", { path: ".github/workflows/ci.yml" }))?.stop).toBe(true);
	expect(writeScopeBeforeTool(ctx("editor", { file_path: "config/.env" }))?.stop).toBe(true);
	expect(writeScopeBeforeTool(ctx("apply_patch", { path: ".git/config" }))?.stop).toBe(true);
});

test("non-write tools are not gated", () => {
	expect(writeScopeBeforeTool(ctx("read_file", { path: "/anywhere/at/all" }))).toBeUndefined();
	expect(writeScopeBeforeTool(ctx("grep", { pattern: "x" }))).toBeUndefined();
});
