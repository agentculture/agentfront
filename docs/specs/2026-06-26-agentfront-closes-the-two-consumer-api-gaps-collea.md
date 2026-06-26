# agentfront closes the two consumer-API gaps colleague's 0.14.0 import-rendered CLI migration hit: Flag accepts choices= (out-of-set values rejected at parse time through agentfront's structured-error path), and a public accessor exposes the single MCP run tool so consumers can introspect and round-trip it without reaching into a private symbol

> agentfront closes the two consumer-API gaps colleague's 0.14.0 import-rendered CLI migration hit: Flag accepts choices= (out-of-set values rejected at parse time through agentfront's structured-error path), and a public accessor exposes the single MCP run tool so consumers can introspect and round-trip it without reaching into a private symbol

## Audience

- agentfront consumers — hosts that import the App registry to render their CLI (colleague is the first adopter), and the agents driving the resulting CLI/MCP surfaces

## Before → After

- Before: Flag carries no choices, so a migrated --algo sha256|md5 flag loses parse-time validation and an invalid value falls through to a late runtime error; and the run tool is only reachable via the private agentfront.mcp_surface._build_run_tool, so a consumer MCP round-trip test must import an underscore-prefixed symbol
- After: a consumer can declare Flag(choices=[...]) and have out-of-set values rejected at parse time, and can obtain + inspect the single MCP run tool (its name + inputSchema, and dispatch a {command,args} call) through a public, documented API

## Why it matters

- these are the only two public-API friction points the full ~26-verb colleague migration hit; closing them makes validation and MCP-test ergonomics match the rest of the 0.14.0 consumer surface and spares the next import adopter from re-hitting them

## Requirements

- Flag gains `choices: Sequence[str] | None = None`; when set it is forwarded to argparse `add_argument(choices=...)` in `_flag_kwargs`, so an out-of-set value is rejected by the parser and flows through agentfront's existing `_CliParser` structured-error path (stderr text + --json), exactly like every other parse error
  - honesty: Flag(['--algo'], choices=['sha256','md5']) given '--algo crc32' exits non-zero with a {code,message,remediation} error on stderr, and that same error rendered as JSON under --json; a Flag declared without choices yields byte-identical parser behaviour to before the change (regression-guarded)
- a public, documented accessor exposes the single MCP run Tool — so a consumer can read its name and inputSchema and dispatch a {command,args} call — without importing the underscore-prefixed agentfront.mcp_surface._build_run_tool
  - honesty: the public accessor returns the SAME run Tool the server's list_tools yields (name=='run', inputSchema.required=={'command','args'}), and a {command,args} call dispatched through a public surface yields the identical result the equivalent CLI verb produces
- explain/overview for a flag declared with choices surfaces the allowed values to a reading agent
  - honesty: explain on a verb that has a choices flag surfaces the allowed values (in text and under --json) via the registry-derived path a consumer's rendered CLI uses

## Honesty conditions

- both gaps are closed against agentfront's live code: choices flows Flag → _flag_kwargs → argparse, and a public run-tool accessor exists in agentfront.mcp_surface / App; both are covered by tests and a CHANGELOG entry, with the teken wrapper kept in lockstep
- the audience is exactly import-adopter hosts (the App registry) plus the agents on the rendered surfaces; both gaps are felt by a REAL adopter (colleague), not hypothetical
- after shipping, one consumer test can (a) assert parse-time rejection of an out-of-set choices value and (b) read the run tool's name+inputSchema and dispatch it — using only public API
- the before-state is verifiable in 0.14.0 code: Flag has no 'choices' field, and the only path to the run tool is the underscore-prefixed _build_run_tool
- these two are the COMPLETE list of public-API friction from the ~26-verb migration — no third gap is silently bundled in or omitted
- the diff touches only choices plumbing + explain flag rendering + the run_tool accessor; it adds no second MCP tool and no new JSON-schema type coverage
- each clause of the success signal maps to an automated test that passes: parse-time reject, byte-identical no-choices Flag, and a public run-tool round-trip

## Success signals

- Flag(['--algo'], choices=['sha256','md5']) rejects '--algo crc32' at parse time with the structured {code,message,remediation} error on stderr and a non-zero exit (and as JSON under --json), a choices-less Flag is byte-identical to today, and a consumer obtains the run Tool + dispatches {command,args} through a public API in a test with no underscore-prefixed import

## Scope / boundaries

- scope is exactly the two asks: it is NOT a broader Flag overhaul (no Union/Optional schema work, no arbitrary per-flag validators beyond choices) and NOT a move to N MCP tools — the single-dispatch run tool stays the only MCP tool

## Decisions

- DECISION (user, 2026-06-26): expose the run tool as a public .run_tool attribute on the Server returned by app.mcp_server() (built internally from _build_run_tool), NOT a public build_run_tool function — one entry point, the server. Consumers needing it already have the [mcp] extra.
- DECISION (user, 2026-06-26): c10 is IN SCOPE — add choices-aware flag rendering to explain's leaf output (text + --json) via the registry-derived path, so `explain <verb>` shows a Flags section listing each flag and, for choices flags, the allowed value set.

## Hard questions (both RESOLVED — see Decisions)

> Note: the devague exporter lists hard questions without their `resolved` flag, so they read as open. Both were resolved with the user on 2026-06-26; resolutions recorded in the Decisions section above.

- **RESOLVED** — which public shape exposes the run tool: an attribute on the server returned by mcp_server() (e.g. .run_tool), a public build_run_tool(app) function (renaming the private _build_run_tool), or both?
  - **Decision:** a `.run_tool` attribute on the Server returned by `app.mcp_server()`, built internally from `_build_run_tool` (which stays private). One entry point — the server. Consumers needing it already have the `[mcp]` extra. (Not a public `build_run_tool`, not both.)
- **RESOLVED** — explain currently renders only a leaf's docstring, not its flags — is adding choices-aware flag rendering to explain in scope here, or is c10 deferred to a follow-up?
  - **Decision:** IN SCOPE. Add choices-aware flag rendering to `explain`'s leaf output (text + `--json`) via the registry-derived path, so `explain <verb>` shows a Flags section listing each flag and, for choices flags, the allowed value set.
