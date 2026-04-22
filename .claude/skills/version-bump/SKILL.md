---
name: version-bump
description: >
  Bump the semver version in pyproject.toml (major, minor, or patch) and
  prepend a Keep-a-Changelog entry to CHANGELOG.md. Use when preparing a
  release, before creating a PR (the version-check CI job blocks merge if
  you don't), or when the user says "bump version", "release", or
  "increment version".
---

# Version Bump

Bump the semver version in `pyproject.toml` and prepend a new entry to
`CHANGELOG.md`. Mirrors the AgentCulture workflow used by `culture` and
other org repos; imported here so the repo is self-contained.

## Usage

Run from the repo root.

```bash
# With changelog content (pipe JSON via stdin):
echo '{"added":["New X"],"changed":["Refactored Y"],"fixed":["Bug in Z"]}' \
  | python3 .claude/skills/version-bump/scripts/bump.py minor

# Without changelog content (inserts empty ### Added/Changed/Fixed stubs):
python3 .claude/skills/version-bump/scripts/bump.py patch

# Check current version without bumping:
python3 .claude/skills/version-bump/scripts/bump.py show
```

## Bump Types

| Type    | Example        | When to use                                                       |
|---------|----------------|-------------------------------------------------------------------|
| `major` | 0.1.0 → 1.0.0  | Breaking changes, namespace restructures, CLI surface breaks      |
| `minor` | 0.1.0 → 0.2.0  | New features, new commands, new modules                           |
| `patch` | 0.1.0 → 0.1.1  | Bug fixes, doc updates, dependency bumps, CI-only changes         |
| `show`  | prints `0.1.0` | Read-only — no files changed                                      |

## Changelog JSON Format

Pass via stdin. All fields are optional — only non-empty sections are rendered.

```json
{
  "added":   ["List of new features"],
  "changed": ["List of changes to existing functionality"],
  "fixed":   ["List of bug fixes"]
}
```

## What It Updates

1. `pyproject.toml` — the `version = "x.y.z"` field (single source of truth;
   `afi/__init__.py` reads it via `importlib.metadata`, so there is no
   separate `__version__` string to keep in sync).
2. `CHANGELOG.md` — inserts a new `## [x.y.z] - YYYY-MM-DD` entry at the top.

## Workflow

When invoking this skill, the agent should:

1. Determine the bump type from the staged/unstaged diff (patch for fixes,
   minor for new features, major for breaking changes).
2. Summarize the changes into `added` / `changed` / `fixed` lists.
3. Pipe the JSON and run the script.
4. Verify with `show`.
5. Commit the bumped `pyproject.toml` + `CHANGELOG.md` alongside the code
   changes, so the version-check CI job sees a consistent bump.

## Why repo-local (not the user-global skill)

A matching skill exists at `~/.claude/skills/version-bump/` for personal use,
but committing it into this repo means:

- The skill travels with the clone — CI hooks, other contributors, and
  agents on fresh machines all discover it without personal configuration.
- The `.md` paths in this SKILL.md reference the in-repo script, so the
  guidance is accurate regardless of whether the user has the global skill.
