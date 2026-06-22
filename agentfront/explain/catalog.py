"""Markdown catalog for ``agentfront explain <path>``.

Each entry is verbatim markdown. Keys are command-path tuples. The empty
tuple and ``("agentfront",)`` both resolve to the root entry (aliased). The legacy
``("teken",)`` key is kept as a back-compat alias for the renamed command.

Keep bodies self-contained — an agent reading a single entry should get
enough context without chaining reads.
"""

from __future__ import annotations

from agentfront import _brand

_ROOT = """\
# agentfront

agentfront is the AgentCulture Agent First Interface runtime. A host package
imports `agentfront.App`, declares its docs and tools once, and derives all
three agent-first surfaces (CLI, MCP server, HTTP site) from that single
registry. agentfront also audits any tool against the seven-bundle agent-first
rubric via `cli doctor`.

## Verbs

- `agentfront learn` — structured self-teaching prompt.
- `agentfront explain <path>` — markdown docs for any noun/verb.
- `agentfront overview [path]` — descriptive rollup across all interface surfaces.
- `agentfront doctor [path]` — self-diagnose agentfront or audit a target CLI; `--fix`
  applies auto-fixable remediations.
- `agentfront cli doctor [path]` — audit a CLI against the rubric (replaces
  `cli verify` in v0.5).
- `agentfront cli overview [path]` — read-only snapshot of a target CLI.

## Universal verb tier (agent-first)

Every agent-first CLI exposes the four universal verbs:

- `learn` — what is this tool?
- `explain <path>` — what does this command do?
- `overview [path]` — what is *present* in the subject the command addresses?
- `doctor [path]` — what is *wrong*, and how do I fix it?

## The runtime model

agentfront is an importable library, not a scaffolder:

```python
from agentfront import App

app = App(name="mytool", version="1.0")
app.add_docs_dir("docs/")

@app.tool
def search(query: str) -> str:
    \"\"\"Search the corpus.\"\"\"
    ...

app.cli()          # argparse CLI (learn / doctor)
app.mcp_server()   # MCP server (minimal tool menu)
app.http_app()     # WSGI site (markdown pages + sitemap)
```

Docs and tools are declared once into a single registry; the three surfaces
only read from it, so they cannot drift apart.

## Exit-code policy

- `0` success
- `1` user-input error (bad flag, bad path, missing arg)
- `2` environment / setup error (tool not installed, unreadable file)
- `3+` reserved

## See also

- `agentfront explain learn`
- `agentfront explain explain`
- `agentfront explain overview`
- `agentfront explain doctor`
- `agentfront explain cli doctor`
- `agentfront explain cli overview`
"""

_LEARN = """\
# agentfront learn

Prints a structured self-teaching prompt covering agentfront's purpose, command
map, exit-code policy, `--json` support, and `explain` pointer.

## Usage

    agentfront learn
    agentfront learn --json

In JSON mode, emits
`{"tool", "purpose", "commands", "exit_codes", "json_support", "explain_pointer"}`
to stdout.

## Rubric role

`learn` is bundle 2 (learnability) of the agent-first rubric. Any CLI that
passes bundle 2 prints ≥200 characters and mentions purpose, commands, exit
codes, `--json`, and `explain`.
"""

_EXPLAIN = """\
# agentfront explain <path>

Prints markdown documentation for any noun/verb path. Unlike `--help`
(terse, positional), `explain` is global and addressable by path.

## Usage

    agentfront explain agentfront
    agentfront explain learn
    agentfront explain cli
    agentfront explain cli doctor
    agentfront explain cli verify --json

In text mode emits the markdown to stdout. In JSON mode emits
`{"path": [...], "markdown": "..."}` to stdout.

## Path resolution

Paths are shell-tokenised: `agentfront explain cli doctor` resolves to the catalog
entry `("cli", "doctor")`. Unknown paths exit `1` with a `hint:` pointing at
`agentfront explain agentfront` for the top-level map.

## Rubric role

`explain` is bundle 5 of the agent-first rubric: every registered noun must
resolve, and bad paths must exit non-zero with remediation.
"""

