# Build Plan — agentfront ships as an importable runtime: add it as a dependency, point it at your markdown and your functions, and you get an agent-first MCP server and a discoverable markdown HTTP doc-site — configurable, batteries-included, no hand-rolled surfaces

slug: `agentfront-ships-as-an-importable-runtime-add-it-a` · status: `exported` · from frame: `agentfront-ships-as-an-importable-runtime-add-it-a`

> agentfront ships as an importable runtime: add it as a dependency, point it at your markdown and your functions, and you get an agent-first MCP server and a discoverable markdown HTTP doc-site — configurable, batteries-included, no hand-rolled surfaces

## Tasks

### t1 — Core App + single-source-of-truth registry: agentfront.App where docs and tools are declared once into one internal registry that every surface reads from

- covers: c16, h3, c5
- acceptance:
  - agentfront.App registers docs and tools into ONE internal registry; a test asserts no second store exists and every surface reads the same instance
  - register-then-remove a doc-or-tool drops it from the registry's single enumeration (add-then-remove test)
  - surfaces can only enumerate from the registry; a test confirms no side-channel path lets a surface present an item absent from the registry

### t2 — HTTP surface: App serves each registered markdown doc as a page plus an auto-generated /sitemap.xml, markdown+sitemap only

- depends on: t1
- covers: c14, h1, c6, h10
- acceptance:
  - App's http surface serves each registered .md as a GET-able page and /sitemap.xml enumerates EXACTLY the registered docs — fetched by a test with zero server code in the host config
  - served output is markdown + sitemap (+optional llms.txt) only: a test asserts no HTML templating, no asset pipeline, no client-side JS

### t3 — MCP surface: registering a plain Python function exposes it as an MCP tool via the official mcp SDK, name/description/schema derived from signature+docstring

- depends on: t1
- covers: c15, h2, c7
- acceptance:
  - an in-process MCP client lists and invokes a registered function as a tool, with zero MCP-protocol code in the host; name/description/input-schema derive from the signature+docstring
  - MCP server is built on the official mcp SDK (added to deps) and exposes ONLY registered functions — listed tool set equals registered set

### t4 — CLI surface: App yields an argparse CLI with learn + doctor verbs derived from the same registry (supports the all-three-surfaces assembly)

- depends on: t1
- acceptance:
  - App.cli() produces an argparse CLI whose 'learn' enumerates the registered docs/tools, needing no per-host argparse code — asserted by invoking learn in a test

### t5 — Retire the cli cite scaffolder + manifest->three-surfaces generation; migrate README and docs/agent-first.md to the runtime model

- depends on: t1, t3
- covers: c4, h8
- acceptance:
  - the cli cite scaffolder + manifest-generation code are removed; 'agentfront cli cite' no longer exists and the package builds + imports without it
  - README and docs/agent-first.md present import->config->three-surfaces as the shipped model; a doc-check asserts nothing still describes cli cite/manifest-generation as current behavior, and the before-state matches the retired surface

### t6 — doctor reframed onto the LIVE surfaces: audits sitemap presence, MCP menu size vs the opinionated threshold, and the learn affordance, each with actionable remediation

- depends on: t1, t3
- covers: h11
- acceptance:
  - doctor reports pass on a healthy App, and fails with an actionable remediation when (a) the sitemap is absent, (b) the learn affordance is missing
  - exceeding the MCP tool-count threshold yields a doctor WARNING (not silent pass, not hard error) — asserted by registering > threshold tools

### t7 — Three-surface assembly: one App instance yields CLI, MCP server, and HTTP app from one call each, with no surface-specific re-declaration

- depends on: t2, t3, t4
- covers: c19, h5
- acceptance:
  - a single App produces all three surfaces via one documented call each, no re-declaration of docs/tools per surface
  - the three surfaces AGREE: CLI learn listing == MCP tool list == HTTP sitemap for a given App (asserted by a test)

### t8 — Cross-surface anti-drift + producer/consumer integration tests proving both audiences are real

- depends on: t7
- covers: h9, c2, h6
- acceptance:
  - anti-drift: no code path makes any surface present an item absent from the registry — proven by failing to surface an unregistered item on each of the three surfaces
  - round-trip: a PRODUCER stands up the surfaces from an App; a CONSUMER uses only an HTTP fetch (sitemap+page) and an MCP client (list+call) with no bespoke glue

### t9 — Dogfood: agentfront serves its OWN CLI+MCP+HTTP from its own in-repo App config, gated in CI

- depends on: t7, t6
- covers: c1, h4, c8
- acceptance:
  - agentfront serves its own three surfaces from its own App config (its docs/ + a chosen tool set) — the full import->config->live round-trip
  - a CI job asserts all three of agentfront's own surfaces come up and agree (sitemap == MCP tools == CLI learn), failing the build on drift

### t10 — Quickstart + worked-example third package that imports agentfront and serves all three surfaces in a tiny config

- depends on: t7, t9
- covers: c3, h7, h12
- acceptance:
  - a worked-example third package under examples/ imports agentfront and serves all three surfaces from a config that is <=30 lines with zero server/protocol code — measured by a test
  - the quickstart is exercised by a test that boots the example's three surfaces and confirms HTTP fetch + MCP list/call + CLI learn all work

## Risks

- [unknown_nonblocking] MCP transport: stdio-first vs streamable-HTTP/SSE (or both) — undecided (task t3)
- [unknown_nonblocking] HTTP server impl: stdlib http.server (leaning, zero outside dep) vs starlette/uvicorn (outside-org, approval-gated) (task t2)
- [unknown_nonblocking] Fate of the teken compatibility wrapper + existing agentfront/cite/ code once the scaffolder is retired (task t5)
- [unknown_nonblocking] Same-wave file contention on pyproject.toml and agentfront/__init__.py — operator must verify file-disjointness before fan-out (waves are formally parallel only)
- [follow_up] Declarative config file (toml/yaml) as a secondary config surface
- [follow_up] Serve learn/doctor over MCP and HTTP too (doctor-on-every-surface applied to the runtime)
