# Changelog

All notable changes to this project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/). This project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.1] - 2026-04-23

### Added

- docs/_sass/color_schemes/dark-terminal.scss, docs/_sass/custom/custom.scss — port the canonical culture design system (byte-identical to the copies in agex-cli and culture). Dark background (#0B0F12), bright-green accent (#41D67A), off-white text; custom hero, btn-cta, and docs-grid components.
- docs/_includes/head_custom.html — inline dark-bg preload so the page does not flash white on load, plus rel=related links back to Culture, agex, and AgentIRC.

### Changed

- docs/_config.yml: color_scheme dark -> dark-terminal so the new SCSS activates.
- docs/index.md: restructured the landing page to use the shared hero + btn-cta + docs-grid components. Visual parity with culture.dev/agex; copy is unchanged.

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
- __Policy:__ every PR now bumps the version, even docs-only or trivial ones. CLAUDE.md updated, and `.github/workflows/tests.yml` version-check gate no longer skips when only docs/config change. PyPI history and `CHANGELOG.md` now track each merged PR 1:1.

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
