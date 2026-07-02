# agentfront ships a public consumer CLI API: a host registers its operations into one App and app.cli() renders its entire nested noun/verb CLI — tool dispatch, per-verb --json, structured {code,message,remediation} errors to stderr, explain/overview from the registry, and a host extension hook for hand-written subcommands — pure-stdlib, from the same registry that backs MCP and HTTP

> agentfront ships a public consumer CLI API: a host registers its operations into one App and app.cli() renders its entire nested noun/verb CLI — tool dispatch, per-verb --json, structured {code,message,remediation} errors to stderr, explain/overview from the registry, and a host extension hook for hand-written subcommands — pure-stdlib, from the same registry that backs MCP and HTTP

## Audience

- host packages building an agent-first tool (colleague first) that want a full CLI from importing agentfront, plus the AI agents that consume that CLI

## Before → After

- Before: App.cli() is a meta CLI emitting only learn/doctor; registered @app.tool funcs are exposed to MCP/HTTP but never dispatched on the CLI; the rich nested-verb machinery exists only in agentfront's internal self-audit CLI (agentfront/cli/) with no consumer API, so a host must rebuild it all by hand
- After: a consumer registers operations into one App and gets a full agent-first CLI rendered from that registry — nested noun/verb groups to arbitrary depth, per-verb signature-derived flags, per-verb --json, structured {code,message,remediation} errors to stderr with non-zero exit, explain catalog and overview nouns — the same registry that yields app.mcp_server() and app.http_app()

## Why it matters

- colleague intends to take agentfront as its one base runtime dependency and stop hand-maintaining agent-first CLI scaffolding (import, do not duplicate); registering its ops into one App also exposes colleague over MCP and HTTP for free; colleague's migration is upstream-first and gated on this shipping

## Requirements

- Tool->CLI dispatch: a registered operation becomes an invocable subcommand whose arguments are derived from its signature/type hints, then the func is called — not merely listed
  - honesty: a test registers a typed function, invokes it through the generated CLI subcommand with parsed args, and asserts the function actually ran with the right values (not just that it was listed)
- Nested noun/verb groups to arbitrary depth are buildable purely from registration (e.g. a feedback noun with record|show|list verbs)
  - honesty: a test builds a >=2-level tree (noun -> verb -> verb) from registration alone and invokes a leaf verb successfully
- Every generated verb supports --json; on success the result goes to stdout, on failure a structured {code,message,remediation} goes to stderr with a non-zero exit code
  - honesty: a test asserts: --json present on every generated verb; success payload on stdout; an induced failure emits {code,message,remediation} on stderr with a non-zero exit; stdout stays clean on failure
