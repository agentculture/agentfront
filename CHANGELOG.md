# Changelog

All notable changes to this project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/). This project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.11.0] - 2026-06-23


### Added

- Importable runtime: `from agentfront import App` declares docs + tools once into a single registry (SSOT).
- HTTP surface — `app.http_app()` serves each markdown doc as a page plus an auto-generated `/sitemap.xml` (stdlib only, markdown+sitemap, no SPA).
- MCP surface — `app.mcp_server()` exposes registered functions as MCP tools via the official `mcp` SDK (name/description/schema from the signature+docstring); zero protocol code in the host.
- CLI surface — `app.cli()` / `run_cli()` build an argparse CLI (learn/doctor, --json) from the same registry.
- Runtime doctor (`agentfront.doctor_live`) auditing the live surfaces: sitemap presence, MCP menu-size threshold warning, learn affordance, each with remediation.
- Three-surface assembly (`agentfront.serve`) with a cross-surface agreement check proving CLI/MCP/HTTP enumerate the same set.
- Dogfood gate — agentfront serves its own three surfaces from its own config (`python -m agentfront._dogfood`), wired into CI.
- Worked-example third package under `examples/quickstart/` (~20-line config).
- Dependency on the `mcp` SDK (the first sanctioned outside-org dependency).


### Changed

- Pivot from a build-time code scaffolder to an importable runtime library: a host imports agentfront and gets all three agent-first surfaces from one code-first config.
- README and docs/agent-first.md now describe the runtime model as the shipped behavior.
- Retired the `cli cite` scaffolder and the manifest->three-surfaces generation vision (the `agentfront/cite/` package and the `cli cite` verb were removed). `cli doctor` and the rubric remain.


### Fixed

- `derive_input_schema` now resolves stringized annotations (PEP 563 / `from __future__ import annotations`) via `get_type_hints`, so tool schemas are correctly typed.

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
