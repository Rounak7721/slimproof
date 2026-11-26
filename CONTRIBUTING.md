# Contributing

Thank you for your help. Bug reports, ideas and pull requests are all welcome.

## Report a bug

Open an [issue](https://github.com/Rounak7721/slimproof/issues). Include:

- your OS, your Python version and the slimproof version (`uvx slimproof --version`)
- the command you ran and the full output
- what you expected

Remove API keys and tokens from configs before you paste them.

## Set up

You need [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/Rounak7721/slimproof
cd slimproof
uv sync --all-extras
```

## Check your change

Run these before you open a pull request. CI runs the same checks.

```sh
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

## Rules for code

- Put logic in `src/slimproof/core/`. `cli.py` and `server.py` only call it.
- Add a test for each change.
- Use type hints and short docstrings on public functions.
- Open pull requests against the `develop` branch.
- Use [conventional commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `test:`, `chore:`.
