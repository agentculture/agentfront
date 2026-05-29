---
title: agentfront
nav_order: 0
permalink: /
description: Agent First Interface — scaffold CLI, MCP, and HTTP surfaces for tools whose primary consumer is an AI agent.
---

<!-- markdownlint-disable MD033 -->
<!-- The landing page is all hero / btn-cta / docs-grid components from
     the shared culture design system — Jekyll markdown can't reach
     those CSS classes, so inline HTML is load-bearing. MD033 stays
     disabled for the rest of this file; no re-enable. -->

<div class="hero">
  <p class="hero-label">Agent First Interface</p>
  <h1 class="hero-headline">Scaffold tools your&nbsp;agents read first.</h1>
  <p class="hero-sub">One manifest. Three surfaces — CLI, MCP, HTTP — each shaped by a different agent-ergonomic discipline. One command: <code>agentfront</code>.</p>
  <div>
    <a href="{{ '/agentculture/' | relative_url }}" class="btn-cta btn-cta--primary">What is AgentCulture?</a>
    <a href="{{ '/agent-first/' | relative_url }}" class="btn-cta btn-cta--secondary">The paradigm</a>
  </div>
</div>

## Quickstart

```bash
uv tool install agentfront
agentfront explain agentfront              # top-level map
agentfront overview                 # cross-surface rollup
agentfront learn                    # structured self-teaching prompt for an agent
```

`uv tool install` is the supported install path — not `pip install`.

## The three surfaces

<div class="docs-grid">
  <a class="docs-card" href="{{ '/agent-first/#cli--learnability' | relative_url }}">
    <h3>CLI — learnability</h3>
    <p class="text-muted">A <code>learn</code> affordance so an agent can introspect the tool and author its own usage skill in one shot.</p>
  </a>
  <a class="docs-card" href="{{ '/agent-first/#mcp--minimalism' | relative_url }}">
    <h3>MCP — minimalism</h3>
    <p class="text-muted">A deliberately small menu. Every verb is a decision point; fewer verbs, better calls.</p>
  </a>
  <a class="docs-card" href="{{ '/agent-first/#http--discoverability' | relative_url }}">
    <h3>HTTP — discoverability</h3>
    <p class="text-muted">Markdown pages plus a sitemap. Any agent with a fetch tool can navigate.</p>
  </a>
</div>

<p class="text-muted" style="margin-top:0.75rem">This site ships a <a href="{{ '/sitemap.xml' | relative_url }}">sitemap.xml</a> — that's the HTTP principle applied to agentfront itself.</p>

## Read next

<div class="docs-grid">
  <a class="docs-card" href="{{ '/agentculture/' | relative_url }}">
    <h3>AgentCulture</h3>
    <p class="text-muted">The OSS org, its agents-as-members model, and where agentfront sits inside it.</p>
  </a>
  <a class="docs-card" href="{{ '/agent-first/' | relative_url }}">
    <h3>Agent First</h3>
    <p class="text-muted">The paradigm — the human-vs-agent design reversal and the three interface disciplines that follow from it.</p>
  </a>
  <a class="docs-card" href="{{ '/rubric/' | relative_url }}">
    <h3>The Rubric</h3>
    <p class="text-muted">The mechanical bundles <code>agentfront cli doctor</code> runs against any CLI. agentfront itself has to pass.</p>
  </a>
</div>

## Links

- **Repo:** <https://github.com/agentculture/agentfront>
- **PyPI:** <https://pypi.org/project/agentfront/>
- **Sibling:** [agex-cli](https://culture.dev/agex) — agent *experience* inside a repo (hooks, CI, workflow). agentfront is the agent's *interface* to a tool.
