# Build Plan — agentfront ships a public consumer CLI API: a host registers its operations into one App and app.cli() renders its entire nested noun/verb CLI — tool dispatch, per-verb --json, structured {code,message,remediation} errors to stderr, explain/overview from the registry, and a host extension hook for hand-written subcommands — pure-stdlib, from the same registry that backs MCP and HTTP

slug: `agentfront-ships-a-public-consumer-cli-api-a-host` · status: `exported` · from frame: `agentfront-ships-a-public-consumer-cli-api-a-host`

> agentfront ships a public consumer CLI API: a host registers its operations into one App and app.cli() renders its entire nested noun/verb CLI — tool dispatch, per-verb --json, structured {code,message,remediation} errors to stderr, explain/overview from the registry, and a host extension hook for hand-written subcommands — pure-stdlib, from the same registry that backs MCP and HTTP

## Tasks

### t1 — Public errors module: promote AfiError {code,message,remediation} + exit-code constants to a public, argparse-free module (agentfront/errors.py), re-exported from agentfront; agentfront.cli._errors becomes a thin re-export

- acceptance:
  - agentfront.errors.AfiError imports without importing argparse; to_dict() yields {code,message,remediation}; agentfront.cli._errors re-exports the same type; a test imports it from the public path

### t2 — Shared CLI core machinery: extract emit_result/emit_error/emit_diagnostic + a structured-error ArgumentParser (parser_class override routing parse errors to {code,message,remediation}, pre-parse raw-argv --json peek) + a dispatch loop (KeyboardInterrupt->130, wrap unexpected exceptions, no traceback) into a shared internal module parameterized by prog/version/issues_url out of _brand

- depends on: t1
- covers: c27, c31, h17, h21
- acceptance:
  - a malformed command emits structured {code,message,remediation} on stderr with nonzero exit honoring --json, and 'error:/hint:' lines without --json
  - a handler raising a bare Exception yields a structured error + nonzero exit (no traceback); a simulated KeyboardInterrupt exits 130; module import graph is stdlib + agentfront only

### t3 — Registry nested groups: add group/path support to Registry/App so ops register under a noun path to arbitrary depth (group= and app.group('feedback') sub-registrar)

- covers: c14, h2
- acceptance:
  - registering ops under group= yields a >=2-level tree enumerable from the registry; app.group() returns a sub-registrar; a leaf op resolves by its full path

### t4 — Registry per-op doc metadata: registered ops carry markdown doc metadata used to derive explain/learn/overview for any consumer App

- depends on: t3
- covers: c29, h19
- acceptance:
  - an op registered with doc metadata is retrievable from the registry; adding an op surfaces its doc with no separate hand-authored catalog edit

### t5 — Registry rich flag declarations: registration accepts custom flags beyond signature derivation (explicit type, boolean on/off --x/--no-x, nargs, dest-rename, defaults)

- depends on: t3
- covers: c30, h20
- acceptance:
  - an op with a custom typed flag, a boolean --x/--no-x flag, and a renamed dest parses correctly and the handler receives the parsed values

### t6 — Registry native aliases (enabling): registration accepts alias names mapping multiple verb/noun names to one handler (e.g. wheels->backends, drive->work)

- depends on: t3
- acceptance:
  - an op registered with an alias is invocable under both its primary name and each alias, dispatching the same handler

### t7 — Host extension points: app.add_command(name, handler, help=...) for a host-written command, plus a host-supplied top-level no-command default handler

- depends on: t3
- covers: c17, c32, h5, h22
- acceptance:
  - app.add_command registers a host verb invocable alongside generated verbs in one CLI run
  - a no-command handler set on the App is called on bare invocation; with none set, bare invocation prints help and exits 0

### t8 — CLI builder (centerpiece): rewrite App.cli()/make_cli to render the full nested noun/verb tree from the registry — signature-derived args + dispatch the func, nested groups, per-verb --json (success->stdout, failure->structured stderr+nonzero exit), bare-noun->overview fallback, wiring add_command + aliases + rich flags + no-command handler; preserve any partial result a host attaches to its structured error

