# Security

## Report a problem

Do not open a public issue for a security problem. Use GitHub's private report instead:

1. Go to the [Security tab](https://github.com/Rounak7721/slimproof/security) of this repository.
2. Click **Report a vulnerability**.
3. Describe the problem and the steps to reproduce it.

## Supported versions

Only the latest release gets security fixes.

## What slimproof does with your data

- slimproof reads your MCP configs to find servers. It never prints the values in `env` blocks or headers.
- With `--exact`, slimproof sends tool definitions to the Anthropic `count_tokens` API with your own `ANTHROPIC_API_KEY`. Without `--exact`, nothing leaves your computer.
- `apply` and `revert` change your config file. Before each change, slimproof saves a full copy of the file to `~/.slimproof/backups/`. A copy of `~/.claude.json` can contain API keys and tokens. Keep the folder private, and delete old backups when you no longer need them.
- Saved slim tools go to `~/.slimproof/overrides/`. They contain only tool definitions.
