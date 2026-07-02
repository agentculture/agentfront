# Testing your front — `agentfront.testing`

See [`how-it-works.md`](./how-it-works.md) for the full story: one `App`
renders every surface (CLI, MCP, HTTP, TAUI) from a single registry, and the
same reducer folds both an agent's `SelectorAction`s and a human's key
presses into one `TAUIState`. That doc ends with a promise — "one App, every
surface, no drift" isn't taken on faith, it's a function you can call. This
page is the reference for that function, and for the rest of
`agentfront.testing`: the public harness a **consumer** of your tool drops
into their own test suite, not an internal helper of this repo.

Every surface `agentfront` derives from your `App` — CLI, MCP, HTTP, TAUI —
is built from the same registry, and `agentfront` dogfoods its own gate: the
`surfaces_agree` check that guards *this* repo's CI is the exact same check
`assert_surfaces_agree` runs against *your* app. Your front is provable in
the same way agentfront's own front is provable, using the same tool.

`agentfront.testing` is stdlib-only except for `call_mcp`, which never
imports the `mcp` package either — every helper here runs in-process, with
no subprocess and no server round trip, so it's safe and fast to call from
`pytest`.

All examples on this page import a small app built like this:

```python
from agentfront import App

app = App(name="mytool", version="1.0")

@app.tool
def search(query: str) -> str:
    """Search the corpus."""
    return f"results for {query}"
```

## `run_cli` — test a CLI verb in-process

```python
from agentfront import App
from agentfront.testing import run_cli

app = App(name="mytool", version="1.0")

@app.tool
def search(query: str) -> str:
    """Search the corpus."""
    return f"results for {query}"

result = run_cli(app, ["search", "hello", "--json"])
assert result.exit_code == 0
assert result.stdout == '"results for hello"\n'
assert result.stderr == ""
```

`run_cli(app, argv) -> CliResult` wraps `agentfront.cli_surface.run_cli` —
the same dispatch a real `mytool search hello --json` invocation uses —
under `contextlib.redirect_stdout`/`redirect_stderr`. `CliResult` is a frozen
dataclass: `exit_code: int`, `stdout: str`, `stderr: str`. No subprocess is
spawned, so this is cheap enough to call once per test.

## `call_mcp` — the MCP `run` tool payload, without a server

```python
from agentfront import App
from agentfront.testing import call_mcp

app = App(name="mytool", version="1.0")

@app.tool
def search(query: str) -> str:
    """Search the corpus."""
    return f"results for {query}"

ok = call_mcp(app, ["search"], {"query": "hello"})
assert ok == {"result": "results for hello"}

missing = call_mcp(app, ["nope"], {})
assert missing == {
    "error": {
        "code": 1,
        "message": "unknown command: nope",
        "remediation": "check available commands in the 'run' tool description",
    }
}
```

