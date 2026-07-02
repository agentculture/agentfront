# How agentfront works

You define **one `App`** — a registry of docs and tools — and agentfront
renders it into every surface an agent, a script, or a human might need to
reach your tool through. Nothing is hand-authored per surface, so nothing
can drift: each surface is a pure read of the same registry.

```python
from agentfront import App

app = App(name="mytool", version="1.0")
app.add_docs_dir("docs/")

@app.tool
def search(query: str) -> str:
    """Search the corpus."""
    ...

app.cli()          # argparse CLI, with `learn`
app.mcp_server()   # minimal MCP tool menu (needs the [mcp] extra)
app.http_app()     # markdown pages + sitemap + /front
app.taui()         # the live-cockpit TAUI state (agent- and human-drivable)
```

Four calls, one registry, four surfaces. Add a doc or a tool once and it is
live everywhere in the same commit — there is no second place to remember
to update.

## Renderings and their consumers

Each surface targets a different consumer, and each consumer wants a
different shape of the *same* underlying state. That state is
[`agentfront.taui.state.TAUIState`](../agentfront/taui/state.py) — the
`taui` field below — projected through three deterministic, stdlib-only
render tiers (`agentfront.taui.mirror`, `agentfront.taui.render.markdown`,
`agentfront.taui.render.ansi`), plus the CLI and MCP surfaces built directly
from the registry:

| Rendering / Surface | `Surfaces` field | Primary consumer |
| --- | --- | --- |
| JSON | `taui` — `app.taui_mirror()` | bots and scripts |
| Markdown | `taui` — `render_markdown(app.taui())`, also served over HTTP at `/front` | agents |
| ANSI/TUI | `taui` — `render_ansi(app.taui())`, the live terminal frame | humans |
| CLI | `cli` — `app.cli()` | agents and humans |
| MCP | `mcp` — `app.mcp_server()` | agents |
| HTTP | `http` — `app.http_app()` | peer fetch surface serving markdown (docs + the `/front` view) |

Why three different renderings of the same TAUI state, instead of one that
everyone shares?

- **JSON is for bots and scripts.** A script that pokes at your tool from CI,
  a cron job, or another program wants exact, stable keys — `state.focused`,
  `available_actions[i].selector` — not prose it has to parse. `app.taui_mirror()`
  (`agentfront.taui.mirror.serialize`) is that contract: `TAUIState.to_dict()`
  plus a `taui_version` and a derived `available_actions` list, so a caller
  never has to re-derive what's clickable.
- **Markdown is for agents.** An LLM-based agent reads structured prose well
  and doesn't need machine-exact keys — it needs headings, lists, and a
  `**(focused)**` marker it can reason about in context. `render_markdown`
  produces that, and it's the same body the HTTP surface serves at `/front`
  and the same body `agentfront.testing.taui.drive` helpers exercise, so an
  agent fetching the doc site and an agent driving TAUI programmatically see
  the identical page.
- **ANSI/TUI is for humans.** A person watching a terminal wants a frame —
  panels, a focus caret, a status line — not a data structure. `render_ansi`
  renders that frame deterministically (no clock, no randomness) from the
  same `TAUIState` the agent-facing renderings use.
- **CLI serves both agents and humans** — it's the one surface built to be
  typed by a person and scripted by an agent equally well, which is why it
  ships a `learn` affordance: a human reads `--help`, an agent reads `learn`
  and writes its own usage notes from the output.
- **MCP is minimal and agent-only** — a single `run` tool with a dispatch
  catalog embedded in its description, not a menu of dozens of individually
  named tools. No human calls an MCP tool directly.
- **HTTP is the peer fetch surface** — a WSGI app serving markdown pages plus
  a `/sitemap.xml`, so any agent with a fetch tool (another agent, a peer
  service, a CI job) can crawl your docs without a bespoke client. `/front`
  is the one dynamic page on that surface: it renders the *live* TAUI state
  as markdown, so a peer fetching `/front` sees the same cockpit an agent
  driving TAUI directly would see — docs and live state through one fetch
  protocol.

## One reducer, two audiences

TAUI's state machine is a single pure function:
`reduce(state: TAUIState, event: Event) -> TAUIState`. It has exactly one
implementation, and both audiences fold through it:

- An **agent** addresses a target directly: `SelectorAction(selector="feedback.record")`.
- A **human** arrives at the same target by navigating: repeated
  `KeyPress("down")` events walking the focus order, landing on the same
  selector.

Both events fold through the same `reduce()`, and both converge on the same
`TAUIState` — not an equivalent one, the *same* one, checked by dataclass
equality. There is no separate "agent state" and "human state" to keep in
sync; there is one state, and two ways to arrive at any given point in it.
That parity is what makes an agent capable of driving the exact UI a human
sees, instead of a shadow API that happens to produce similar results.

## The proof: `agentfront.testing`

Every claim above — one registry renders every surface, and the surfaces
agree — is backed by a runnable check, not just a docstring. `agentfront.serve.surfaces_agree(app)`
queries each surface independently (the HTTP sitemap and `/front` body, the
CLI `learn --json` listing, the MCP command catalog, the TAUI mirror's
`available_actions`) and confirms they all enumerate the same docs and
tools the registry holds.

`agentfront.testing` is the public, importable form of that proof — the
harness a *consumer* of your tool drops into their own CI, not an internal
test helper:

```python
from agentfront.testing import assert_surfaces_agree, run_cli

def test_my_tool_surfaces_agree():
    assert_surfaces_agree(build_app())   # raises AssertionError naming the drift

def test_my_tool_cli_smoke():
    result = run_cli(build_app(), ["learn", "--json"])
    assert result.exit_code == 0
```

`run_cli` drives the CLI in-process (no subprocess) and returns exit code
plus captured stdout/stderr as a `CliResult`. As the surfaces round out, the
harness grows matching helpers for the other two: an MCP dispatcher
(`call_mcp`) so a consumer can assert MCP responses without standing up a
real server, and TAUI helpers (`drive`, `assert_agent_human_parity`,
snapshot/resume) so a consumer can assert that an agent path and a human
path through the cockpit really do converge, per the reducer parity above.
The point is the same in every case: the proof that "one App, every surface,
no drift" holds isn't something you take on faith — it's a function you can
call from your own test suite.

## See also

- [agent-first.md](./agent-first.md) — the Agent First paradigm each surface's
  discipline (learnability / minimalism / discoverability) comes from.
- [agentculture.md](./agentculture.md) — the org this project is foundational to.
- [consumer-cli.md](./consumer-cli.md) — the versioned public API reference for
  the CLI surface.
- [../README.md](../README.md) — install and quick-start.
