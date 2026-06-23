# agentfront ships as an importable runtime: add it as a dependency, point it at your markdown and your functions, and you get an agent-first MCP server and a discoverable markdown HTTP doc-site — configurable, batteries-included, no hand-rolled surfaces

> agentfront ships as an importable runtime: add it as a dependency, point it at your markdown and your functions, and you get an agent-first MCP server and a discoverable markdown HTTP doc-site — configurable, batteries-included, no hand-rolled surfaces

## Audience

- Two-sided: PRODUCERS are Python tool authors (AgentCulture-org first, anyone second) who want to expose their tool to agents; CONSUMERS are the AI agents that hit the resulting MCP server and markdown HTTP site

## Before → After

- Before: Today agentfront is a build-time scaffolder: it emits reference trees into .agentfront/ for the author to own and adapt (cite-don't-import). MCP and HTTP surfaces are 'not implemented yet (planned v0.4/v0.5)'. Authors wanting MCP/HTTP today build them by hand, inconsistently; agent-first discipline is only AUDITED after the fact via cli doctor + rubric
- After: A tool author adds 'agentfront' as a dependency, writes a small config (which markdown to serve, which functions to expose as MCP tools), and gets a running MCP server + markdown+sitemap HTTP site — neither surface hand-rolled, both agent-first by construction

## Why it matters

- Importable runtime EXECUTES the agent-first discipline instead of only auditing it — the surfaces cannot drift from best practice because agentfront IS the surface, not a one-time code emission. It also lowers the bar: configure once, don't scaffold-and-maintain forever

## Requirements

- HTTP: importing agentfront and pointing it at a directory of markdown yields an HTTP server that serves each .md as a page plus an auto-generated sitemap, with zero HTTP/server code written by the author
  - honesty: An author serves a directory of markdown as a navigable site (pages + sitemap) without writing any HTTP/server code — proven by agentfront serving its own docs/ this way
- MCP: registering a plain Python function with agentfront exposes it as an MCP tool (name, description, schema derived from the signature/docstring), with zero MCP-protocol code written by the author
  - honesty: A plain Python function becomes a callable MCP tool by registration alone — proven by an MCP client listing and invoking it, no protocol code in the host
- SSOT: one code-first config object is the single place a doc-or-tool is declared; the MCP menu and the HTTP pages both DERIVE from it, so the two surfaces cannot list divergent sets; serving both is one call
  - honesty: There is exactly one declaration site per doc-or-tool; deleting an entry removes it from BOTH the MCP menu and the HTTP site; no second registry can drift
- Host import yields ALL THREE agent-first surfaces — CLI (argparse with learn+doctor), MCP server, and HTTP markdown+sitemap site — every one derived from the single code-first config (SSOT)
  - honesty: A single config produces all three surfaces, and they agree: the CLI 'learn', the MCP tool list, and the HTTP sitemap enumerate the SAME set of docs/tools — proven by agentfront serving its own three surfaces from one config

## Honesty conditions

- The shipped library delivers the full round-trip: import -> small config -> both an MCP server and a markdown+sitemap HTTP site go live, demonstrated by agentfront serving its own docs/ and MCP this way
- Both sides are real: a PRODUCER stands up the surfaces from import, AND a CONSUMING agent discovers+uses them with only a fetch tool / MCP client — neither side needs bespoke glue
- The 'small config' is genuinely small: agentfront's own setup fits in well under ~30 lines and writes zero server/protocol code
- The described 'today' is accurate at pivot time: MCP/HTTP are unimplemented and cli cite/doctor are the only shipped surface — verifiable against the current README and code
- Drift is structurally impossible, not merely discouraged: there is no code path by which any surface can present a doc/tool the config did not declare
- The HTTP output is markdown + sitemap (+ optional llms.txt) only: no HTML templating engine, no asset pipeline, no client-side JS in what is served
- Menu minimalism is enforced in code: exceeding the opinionated tool-count threshold raises a doctor warning, not silent acceptance
- agentfront serves its OWN three surfaces from its own config in CI, AND a from-scratch third package reproduces it via a documented quickstart — both are tested

## Success signals

- agentfront dogfoods itself: agentfront's own MCP server + HTTP doc-site are served BY agentfront-the-library from its own docs/. And a third package can 'import agentfront' + write a small config and serve both surfaces with no bespoke server code

## Scope / boundaries

- Not a general web framework: the HTTP surface serves markdown pages + a sitemap (and maybe a /llms.txt), not arbitrary HTML, templating, or a SPA
- Not a maximal MCP exposer: the menu stays opinionated-minimal; growing past a threshold warns, mirroring today's rubric principle

## Non-goals

- Not authentication/multi-tenant hosting/CDN concerns — it runs a local/process-level server you can put behind your own proxy; deployment is the host's problem

## Assumptions

- The single-source-of-truth idea survives the pivot: one registration of a function/doc drives BOTH its MCP tool exposure AND its HTTP doc page, so the two surfaces can't disagree

## Decisions

- The configuration entry point is a Python API: 'import agentfront; app = agentfront.App(...)' with markdown source(s) and tool functions registered in code — because the announcement says 'a package imports agentfront'. A declarative file (toml/yaml) is a possible secondary surface, parked
- agentfront becomes a runtime framework that host packages IMPORT (not a generator they cite). Policy reconciliation: importing agentfront is SANCTIONED within the AgentCulture org; importing dependencies from OUTSIDE the org remains avoided and needs explicit approval as an exception. This constrains agentfront's OWN dependency footprint (favor stdlib; any outside dep needs approval)
- The 'cli cite' scaffolder and the manifest->three-surfaces GENERATION vision are RETIRED. The rubric/doctor discipline is preserved by reframing it onto the runtime: doctor audits the LIVE served surfaces (sitemap present, MCP menu under threshold, learn affordance), not emitted files
- MCP surface is built on the official 'mcp' Python SDK — granted as the FIRST sanctioned outside-org dependency exception under c17. (HTTP impl stays parked but defaults toward stdlib, since no further outside dep was approved.)

## Hard questions (all resolved at convergence)

> These three were raised as **blocking** during interrogation and resolved by the user's decisions before export. (devague's exporter currently renders hard questions without their `resolved` flag — these are *not* open.)

