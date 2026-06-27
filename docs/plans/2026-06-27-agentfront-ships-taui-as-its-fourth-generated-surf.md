# Build Plan — agentfront ships TAUI as its fourth generated surface: one source of truth renders to JSON (the agent baseline), TUI/ANSI (the human terminal), and markdown (readable) — the JSON mirror exposes stable ids, selectors, and available_actions so an agent can drive and test the exact UI a human uses

slug: `agentfront-ships-taui-as-its-fourth-generated-surf` · status: `exported` · from frame: `agentfront-ships-taui-as-its-fourth-generated-surf`

> agentfront ships TAUI as its fourth generated surface: one source of truth renders to JSON (the agent baseline), TUI/ANSI (the human terminal), and markdown (readable) — the JSON mirror exposes stable ids, selectors, and available_actions so an agent can drive and test the exact UI a human uses

## Tasks

### t1 — Add agentfront/taui/state.py: TAUIState dataclass tree (header, panels, zones, popups, status, work, focus) with to_dict/from_dict

- covers: c1, h1
- acceptance:
  - from_dict(to_dict(s)) == s for a representative state and json.dumps(state.to_dict()) never raises (pure dict/list/str/int/float/bool/None)
  - every panel/popup/zone node carries a stable string id; state is the single source — no view-specific field exists

### t2 — Add agentfront/taui/events.py: event union (UserInput, KeyPress, SelectorAction, Tick, Dismiss) with JSONL dumps/loads and a from_dict dispatcher

- acceptance:
  - loads_events(dumps_events(evs)) round-trips a representative event list; an unknown 'type' raises a structured ValueError
  - SelectorAction carries a selector string (+optional args); KeyPress carries a key name — both first-class

### t3 — Add agentfront/taui/derive.py: registry-derived baseline TAUIState from an App (panels from ToolEntry.group; available_actions from app.list_tools()+app.list_commands(); selectors from dotted paths)

- depends on: t1
- covers: c3
- acceptance:
  - make_baseline(app) yields one panel per top-level group plus a root panel; every tool AND host command appears exactly once as an action with a dotted-path id (e.g. 'feedback.record')
  - aliases produce alternate selectors mapping to the same action id; App.name/version/description populate the header

### t4 — Add agentfront/taui/selectors.py: resolve(state, selector) -> node and all_selectors_resolve(state) -> bool

- depends on: t1
- covers: h2
- acceptance:
  - resolve() returns the node for every advertised selector; an unknown selector raises AgentfrontError(code=EXIT_USER_ERROR)
  - all_selectors_resolve(state) is True for a registry-derived baseline; a test asserts every advertised selector resolves

### t5 — Add agentfront/taui/reducer.py: reduce(state, event) -> state (pure) — the SINGLE fold for both agent SelectorAction and human KeyPress

- depends on: t1, t2
- covers: h3
- acceptance:
  - a SelectorAction('x') and the KeyPress sequence selecting the same action produce an EQUAL resulting state (one reducer, no agent-only/human-only path)
  - reduce is pure: same (state,event) -> equal next state; the input state object is not mutated

### t6 — Add agentfront/taui/render/ansi.py: render_ansi(state) -> str (stdlib-only, deterministic)

- depends on: t1
- covers: c1
- acceptance:
  - render_ansi is deterministic: same state -> byte-identical string; no clock/random; zero third-party imports
  - the frame shows header, panels, the focused-node marker, and the status line, all derived solely from state

### t7 — Add agentfront/taui/render/markdown.py: render_markdown(state) -> str (stdlib-only, deterministic)

- depends on: t1
- acceptance:
  - render_markdown is deterministic and stdlib-only; same state -> identical markdown
  - markdown lists panels and available_actions in human-readable form derived solely from state

### t8 — Add agentfront/taui/mirror.py: serialize(state) -> JSON mirror dict with taui_version, stable ids, and available_actions DERIVED from the state tree

- depends on: t1, t4
- covers: h2, h5
- acceptance:
  - available_actions is built FROM the state tree (not a separate list); every action selector resolves via selectors.resolve — asserted for a baseline AND an extended state
  - the mirror dict is JSON-serializable and describes the SAME screen as render_ansi for the same state (co-equal outputs of one state)

### t9 — Add agentfront/taui/diagnose.py: cross-render invariant checker over (mirror, ansi, markdown) of one state

- depends on: t6, t7, t8
- covers: h4
- acceptance:
  - diagnose(state) passes when mirror/ANSI/markdown agree on panels/actions/focus from the same state; it FAILS a deliberately desynced fixture
  - diagnose runs clean on every tui_sim-style snapshot in the test suite

### t10 — Add agentfront/taui/driver.py: a thin reference TTY driver that folds keystrokes through reduce and repaints render_ansi

- depends on: t5, t8
- acceptance:
  - the driver reads a key, applies reduce(state, KeyPress), repaints render_ansi(state); unit-testable with a scripted key list (no real TTY)
  - thin reference only (no production live-loop): a scripted N-keystroke run yields the same final state as folding the same events via reduce directly

### t11 — Wire app.taui()/taui_mirror()/taui_driver() accessors in agentfront/app.py (lazy imports, mirroring app.cli()/mcp_server()/http_app())

- depends on: t3, t8, t10
- covers: c3
- acceptance:
  - app.taui() returns the registry-derived baseline; app.taui_mirror() its JSON mirror; app.taui_driver() the reference driver — all lazy-imported like the other surfaces
  - accessors add NO import-time third-party dependency and work on an App with only @app.tool/add_command registrations

### t12 — Extend agentfront/serve.py (Surfaces/build_surfaces/surface_inventory/surfaces_agree) + the dogfood gate to include TAUI

- depends on: t11, t9
- covers: h4
- acceptance:
  - surface_inventory(app) includes TAUI actions; surfaces_agree(app) returns False if TAUI available_actions selectors diverge from the registry tool/command paths
  - the existing dogfood gate runs the TAUI cross-render diagnose and passes for the dogfood App

### t13 — Add a stdlib-only / boundary guard test (no third-party runtime dep from TAUI; not a general TUI framework)

- depends on: t1
- covers: c5, h7
- acceptance:
  - a test imports agentfront.taui and asserts no third-party module (textual/rich/blessed) is imported; pyproject adds no new base dep and no [taui] extra
  - the package exposes only the agent-first contract (state/mirror/render/reduce/selector-dispatch); a test pins the public API surface

### t14 — Add an end-to-end flow test: an agent completes a multi-step flow via mirror+selector dispatch; a human via keystrokes; assert identical final state

- depends on: t11
- covers: c2, c6, h3, h5
- acceptance:
  - a scripted multi-step flow driven ONLY by reading taui_mirror + dispatching selectors reaches the SAME final state as the equivalent human keystroke sequence (byte-identical to_dict())
  - at each step the mirror's available_actions suffices for the agent to choose the next action without out-of-band knowledge

### t15 — Add a colleague-parity conformance test: run colleague's TAUI behavioral tests unchanged against agentfront's implementation

- depends on: t11
- covers: c4, h6
- acceptance:
  - ported colleague TAUI behavioral tests (state round-trip, mirror available_actions, reducer, diagnose) pass UNCHANGED against agentfront.taui
  - any colleague-specific shape that doesn't map is recorded as a follow-up risk, not silently dropped

## Risks

- [follow_up] colleague-side migration: colleague imports agentfront.taui and deletes its hand-built tui/ (separate repo — file an agentculture/colleague issue)
- [unknown_nonblocking] complex param widgets deferred: derive_input_schema maps only base types; Optional/Union/generics fall back to string, so rich input forms are out of v1 scope
