"""Markdown catalog for ``afi explain <path>``.

Each entry is verbatim markdown. Keys are command-path tuples. The empty
tuple and ``("afi",)`` both resolve to the root entry (aliased).

Keep bodies self-contained — an agent reading a single entry should get
enough context without chaining reads.
"""

from __future__ import annotations

_ROOT = """\
# afi

afi is the AgentCulture Agent First Interface scaffolder. It emits reference
drops for agent-first CLIs (and, later, MCP servers and HTTP sites) and
audits any tool against the seven-bundle agent-first rubric.

## Verbs

- `afi learn` — structured self-teaching prompt.
- `afi explain <path>` — markdown docs for any noun/verb.
- `afi overview [path]` — descriptive rollup across all interface surfaces.
- `afi doctor [path]` — self-diagnose afi or audit a target CLI; `--fix`
  applies auto-fixable remediations.
- `afi cli cite [path]` — drop the CLI reference pattern into a project.
- `afi cli doctor [path]` — audit a CLI against the rubric (replaces
  `cli verify` in v0.5).
- `afi cli overview [path]` — read-only snapshot of a target CLI.

## Universal verb tier (agent-first)

Every agent-first CLI exposes the four universal verbs:

- `learn` — what is this tool?
- `explain <path>` — what does this command do?
- `overview [path]` — what is *present* in the subject the command addresses?
- `doctor [path]` — what is *wrong*, and how do I fix it?

## Principles

afi is deliberately dumb: it emits references with literal `{{tokens}}` and
never merges into a consumer project. The agent running afi handles
integration. Pre-commit, CI, and other agent-workflow tooling live in the
sibling project `agex-cli`.

## Exit-code policy

- `0` success
- `1` user-input error (bad flag, bad path, missing arg)
- `2` environment / setup error (tool not installed, unreadable file)
- `3+` reserved

## See also

- `afi explain learn`
- `afi explain explain`
- `afi explain overview`
- `afi explain doctor`
- `afi explain cli cite`
- `afi explain cli doctor`
- `afi explain cli overview`
"""

_LEARN = """\
# afi learn

Prints a structured self-teaching prompt covering afi's purpose, command
map, exit-code policy, `--json` support, and `explain` pointer.

## Usage

    afi learn
    afi learn --json

In JSON mode, emits
`{"tool", "purpose", "commands", "exit_codes", "json_support", "explain_pointer"}`
to stdout.

## Rubric role

`learn` is bundle 2 (learnability) of the agent-first rubric. Any CLI that
passes bundle 2 prints ≥200 characters and mentions purpose, commands, exit
codes, `--json`, and `explain`.
"""

_EXPLAIN = """\
# afi explain <path>

Prints markdown documentation for any noun/verb path. Unlike `--help`
(terse, positional), `explain` is global and addressable by path.

## Usage

    afi explain afi
    afi explain learn
    afi explain cli
    afi explain cli cite
    afi explain cli verify --json

In text mode emits the markdown to stdout. In JSON mode emits
`{"path": [...], "markdown": "..."}` to stdout.

## Path resolution

Paths are shell-tokenised: `afi explain cli cite` resolves to the catalog
entry `("cli", "cite")`. Unknown paths exit `1` with a `hint:` pointing at
`afi explain afi` for the top-level map.

## Rubric role

`explain` is bundle 5 of the agent-first rubric: every registered noun must
resolve, and bad paths must exit non-zero with remediation.
"""

_CLI = """\
# afi cli

The `cli` noun groups verbs that act on *a CLI project* (the target
project). From v0.5 there are three active verbs plus one deprecated alias:

- `afi cli cite [path]` — drop the Python agent-first reference tree into
  `<path>/.afi/reference/python-cli/` for an agent to integrate.
- `afi cli doctor [path]` — run the seven-bundle agent-first rubric against
  the CLI at `<path>` and surface remediations; `--fix` applies any
  auto-fixable ones, `--dry-run` previews them.
- `afi cli overview [path]` — read-only descriptive snapshot of the CLI at
  `<path>` (or afi's own scaffolded template when no path is given).
- `afi cli verify [path]` — *deprecated* alias for `afi cli doctor`; will be
  removed in v0.6.0.

See `afi explain cli cite`, `afi explain cli doctor`, and
`afi explain cli overview` for details.
"""

