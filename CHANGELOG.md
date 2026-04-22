# Changelog

All notable changes to this project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/). This project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-04-22

### Added

- CHANGELOG.md following Keep a Changelog / SemVer, seeded with the 0.1.0 scaffold entry.
- Imported the `version-bump` skill into the repo at `.claude/skills/version-bump/` (script + SKILL.md). Mirrors the AgentCulture flow used by `culture`; repo-local so the skill travels with the clone rather than depending on a per-contributor global install.

### Fixed

- afi/__main__.py: propagate main() exit code via sys.exit(main()) so python -m afi returns non-zero on failure (Qodo #1, Copilot).
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
