# Consumer CLI — Public API Reference

The consumer CLI is the agent-first command-line surface derived from an
`agentfront.App`. A host registers docs and tools once; `app.cli()` renders
the full CLI from that single registry.

## Versioned Public API

Pin to `agentfront >= 0.13`. The following symbols are stable and
documented:

| Symbol | Description |
|---|---|
| `agentfront.App` | The code-first config object |
| `agentfront.errors.AgentfrontError` | Structured error type |
| `agentfront._registry.Flag` | Per-verb CLI flag declaration |

### `agentfront.App`

```python
from agentfront import App

app = App(name="mytool", version="1.0", description="A test tool")
```

| Method | Purpose |
|---|---|
| `app.tool(func, *, name, description, group, doc, flags, aliases)` | Register a function as a CLI tool |
| `app.group(*prefix)` | Return a sub-registrar for nested groups |
| `app.add_command(name, handler, *, help, configure, aliases)` | Register a host-written CLI command |
| `app.set_no_command_handler(handler)` | Set the bare-invocation handler |
| `app.cli()` | Return the argparse CLI parser |
| `app.run_cli(argv)` | Parse *argv* and dispatch (returns exit code) |
| `app.mcp_server()` | Return the MCP server (requires `[mcp]` extra) |
| `app.http_app()` | Return the WSGI HTTP app |

### `agentfront.errors.AgentfrontError`

```python
from agentfront.errors import AgentfrontError, EXIT_USER_ERROR

raise AgentfrontError(
    code=EXIT_USER_ERROR,
    message="invalid input",
    remediation="check the --help output",
)
```

Carries `{code, message, remediation}`; emitted to stderr with structured
formatting. No Python traceback leaks.

### `agentfront._registry.Flag`

```python
from agentfront._registry import Flag

@app.tool(flags=(
    Flag(names=("--verbose", "-v"), action="store_true"),
    Flag(names=("--port",), type=int, default=8080),
))
def serve(host: str = "localhost") -> str:
    """Start the server."""
    ...
```

Declares custom CLI flags beyond signature-derived arguments: explicit type,
boolean on/off, `nargs`, dest-rename, defaults, and required markers.

## Worked Example

```python
from agentfront import App

app = App(name="mytool", version="1.0")

# --- Grouped operations ---------------------------------------------------
@app.tool(group="feedback")
def record(text: str) -> str:
    """Record a feedback entry."""
    return f"recorded: {text}"

@app.tool(group="feedback")
def show(entry_id: str) -> str:
    """Show a feedback entry."""
    return f"entry {entry_id}"

# --- Host-owned launcher verb (not generated from @app.tool) ---------------
def tui_handler(args) -> int:
    """Launch an interactive TUI — host-owned, not agentfront-generated."""
    print("Launching TUI...")
    return 0

app.add_command("tui", tui_handler, help="launch interactive TUI")

# --- Derive the CLI -------------------------------------------------------
if __name__ == "__main__":
    import sys
    sys.exit(app.cli().parse_args())
```

This yields:

```
mytool feedback record "great tool"    # generated verb
mytool feedback show 42                # generated verb
mytool tui                              # host-owned launcher
mytool learn                             # agent-facing summary
mytool doctor                            # readiness check
mytool overview                          # list available commands
```

The `tui` verb is **not** generated from a `@app.tool` — it's registered via
`app.add_command`, proving the boundary: agentfront cannot generate a raw-mode
REPL; the host registers it through the extension hook.

## Pure-Stdlib Guarantee

The consumer CLI path (`agentfront.app`, `agentfront.cli_surface`,
`agentfront._cli_core`, `agentfront._registry`, `agentfront.errors`,
`agentfront.cli._output`) imports only stdlib + `agentfront`. The `mcp` SDK
is an **optional** extra (`[mcp]`) used exclusively by `agentfront.mcp_surface`.

```toml
# pyproject.toml
dependencies = []

[project.optional-dependencies]
mcp = ["mcp>=1.28.0"]
```

A CI guard asserts no third-party module is imported on the core path.

## Dogfooding

agentfront is expected to render its own CLI/MCP/HTTP surfaces from an App once
bootstrapped; this consumer API is that round-trip. The same `App` object that
builds the CLI via `app.cli()` also yields `app.mcp_server()` (single-dispatch
with one `run` tool) and `app.http_app()` (WSGI markdown site), all derived
from the single registry — so the three surfaces cannot drift apart.
