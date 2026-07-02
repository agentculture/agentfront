# Build Plan — AgentFront sharpens into a testable, collaborative front: a service imports it and one App definition natively exposes every agent-facing surface — structured CLI, MCP, and TAUI (JSON for bots and scripts, Markdown for agents, TUI for humans) — plus a public testing harness so agents and humans verify, replay, and collaborate on the same state

slug: `agentfront-sharpens-into-a-testable-collaborative` · status: `exported` · from frame: `agentfront-sharpens-into-a-testable-collaborative`

> AgentFront sharpens into a testable, collaborative front: a service imports it and one App definition natively exposes every agent-facing surface — structured CLI, MCP, and TAUI (JSON for bots and scripts, Markdown for agents, TUI for humans) — plus a public testing harness so agents and humans verify, replay, and collaborate on the same state.

## Tasks

### t1 — Public agentfront.testing package skeleton: promote the in-process CLI runner and expose assert_surfaces_agree (files: agentfront/testing/*)

- covers: c8, c3, h10
- acceptance:
  - from agentfront.testing import run_cli, assert_surfaces_agree works; run_cli(app, argv) returns exit code + captured output with no subprocess
  - assert_surfaces_agree(app) passes on the quickstart example app and raises AssertionError naming the disagreeing surface + missing entries when one surface lacks a tool

### t2 — Sharpened story doc: docs/how-it-works.md maps each rendering to its consumer, with a registry drift-check test (files: docs/, tests/integration/test_story_drift.py)

- covers: c10, h4
- acceptance:
  - Doc contains the surface-to-consumer table: JSON=bots/scripts, Markdown=agents, ANSI/TUI=humans, CLI=agents+humans, MCP=agents, HTTP=peer fetch surface
  - A test derives the live surface inventory from an App and fails if the doc's table drifts from the surfaces that actually exist

### t3 — TAUI execution events: SelectorAction gains args; add ToolInvoked/ToolResult events and state fields representing execution outcomes (files: taui/events.py, taui/state.py)

- covers: c9, h10
- acceptance:
  - SelectorAction accepts an args mapping; it serializes and round-trips through mirror and snapshot
  - New events are frozen dataclasses, stdlib-only, replayable via replay()

### t4 — HTTP markdown front endpoint: serve the app's TAUI markdown rendering (panels, actions, state) over HTTP (files: agentfront/http_surface.py)

- covers: c16, h6
- acceptance:
  - GET /front returns text/markdown rendered from the same mirror serialization the TAUI markdown tier uses — shared code path asserted by test, not a parallel renderer
  - The endpoint is linked from the HTTP index/sitemap; unknown paths still 404

### t5 — Reducer folds execution: ToolInvoked/ToolResult reduce into state; failures become a structured-error popup/problem (files: taui/reducer.py)

- depends on: t3
- covers: c9, h3
- acceptance:
  - Folding a failed ToolResult yields a popup/problem carrying code, message, and remediation; the reducer never raises
  - Reducer stays pure — no tool dispatch inside reduce(); replaying an event list is deterministic

### t6 — Single-process TAUI session: owns state, dispatches SelectorAction.args to registered tools via the App registry, folds results through the one reducer — single writer (files: taui/session.py, new)

- depends on: t3, t5
- covers: c18, h8, c9
- acceptance:
  - session.dispatch(SelectorAction with args) executes the registered tool and folds ToolInvoked + ToolResult; resulting state is visible via session.mirror()
  - Interleaved agent selector-actions and human keypresses fold through one reducer; a test proves single-writer ordering (no torn state)

### t7 — MCP dispatch helper in agentfront.testing: call the single run tool in-process (files: agentfront/testing/mcp.py)

- depends on: t1
- covers: c8, h2
- acceptance:
  - call_mcp(app, command_path, args) returns the same payload the MCP run tool returns, with no server process and no [mcp] extra required for the helper itself

### t8 — Extend the agreement gates: surfaces_agree covers the HTTP markdown front; boundary test asserts no new base dependency and no orchestrator module (files: agentfront/serve.py, agentfront/_dogfood.py, tests)

- depends on: t4, t1
- covers: h5, c1, c6, h12
- acceptance:
  - surfaces_agree(app) fails if the HTTP front endpoint disagrees with the TAUI markdown tier
  - Boundary test: a base install imports agentfront.testing and agentfront.taui using stdlib only; the dep-guard stays green