_CLI_CITE = """\
# afi cli cite [path] [--lang LANG] [--out DIR] [--json]

Emit the agent-first CLI reference tree into the target project.

## What it does

1. Copies the reference tree (bundled with afi-cli under
   `afi/cite/references/<lang>-cli/`) to `<path>/.afi/reference/<lang>-cli/`
   wholesale. Tokens `{{project_name}}`, `{{slug}}`, `{{module}}` are left
   **literal** — the agent consuming the reference substitutes them.
2. Adds `.afi/` to `<path>/.gitignore` if missing. Never modifies
   `.gitignore` otherwise.
3. Never touches anything outside `<path>/.afi/` and the single gitignore
   line.

Re-running wipes and re-writes `<path>/.afi/reference/<lang>-cli/` —
always the latest reference. The `.gitignore` line is check-before-modify.

## Arguments

- `path` (optional, default `.`) — target project directory.
- `--lang` — reference language. v0.2 supports `python`.
- `--out DIR` — override the output directory (default:
  `<path>/.afi/reference/<lang>-cli/`).
- `--json` — emit the report as a JSON object instead of text.

## Output contains

- Count of files written and their root directory.
- Whether `.gitignore` was updated.
- A three-step `next_steps` list: read AGENT.md, apply the pattern,
  run `afi cli verify .`.
- Pointers to `afi explain cli cite` and `afi explain cli verify` for
  more detail.

## Exit codes

- `0` success
- `1` user error (bad lang, missing target, bad `--out`)
- `2` environment error (reference tree missing in install)
"""

_CLI_DOCTOR = """\
# afi cli doctor [path] [--json] [--fix] [--dry-run] [--strict]

Audit a CLI at `path` against the seven-bundle agent-first rubric and
surface inconsistencies with actionable remediation. Replaces
`afi cli verify` in v0.5; the old name is a deprecated alias.

## Bundles

1. **structure** — `pyproject.toml` with `[project.scripts]`, `tests/`
   dir, `<tool> --help` exits 0, target `main(argv: list[str] | None =
   None) -> int` signature conforms.
2. **learnability** — `<tool> learn` exits 0, stdout ≥ 200 chars, mentions
   purpose, commands, exit codes, `--json`, `explain`.
3. **json** — `<tool> learn --json` is parseable; stderr clean on success;
   `<tool> explain --json` works.
4. **errors** — bogus verb exits non-zero with a `hint:` line, no Python
   traceback; exit-code policy documented in `learn`.
5. **explain** — `<tool> explain` and `<tool> explain <tool>` succeed;
   bogus path fails with remediation.
6. **overview** — `<tool> overview` and `<tool> cli overview` succeed;
   `overview --json` carries the stable keys `subject` + `sections`;
   missing target paths fall back gracefully.
7. **doctor** — `<tool> doctor` produces a non-empty report;
   `<tool> doctor --json` carries `healthy` (bool) + `checks` (list);
   each check entry has `id`, `passed`, `severity`, `message`; failed
   checks supply a non-empty `remediation`.

## --fix and --dry-run

Failed checks may declare `auto_fixable: true` and a `fix_id`. With
`--fix`, doctor invokes the registered handler for each fixable check
and re-runs the rubric to report the post-fix verdict. With `--dry-run`
it lists the planned fixes without mutating. The fix registry lives in
`afi.doctor.fixes`; v0.5 ships the registry skeleton with no initial
handlers (every remediation is "explain how to fix" until follow-up PRs
populate the table).

## Strategy

Hybrid: static file checks (pyproject, tests/) + black-box subprocess
probes for every behavioral check. `<tool>` is resolved from
`[project.scripts]`; if not on PATH, falls back to `uv run --project
<path>`.

## Arguments

- `path` (optional, default `.`) — target project directory.
- `--json` — emit `{tool, subject, healthy, checks, summary}`.
- `--fix` — apply auto-fixable remediations in place.
- `--dry-run` — preview which fixes would run, without mutating.
- `--strict` — treat warnings as failures.

## Exit codes

- `0` if no `error`-severity check failed (strict: no failure at all).
- `1` if the rubric failed.
- `2` if doctor itself couldn't set up (can't find the tool, no
  pyproject, etc.).
"""

