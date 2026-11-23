---
name: slimproof
description: Audit MCP tool definitions for token cost and safely rewrite bloated descriptions. Use when the user wants to reduce MCP or tool token usage, asks which MCP servers or tools are heaviest, or wants to slim tool descriptions.
argument-hint: "[server-name]"
---

# Slim MCP tool definitions

## Workflow
1. Call `audit_config`. If the user gave a stdio command or URL instead of a configured server, call `audit_server`.
2. Show the 5 heaviest tools (server, tool, ~tokens) and their findings (rule id + message). Token counts are estimates.
3. Pick the server to slim: the one the user named, else ask (suggest the heaviest one with findings).
4. Call `get_tools` for that server. Rewrite `description` and `title` values everywhere: the tool's own, and every one nested inside `inputSchema` (`properties`, `items`, `anyOf`, `$defs`). Nested parameter descriptions often hold most of a tool's tokens; the guard allows changing them. Follow [rewrite-rules.md](rewrite-rules.md) and the style of [examples.md](examples.md) and copy everything else exactly.
5. Call `compare` with the original tools and your rewrites. You may send only the tools you changed, as long as both lists hold the same tools. If any tool has `problems`, fix it and call `compare` again. Never present a version that still has problems.
6. Report a before/after token table and the total saved. Show the slim descriptions on request, ready to paste into the server's source.

## Rules
- If SP008 fires, make the two descriptions clearly different; don't shorten them.
- Never print `env` values, headers or other secrets from MCP configs.
- This workflow is read-only. Never create, edit or delete any file unless the user explicitly asks, and say which file first.