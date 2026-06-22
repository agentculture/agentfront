---
title: Agent First
nav_order: 2
---

**Agent First** is AgentCulture's guiding paradigm: when you design software, *the primary consumer is an AI agent, not a human*. Every other decision — CLI shape, docs layout, protocol menu, error messages — flows from that reversal.

This document explains what the paradigm means, how it manifests in each interface surface, and why `agentfront` is the foundational tool for the rest of AgentCulture to ship it.

## The reversal

Traditional tool design assumes a human at the keyboard. `--help` is terse because the human has patience to skim it. Errors are prose because the human reads English. Menus grow features because the human wants power. Docs are hand-curated because the human will navigate.

Agents have a different profile:

| Dimension                | Human default               | Agent default                                         |
| ------------------------ | --------------------------- | ----------------------------------------------------- |
| **Discovery**            | man pages, Google, Stack    | fetch + parse structured input                        |
| **Learning curve**       | tolerated, once             | paid every session unless the tool is introspectable  |
| **Menu cardinality**     | features-as-virtue          | every verb is a decision point that can go wrong      |
| **Error handling**       | re-read, adjust, retry      | needs machine-actionable reason, not prose apology    |
| **Memory**               | persistent, contextual      | bounded context window; docs must fit or be indexed   |

Agent First inverts the defaults. You don't *remove* human usability — you design for agents, and humans get the benefit of clarity that results.

## The three surfaces

Most tools end up needing more than one interface. The common ones are:

- A **command-line interface** a shell or subagent can invoke.
- A **programmatic interface** (increasingly: an MCP server) another agent can call.
- A **documentation surface** an agent with a fetch tool can navigate.

Agent First treats each surface as a design problem with its own discipline:

### CLI — learnability

The `--help` screen isn't enough. An agent that just met your tool shouldn't have to scrape help text and guess at semantics. Instead, expose a `learn` affordance: a single command that prints a concise, structured self-description aimed at an agent reader. It answers "what does this tool do, what are its verbs, what do they take, and what's the minimum I need to use it correctly." An agent can then write its own usage skill for the tool from that output without further trial-and-error.

### MCP — minimalism

An MCP server can expose dozens of tools. It should expose the fewest. Each tool in the menu is a decision point that a calling agent has to disambiguate correctly. A minimal, well-named menu is easier to use, easier to reason about, and harder to misuse than a maximal one — even if the maximal one theoretically enables more. When in doubt, collapse related verbs into one with richer arguments, or leave the advanced verb off the menu entirely.

### HTTP — discoverability

An agent's fetch tool doesn't navigate like a human with a browser. It follows links, parses markdown, and obeys sitemaps. So: every HTTP surface AgentCulture ships is **markdown-first with a sitemap**. No SPA, no SDK, no login wall. If an agent can GET the root URL and a sitemap, it can build a complete map of the docs and pull exactly the pages it needs — no bespoke client required.

### Diagnosability — `doctor` on every surface

Learnability tells the agent *what is here*; diagnosability tells it *what is wrong, and how to fix it*. Every agent-first tool exposes a `doctor` verb (CLI), tool (MCP), or endpoint (HTTP) that surveys its own install and surfaces inconsistencies with actionable remediation. The pillar joins learnability / minimalism / discoverability as a baseline contract: when the tool is broken, an agent must be able to diagnose it without reading source, and the failure mode must always carry a `remediation` string. `--fix` is offered when remediation is safe to auto-apply; otherwise the verb explains the fix in prose an agent can act on.

## Why `agentfront` is foundational

Every AgentCulture tool eventually wants all three surfaces. Without a shared runtime, each project would:

1. Re-implement the three surfaces from scratch, inconsistently.
2. Drift over time — one project's CLI is more agent-friendly than another's, for no reason beyond author preference. Worse, *within* a project the CLI, MCP, and HTTP views of the same tool can disagree about what is exposed.
3. Miss the baked-in best practices — the next `culture`-sized project might ship a CLI without `learn`, or an MCP with forty tools, or an HTTP doc site without a sitemap.

`agentfront` solves this once, as an **importable runtime library**:

```python
from agentfront import App

app = App(name="mytool", version="1.0")
app.add_docs_dir("docs/")

@app.tool
def search(query: str) -> str:
    """Search the corpus."""
    ...

app.cli()          # argparse CLI with the universal verbs
app.mcp_server()   # minimal MCP tool menu
app.http_app()     # markdown pages + sitemap
```

- Docs and tools are declared **once** into a single registry on the `App`.
- The CLI, MCP server, and HTTP site each *read from that one registry* — they are derived, never separately authored, so they cannot drift apart.
- The discipline is enforced by the runtime, not by author discipline:
  - The CLI always has `learn`.
  - The MCP surface exposes exactly the tools registered on the `App` — a minimal, declared menu.
  - The HTTP docs are markdown + sitemap by construction.

Ship a new AgentCulture tool → `import agentfront`, build an `App`, register your docs and tools → you have three agent-ergonomic surfaces, consistent with every other project in the org and consistent with each other. That's the *foundational* claim: AgentCulture's surface-area compounds instead of fragmenting.

> Earlier alpha releases pursued a different shape — a `cli cite` scaffolder that dropped a reference tree into a project, plus a manifest-driven generator that would *emit* the three surfaces as files. That has been retired. agentfront is now a runtime you import, not a generator that writes code, so the surfaces stay live and in sync with the single registry rather than being snapshotted into files that drift.

## Dogfooding

`agentfront` itself is required to use its own runtime. Its hand-written CLI in `agentfront/cli/` is the reference implementation of the universal verbs and the rubric the runtime checks against; the runtime-derived CLI (`App.cli()`) builds the same surface from a registry. The same single-registry model backs the MCP and HTTP surfaces — a self-validating loop where agentfront's own three surfaces are produced by the very `App` it asks every other tool to use.

## Agent First is a discipline, not a switch

Every feature proposal in AgentCulture has to pass an Agent First review:

- Does this add a menu item an agent now has to reason about?
- Is the behavior introspectable, or does it require reading source?
- Can an agent discover it from a single fetch?
- Does the failure mode return something actionable, or does it require another round-trip?

If the answer to any of those is "no," the feature either changes shape or doesn't ship. That's what "Agent First in everything we do" means in practice.

## The rubric

The discipline above is made mechanical by the [**rubric**](./rubric.md) — seven bundles of concrete checks that `agentfront cli doctor` runs against any CLI. Each bundle corresponds to one of the principles above:

1. **structure** — argparse discipline and project layout.
2. **learnability** — a `learn` affordance that satisfies the CLI principle.
3. **json** — machine-readable output, so agents parse structure not prose.
4. **errors** — propagation with remediation, no tracebacks.
5. **explain** — global addressable markdown docs, per the HTTP principle applied to the CLI surface.
6. **overview** — descriptive snapshot of the surface; *what is present*.
7. **doctor** — diagnosability with actionable remediation; *what is wrong, and how to fix it*.

See [`rubric.md`](./rubric.md) for the exact checks and severities. agentfront itself is required to pass — the `tests/test_self_doctor.py` acceptance gate blocks any regression.

## See also

- [agentculture.md](./agentculture.md) — the org, membership model, and project list.
- [rubric.md](./rubric.md) — the seven-bundle rubric, concrete check list.
- [../CLAUDE.md](../CLAUDE.md) — agentfront stack choices and common commands.
- [../README.md](../README.md) — install and quick-start.
