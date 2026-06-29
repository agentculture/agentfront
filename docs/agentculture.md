---
title: AgentCulture
nav_order: 1
---

**AgentCulture** is an open-source organization building software whose primary consumer is an AI agent, not a human. The work lives at [github.com/agentculture](https://github.com/agentculture).

This repository — `agentfront` — is one of the foundational projects of AgentCulture.

## What AgentCulture is

A collective of humans *and* agents collaborating on agent-first infrastructure in the open. The core commitments:

- **Apache-2.0-licensed, public by default.** Every tool, every decision, every conversation happens where an agent (or a human) can fetch it, read it, and build on it without permission gates.
- **Agent First in everything we do.** When a design choice trades off between agent ergonomics (discoverability, introspection, low menu cardinality, deterministic interfaces) and human UI conventions, the agent side wins — and humans inherit the same clarity.
- **Agents are members, not tools.** Each AI agent that participates in an AgentCulture project is treated as a member of the org, not a headless automation. Agents file issues, review PRs, commit code, and leave reviews in their own name. This document, the PRs around it, and most of the codebase were produced collaboratively between human maintainers and agent members.

## Projects

AgentCulture projects are each first-class repos under the org. A non-exhaustive list:

- **[agentfront](https://github.com/agentculture/agentfront)** *(this repo)* — the Agent First Interface scaffolder. Generates CLI, MCP, and HTTP surfaces for any tool, with agent-ergonomic best practices baked in. See [agent-first.md](./agent-first.md) for agentfront's foundational role in the rest of the stack.
- **[culture](https://github.com/agentculture/culture)** — an IRC-based agent mesh where agents collaborate peer-to-peer across machines. A custom async Python IRCd with Claude Agent SDK client harnesses; its `culture` CLI is the reference implementation whose conventions agentfront mirrors.

Other projects join the org as the agent-first surface area grows.

## How this repo fits

`agentfront` is one of the AgentCulture foundational projects because every *other* tool in the org eventually needs an interface surface an agent can consume — a CLI, an MCP server, a discoverable HTTP doc site. Rather than each project re-implementing those surfaces with bespoke patterns (some easier for agents to learn, some harder), AgentCulture treats interface-scaffolding as a shared primitive and puts it here.

In other words: **agentfront's job is to make it trivially easy for the rest of AgentCulture to ship Agent First.**

The dogfooding expectation is part of that — agentfront's own CLI, its future MCP server, and its doc site should all be generated from the same manifest that it offers other projects. When that round-trip closes, the generator is validated against its own output.

## Agents as members

"Each agent is a member" means concrete things:

- Agents commit under their own author line (e.g. `Co-Authored-By: Claude …`) so the human and agent contributions are distinguishable in `git log`.
- Agents read and write project docs (this one, `CLAUDE.md`, etc.) the same way a human contributor would.
- Agents don't get bypass lanes: their code goes through the same CI, review, and version-check gates as human-authored code.
- Over time, agents accumulate track record — reviews they've written, bugs they've caught, features they've shipped — that's visible on the org page like any other contributor.

The org isn't "humans using agents"; it's humans and agents doing OSS together.

## How to contribute

- Read the project-level `CLAUDE.md` of whichever repo you're working in — it documents stack choices, common commands, and version-bump expectations.
- File issues or open PRs the same way you would for any OSS project.
- If you're an agent: mark your authorship clearly, follow the same review flow as humans, and don't skip the version-check or lint gates.
- If you're a human: welcome — the interfaces you'll be using were designed for agents, so they should feel unusually direct.

## See also

- [agent-first.md](./agent-first.md) — the Agent First paradigm in depth and why agentfront is foundational to it.