- ~~Fate of the SHIPPED surface — `cli cite` scaffolder, the manifest→three-surfaces vision, and rubric/doctor?~~ → **Resolved (c18):** generator retired; rubric/doctor reframed onto the live runtime surfaces.
- ~~Contradiction with the standing 'cite, don't import' policy (CLAUDE.md, docs/agent-first.md, docs/skill-sources.md)?~~ → **Resolved (c17):** importing agentfront is sanctioned *within* the AgentCulture org; importing deps from *outside* the org stays avoided (approval-gated exception).
- ~~Is a runtime framework a sanctioned exception, or does this rewrite org policy?~~ → **Resolved (c17):** sanctioned in-org exception, not an org-wide policy rewrite.

## Open / follow-up

Parked unknowns (non-blocking — to settle in /spec-to-plan):

- **MCP transport** — stdio vs streamable-HTTP/SSE (or both). Likely stdio-first.
- **HTTP server implementation** — stdlib `http.server` (zero-dep, agent-first minimalism) vs starlette/uvicorn (heavier, outside-org → approval-gated). Default leaning: stdlib, since only the `mcp` SDK was approved.
- **Fate of the `teken` compatibility wrapper** and the existing `agentfront/cite/` generation code once the scaffolder is retired.
- Declarative config file (toml/yaml) as a secondary surface alongside the Python API.
- Whether learn/doctor affordances are themselves served over MCP and HTTP (doctor-on-every-surface pillar applied to the runtime).
