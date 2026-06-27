# agentfront ships TAUI as its fourth generated surface: one source of truth renders to JSON (the agent baseline), TUI/ANSI (the human terminal), and markdown (readable) — the JSON mirror exposes stable ids, selectors, and available_actions so an agent can drive and test the exact UI a human uses

> agentfront ships TAUI as its fourth generated surface: one source of truth renders to JSON (the agent baseline), TUI/ANSI (the human terminal), and markdown (readable) — the JSON mirror exposes stable ids, selectors, and available_actions so an agent can drive and test the exact UI a human uses

## Audience

- AI agents consuming a tool's interface (primary) and the humans operating the same tool (co-equal); plus tool authors who define one App config and want a fourth surface for free

## Before → After

- After: From a single agentfront App config, a tool author gets a TAUI surface: the same state renders to a human ANSI/TUI terminal, a readable markdown view, and an agent-facing JSON mirror with stable ids + selectors + available_actions; an agent drives the exact UI a human uses via selector-dispatched actions and an event log

## Why it matters

- Today an agent can use CLI/MCP/HTTP but cannot operate or test a tool's interactive terminal UI; colleague proved one-state/many-renders TAUI by hand but every consumer would re-build it. agentfront already renders 3 surfaces from one config — TAUI is the missing fourth, and lifting it into agentfront means consumers (colleague first) get it instead of hand-maintaining it

## Honesty conditions

- One state object is the sole source: the JSON mirror, the ANSI/TUI render, and the markdown render all derive from a single to_dict() — change state once and all three change; a test asserts no view-specific source of truth
- available_actions in the JSON mirror is DERIVED from the state tree (every advertised selector resolves to a real node) so it cannot drift from what the UI offers; a test asserts every selector resolves
- The agent-facing JSON mirror and the human-facing ANSI render are co-equal first-class outputs of the SAME state — neither is a second-class afterthought; a test exercises both from one state and asserts they describe the same screen
- An agent's selector-dispatched action and a human's keystroke fold through the SAME reducer into the SAME next state — no agent-only or human-only state path; a test drives one flow both ways and asserts identical resulting state
- Lifting TAUI into agentfront removes per-consumer reimplementation: colleague can delete its hand-built tui/ and import agentfront's instead with behavior preserved — colleague's lifted TAUI tests pass unchanged against agentfront's implementation
- agentfront's base package gains NO third-party runtime dependency from TAUI (stdlib-only core + JSON mirror); any richer-renderer path is an opt-in extra, never a base dependency
- A diagnose-style cross-render invariant runs clean on every snapshot: the JSON, ANSI, and markdown mirrors agree on render/layout/focus/input-routing

## Success signals

- An agent completes a multi-step interactive flow using ONLY the JSON mirror + selector dispatch that a human completes via keystrokes, and a deterministic test proves both paths reach byte-identical state (colleague's 'same state -> same frame' + tui_sim cross-check is the proof model); agentfront dogfoods its own TAUI; colleague can cite agentfront's TAUI instead of hand-maintaining tui/

## Scope / boundaries

- Not a general-purpose TUI framework competing with textual/rich/blessed, not pixel/GUI rendering, and not a replacement for the CLI/MCP/HTTP surfaces — TAUI is additive. Scope is the agent-first contract: one state, deterministic renders, a JSON mirror with stable ids/selectors/available_actions, and selector-dispatched actions over an event reducer

## Decisions

- DELIVERY MODEL = IMPORT, NOT SCAFFOLD: agentfront is an importable runtime library that RENDERS the TAUI surface at runtime from the App config (e.g. app.taui()/app.taui_mirror()/app.taui_driver()), exactly like app.cli()/app.mcp_server()/the HTTP site. It does NOT scaffold TAUI source files into the consumer for them to own. This is the scalable method per the runtime pivot.
- RENDERING DEP = STDLIB-ONLY ANSI: hand-rolled pure-Python ANSI/markdown renderers, zero third-party (colleague's precedent). Honors AgentCulture's outside-org dep policy; the JSON mirror (agent baseline) needs no UI lib. Resolves q1.
- STATE PROVENANCE = HYBRID: agentfront auto-derives a BASELINE cockpit from the App command registry (commands -> panels/actions/selectors), and the author can EXTEND it with UI-specific structure (popups, zones, custom panels, work feeds). Resolves q2.
- V1 SCOPE = PURE CORE + THIN REFERENCE DRIVER: ship state+reduce+render-tiers+JSON mirror+selector dispatch+replay/snapshot + a thin reference TTY driver; defer a production-grade live loop (colleague found live-wiring the most error-prone). Resolves q3.
- COLLEAGUE TIE-IN = LIFT & GENERALIZE: extract colleague's proven tui/ (state, events, reducer, taui mirror, selectors, render tiers, diagnose) into agentfront, generalize to the registry-derived/import model; colleague then imports agentfront's TAUI and deletes its copy. Resolves q4 (risk).

## Hard questions

> **All four resolved by the user on 2026-06-27** (recorded as Decisions above).
> The exporter renders hard questions without their `resolved` flag (known
> devague lossiness — `devague-hard-question-resolve-gap`), so resolution status
> is restored here by hand.

- **q1 — RENDERING DEP** (blocking) — *RESOLVED → stdlib-only hand-rolled ANSI.*
  stdlib-only ANSI vs the `textual`/`rich` PyPI library behind an opt-in `[taui]`
  extra. Chose stdlib-only: honors AgentCulture's outside-org dep policy, keeps
  agentfront pure-stdlib like its CLI core, and the JSON mirror (agent baseline)
  needs no UI lib. A richer-renderer extra remains a future, opt-in possibility.
- **q2 — STATE PROVENANCE** (blocking) — *RESOLVED → hybrid.* registry-derived
  vs author-supplied vs hybrid. Chose hybrid: agentfront auto-derives a baseline
  cockpit from the App command registry, and the author extends it with
  UI-specific structure (popups, zones, custom panels, work feeds).
- **q3 — V1 SCOPE** (blocking) — *RESOLVED → pure core + thin reference driver.*
  full live interactive TTY driver vs pure deterministic core only. Chose core +
  thin reference driver; a production-grade live loop is deferred (colleague found
  live-wiring the most error-prone part: inert popup buttons / quit-traps).
- **q4 — COLLEAGUE TIE-IN** (risk, non-blocking) — *RESOLVED → lift & generalize.*
  extraction vs greenfield. Chose lift-and-generalize: extract colleague's proven
  `tui/`, generalize to the registry-derived/import model, then colleague imports
  agentfront's TAUI and deletes its copy.
