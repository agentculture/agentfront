# afi-cli

**Agent First Interface** — scaffold tools whose primary consumer is an AI agent, not a human.

From a single source of truth, afi-cli generates three interface surfaces, each shaped by a different agent-ergonomic principle:

- **CLI** — with a `learn` affordance so an agent can introspect the tool and author its own usage skill (not just read `--help`).
- **MCP server** — a deliberately minimal menu, tuned for low surface area over maximal API coverage.
- **HTTP site** — markdown pages plus a sitemap, navigable by any agent with a fetch tool.

## Status

Greenfield. Stack and entry points are not yet chosen; see [`CLAUDE.md`](./CLAUDE.md) for the design north star and repo setup (markdown lint hook, lint skill, etc.).