_CLI = """\
# agentfront cli

The `cli` noun groups verbs that act on *a CLI project* (the target
project). From v0.5 there are two active verbs plus one deprecated alias:

- `agentfront cli doctor [path]` — run the seven-bundle agent-first rubric against
  the CLI at `<path>` and surface remediations; `--fix` applies any
  auto-fixable ones, `--dry-run` previews them.
- `agentfront cli overview [path]` — read-only descriptive snapshot of the CLI at
  `<path>` (or agentfront's own runtime model when no path is given).
- `agentfront cli verify [path]` — *deprecated* alias for `agentfront cli doctor`; will be
  removed in v0.6.0.

See `agentfront explain cli doctor` and `agentfront explain cli overview` for
details.
"""

_CLI_DOCTOR = """\
# agentfront cli doctor [path] [--json] [--fix] [--dry-run] [--strict]

Audit a CLI at `path` against the seven-bundle agent-first rubric and
surface inconsistencies with actionable remediation. Replaces
`agentfront cli verify` in v0.5; the old name is a deprecated alias.

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
`agentfront.doctor.fixes`; v0.5 ships the registry skeleton with no initial
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
# agentfront doctor [path] [--json] [--fix] [--dry-run] [--strict]

The diagnosability pillar of the agent-first contract. `doctor` answers
*what is wrong, and how do I fix it?* — distinct from `learn` (what is
this?), `explain` (what does this verb do?), and `overview` (what is
present?).

## Two modes

- **No path** — self-diagnosis of agentfront's own install. In-process, fast,
  read-only. Surveys version consistency (pyproject vs.
  importlib.metadata), CHANGELOG entry, surface coherence (every
  argparse leaf appears in `learn` and `explain`), reference-tree
  integrity, and rubric-module loadability.
- **With path** — black-box rubric audit of the target CLI, identical
  to `agentfront cli doctor <path>`.

## --fix and --dry-run

When run against a target, `--fix` applies auto-fixable remediations
(checks with `auto_fixable: true` and a `fix_id` in
`agentfront.doctor.fixes`); `--dry-run` previews the fix list without
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
# agentfront overview [path]

Emits a **read-only descriptive snapshot** of the interface surfaces
present in the target project. Descriptive, not diagnostic — see
`agentfront cli verify` for rubric grading.

## Universal verb triple

`overview` is the third verb of the agent-first universal triple
(`learn`, `explain`, `overview`). Other culture-embedded CLIs follow the
same pattern:

- `agex overview --agent <backend>` — agex config for a backend.
- `culture mesh overview` / `culture agent overview` — subject-of-noun.
- `agentfront cli overview [path]` / `agentfront overview [path]` — agentfront's two entry
  points.

## What it reports

- **agentfront overview [path]** — rollup across all agentfront surfaces. In v0.3 only
  the `cli` surface is implemented; `mcp` (v0.4) and `site` (v0.5) follow.
  Currently delegates to the `cli` inspector and appends a `> note:`
  about unimplemented surfaces.
- **agentfront cli overview [path]** — deep on the CLI subject: project root,
  command surface (detected nouns/verbs), agent-first triple presence,
  rubric posture, notes for agents.

## Zero-target default

If `path` is omitted, or the target has no detectable CLI surface, agentfront
describes **its own runtime model** — the importable `App` that derives the
CLI / MCP / HTTP surfaces from one registry, and the agent-first universal
verbs every surface ships. No file is read, so this fallback is complete and
deterministic.

## Usage

    agentfront overview
    agentfront overview .
    agentfront cli overview .
    agentfront cli overview /path/to/project
    agentfront cli overview --json .

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
    (_brand.PROG,): _ROOT,
    (_brand.LEGACY_PROG,): _ROOT,  # back-compat: `agentfront explain teken` still resolves
    ("learn",): _LEARN,
    ("explain",): _EXPLAIN,
    ("overview",): _OVERVIEW,
    ("doctor",): _DOCTOR,
    ("cli",): _CLI,
    ("cli", "doctor"): _CLI_DOCTOR,
    # Deprecated alias — keep the catalog entry so `agentfront explain cli verify`
    # still resolves while the alias is supported. Removed in v0.6.0.
    ("cli", "verify"): _CLI_DOCTOR,
    ("cli", "overview"): _OVERVIEW,
}
