# Changelog

All notable changes to this project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/). This project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.18.0] - 2026-06-27

### Added

- TAUI v0.2 work-loop cockpit: Background field (theme/animation/frame/semantic) and a conversation panel with consecutive-duplicate collapse on TAUIState
- TAUI SkillSuggested and WorkStep events; reducer now folds Tick (advances background.frame), UserInput (appends to the conversation panel), SkillSuggested (opens a skill-suggestion popup + sets background) and WorkStep (steps the work item, logs, and opens an error popup on failure)
- Structured 7-class diagnose_structured() (STATE/RENDER/LAYOUT/FOCUS/INPUT_ROUTING/THEME/POPUP_LIFECYCLE) alongside the existing flat diagnose()
- agentfront.taui.snapshot: write/read the snapshot quad (.taui.json/.ansi/.events.jsonl/.md), replay() to fold an event trail back to a state, and a JSON<->Markdown faithful() check
- selectors.resolve() now resolves zone keys (e.g. top.status); ANSI render gains a frame-driven status glyph and both renderers render the conversation panel

### Changed

- TAUI SCHEMA_VERSION bumped 0.1 -> 0.2; the JSON mirror now carries background + conversation
- Closed all 12 colleague-parity gaps tracked in test_taui_colleague_parity.py (unblocks colleague importing agentfront.taui instead of maintaining its own TUI)

### Fixed