_DOCTOR = """\
# afi doctor [path] [--json] [--fix] [--dry-run] [--strict]

The diagnosability pillar of the agent-first contract. `doctor` answers
*what is wrong, and how do I fix it?* — distinct from `learn` (what is
this?), `explain` (what does this verb do?), and `overview` (what is
present?).

## Two modes

- **No path** — self-diagnosis of afi's own install. In-process, fast,
  read-only. Surveys version consistency (pyproject vs.
  importlib.metadata), CHANGELOG entry, surface coherence (every
  argparse leaf appears in `learn` and `explain`), reference-tree
  integrity, and rubric-module loadability.
- **With path** — black-box rubric audit of the target CLI, identical
  to `afi cli doctor <path>`.

## --fix and --dry-run

When run against a target, `--fix` applies auto-fixable remediations
(checks with `auto_fixable: true` and a `fix_id` in
`afi.doctor.fixes`); `--dry-run` previews the fix list without
mutating. Self-doctor is read-only; `--fix` and `--dry-run` are no-ops
there (a diagnostic message is emitted to stderr).

## JSON shape

    {
      "tool": str,
      "subject": str,
      "healthy": bool,
      "checks": [
        {
          "id": str,
          "bundle": str,
          "passed": bool,
          "severity": "error" | "warn" | "info",
          "message": str,
          "remediation": str,
          "auto_fixable": bool,
          "fix_id": str
        }, ...
      ],
      "summary": {"total": int, "passed": int, "failed": int,
                  "errors": int, "warnings": int}
    }

The `healthy` and `checks` keys, plus the per-check `id` / `passed` /
`severity` / `message` / `remediation` shape, are mandated by rubric
bundle 7 — every agent-first CLI's `doctor --json` must conform.

## Exit codes

- `0` if no `error`-severity check failed (strict: no failure at all).
- `1` if any check failed.
- `2` if doctor itself couldn't set up.
"""


_OVERVIEW = """\
# afi overview [path]

Emits a **read-only descriptive snapshot** of the interface surfaces
present in the target project. Descriptive, not diagnostic — see
`afi cli verify` for rubric grading.

## Universal verb triple

`overview` is the third verb of the agent-first universal triple
(`learn`, `explain`, `overview`). Other culture-embedded CLIs follow the
same pattern:

- `agex overview --agent <backend>` — agex config for a backend.
- `culture mesh overview` / `culture agent overview` — subject-of-noun.
- `afi cli overview [path]` / `afi overview [path]` — afi's two entry
  points.

## What it reports

- **afi overview [path]** — rollup across all afi surfaces. In v0.3 only
  the `cli` surface is implemented; `mcp` (v0.4) and `site` (v0.5) follow.
  Currently delegates to the `cli` inspector and appends a `> note:`
  about unimplemented surfaces.
- **afi cli overview [path]** — deep on the CLI subject: project root,
  command surface (detected nouns/verbs), agent-first triple presence,
  rubric posture, notes for agents.

## Zero-target default

If `path` is omitted, or the target has no detectable CLI surface, afi
describes **its own scaffolded reference template** (the tree under
`afi/cite/references/python-cli/`). afi knows its own creations
perfectly, so this fallback is complete and deterministic.

## Usage

    afi overview
    afi overview .
    afi cli overview .
    afi cli overview /path/to/project
    afi cli overview --json .

## JSON shape

    {
      "subject": str,
      "path": str | null,
      "sections": [{"heading": str, "body_md": str, "findings": [...]}],
      "warnings": [str, ...],
      "notes": [str, ...]
    }

Stable keys — culture's embed helper can machine-read the output.

## Rubric role

Rubric bundle 6 (`overview_cmd`) asserts:

- a top-level `overview` verb exists and works (non-empty stdout);
- every noun with action-verbs also exposes an `overview` verb (checked
  against the `cli` noun today; generalises as nouns are added);
- `overview --json` carries the stable keys `subject` and `sections`;
- missing target paths fall back gracefully (exit 0 with a warning) —
  descriptive verbs must not hard-fail the way `verify` does.

The **read-only** invariant is a *design* contract — the verb has no
mutating flags (`--out`, `--write`, etc.) — rather than a runtime
filesystem probe, keeping the rubric fast and black-box.
"""


ENTRIES: dict[tuple[str, ...], str] = {
    (): _ROOT,
    ("afi",): _ROOT,
    ("learn",): _LEARN,
    ("explain",): _EXPLAIN,
    ("overview",): _OVERVIEW,
    ("doctor",): _DOCTOR,
    ("cli",): _CLI,
    ("cli", "cite"): _CLI_CITE,
    ("cli", "doctor"): _CLI_DOCTOR,
    # Deprecated alias — keep the catalog entry so `afi explain cli verify`
    # still resolves while the alias is supported. Removed in v0.6.0.
    ("cli", "verify"): _CLI_DOCTOR,
    ("cli", "overview"): _OVERVIEW,
}