- depends on: t2, t3, t4, t5, t6, t7
- covers: c13, c15, c28, h1, h3, h18
- acceptance:
  - a registered typed op becomes an invocable subcommand that runs with parsed args (asserted it actually ran, not just listed)
  - every generated verb supports --json: success payload on stdout; an induced failure emits {code,message,remediation} on stderr + nonzero exit; stdout stays clean on failure
  - a registered noun group invoked with no verb renders that group's overview (exit 0) with no host code wiring the fallback

### t9 — Registry-derived explain/overview/learn: make explain<path>, overview nouns, and learn derive from the registry doc metadata for any consumer App (not just agentfront's own self-audit)

- depends on: t4, t8
- covers: c16, h4
- acceptance:
  - on a consumer App, explain <noun> <verb> returns that op's registered doc and overview lists the registry's nouns
  - learn enumerates exactly the registered op set; adding an op makes it appear in explain/learn/overview with no catalog edit

### t10 — Single-dispatch MCP: rewrite make_mcp_server to expose ONE dispatch tool taking a command-path + args, dispatching through the same registry, returning the op result on success and a structured {code,message,remediation} payload on failure, with the command catalog embedded in the tool's inputSchema

- depends on: t3, t9
- covers: c24, h24
- acceptance:
  - mcp_server() exposes exactly one tool; a valid command-path+args runs the op and returns the right result; a bad path/args returns a structured {code,message,remediation} payload (not an opaque exception)
  - the single tool's inputSchema/description embeds the registry-derived command catalog for discoverability

### t11 — Cross-surface invariant + serve.py harness: update serve.py surface_inventory/surfaces_agree to compare the single MCP tool's command catalog (not N tool entries) against the CLI verb set and learn catalog under single-dispatch

- depends on: t8, t9, t10
- covers: c23, c37, h23, h27
- acceptance:
  - surfaces_agree(app) returns True for a consumer App under single-dispatch MCP, comparing the single tool's command catalog == CLI verb set == learn catalog; http_app() still serves the registry docs
  - a regression test covers the catalog-based comparison; adding/removing an op updates all three surfaces together

### t12 — Pure-stdlib guard + versioned public symbols: a test/CI guard asserts no new third-party runtime dependency on the consumer CLI path and that mcp stays the optional [mcp] extra; document and version the public symbols (App.cli, app.add_command, app.group, agentfront.errors); a host-owned REPL/TUI verb is host-registered via add_command, not generated

- depends on: t7, t8
- covers: c6, c19, h7, h13
- acceptance:
  - the import graph of the consumer CLI path is stdlib + agentfront only; a guard asserts no third-party runtime import and that [mcp] remains optional
  - a host-owned REPL/TUI launcher verb is added via the extension hook (not generated) and appears beside generated verbs

### t13 — End-to-end consumer App + success-signal suite + docs: an example consumer App built only by registration (>=2-level nesting + per-verb flags + a host add_command launcher verb), exercised by an e2e test that is the conjunction of the spec's success signals; docs for the versioned public API; dogfood note

- depends on: t8, t9, t10, t11, t12
- covers: c1, c2, c3, c4, c5, c8, h8, h9, h10, h11, h12, h14
- acceptance:
  - an e2e test builds a consumer App by registration only and asserts app.cli() renders+dispatches nested verbs, per-verb --json, structured errors, the extension hook, and registry-derived explain/overview/learn
  - the same App still yields app.mcp_server() (single-dispatch) and app.http_app(); the before->after contrast vs current learn/doctor-only main is captured
  - docs cover the documented, versioned public symbols a consumer pins

## Risks

- [unknown_nonblocking] Wave-1 tasks t4/t5/t6/t7 (registry doc metadata, rich flags, aliases, add_command) all write agentfront/_registry.py + app.py — formally parallel but operationally serialized at merge. For workforce execution: either one agent owns the registry-extension file set, or give t5->t4->t6->t7 explicit deps to serialize. t8 (CLI builder, cli_surface.py) and t1 (errors.py) are genuinely file-disjoint from the registry tasks.
- [unknown_nonblocking] t8 (CLI builder) is the critical-path bottleneck: 6 deps in and 5 tasks depend on it. Keep its scope tight; if it grows, split the bare-noun->overview fallback and the add_command/alias wiring into follow-on tasks.
