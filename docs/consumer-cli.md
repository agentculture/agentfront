# Consumer CLI — Public API Reference

The consumer CLI is the agent-first command-line surface derived from an
`agentfront.App`. A host registers docs and tools once; `app.cli()` renders
the full CLI from that single registry.

## Versioned Public API

Pin to `agentfront >= 0.13` (`>= 0.22` for `run_cli`'s full contract,
`meta_verb`, `add_learn_section` and the top-level `Flag`). The following
symbols are stable and documented:

| Symbol | Description |
|---|---|
| `agentfront.App` | The code-first config object |
| `agentfront.errors.AgentfrontError` | Structured error type |
| `agentfront.Flag` | Per-verb CLI flag declaration (also importable as `agentfront._registry.Flag`) |

Names with a leading underscore (`cli_surface._CliParser`, `_dispatch`,
`_propagate_raw_argv`, a parser's `_actions`) are not part of this API. If you
reach for one, use the hooks below instead, or open an issue.

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
| `app.run_cli(argv=None)` | Parse *argv* (default `sys.argv[1:]`), dispatch, return the exit code ([contract](#apprun_cli)) |
| `app.meta_verb(name, handler=None, *, configure=None)` | Point `explain`, `overview` or `doctor` at a host handler ([meta-verbs](#meta-verbs)) |
| `app.add_learn_section(title, text)` | Append a prose section to `learn` |
| `app.mcp_server()` | Return the MCP server (requires `[mcp]` extra) |
| `app.http_app()` | Return the WSGI HTTP app |

### `app.run_cli`

The supported body of a `main(argv) -> int` entry point:

```python
def main(argv: list[str] | None = None) -> int:
    return app.run_cli(argv)
```

It returns an exit code and never raises `SystemExit` for its own exits:

| Situation | Exit code | Output |
|---|---|---|
| success, `--help`, `--version` | `0` | stdout (`--version` prints `<name> <version>`) |
| parse error (unknown verb, missing argument) | `1` | `error:` / `hint:` on stderr, or a `{code, message, remediation}` object when `--json` is in argv |
| handler raises `AgentfrontError` | its `code` | rendered the same way |
| handler raises anything else | `1` | wrapped, no traceback |
| `KeyboardInterrupt` | `130` | none |
| bare invocation | the no-command handler's code, else `0` with help | |

Only a handler that calls `sys.exit()` itself propagates `SystemExit`.
`agentfront.cli_surface.run_cli(app, argv)` is the same function.

### Meta-verbs

Every generated CLI has four meta-verbs. The built-ins are derived from the
registry; each takes `--json`:

| Verb | Built-in | Overridable |
|---|---|---|
| `learn` | purpose, docs, commands, host sections, `--json`, exit codes, `explain` pointer | **no**, extend with `add_learn_section` |
| `explain [path...]` | a tool's doc, a group's children, or the root (also for `explain <app name>`) | yes |
| `overview [scope]` | top-level nouns, or the verbs under one noun | yes |
| `doctor` | registry counts; `--json` gives `{healthy, checks}` | yes |

Override one when the generic output can't carry your tool's knowledge, such as
identity checks in `doctor` or a hand-written explain catalog:

```python
import json

@app.meta_verb("doctor")
def doctor(args) -> int:
    checks = [{"id": "config", "passed": True, "severity": "error",
               "message": "config found", "remediation": ""}]
    healthy = all(c["passed"] for c in checks)
    if args.json:
        print(json.dumps({"healthy": healthy, "checks": checks}))
    else:
        print("healthy" if healthy else "unhealthy")
    return 0 if healthy else 1

app.meta_verb("explain", my_explain, configure=lambda p: p.add_argument("--raw", action="store_true"))
```

The handler contract:

- agentfront still builds the verb's parser, so the arguments stay stable:
  `--json` on every verb, `path` (a list) on `explain`, optional `scope` on
  `overview`. `configure(parser)` may add more arguments.
- The handler receives the parsed `argparse.Namespace` and returns an exit code
  (`None` means `0`). Results go to stdout; honour `args.json`.
- Raise `AgentfrontError` to fail; it is rendered like any other error.
  Anything else is wrapped with no traceback.
- Overrides are CLI-only. The registry, MCP, HTTP and `learn` are unchanged,
  so `surfaces_agree` still holds.
- Your handler owns its output, so it owns that verb's
  [rubric](./rubric.md) bundle: `explain` must exit non-zero with a `hint:` on
  an unknown path, `overview --json` must carry `subject` and `sections` and
  must not fail on an unknown scope, and `doctor --json` must give
  `{healthy, checks}` with a `remediation` on every failed check.
- `learn` can't be overridden (it raises `ValueError`) because its `--json`
  `docs` and `tools` lists are the CLI inventory that the cross-surface
  agreement check reads. Add what the registry can't know with
  `app.add_learn_section("Runtime", "...")`. It is rendered as `## Runtime` in
  text and as `{"title", "text"}` in the `sections` list under `--json`.
- Overriding the same verb twice raises `DuplicateError`. An unknown name
  raises `ValueError`. `app.get_meta_verb(name)` returns the override or
  `None`.

The rubric also asks for a `cli overview` verb. Register it as an ordinary
grouped tool: `@app.tool(name="overview", group="cli")`.

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

### `agentfront.Flag`

```python
from agentfront import Flag

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
def main(argv: list[str] | None = None) -> int:
    return app.run_cli(argv)

if __name__ == "__main__":
    import sys
    sys.exit(main())
```

This yields:

```text
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
