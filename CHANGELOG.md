# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- A Results section in the README, with the eval numbers and the tokens saved for each server.
- `docs/architecture.md`: how slimproof works inside, with diagrams.
- `server.json` for the MCP Registry.
- CI also tests Python 3.11 and 3.13, and the package lists all four supported versions.

### Fixed

- `compare --exact` shows a one-line error and exits with code 2 when the Claude API call fails, for example with a wrong API key. Before, it showed a traceback.

## [0.1.1] - 2026-11-26

### Added

- `--top N` for `audit` and `server`: show only the N heaviest tools and N findings. One row sums up the other tools, and the total still counts every tool. JSON output always has everything.
- A closing `Total:` line after the findings, so you see the totals without scrolling up. When there are many findings, the line suggests `--top 10`.
- A demo GIF in the README, and a link to the full demo video on YouTube.

### Changed

- The audit no longer shows the log lines that servers write to stderr. If a server fails, the audit shows its last 5 log lines below the error, to help you find the cause.
- SP007 quotes the repeated sentence up to a whole word and adds `…` when it cuts the sentence.

### Fixed

- The package now includes the `LICENSE` file.

## [0.1.0] - 2026-11-26

The first release.

### Added

- `slimproof audit`: rank the tools in your MCP configs by token cost. slimproof reads `.mcp.json`, `~/.claude.json` and the Claude Desktop config.
- `slimproof server`: audit one stdio or HTTP server without a config.
- Bloat rules SP001–SP007. They find filler openings, text that only repeats a name or type, extra markdown, very long descriptions, sentences repeated across tools and tools that look almost the same.
- Token counts: a fast estimate by default (shown with `~`), or exact Claude counts with `--exact` and your own `ANTHROPIC_API_KEY`.
- `--budget` and `--window`: exit with code 1 when tools use too much of the context window. Use this in CI.
- `slimproof compare`: check slim tools against the originals. It shows the tokens saved and any guard problems.
- A guard that refuses a rewrite if anything except `description` or `title` changes.
- `slimproof proxy`, `apply` and `revert`: serve saved slim tools to Claude Code through a small proxy, and undo it. If a server changes a tool, the proxy serves the original.
- `slimproof mcp`: slimproof as an MCP server with the tools `audit_config`, `audit_server`, `get_tools`, `compare` and `save_overrides`.
- A Claude Code plugin with the `/slimproof` skill. It audits, slims, checks and saves in one flow.

### Known issues

- `apply` and `revert` save full copies of the config to `~/.slimproof/backups/`. A copy of `~/.claude.json` can contain API keys. Keep the folder private, and delete old backups.
- The proxy works only with local stdio servers. Plugin servers and remote HTTP servers can't use it yet.
- `compare --exact` shows a traceback if the API call fails.

[0.1.1]: https://github.com/Rounak7721/slimproof/releases/tag/v0.1.1
[0.1.0]: https://github.com/Rounak7721/slimproof/releases/tag/v0.1.0
