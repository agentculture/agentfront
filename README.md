# afi-cli

**Agent First Interface** — scaffold tools whose primary consumer is an AI agent, not a human.

From a single source of truth, afi-cli generates three interface surfaces, each shaped by a different agent-ergonomic principle:

- **CLI** — with a `learn` affordance so an agent can introspect the tool and author its own usage skill (not just read `--help`).
- **MCP server** — a deliberately minimal menu, tuned for low surface area over maximal API coverage.
- **HTTP site** — markdown pages plus a sitemap, navigable by any agent with a fetch tool.

Part of the [AgentCulture](https://github.com/agentculture) OSS org — see [`docs/agentculture.md`](./docs/agentculture.md) for the org, its paradigm, and how afi-cli is foundational to it. The design brief is in [`docs/agent-first.md`](./docs/agent-first.md).

## Install

```bash
uv tool install afi-cli
```

Then `afi --version` should work on your PATH. `uv tool install` is the supported path — not `pip install`.

## Usage

```bash
afi learn    # self-description for an agent reader
afi --help   # subcommand listing
```

Feature commands (scaffold generators for CLI / MCP / HTTP) are not implemented yet — the `learn` stub is a placeholder that demonstrates the agent-learnability principle.

## Develop

```bash
uv sync                          # install + dev deps
uv run pytest -n auto -v         # tests
uv run afi learn                 # run the CLI from source
uv run pre-commit install        # enable lint hooks
```

See [`CLAUDE.md`](./CLAUDE.md) for design intent and full command reference.

## License

MIT. © 2026 Ori Nachum / AgentCulture.