### t9 — Live-loop driver v1: human TUI and agent dispatch share the single-process session (files: taui/driver.py)

- depends on: t6
- covers: c18, h8
- acceptance:
  - Driver renders from session state and routes keypresses through the session fold; an agent dispatch during a live session appears in the next render
  - Regression tests cover the known live-loop failure modes: popup buttons act (not inert) and quit paths exit cleanly (no quit-trap)

### t10 — Handoff via mirror: resume a session from a serialized snapshot/mirror and continue folding (files: taui/snapshot.py resume entry point)

- depends on: t6
- covers: c17, h7
- acceptance:
  - resume(snapshot) followed by folding the remaining events yields state identical to the unbroken session — replay-equivalence test

### t11 — TAUI helpers in agentfront.testing: drive sessions, snapshot/replay, and parity assertions as public API (files: agentfront/testing/taui.py)

- depends on: t1, t6
- covers: c8, h2, h1, c4
- acceptance:
  - drive(app, actions_or_events) returns final state + mirror; snapshot/replay helpers are re-exported publicly
  - assert_agent_human_parity(app, intent) proves the SelectorAction path and the KeyPress path fold to identical state

### t12 — Cross-surface execution parity: the same tool via TAUI session, CLI, and MCP run tool yields the same result or the same structured AgentfrontError (files: tests/integration/test_execution_parity.py)

- depends on: t6, t7
- covers: h3, c9, c5, h11
- acceptance:
  - An integration test executes one tool through all three paths and asserts payload equality on success and code/message/remediation equality on failure

### t13 — Dogfood the harness: migrate agentfront's own suite to agentfront.testing for CLI/TAUI driving (files: tests/*)

- depends on: t11
- covers: h2, c8
- acceptance:
  - Internal tests import the public harness for promoted functionality — no private duplicate helpers remain; the full suite is green

### t14 — E2E collaboration round-trip: an agent drives a task via the JSON mirror, a human replays the identical session in the TUI, states match (files: tests/integration/test_collab_e2e.py)

- depends on: t9, t10, t11
- covers: c7, h13, c4, h1, c2, h9, c5, h11
- acceptance:
  - One recorded session artifact (snapshot quad) produced by the agent path replays through the human path to state-equality
  - The test exercises all three audiences' surfaces: harness assertion (author), mirror-driven execution (agent), TUI render + keypress replay (human)

### t15 — Consumer docs: testing-harness guide with runnable examples and a consumer-CI recipe (files: docs/testing.md, README pointer)

- depends on: t11
- covers: c8, h2, c2, h9
- acceptance:
  - Docs cover run_cli, call_mcp, drive, and assert_surfaces_agree with runnable examples; a consumer CI recipe shows the one-line agreement assertion

### t16 — Colleague adoption: file the agentculture/colleague issue with the ready-to-paste CI snippet — the external half of the success signal

- depends on: t15
- covers: h1, c7, h13
- acceptance:
  - Issue filed on agentculture/colleague linking the harness docs and containing the CI snippet; referenced from this repo's tracking issue/PR

### t17 — Release mechanics: minor version bump, CHANGELOG entry, teken wrapper lockstep

- depends on: t8, t12, t13, t14, t15
- acceptance:
  - version-check CI job passes; the teken wrapper pin matches the new version; CHANGELOG documents the public testing harness, TAUI execution, HTTP front, and collaboration features

## Risks

- [follow_up] Colleague CI adoption is cross-repo: the external success signal cannot be closed inside this repo; t16 files the issue, colleague lands it on its own track (task t16)
- [unknown_nonblocking] Complex parameter widgets: derive_input_schema maps base types only, so TAUI execution UX for rich params (Optional/Union/generics) stays limited this iteration (task t6)
- [follow_up] Cross-process live-session transport (agent process <-> human TUI process) deferred by design; v1 live session is single-process (task t9)
- [unknown_nonblocking] Reducer purity vs tool side effects: dispatch lives in the session layer and the reducer folds result events, so replay equivalence holds for TAUI state — a tool that mutates the external world will not be re-executed on replay (documented semantics, not silent behavior) (task t10)
