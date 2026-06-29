# agentfront

**Agent First Interface** — an importable runtime for tools whose primary consumer is an AI agent, not a human.

> Formerly `teken` (and `afi-cli` before that). The project was renamed to **agentfront** — the agent-facing front a tool presents. The `teken` package and the `teken` command still work as deprecated aliases — see [Install](#install).

You `import agentfront`, build one `App`, and declare your docs and tools **once**. From that single registry, agentfront derives three interface surfaces, each shaped by a different agent-ergonomic principle:

- **CLI** — with a `learn` affordance so an agent can introspect the tool and author its own usage skill (not just read `--help`).
- **MCP server** — a deliberately minimal menu, tuned for low surface area over maximal API coverage.
- **HTTP site** — markdown pages plus a sitemap, navigable by any agent with a fetch tool.

Because all three surfaces read from the same registry, they cannot drift apart. agentfront is a library you embed in your tool, not a code generator that scaffolds files. (Earlier alpha releases shipped a `cli cite` scaffolder and a manifest→three-surfaces generator; that approach has been retired in favour of the importable runtime.)

Part of the [AgentCulture](https://github.com/agentculture) OSS org — see [`docs/agentculture.md`](./docs/agentculture.md) for the org, its paradigm, and how agentfront is foundational to it. The design brief is in [`docs/agent-first.md`](./docs/agent-first.md); the concrete rubric that `agentfront cli doctor` enforces is in [`docs/rubric.md`](./docs/rubric.md).

## Install

```bash
uv tool install agentfront
```

Then `agentfront --version` should work on your PATH. `uv tool install` is the supported path — not `pip install`.

The CLI and HTTP surfaces are pure standard library and have **no third-party dependency**. The MCP surface is the one surface that needs the official [`mcp`](https://pypi.org/project/mcp/) SDK, so it ships behind an optional extra — install it only when you want `app.mcp_server()`:

```bash
uv tool install 'agentfront[mcp]'   # CLI + HTTP + MCP
```

Calling `app.mcp_server()` without the extra installed raises a `ModuleNotFoundError` that names the extra to add.

```bash
uv tool install teken   # still works: a thin wrapper that installs agentfront
```

The `teken` command is retained as a deprecated alias for `agentfront` (it prints a one-line notice to stderr and forwards). New usage should prefer `agentfront`.

## Usage

agentfront is a library. In your tool, build an `App`, register docs and tools, then ask for whichever surface(s) you want to serve:

```python
from agentfront import App

app = App(name="mytool", version="1.0")
app.add_docs_dir("docs/")            # every *.md becomes a page on the HTTP site

@app.tool
def search(query: str) -> str:
    """Search the corpus."""        # docstring + signature feed the MCP tool schema
    ...

http_app = app.http_app()            # WSGI app: markdown pages + /sitemap.xml
mcp = app.mcp_server()               # MCP server exposing the registered tools
cli = app.cli()                      # argparse CLI with learn / doctor verbs
```

Docs and tools are declared once into a single registry; the three surfaces only read from it, so a tool you add is automatically present on every surface and they cannot disagree.

### Audit a CLI against the rubric

agentfront also ships a CLI of its own (`uv tool install agentfront`) that introspects itself and audits other agent-first CLIs. Every command supports `--json` where it produces a listing or report, and respects the [exit-code policy](./docs/rubric.md#exit-code-policy) (`0` success / `1` user error / `2` env error).

```bash
agentfront learn                       # structured self-teaching prompt for an agent
agentfront learn --json                # same, as a JSON payload
agentfront explain cli doctor          # markdown docs for any noun/verb path
agentfront explain agentfront          # top-level map

agentfront cli doctor [path]           # audit a CLI at <path> against the seven-bundle rubric
agentfront cli doctor . --json         # full structured report
agentfront cli doctor . --strict       # treat warnings as failures
agentfront cli overview [path]         # read-only descriptive snapshot of a CLI
```

`agentfront cli doctor` is a **hybrid** auditor: static checks for repo structure (`pyproject.toml`, `tests/`) and black-box subprocess probes for behavior (`learn`, `--json`, error discipline, `explain`). Every failure includes a concrete `remediation` pointer. (`agentfront cli verify` remains as a deprecated alias for `cli doctor`.)

## Develop

```bash
uv sync                          # install + dev deps
uv run pytest -n auto -v         # tests (includes the self-doctor acceptance gate)
uv run agentfront cli doctor .   # same gate, interactive
uv run pre-commit install        # enable lint hooks
```

The `tests/test_self_doctor.py` acceptance gate runs the rubric and self-doctor in-process against the repo root; any regression that breaks a bundle blocks the commit.

See [`CLAUDE.md`](./CLAUDE.md) for design intent and full command reference.

## License

Apache License 2.0. © 2026 Ori Nachum / AgentCulture. See [`LICENSE`](./LICENSE).