`call_mcp(app, command, args=None) -> dict` dispatches `command` (a list of
path segments, matching the MCP `run` tool's own `command` argument) against
your app's registry and returns the exact payload shape the real MCP server
would — `{"result": <value>}` on success, XOR
`{"error": {"code", "message", "remediation"}}` on failure. It builds that
payload from the same shared helpers (`agentfront._run_dispatch`) the real
`agentfront.mcp_surface` uses, so you get MCP-surface-accurate assertions
without installing the optional `agentfront[mcp]` extra or standing up a
server. A raised `agentfront.errors.AgentfrontError` maps to its own
`.to_dict()`; any other exception maps to the generic
`{"code": 1, "message": "<ExcName>: <exc>", "remediation": "check command arguments"}`
shape; an async tool function is resolved transparently.

## `drive` — fold a scripted event trail through a live `Session`

```python
from agentfront import App
from agentfront.testing import drive
from agentfront.taui.events import SelectorAction, UserInput

app = App(name="mytool", version="1.0")

@app.tool
def search(query: str) -> str:
    """Search the corpus."""
    return f"results for {query}"

events = [
    UserInput(text="looking for docs"),
    SelectorAction(selector="search", args={"query": "docs"}),
]
session = drive(app, events)

lines = [line.text for line in session.state.conversation]
assert lines == ["looking for docs", "→ search", "✓ search: results for docs"]
assert session.last_result == {"result": "results for docs"}
assert session.mirror()["taui_version"] == "0.2"
```

`drive(app, events) -> Session` builds a fresh
[`agentfront.taui.session.Session`](../agentfront/taui/session.py) and folds
`events` in order. A `SelectorAction` that resolves to a registered tool
goes through `session.dispatch` — so it **actually executes the tool**,
exactly as a live agent driving the session would — while every other event
(`UserInput`, `KeyPress`, …) folds through `session.fold` directly. The
returned `Session` gives you three read-only handles to inspect:

- `session.state` — the current `TAUIState` (conversation, panels, popups,
  `work_item`, `problems`, `focused`, …).
- `session.mirror()` — `agentfront.taui.mirror.serialize(session.state)`,
  the JSON-shaped view a bot or script would fetch (adds `taui_version` and
  a derived `available_actions` list).
- `session.last_result` — the MCP-shape payload from the most recent tool
  dispatch (`None` until one runs); it agrees byte-for-byte with
  `call_mcp(app, [...], args)` for the same call.

## `assert_surfaces_agree` — the one-liner

This is the single most important function on this page: it is the exact
check `agentfront` runs on itself, made public so your app's CI can run it
too.

```python
from agentfront import App
from agentfront.testing import assert_surfaces_agree

app = App(name="mytool", version="1.0")

@app.tool
def search(query: str) -> str:
    """Search the corpus."""
    return f"results for {query}"

assert_surfaces_agree(app)   # raises AssertionError naming the drift, or returns None
```

`assert_surfaces_agree(app) -> None` calls
`agentfront.serve.surface_inventory(app)` — the same inventory the
`surfaces_agree` gate protecting this repo's own CI uses — and compares
every doc-bearing surface (registry, HTTP, CLI) and every tool-bearing
surface (registry, CLI, MCP, TAUI) against the registry. On a mismatch it
raises `AssertionError` naming the disagreeing pair and the exact set
difference, e.g. `"cli_tools missing vs registry_tools: {'a/b'}"` — so a
failing consumer test tells you precisely what drifted, not just that
something did.

### The consumer-CI recipe

Drop this file into your test suite:

```python
# test_surfaces_agree.py
from myapp import app

from agentfront.testing import assert_surfaces_agree


def test_surfaces_agree():
    assert_surfaces_agree(app)
```

Wire it into any CI the same way you already run the rest of your test
suite — add a `pytest` step (or job) that runs alongside your unit tests;
there is nothing agentfront-specific to configure. Because `run_cli` and
`call_mcp` above are also in-process, a consumer's entire surface-parity
suite — CLI smoke tests, MCP dispatch tests, and this one-liner — runs as
plain `pytest`, no subprocess, no server, no `mcp` extra required unless a
test specifically cross-checks the real MCP server.

## `assert_agent_human_parity` and `assert_replay_equivalent`

```python
from agentfront import App
from agentfront.taui.events import SelectorAction
from agentfront.taui.session import Session
from agentfront.testing import assert_agent_human_parity, assert_replay_equivalent

app = App(name="mytool", version="1.0")

@app.tool
def search(query: str) -> str:
    """Search the corpus."""
    return f"results for {query}"

def handle_status(**kwargs):
    return "status: ok"

app.add_command("status", handle_status, help="Show status")

# "cmd.status" is a host command, not a registered tool, so an agent
# dispatching it degrades to pure navigation -- exactly what a human
# arrow-keying to the same panel item produces. A *tool* selector here
# would legitimately diverge: the agent path would execute the tool
# (changing conversation/work_item), which pure key-navigation never does.
assert_agent_human_parity(app, "cmd.status")

session = Session(app)
session.dispatch(SelectorAction(selector="search", args={"query": "docs"}))
assert_replay_equivalent(session)
```

`assert_agent_human_parity(app, selector) -> None` proves the reducer parity
`how-it-works.md` describes: an agent's `SelectorAction(selector=selector)`
dispatch and a human's arrow-key walk along `focus_order` to that same
selector must land on the *same* `TAUIState` (dataclass equality), not just
an equivalent one. It raises `AssertionError` naming both final `focused`
values on mismatch, or naming the selector as unreachable by navigation.
Pick a `selector` that is pure navigation on the agent side too — a panel
item, a doc, or (as above) a host command — since a selector that resolves
to a registered tool executes on the agent path and has no human-navigation
equivalent to compare against.

`assert_replay_equivalent(session) -> None` proves the trail-is-truth
invariant `Session` is built on:
`replay(session.events[session.replay_base_index:], initial=session.initial) == session.state`.
This holds for a fresh session (`replay_base_index == 0`) and for a resumed
one (only the events folded *since* resumption are replayed, on top of the
state it resumed from — see
[the handoff recipe](#handoff-resume--livedriver) below). It raises
`AssertionError` with both the replayed and actual states on mismatch.

## Collaboration recipes

Two patterns cover the ways an agent and a human hand a TAUI session back
and forth. Both are built on the snapshot quad
(`write_snapshot` / `read_snapshot` / `Snapshot`, re-exported from
`agentfront.testing`) and `agentfront.taui.session.Session`.

**A semantic to know before using either recipe:** `replay` (and therefore
`read_snapshot` + `replay`, and `resume` continuing a session) never
re-executes a tool's side effects. `reduce()` — the pure function `replay`
folds events through — only *folds* the `ToolInvoked`/`ToolResult` events
already on the trail; it never calls the tool function again. A snapshot's
`.events.jsonl` is a record of what happened, not a script to re-run. This
is a spec-level guarantee, not an implementation detail: `docs/how-it-works.md`
describes `reduce()` as performing "no tool dispatch" by design.

### Record + review

An agent drives a real tool, then pauses; a human reads the snapshot back
and confirms the replayed trail reproduces the paused state — with the
tool's side effect having happened exactly once.

```python
from agentfront import App
from agentfront.taui.events import SelectorAction
from agentfront.taui.session import Session
from agentfront.testing import read_snapshot, replay, write_snapshot

calls = []

app = App(name="mytool", version="1.0")

@app.tool(group="feedback")
def record(text: str) -> str:
    """Record feedback (a real side effect: appends to calls[])."""
    calls.append(text)
    return f"recorded: {text}"

# --- agent: drive a real tool, then hand off with a snapshot ---
session = Session(app)
session.dispatch(SelectorAction(selector="feedback.record", args={"text": "nice tool"}))
assert calls == ["nice tool"]

stem = "/tmp/mytool-review"
write_snapshot(stem, session.state, session.events)

# --- human: read the snapshot back and replay its trail ---
snap = read_snapshot(stem)
replayed = replay(snap.events, initial=app.taui())
assert replayed == snap.state
assert calls == ["nice tool"]   # replay folded the trail; it did not re-run record()
```

`write_snapshot(stem, state, events)` writes four files —
`<stem>.taui.json`, `<stem>.ansi`, `<stem>.md`, `<stem>.events.jsonl` — so a
human reviewer has a rendered frame and a markdown page to read as well as
the machine-checkable JSON and event trail. `read_snapshot(stem) ->
Snapshot(state, ansi, markdown, events)` reads them back.

### Handoff: `resume` + `LiveDriver`

An agent pauses mid-session — here, after a failing tool call — and a human
resumes it live, dismisses the resulting error popup, and quits.

```python
from agentfront import App
from agentfront.errors import AgentfrontError
from agentfront.taui.driver import LiveDriver
from agentfront.taui.events import SelectorAction
from agentfront.taui.session import Session
from agentfront.testing import resume, write_snapshot

app = App(name="mytool", version="1.0")

@app.tool
def risky() -> str:
    """Always fails, to demonstrate the tool-error popup + dismissal."""
    raise AgentfrontError(code=3, message="risky failed", remediation="try again later")

# --- agent: hit a failure, then pause the session ---
session = Session(app)
session.dispatch(SelectorAction(selector="risky", args={}))
stem = "/tmp/mytool-handoff"
write_snapshot(stem, session.state, session.events)

# --- human: resume the session and drive it live ---
resumed = resume(stem, app)
driver = LiveDriver(resumed)
assert resumed.state.popups[0].visible is True   # the blocking error popup

driver.feed_key("esc")   # dismisses the popup (its Action.input == "esc")
assert resumed.state.popups[0].visible is False

driver.feed_key("q")     # always quits, even mid-popup
assert driver.running is False
```

`resume(source, app) -> Session` accepts either a snapshot stem (it calls
`read_snapshot` for you) or an already-loaded `Snapshot` object, and returns
a live `Session` continuing from exactly that point — its `state` and
`events` are the snapshotted ones, and `replay_base_index` is set so
`assert_replay_equivalent` still holds for everything folded *after* the
resume.

`LiveDriver` is the shared front end for both audiences over one live
`Session`: a human's `feed_key` and an agent's `dispatch` both write through
the session's single lock, so either side's action is visible in the other's
next render. Two behaviors worth knowing: a visible popup's own `Action`s
fire on their bound key — `esc` here, because the tool-error popup the
reducer opens always binds a `.dismiss` action to `"esc"` — instead of
plain navigation; and `"q"` **always** quits (`driver.running` goes
`False`), even with a blocking popup still visible, so a human is never
trapped.

## See also

- [`how-it-works.md`](./how-it-works.md) — the one-`App`-every-surface
  story this harness proves.
- [`consumer-cli.md`](./consumer-cli.md) — the versioned public API
  reference for the CLI surface.
- [`../README.md`](../README.md) — install and quick-start.
