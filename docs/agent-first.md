# Agent First

**Agent First** is AgentCulture's guiding paradigm: when you design software, *the primary consumer is an AI agent, not a human*. Every other decision — CLI shape, docs layout, protocol menu, error messages — flows from that reversal.

This document explains what the paradigm means, how it manifests in each interface surface, and why `afi-cli` is the foundational tool for the rest of AgentCulture to ship it.

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

## Why `afi-cli` is foundational

Every AgentCulture tool eventually wants all three surfaces. Without a shared scaffolder, each project would:

1. Re-implement the three surfaces from scratch, inconsistently.
2. Drift over time — one project's CLI is more agent-friendly than another's, for no reason beyond author preference.
3. Miss the baked-in best practices — the next `culture`-sized project might ship a CLI without `learn`, or an MCP with forty tools, or an HTTP doc site without a sitemap.

`afi-cli` solves this once:

- One manifest per tool describes verbs, arguments, outputs, and docs.
- The scaffolder emits the CLI, the MCP server, and the HTTP site from that manifest.
- The discipline is enforced by the generator, not by author discipline:
  - CLI always has `learn`.
  - MCP menu is filtered to the declared minimal set, with warnings when the menu grows past an opinionated threshold.
  - HTTP docs are markdown + sitemap by construction.

Ship a new AgentCulture tool → write its manifest → `afi scaffold` → you have three agent-ergonomic surfaces, consistent with every other project in the org. That's the *foundational* claim: AgentCulture's surface-area compounds instead of fragmenting.

## Dogfooding

`afi-cli` itself is required to use its own output. Its current CLI is hand-written — unavoidable while the generator doesn't exist. Once the manifest schema and generator are designed, the next step is to regenerate `afi-cli`'s own CLI from its own manifest and make the generated artifact the canonical source. The hand-written CLI in `afi/cli/` then becomes the reference the generator must reproduce byte-for-byte — a self-validating loop.

Same loop applies to the MCP and HTTP surfaces when they're added.

## Agent First is a discipline, not a switch

Every feature proposal in AgentCulture has to pass an Agent First review:

- Does this add a menu item an agent now has to reason about?
- Is the behavior introspectable, or does it require reading source?
- Can an agent discover it from a single fetch?
- Does the failure mode return something actionable, or does it require another round-trip?

If the answer to any of those is "no," the feature either changes shape or doesn't ship. That's what "Agent First in everything we do" means in practice.

## See also

- [agentculture.md](./agentculture.md) — the org, membership model, and project list.
- [../CLAUDE.md](../CLAUDE.md) — afi-cli stack choices and common commands.
- [../README.md](../README.md) — install and quick-start.
