# AgentFront sharpens into a testable, collaborative front: a service imports it and one App definition natively exposes every agent-facing surface — structured CLI, MCP, and TAUI (JSON for bots and scripts, Markdown for agents, TUI for humans) — plus a public testing harness so agents and humans verify, replay, and collaborate on the same state

> AgentFront sharpens into a testable, collaborative front: a service imports it and one App definition natively exposes every agent-facing surface — structured CLI, MCP, and TAUI (JSON for bots and scripts, Markdown for agents, TUI for humans) — plus a public testing harness so agents and humans verify, replay, and collaborate on the same state.

## Audience

- Service authors (human devs) who want their tool consumable by agents; AI agents that operate the generated fronts; and human operators using the TUI — all three consume the same App.

## Before → After

- Before: agentfront 0.19.x already renders four surfaces (CLI, MCP, HTTP, TAUI) from one App, but the testability story is internal-only: surfaces_agree/_dogfood is agentfront's own gate, tests use private in-process helpers, and consumers get no published harness; TAUI v1 is navigation-only (no tool execution via SelectorAction.args), and the conceptual story still says 'four surfaces' rather than the sharpened 'JSON for bots, Markdown for agents, TUI for humans' framing.
- After: A consumer can (a) define one App, (b) mount it as CLI, MCP, and TAUI with agents driving the same reducer humans do, and (c) import a public agentfront.testing harness to assert in their own CI that their surfaces agree, drive any surface in-process, and snapshot/replay sessions — making agent work reviewable by humans and human intent replayable by agents.

## Why it matters

- Agent-human collaboration needs a shared, verifiable substrate: if the agent's JSON path and the human's TUI path fold through one reducer AND the consumer can prove surface agreement in their own CI, then a human can trust, review, and replay what an agent did — and vice versa — without bespoke glue.

## Requirements

- Ship a public agentfront.testing module: in-process CLI runner, MCP single-run-tool dispatch helper, TAUI driver (fold events/selector-actions and read the mirror), snapshot/replay helpers, and a one-line surface-agreement assertion consumers run in their own CI.
  - honesty: agentfront.testing is documented public API, stdlib-only, and dogfooded: agentfront's own suite migrates to it for CLI/TAUI driving so the harness cannot drift from what internal tests exercise.
- Close TAUI's navigation-only gap: SelectorAction carries args and dispatches registered tools through the reducer, so an agent can execute work (not just navigate) via the JSON mirror — the same execution path a human keystroke flow reaches.
  - honesty: Executing the same tool via SelectorAction.args, via the CLI, and via the MCP run tool yields the same result or the same structured AgentfrontError {code,message,remediation}; TAUI execution failures land in the mirror as state (popup/problem), never a crash.
- Sharpen the conceptual story in docs: one canonical 'how it works' page mapping each rendering to its consumer (JSON = bots/scripts, Markdown = agents, ANSI/TUI = humans, CLI = agents+humans, MCP = agents), replacing the flat 'four surfaces' framing.
  - honesty: The story doc's surface-to-consumer table is checked against the live registry/surface inventory by a test (extend the dogfood gate), so the sharpened story cannot silently drift from the code.
- HTTP serves the front as markdown on request: beyond docs (already text/markdown), add an endpoint exposing the app's TAUI markdown rendering — panels, available actions, state — so a fetch-only agent reads the same markdown view of the tool a terminal agent gets.
  - honesty: The HTTP markdown-front endpoint renders from the same mirror serialization the TAUI markdown tier uses (one code path, not a parallel renderer), and the surface-agreement gate extends to cover it.
- Handoff via mirror: a session serialized to the mirror/snapshot can be resumed — restore state, continue folding events — so an agent can pause and a human picks up (and vice versa) with nothing lost.
  - honesty: Round-trip proven: serialize -> resume -> fold remaining events yields state identical to an unbroken session (replay equivalence), asserted by a public testing-harness helper.
- Live shared session v1 is single-process: one process owns TAUI state and renders the human TUI; the agent participates through that process's dispatch (selector actions), all mutations folding through the one reducer (single writer). Cross-process transport (socket/file) is a follow-up, not this iteration.
  - honesty: Single-writer holds under test: interleaved agent selector-actions and human keypresses in a live session fold through one reducer with no torn renders; the previously-identified live-loop failure modes (inert popup buttons, quit-traps) have explicit regression tests.

## Honesty conditions

- One App definition is genuinely the single source: registering a tool once makes it appear on every mounted surface (CLI, MCP, TAUI mirror/markdown/TUI) with no per-surface code, and the public surface-agreement assertion proves it for consumers, not just for agentfront itself.
- Each audience has a concrete surface it exercises in the shipped result: service authors define the App and run the harness in CI, agents drive JSON/markdown/MCP, humans use the TUI — no audience is aspirational.
- The named gaps are real in 0.19.x and verifiable against the repo: __all__ exports only App/AgentfrontError (no testing toolkit), surfaces_agree is not documented for consumers, and SelectorAction carries no args/execution path.
- Proven by the harness itself: for the same intent, agent path (SelectorAction through the JSON mirror) and human path (KeyPress) fold to identical state, asserted via a PUBLIC helper; and at least one external consumer CI (colleague) runs the surface-agreement assertion.
- The trust chain is testable, not rhetorical: the harness assertions (surface agreement, agent/human path parity, replay equivalence) are exactly the properties the collaboration story depends on.
- The shipped diff adds no new base dependency (the existing dep-guard/boundary test stays green) and introduces no message-bus or orchestrator module.
- Both signals are observable events: a colleague CI run invoking the public harness, and one recorded session artifact replayed to state-equality across the agent and human paths.

## Success signals

- A consumer repo (colleague is the live candidate) imports the public testing harness and asserts surface agreement in its own CI; and one session artifact round-trips: an agent drives a task through the TAUI JSON mirror, a human reviews/replays the identical session in the TUI, states match.

## Scope / boundaries

- Not a web-UI framework and not an agent orchestrator: TAUI stays stdlib-only ANSI/markdown/JSON, collaboration means shared verifiable state (snapshots, replay, one reducer) rather than a message bus or multi-agent runtime, and no new base dependencies are introduced.

## Decisions

- USER (2026-07-02): HTTP remains an equal peer surface in the sharpened story — not repositioned or de-emphasized — with markdown-native support on request.
- USER (2026-07-02): collaboration v1 scope is all three modes — artifact-mediated review (snapshot+replay), handoff via mirror, and live shared session.
- USER (2026-07-02): TAUI tool execution (SelectorAction.args) is in scope for this iteration.

## Open / follow-up

- Complex parameter widgets: derive_input_schema still maps only base types (Optional/Union/generics fall back to string) — TAUI execution UX for rich params stays limited in this iteration. *(unknown, non-blocking; hand-patched: the exporter omits `unknown_nonblocking` items — see frame v1)*
- Colleague-side migration (import agentfront.taui + delete its tui/, tracked as colleague#249) proceeds on its own track; this frame only needs colleague as the success-signal consumer, not its full migration.
- Cross-process live-session transport (agent process <-> human TUI process via socket/file/other) — deferred; v1 live session is single-process by design.