- Dismissing a popup now also clears its blocking flag, and repeated failed WorkSteps refresh a single error popup, so diagnose_structured no longer false-positives on normal work-loop states
- Dismiss(target=id) now hides the named popup (colleague's by-id semantics); bare Dismiss() still hides the topmost. Repeated SkillSuggested events refresh a single skill-suggestion popup instead of appending duplicate ids. A malformed Tick delta (e.g. from a hand-edited event trail) degrades to a no-op frame advance instead of crashing replay()

## [0.17.0] - 2026-06-27

### Added

- TAUI — agentfront's fourth generated surface: one TAUIState renders to a JSON mirror (agent baseline), ANSI/TUI (human terminal), and markdown (readable), with stable ids, dotted-path selectors, and a derived available_actions list so an agent drives the exact UI a human uses.
- app.taui() / app.taui_mirror() / app.taui_driver() lazy accessors deriving a baseline cockpit from the App command registry (stdlib-only, no new dependency).
- agentfront.taui package: state, events, reducer (a single fold for both agent SelectorAction and human KeyPress), selectors, derive, mirror, diagnose (cross-render invariant), render/ansi, render/markdown, and a thin reference driver.

### Changed

- serve.surfaces_agree / surface_inventory and the dogfood gate now include TAUI as a fourth surface and run the cross-render diagnose (agentfront dogfoods its own TAUI).

## [0.16.0] - 2026-06-27

### Added

- An explicit `Flag` whose `dest` (or `--<param>` long option) matches a signature parameter now **replaces** that parameter's auto-derived CLI arg instead of colliding with it at build time (issue #40). Only the explicit `Flag` is registered, so it can carry `choices`/`type` for a **value-carrying** flag; the dispatcher still forwards the value because the parameter stays in the signature and the `Flag` writes to the same `dest`. The signature default is backfilled onto the merged flag when the `Flag` declares none, so omitting the flag yields the function's own default rather than `None`. This lets a value-carrying flag (e.g. `--algo sha256|md5` whose value the verb consumes) express its parse-time `choices` declaratively instead of a per-verb hand-rolled guard. Tools with no explicit `Flag` for a signature param are byte-identical to before; `Flag`-only flags are unchanged; `explain`/`overview` surface the merged flag's `choices` (as #38 already does).

## [0.15.0] - 2026-06-26

### Added

- `Flag(choices=...)` for issue #38 (Ask 1): a per-verb flag can declare an allowed value set, forwarded to argparse so an out-of-set value is rejected at parse time through agentfront's structured `{code,message,remediation}` error path (stderr text + `--json`), consistent with every other parse error. A choices-less `Flag` is byte-identical to before.
- Public `run_tool` attribute on the MCP server returned by `make_mcp_server(app)` / `app.mcp_server()` for issue #38 (Ask 2): it is the single `run` Tool the server lists, so a consumer can introspect its `name`/`inputSchema` or drive a `{command,args}` round-trip through a supported API instead of importing the private `_build_run_tool`.
- `explain <verb>` now renders a `Flags:` section (text) and a `flags` array (`--json`) for a registry-derived leaf, surfacing each flag's allowed values when it declares `choices` (issue #38 Ask 1, third criterion). The `flags` key is omitted for a flag-less op, so existing payloads are unchanged.

## [0.14.0] - 2026-06-26

### Added

- Public consumer CLI API for issue #35: App.cli()/run_cli render a host's full nested noun/verb CLI from the App registry (signature-derived args + tool dispatch, n-level groups via group=/app.group(), per-verb --json, structured AgentfrontError {code,message,remediation} to stderr, registry-derived explain/overview/learn, bare-noun->overview, rich per-verb flags, native aliases, app.add_command() host launcher verbs + no-command handler).
- Single-dispatch 'CLI on MCP' tool: app.mcp_server() now exposes ONE run tool taking {command,args} with the command catalog embedded, replacing N-tools.
- Public agentfront.errors.AgentfrontError; agentfront/_cli_core.py shared dispatch/error machinery; cross-surface invariant harness (serve.surfaces_agree) compares CLI == single MCP catalog == learn.
- docs/consumer-cli.md documenting the versioned public API.

### Changed

- agentfront.cli._errors.AfiError renamed to the public AgentfrontError (completes the deferred PR #22 rename).
- Maintainability cleanup of the new CLI surface (no behaviour change, all 442 tests green): split the explain/overview handlers and the signature/flag derivation into focused helpers to clear SonarCloud cognitive-complexity (S3776) and invariant-return (S3516) findings, merged a duplicated overview branch (S1871), hoisted the repeated `--json` help literal into a constant (S1192), and dropped the unused `doctor` handler arg (S1172).

## [0.13.1] - 2026-06-26

### Added

- Converged design spec for the public consumer CLI API (issue #35) at docs/specs/2026-06-26-agentfront-ships-a-public-consumer-cli-api-a-host.md — app.cli() renders a host's full nested noun/verb CLI from the App registry; MCP ships as a single-dispatch "CLI on MCP" tool; app.add_command() for host verbs; a public `AgentfrontError` (the structured error type, renamed from its legacy internal name — completing the deferred PR #22 rename). Authored via /think with sonnet-subagent and ask-colleague exploration.

## [0.13.0] - 2026-06-24

### Added

- **Memory-discipline "Conventions and workflow" section in `CLAUDE.md`** — a
  per-task *recall-before / remember-after* convention (scope localized to this
  repo's nick) so the vendored `remember` / `recall` skills are actually used,
  not just present: `/recall` before non-trivial work to build on prior
  decisions instead of re-deriving them, and `/remember` when a non-obvious
  decision, constraint, fix-and-why, or hard-won gotcha surfaces. The section
  documents this repo's memory as **in-repo and public** — records resolve to
  `<repo-root>/.eidetic/memory` (committed, team- and mesh-shared). Inserted
  idempotently (skipped if already present), slotted under an existing
  "Conventions and workflow" heading when one exists, else appended.

### Changed

- **Refreshed the `remember` + `recall` wrappers from eidetic-cli 0.10.0**
  (cite-don't-import) — picks up eidetic's **project-local store default**: the
  files backend now resolves per record by visibility — PUBLIC records inside a
  git repo go to `<repo-root>/.eidetic/memory` (committed, team-shared), PRIVATE
  records (or any record outside a repo) go to `$HOME/.eidetic/memory` (never
  committed), an explicit `EIDETIC_DATA_DIR` still wins, and recall reads both
  stores and merges. Also carries the 0.9.3 hardening (interactive-stdin guard,
  `help` as a search term, SIGPIPE-safe suffix parsing). **Recipe policy
  override (the wrappers here are NOT byte-verbatim):** the injected default
  visibility is flipped from eidetic's `private` to **`public`**, so a plain
  `/remember` lands the note in `./.eidetic/memory` in this repo, kept as part
  of the repo — pass `--visibility private` to route a record to `$HOME`
  instead. `remember` drives `eidetic remember` (idempotent upsert of one JSON
  record or an NDJSON batch on stdin); `recall` drives `eidetic recall` with
  four search modes (exact / approximate / keyword / hybrid). Each `SKILL.md` is
  localized only in the illustrative `--scope <nick>` examples (Provenance keeps
  "First-party to eidetic-cli"). Runtime dep: the `eidetic` CLI on PATH (else a
  local eidetic-cli checkout with `uv`) — **`eidetic >= 0.10.0`** for the
  in-repo routing; on an older CLI the public records still work but are stored
  in `$HOME/.eidetic/memory` instead of in-repo. Propagated by rollout-cli's
  `eidetic-memory` recipe.

### Fixed

- **teken wrapper bumped in lockstep to `0.13.0`** — the rollout-cli version
  bump did not carry `packaging/teken/pyproject.toml`, so the version,
  `agentfront==` pin, and `agentfront[mcp]==` pin lagged at `0.11.1`. That
  tripped the teken-lockstep CI guard and `tests/unit/test_wrapper_lockstep.py`.
  All three are now realigned to `0.13.0`.
- **Corrected the public-default docs in the `remember`/`recall` wrappers** —
  the recipe POLICY OVERRIDE flips the injected default visibility to `public`,
  but the `remember.sh` usage text and the `remember.sh`/`recall.sh` header
  comments still described eidetic's upstream `private` default. The docstrings
  and comments now state the `public` default (pass `--visibility private` to
  route a record to `$HOME`), matching behavior. Also hardened the
  `remember.sh` interactive-stdin guard to fire on a flags-only invocation that
  carries no JSON record (not just on zero args), so it can't hang on a TTY.
  These doc/guard fixes are filed upstream against the rollout-cli
  `eidetic-memory` recipe + eidetic-cli to be re-propagated.

## [0.12.0] - 2026-06-23

### Added

- **Vendored the `remember` + `recall` memory skills from eidetic-cli**
  (cite-don't-import) — the write/read halves of eidetic's shared
  `~/.eidetic/memory` surface, so this agent (Claude and its colleague backend)
  can persist facts across sessions and recall them later, sharing one store.
  `remember` drives `eidetic remember` (idempotent upsert of one JSON record or
  an NDJSON batch on stdin, dedup by id + content hash); `recall` drives
  `eidetic recall` with four search modes — exact / approximate / keyword /
  hybrid — each hit carrying text, full provenance metadata, a relevance score,
  and a freshness signal. The `.sh` wrappers are byte-verbatim from eidetic-cli
  (their first-party origin); each `SKILL.md` is localized only in the
  illustrative `--scope <nick>` examples (Provenance keeps "First-party to
  eidetic-cli"). Both default to this agent's PRIVATE scope, reading the suffix
  from `culture.yaml`. Runtime dep: the `eidetic` CLI on PATH (else a local
  eidetic-cli checkout with `uv`). Propagated by rollout-cli's `eidetic-memory`
  recipe.

## [0.11.1] - 2026-06-23

### Added

- packaging/teken: `teken[mcp]` extra at full parity with `agentfront[mcp]` — `uv tool install "teken[mcp]"` now pulls `agentfront[mcp]`. The new `agentfront[mcp]==<ver>` pin is kept in version-lockstep with the root project by the version-bump skill, the CI guard (`tests.yml`), and the TestPyPI dev-version step (`publish.yml`); a `tests/unit/test_wrapper_lockstep.py` regression covers all three pins. Resolves issue #31. (Downstream audit found no sibling consuming agentfront or its MCP surface, so the change is purely additive — no remediation needed.)

## [0.11.0] - 2026-06-23

### Added

- Importable runtime: `from agentfront import App` declares docs + tools once into a single registry (SSOT).
- HTTP surface — `app.http_app()` serves each markdown doc as a page plus an auto-generated `/sitemap.xml` (stdlib only, markdown+sitemap, no SPA).
- MCP surface — `app.mcp_server()` exposes registered functions as MCP tools via the official `mcp` SDK (name/description/schema from the signature+docstring); zero protocol code in the host. Ships behind the optional `agentfront[mcp]` extra (see Changed).
- CLI surface — `app.cli()` / `run_cli()` build an argparse CLI (learn/doctor, --json) from the same registry.
- Runtime doctor (`agentfront.doctor_live`) auditing the live surfaces: sitemap presence, MCP menu-size threshold warning, learn affordance, each with remediation.
- Three-surface assembly (`agentfront.serve`) with a cross-surface agreement check proving CLI/MCP/HTTP enumerate the same set.
- Dogfood gate — agentfront serves its own three surfaces from its own config (`python -m agentfront._dogfood`), wired into CI.
- Worked-example third package under `examples/quickstart/` (~20-line config).
- HTTP `/llms.txt` discovery endpoint listing the docs + tool menu from one well-known URL.

### Changed

- The `mcp` SDK is now an **optional extra** (`agentfront[mcp]`) rather than a hard runtime dependency. The CLI and HTTP surfaces are pure standard library, so the core install pulls in nothing third-party; install `agentfront[mcp]` only to use the MCP surface. `app.mcp_server()` without the extra raises a `ModuleNotFoundError` that names the extra to add. This keeps the org's first sanctioned outside-org dependency (the `mcp` SDK) opt-in.
- Pivot from a build-time code scaffolder to an importable runtime library: a host imports agentfront and gets all three agent-first surfaces from one code-first config.
- README and docs/agent-first.md now describe the runtime model as the shipped behavior.
- Retired the `cli cite` scaffolder and the manifest->three-surfaces generation vision (the `agentfront/cite/` package and the `cli cite` verb were removed). `cli doctor` and the rubric remain.

### Fixed

- `derive_input_schema` now resolves stringized annotations (PEP 563 / `from __future__ import annotations`) via `get_type_hints`, so tool schemas are correctly typed.
- `run_cli` preserves argparse's exit codes, so `--help` exits 0 instead of being reported as a failure.
- The three-surface agreement check uses the `mcp` SDK's public in-memory client session instead of private server internals.
- MCP surface now awaits `async def` tools before serializing the result, so a host can register coroutine tools without the surface returning a raw coroutine object (Qodo review finding).
- Internal quality pass on the new runtime surfaces (SonarCloud findings): `run_cli` translates argparse's exit via a private parser exception instead of catching `SystemExit`; HTTP status/content-type literals are named constants; `learn`/`doctor` CLI handlers no longer carry an invariant return value or an unused parameter; `# noqa` rationales moved out of the suppression code list.

## [0.10.2] - 2026-05-29

### Changed

- SonarCloud now ingests test coverage and shows it in the PR decoration. Added `relative_files = true` to `[tool.coverage.run]` so `coverage.xml` records repo-relative filenames (`agentfront/...`) that match `sonar.sources`; previously `coverage.py` recorded an absolute source root and stripped the `agentfront/` prefix from filenames, so SonarCloud could not match them and silently dropped coverage. Mirrors the sibling `devex` repo.

### Removed

- The `coverage.xml` sticky-comment bot (`.github/scripts/coverage_comment.py` and its Tests-workflow step), now redundant with native SonarCloud coverage in the PR decoration — matching `devex`, which has no such bot.

## [0.10.1] - 2026-05-29

### Added

- The Tests workflow now posts the `coverage.xml` result as a sticky comment on each PR (overall line/branch coverage plus a collapsible per-file table of anything below 100%), via `.github/scripts/coverage_comment.py`. It updates one comment in place across re-runs and surfaces the real coverage number even on PRs where SonarCloud's "new code" period has nothing to measure.

### Changed

- CI now blocks on the SonarCloud quality gate (`sonar.qualitygate.wait=true` in `sonar-project.properties`), matching the sibling `convertible` repo — a red gate (coverage regression on new code, new bugs/vulnerabilities) fails the Tests workflow. The scan/gate stays a no-op on token-less repos and fork PRs, and the Scan step is bounded by a 10-minute `timeout-minutes` so a slow gate can't stall CI.

### Fixed

- Documented `python3` as a runtime dependency of the vendored `assign-to-workforce` skill (its `split-plan` subcommand renders the table via an inline `python3` program) in `docs/skill-sources.md`, resolving a Qodo review finding on PR #25. The vendored script stays verbatim; a preflight `python3` guard with a clear error is deferred upstream to devague per the skills-portability rule.

## [0.10.0] - 2026-05-29

### Added

- Vendored the devague workflow trio under `.claude/skills/` (cite, don't import): `think` (idea→spec), `spec-to-plan` (spec→plan), and `assign-to-workforce` (plan→parallel implementation) — the agent-facing operator chain for the deterministic `devague` CLI. Cited from `agentculture/guildmaster`'s mesh-broadcast copy (authored upstream in `agentculture/devague`); each ships `type: command` frontmatter (load-bearing on the culture/agex backend) and a single entry-point script. Runtime dep: `uv tool install devague`. Recorded in `docs/skill-sources.md`. Closes #23.

## [0.9.0] - 2026-05-29

### Added

- `teken` retained as a deprecated CLI alias: it prints a one-line deprecation notice to stderr, then forwards to `agentfront`.
- `teken` retained as a thin PyPI compatibility wrapper that depends on `agentfront==<version>`, so `uv tool install teken` keeps working and installs `agentfront`.

### Changed

- **Breaking:** Renamed the project from `teken` to `agentfront` — the agent-facing front a tool presents. The canonical PyPI distribution and the import package are now `agentfront`; the primary CLI command is `agentfront`.
- Cited reference trees now write to `.agentfront/` instead of `.teken/` (existing `.teken/` trees are still detected on read for backward compatibility).
- Renamed the GitHub repo, PyPI Trusted Publisher, Cloudflare Pages project, and SonarCloud project key (`agentculture_agentfront`) to match.

### Removed

- Retired the older `afi` surface left over from the previous rename: the `afi` console command, the `afi-cli` PyPI wrapper distribution, and `.afi/` read-detection are gone. (`afi-cli` stays on PyPI at its last release but is no longer published.)

## [0.8.0] - 2026-05-22

### Added

- `afi` retained as a deprecated CLI alias: it prints a one-line deprecation notice to stderr, then forwards to `teken`.
- `afi-cli` retained as a thin PyPI compatibility wrapper that depends on `teken==<version>`, so `uv tool install afi-cli` keeps working and installs `teken`.

### Changed

- **Breaking:** Renamed the project from `afi` to `teken` (Hebrew תֶּקֶן, "standard"). The canonical PyPI distribution and the import package are now `teken`; the primary CLI command is `teken`.
- Cited reference trees now write to `.teken/` instead of `.afi/` (existing `.afi/` trees are still detected on read for backward compatibility).
- Removed `python -m afi` — use `python -m teken` (the `afi` console command still works as an alias).

## [0.7.0] - 2026-05-12

### Added

- Vendored `cicd` skill from steward (`.claude/skills/cicd/`) — `agex pr`-layered workflow with steward-derived `status` and `await` extensions. Resolves [#17](https://github.com/agentculture/afi-cli/issues/17).
- Vendored `communicate` skill from steward (`.claude/skills/communicate/`) — cross-repo GitHub issue I/O (post/comment/fetch) plus Culture mesh messaging, backed by `agtag` for signature resolution. Resolves [#18](https://github.com/agentculture/afi-cli/issues/18).
- `docs/skill-sources.md` ledger tracking upstream provenance and local divergence for each vendored skill.
- `culture.yaml` declaring `afi-cli` as the agent nick (so `agtag` resolves issue signatures as `- afi-cli (Claude)` instead of falling back to the git remote basename).

## [0.6.3] - 2026-05-12

### Added

- SonarCloud pipeline: integrate scan step into tests workflow with coverage.xml input; add sonar-project.properties pointing at agentculture_afi-cli.

## [0.6.2] - 2026-05-06

### Changed

- doctor: extract _DEFAULT_DOCTOR_COMMAND constant for the default verb name threaded into resolver remediations (SonarCloud duplicate-literal finding on PR #14)

## [0.6.1] - 2026-05-06

### Fixed

- afi doctor --package: validate PEP 610 dir_info.editable so non-editable file:// installs are rejected with a clear remediation (PR #14 review)
- afi doctor / afi cli doctor: error remediation now names the verb the user invoked instead of hardcoding afi doctor (PR #14 review)

## [0.6.0] - 2026-05-05

### Added

- `afi doctor --package <name>` and `afi cli doctor --package <name>`: resolve an editable-installed distribution to its source root via PEP 610 `direct_url.json` so an agent can audit a target tool from anywhere without knowing its filesystem location (issue #13).

### Changed

- `afi doctor` self-mode headline now reads `afi doctor: structural self-check passed (N/M). Run 'afi doctor <path>' to audit a target CLI.` instead of the bare `healthy: N/M passed, ...`. Target-audit headline is unchanged. Removes the "green light is over-confident" framing flagged in issue #13.

### Fixed

- `afi doctor`: clearer error when the positional argument is not a project root. The remediation now names both `afi doctor .` and `--package <name>` so an agent learns the contract from the diagnostic (issue #13).

## [0.5.0] - 2026-04-26

### Added

- afi doctor [path] — global verb. With no path, runs the in-process self-diagnosis (version consistency, CHANGELOG entry, surface coherence between argparse / learn / explain, reference-tree integrity, rubric module loadability). With a path, forwards to the target audit. Supports --json, --fix, --dry-run, --strict.
- afi cli doctor [path] — replaces afi cli verify as the rubric audit verb. Adds --fix (apply auto-fixable remediations) and --dry-run (preview them). Same exit-code policy as verify.
- Rubric bundle 7 (doctor) — asserts the target CLI exposes a doctor verb with the agent-first contract: non-empty report on stdout, --json carries healthy (bool) + checks (list), each check has id/passed/severity/message, failed checks supply remediation. Mirrors the bundle-6 (overview) pattern.
- afi.doctor package — public surface (run_self_diagnosis, Diagnosis, is_healthy) plus the fix registry skeleton (register_fix / apply_fix / FixOutcome). v0.5 ships the registry with no initial handlers; remediations are explain-how-to-fix until follow-ups populate the table.
- CheckResult: auto_fixable (bool) and fix_id (str) fields, surfaced in to_dict().

### Changed

- Universal verb tier expanded from learn/explain/overview to learn/explain/overview/doctor; afi.overview.cli_surface enumerates the four under heading Agent-first universals (was Agent-first triple).
- afi learn output now lists overview, doctor, cli doctor, cli overview alongside the existing verbs (closes a long-standing drift introduced when overview shipped in v0.3).
- afi explain catalog gains doctor and cli doctor entries; cli verify now resolves to the cli doctor body during the deprecation window.
- docs/agent-first.md adds diagnosability as the fourth pillar; docs/rubric.md adds Bundle 6 (overview) and Bundle 7 (doctor) sections and bumps the preamble from five to seven bundles.
- afi/cite/references/python-cli/AGENT.md updated to list all seven rubric bundles and point at afi cli doctor.
- tests/test_self_verify.py renamed to tests/test_self_doctor.py; expected bundle set is now seven; new in-process self-diagnosis assertion.

## [0.4.1] - 2026-04-23

### Added

- docs/_sass/color_schemes/dark-terminal.scss, docs/_sass/custom/custom.scss — port the canonical culture design system (byte-identical to the copies in agex-cli and culture). Dark background (#0B0F12), bright-green accent (#41D67A), off-white text; custom hero, btn-cta, and docs-grid components.
- docs/_includes/head_custom.html — inline dark-bg preload so the page does not flash white on load, plus rel=related links back to Culture, agex, and AgentIRC.

### Changed

- docs/_config.yml: color_scheme dark -> dark-terminal so the new SCSS activates.
- docs/index.md: restructured the landing page to use the shared hero + btn-cta + docs-grid components. Visual parity with culture.dev/agex; hero and card copy were rewritten to match the new layout.

## [0.4.0] - 2026-04-23

### Added

- docs/_config.yml, docs/Gemfile, docs/index.md, docs/.gitignore — Jekyll site scaffold modeled on agex-cli with just-the-docs theme, baseurl /afi, and jekyll-sitemap plugin so /afi/sitemap.xml is auto-generated on build.
- .github/workflows/docs.yml — PR preview + main deploy pipeline to Cloudflare Pages project afi (Direct Upload via wrangler). Deploy step is gated on CLOUDFLARE_API_TOKEN presence so CI stays green until secrets land via agentculture/cloudflare.

### Changed

- docs/ layout now follows the agex-cli pattern: existing agentculture.md, agent-first.md, and rubric.md render under <https://culture.dev/afi/> without content edits.

## [0.3.0] - 2026-04-23

### Added

- afi cli overview [path] — read-only markdown snapshot of a target CLI (entry point, command surface, agent-first triple presence, rubric posture). Falls back to afi's own scaffolded template when path is omitted or the target has no detectable CLI surface.
- afi overview [path] — top-level rollup across interface surfaces; currently reports cli only (mcp and site follow in v0.4 / v0.5). Delegates to the cli inspector and notes unimplemented surfaces.
- Rubric bundle 6 (overview_cmd) — asserts target CLIs expose a top-level `overview` verb, an `overview` verb under the `cli` noun, a stable `--json` shape with `subject` and `sections` keys, and graceful fallback on missing target paths.
- Structure-bundle `main_entry_contract` check — probes the target's [project.scripts] entry via a uv subprocess to confirm the function matches `main(argv: list[str] | None = None) -> int` and does not `sys.exit` on normal paths (argparse --help SystemExit(0) is tolerated).
- Universal verb triple documented in the explain catalog: `learn` / `explain` / `overview` are mandated on every agent-first CLI; afi now self-verifies against the full triple.

## [0.2.0] - 2026-04-22

### Added

- `afi explain <path>` — global markdown catalog lookup; resolves any noun/verb path to structured markdown. `--json` mode emits `{path, markdown}`.
- `afi cli cite [path]` — emit the agent-first Python CLI reference tree into `<path>/.afi/reference/python-cli/` with literal `{{tokens}}`; adds `.afi/` to `.gitignore` if missing; writes `AGENT.md` and `MANIFEST.json`. Safe for brownfield use (only touches `.afi/` plus one gitignore line).
- `afi cli verify [path]` — five-bundle agent-first rubric auditor: structure, learnability, json, errors, explain. Supports `--json` and `--strict`.
- Exit-code policy: `0` success / `1` user error / `2` environment error; `3+` reserved.
- Self-verify acceptance gate: `afi cli verify` on the afi-cli repo passes every bundle; `tests/test_self_verify.py` blocks regressions.
- `docs/rubric.md` — canonical five-bundle checklist.

### Changed

- `afi learn` now emits a structured self-teaching prompt (purpose, command map, exit codes, `--json`, `explain`); `--json` mode emits a typed payload.
- `afi/cli/__init__.py` refactored: `_AfiArgumentParser` routes argparse errors through our structured format (so unknown verbs carry a `hint:` line); error handling centralised in `_dispatch`.
- Coverage threshold raised from 50% to 70% (current coverage ~82%).

## [0.1.2] - 2026-04-22

### Added

- docs/agentculture.md — description of the AgentCulture OSS org, the agents-as-members model, current project list, and how to contribute.
- docs/agent-first.md — the Agent First paradigm in depth: the human-vs-agent design reversal, the three interface disciplines (learnability on CLI, minimalism on MCP, discoverability on HTTP), afi-cli's foundational role, the dogfooding loop, and the Agent First review gate.

### Changed

- README.md and CLAUDE.md: link the two new docs so humans and future Claude sessions read the org context before making design decisions.
- **Policy:** every PR now bumps the version, even docs-only or trivial ones. CLAUDE.md updated, and `.github/workflows/tests.yml` version-check gate no longer skips when only docs/config change. PyPI history and `CHANGELOG.md` now track each merged PR 1:1.

## [0.1.1] - 2026-04-22

### Added

- CHANGELOG.md following Keep a Changelog / SemVer, seeded with the 0.1.0 scaffold entry.
- Imported the `version-bump` skill into the repo at `.claude/skills/version-bump/` (script + SKILL.md). Mirrors the AgentCulture flow used by `culture`; repo-local so the skill travels with the clone rather than depending on a per-contributor global install.

### Fixed

- `afi/__main__.py`: propagate main() exit code via sys.exit(main()) so python -m afi returns non-zero on failure (Qodo #1, Copilot).
- publish.yml: use uv run python -c for tomllib version read so the dev-version step uses the uv-managed 3.12 interpreter instead of whatever python is on PATH (Qodo #3).
- publish.yml: guard test-publish on same-repo PRs (head.repo.full_name == github.repository) so fork PRs do not attempt OIDC trusted publishing and fail CI for external contributors (Qodo #4).

## [0.1.0] - 2026-04-22

### Added

- Initial package scaffold: `afi/` with `__init__.py` (version via
  `importlib.metadata`), `__main__.py` (`python -m afi`), and
  `afi/cli/__init__.py` holding an argparse entry point.
- `afi learn` subcommand — prototype of the agent-learnability affordance,
  printing a minimal self-description.
- `pyproject.toml` with hatchling build and `afi = "afi.cli:main"` console
  script, installable via `uv tool install afi-cli`.
- Dev toolchain mirroring `culture` conventions: pytest (xdist, cov), bandit,
  pylint, flake8 + bandit + bugbear plugins, black, isort, pre-commit.
- CI workflows: `tests.yml` (pytest + coverage + version-check gate),
  `publish.yml` (TestPyPI on PR, PyPI on push to main via OIDC Trusted
  Publishing), `security-checks.yml` (weekly bandit/pylint).
- Pre-commit extended with Python hooks (flake8, isort, black) alongside the
  pre-existing markdownlint-cli2 check.
- `CLAUDE.md` and `README.md` pivoted from greenfield to early-alpha with the
  stack choices recorded; install path documented as `uv tool install afi-cli`.
- Markdown lint tooling: `scripts/lint-md.sh` (auto-fix) and
  `.claude/skills/lint-markdown/SKILL.md`.