- explain <path> and overview are derivable from the registry for any consumer App, not just agentfront's own CLI
  - honesty: a test on a consumer App (not agentfront's own) asserts explain <path> returns the verb's catalog entry and overview lists the registry's nouns
- A host can register its own hand-written subcommand alongside generated ones via a documented extension hook
  - honesty: a test registers a hand-written subcommand via the documented hook and invokes both it and a generated verb in one CLI run
- The whole consumer CLI API is pure-stdlib: no new third-party runtime dependency; mcp stays an optional extra
  - honesty: the import graph of the consumer CLI API touches only stdlib + agentfront; a test/CI guard asserts no third-party import on the core path and that the [mcp] extra remains optional
- Cross-surface invariant from ONE registry: the CLI renders the nested verb tree; the MCP surface exposes a single dispatching tool whose command catalog enumerates the same operations; learn lists the same set; http_app() still serves the docs. Add/remove an op once -> all surfaces update together (no drift)
  - honesty: a test asserts, for one consumer App, that the CLI verb set == the single MCP tool's documented command catalog == learn's catalog, and http_app() still serves the registry docs; adding/removing an op updates all three together
- The MCP dispatch tool runs a registered op by command path + args and returns its result on success, and on failure returns a structured {code,message,remediation} payload (not an opaque exception) so an agent gets actionable feedback
  - honesty: a test invokes the single MCP tool with a valid command-path + args and asserts the op ran with the right result; a bad path/args yields a structured {code,message,remediation} failure payload, not an opaque exception
- Parse-time argparse errors (unknown verb, missing required arg) route through the structured {code,message,remediation} format, not raw argparse 'prog: error:' text — via a parser_class override propagated to every subparser, plus a pre-parse raw-argv --json peek so parse-time errors honour --json before args.json exists
  - honesty: a test runs a malformed command with --json and asserts a structured JSON {code,message,remediation} error on stderr with non-zero exit and clean stdout; the same without --json prints 'error:/hint:' lines
- Bare noun with no subverb auto-falls-through to that noun's overview — a framework default emitted from the group, not hand-wired per host group (colleague has this identical _no_verb->overview pattern across all 13 groups)
  - honesty: a test invokes a registered noun group with no verb and asserts it renders that group's overview (exit 0), with no host code wiring the fallback
- explain <path> and learn are auto-generated from the registry: registered operations carry markdown doc metadata, so explain/learn/overview enumerate the same registry set as the CLI (no hand-written per-command catalog) — this is what preserves CLI<->learn set-equality
  - honesty: a test on a consumer App asserts explain <noun> <verb> returns that op's registered doc and learn lists exactly the registered op set; adding an op makes it appear in all three with no catalog edit
- Per-verb flag declarations are rich: beyond signature-derived args, the registration accommodates custom flags with explicit type, boolean on/off (BooleanOptionalAction-style), nargs, dest-rename, and defaults (colleague's 'work' verb alone declares ~18 such flags) — otherwise generated subparsers are bare and the host re-hand-rolls flags
  - honesty: a test registers an op with a custom typed flag, a boolean --x/--no-x flag, and a renamed dest, invokes it, and asserts the handler received the parsed values
- Dispatch is robust: KeyboardInterrupt exits 130 cleanly; any non-structured exception from a handler is wrapped into {code,message,remediation} so no Python traceback ever leaks to stderr
  - honesty: a test asserts a handler raising a bare Exception yields a structured error + non-zero exit (no traceback), and a simulated KeyboardInterrupt yields exit 130
- App.cli() supports a host-supplied top-level no-command default handler so a bare invocation (e.g. 'colleague' with no args) can route to host logic (session at a TTY vs help) instead of agentfront hardcoding the bare-invocation behaviour
  - honesty: a test sets a no-command handler on a consumer App and asserts a bare invocation calls it; with none set, a bare invocation prints help and exits 0
- The existing cross-surface harness in agentfront/serve.py (surface_inventory / surfaces_agree, which today asserts registry_tools == cli_tools == mcp_tools) is updated so under single-dispatch MCP it compares the single tool's command catalog (not N tool entries) against the CLI/learn set — otherwise the existing set-equality test fails by construction
  - honesty: a regression test asserts surfaces_agree(app) is True for a consumer App under single-dispatch MCP — comparing the single tool's command catalog to the CLI verb set and learn catalog (the serve.py mcp comparison is updated from N-entry to catalog-based)

## Honesty conditions

- an end-to-end test on a consumer App asserts app.cli() renders nested verbs + dispatch + per-verb --json + structured errors + the extension hook, with zero third-party runtime imports on that path
- colleague can render its full CLI by importing agentfront with no hand-rolled argparse — its converged spec's acceptance is satisfied by this API's public surface
- verified against current main: agentfront/cli_surface.py make_cli registers only learn+doctor (lines ~105/109) and no path dispatches registered @app.tool ToolEntry funcs on the CLI
- the after-state is exactly the conjunction of the success-signal tests passing on a consumer App built only by registration
- colleague's spec docs/specs/2026-06-25-colleague-s-agent-first-cli-is-rendered-from-an-im.md states its migration is gated on this; shipping it removes colleague's duplicated scaffolding
- a host-owned REPL/TUI verb is added via the extension hook (not generated), and a CI guard asserts the core path adds no third-party runtime dependency
- the acceptance-criteria test suite (nesting, --json, structured errors, explain/overview, extension hook, cross-surface parity, no-new-dep, versioned symbol) is green
- surfaces_agree(app) returns True for a consumer App under single-dispatch MCP, comparing the single tool's command catalog to the CLI verb set and learn catalog; a regression test covers it
- the single MCP tool's inputSchema/description embeds the command catalog so an agent discovers available commands from the one tool; learn/explain expose the same registry-derived catalog

## Success signals

- a consumer builds a CLI with >=2 levels of nesting and per-verb flags purely by registering ops (no hand-rolled argparse); every generated verb supports --json (success->stdout, failure->{code,message,remediation}->stderr + non-zero exit); explain <path> and overview are registry-derived; a host registers its own hand-written subcommand alongside generated ones (one test invokes both); the same App still yields mcp_server()/http_app() unchanged and a test asserts CLI/MCP/learn enumerate the same operation set; no new runtime dep; the public symbol is documented and versioned

## Scope / boundaries

- agentfront cannot express a raw-mode REPL or live TUI and will not try; those stay host-owned launcher verbs the host registers via the extension hook. Core stays pure-stdlib — no new third-party runtime dep; mcp stays behind the [mcp] extra. CLI may have full operation coverage (learnability surface); MCP minimalism is unchanged

## Non-goals

- not a re-architecture of the registry's role: docs/tools still declared once; the CLI builder only adds a read path that dispatches tools, it does not introduce a second store
- The framework error machinery must not swallow or destroy a partial result a host attaches to its structured error (colleague's CliError.result, emitted to stdout in --json before re-raise) — agentfront only guarantees not to destroy it; partial-result semantics stay host-owned

## Assumptions

- Grounded in current main: explain (agentfront/explain/catalog.py) is a hand-authored static ENTRIES dict and overview (agentfront/overview/cli_surface.py) enumerates nouns by a regex+filesystem walk of_commands/*.py — NEITHER is registry-derived today. The consumer API must add a registry-derivation path so explain/overview work for any App, not just agentfront's own self-audit
- Depth: colleague needs exactly 2-level nesting (noun verb) across 13 groups, widest is 'tui' with 10 subverbs; 'arbitrary depth' in the spec exceeds the immediate need but is harmless. No 3-level nesting is required by the first consumer
- Accepted tradeoff of single-dispatch MCP (per colleague's ergonomics analysis): an MCP client sees ONE tool via tools/list and loses per-op JSON schemas + native discoverability, so it must learn the command grammar via learn/explain. Accepted in exchange for minimal tool-call noise regardless of registry size; mitigated by the single tool's inputSchema embedding the command catalog and by learn/explain being registry-derived

## Decisions

- Public symbol: grow App.cli() so it dispatches registered tools (instead of adding a separate app.build_cli()). cli() stays the one documented entry; learn/doctor become auto-registered meta-verbs alongside the host's generated nouns
- Reuse, don't fork: promote the existing internal machinery (the structured error type {code,message,remediation} — promoted and renamed to a public `AgentfrontError`, see below — emit_result/emit_error stdout/stderr split, the _AgentfrontArgumentParser register(sub) pattern, explain catalog, overview) into a shared internal module the consumer surface builds on, so agentfront's own CLI and a consumer's CLI share one implementation
- CLI nesting via explicit group= on registration (e.g. @app.tool(group='feedback') / app.group('feedback')) feeds the nested subparser tree to arbitrary depth. The 'clean MCP names' rationale is moot now that MCP collapses to a single tool, but explicit grouping keeps the registry tree first-class and makes the single MCP tool's command catalog trivial to derive
- Extension hook = app.add_command(name, handler, help=...): a host registers its own hand-written command into the App (e.g. an interactive session/tui launcher agentfront can't generate); the CLI builder wires it beside the generated verbs. Keeps everything routed through the App rather than leaking the raw argparse subparsers object
- Reuse surface is clean (per machinery audit): _output.py is fully generic;_errors.py is generic except an ISSUES_URL in the bug-wrap;_AgentfrontArgumentParser + _dispatch are generic except_brand refs. Promotion = parameterize prog/version/issues_url (supplied by App), rename the structured error type (currently in agentfront/cli/_errors.py) to a public `AgentfrontError` in a shared package-level module (agentfront.errors) that does not import argparse so non-CLI consumers import it without argparse, and keep the register(sub) convention as-is (zero coupling)
- Native verb/noun aliases: registration accepts alias names (e.g. alias=['wheels']) mapping multiple names to one handler, so deprecated aliases (colleague's wheels->backends, drive->work) don't force two hand-written add_command entries
- MCP = single-dispatch 'CLI on MCP' ONLY (user decision 2026-06-26): app.mcp_server() exposes ONE tool taking a command-path + args, dispatching through the same registry, returning the op result on success and a structured {code,message,remediation} payload on failure. Supersedes N-tools. Consequence: colleague's converged spec must revise its CLI/MCP/learn set-equality honesty condition to compare the single tool's command catalog (colleague-side follow-up)
- Promote the structured error type to a PUBLIC importable symbol `agentfront.errors.AgentfrontError` (re-exported from agentfront) so consumers stop reaching into the private agentfront.cli._errors; agentfront's own CLI and consumer CLIs share one public type. Move it to a shared module that does not import argparse so non-CLI consumers can import it too. This completes the deferred internal rename (PR #22): the legacy structured-error class name is removed entirely, so no retired identifier is reintroduced

## Hard questions

- CONFLICT: single-dispatch 'CLI on MCP' (1 MCP tool) breaks colleague's converged honesty condition requiring CLI/MCP/learn to enumerate the SAME set (N MCP tools). RESOLVED (user, 2026-06-26): single-dispatch ONLY; colleague revises its CLI/MCP/learn set-equality honesty condition to compare the single MCP tool's command catalog (colleague-side follow-up). (blocking)

## Open / follow-up

- which agentfront version ships this and the exact >= floor colleague pins is a release-time follow-up
- colleague's converged spec must revise its CLI/MCP/learn set-equality honesty condition to compare the single MCP tool's command catalog (not N tool entries) — a colleague-side follow-up triggered by the single-dispatch-only decision; coordinate via an issue on agentculture/colleague

### Open design notes (non-blocking parks)

<!-- Re-attached after export: the devague exporter currently emits only `follow_up`
     vagueness and drops `unknown_nonblocking` parks. These are implementer notes,
     not convergence blockers. -->

- signature->argparse arg typing is coarse: `Optional[T]` / `Union` / `list[int]` fall back to `string` today (same edge as `derive_input_schema` in `agentfront/_registry.py`). Acceptable for v1; richer typing is a follow-up.
- positional-vs-flag mapping rule (required params -> positional, defaulted -> optional `--flag`) needs to be pinned during implementation but does not block convergence.
