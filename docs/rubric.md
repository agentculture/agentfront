---
title: Rubric
nav_order: 3
---

The rubric is the concrete, checkable form of the [Agent First](./agent-first.md) discipline. It is what `agentfront cli doctor` enforces and what `agentfront cli cite` emits a reference for.

Seven bundles. Every bundle contains a small set of mechanical checks. A CLI that passes every bundle is "agent-first compliant" by agentfront's definition. `agentfront` itself must pass — the `tests/test_self_doctor.py` acceptance gate blocks any regression.

> Note: `agentfront cli verify` is a deprecated alias for `agentfront cli doctor` retained through one minor cycle (removed in v0.6.0).

## Exit-code policy

| Code  | Meaning                                            |
| ----- | -------------------------------------------------- |
| `0`   | success                                            |
| `1`   | user-input error (bad flag, bad path, missing arg) |
| `2`   | environment / setup error (tool not installed, unreadable file) |
| `3+`  | reserved                                           |

## Bundle 1 — structure

**What it checks** *(static)*:

- `pyproject.toml` exists with a `[project.scripts]` entry.
- `tests/` directory exists.
- `<tool> --help` exits `0` and prints usage.

**Why:** Agent-first tools are installable and introspectable. The entry point must be findable from `pyproject.toml` without reading source. A `tests/` directory signals the tool is maintained.

## Bundle 2 — learnability

**What it checks** *(black-box)*:

- `<tool> learn` exits `0`.
- `stdout` is ≥ 200 characters.
- Output mentions: **purpose**, **commands**, **exit** codes, `--json`, **explain** (case-insensitive substring match).

**Why:** `--help` is terse and fragmented across subparsers. `learn` is a single, structured prompt an agent can read in one shot to author its own usage skill. The 200-character floor and marker list guarantee the prompt says something useful.

## Bundle 3 — json (machine readability)

**What it checks** *(black-box)*:

- `<tool> learn --json` stdout is valid JSON.
- stderr stays empty on successful `<tool> learn --json`.
- `<tool> explain --json` stdout is valid JSON.

**Why:** Agents parse structure more reliably than prose. At least one listing verb must return JSON; `learn` is the universal candidate. stdout/stderr must not mix — an agent's JSON parser would choke.

## Bundle 4 — errors (propagation)

**What it checks** *(black-box)*:

- `<tool> <bogus-verb>` exits non-zero.
- stderr contains a line starting with `hint:` or `try:`.
- No Python traceback leaks to stderr.
- `<tool> learn` output documents the exit-code policy (mentions "exit" and the codes `0`, `1`, `2`).

**Why:** An agent hitting an error needs a machine-actionable next step, not a stack trace. The `hint:` prefix is the agreed-upon remediation marker. A traceback is a developer artifact that bypasses the structured error contract.

## Bundle 5 — explain (addressable docs)

**What it checks** *(black-box)*:

- `<tool> explain` (no args) exits `0` with markdown.
- `<tool> explain <tool>` exits `0` with markdown.
- `<tool> explain <bogus-path>` exits non-zero and stderr carries a `hint:` line.

**Why:** `--help` is positional and terse. `explain <path>` is global and addressable: an agent can fetch any noun/verb's full markdown by path, and the tool itself points at valid paths when a miss happens. This is how an agent navigates the tool's menu without `--help` scraping.

## Bundle 6 — overview

**What it checks** *(black-box)*:

- `<tool> overview` and `<tool> cli overview` exit `0` with non-empty stdout.
- `<tool> overview --json` parses and carries the stable keys `subject` and `sections`.
- `<tool> overview <bogus-path>` falls back gracefully (exit `0` with a warning) — descriptive verbs do not hard-fail the way diagnostic verbs do.

**Why:** *what is present* is a different question from *what is wrong*. `overview` answers the former; `doctor` answers the latter. An agent integrating with the tool reads `overview` to learn the shape, `doctor` to learn the health.

## Bundle 7 — doctor

**What it checks** *(black-box)*:

- `<tool> doctor` produces a non-empty report on stdout (any exit code — a healthy doctor exits `0`, an unhealthy doctor exits non-zero, both satisfy the contract).
- `<tool> doctor --json` parses to an object with stable keys `healthy` (bool) and `checks` (list).
- Every entry in `checks` carries `id`, `passed`, `severity`, `message`.
- When `healthy: false`, every failed check supplies a non-empty `remediation` — doctor's promise is that failures are always actionable.

**Why:** the diagnosability pillar of the agent-first contract. An agent hitting an unhealthy tool needs to know *what's wrong and how to fix it* without reading source. The `doctor` verb is also the natural home for `--fix` (auto-apply remediations declared `auto_fixable: true` with a `fix_id`); the rubric does not assert `--fix` itself because it has side effects, but checks declaring it satisfy the wider doctor contract.

## Severities

Each check returns a `CheckResult` with a `severity` field (`error`, `warn`, or `info`). Only `error`-severity failures cause `agentfront cli doctor` to exit non-zero by default. `--strict` promotes all failures (including `warn`) to non-zero exit.

## Adding checks

Each bundle is a module under `agentfront/rubric/checks/`, exposing:

```python
CHECKS = [check_1, check_2, ...]

def run(ctx: VerifyContext) -> list[CheckResult]:
    return [check(ctx) for check in CHECKS]
```

A new check is a function `(VerifyContext) -> CheckResult`. Add it to `CHECKS`. Write a unit test against a `FakeRunner`. Done.

## Not-in-scope (on purpose)

The rubric checks **generic agent-first affordances**, not tool-specific verbs. A tool that only has `learn`, `explain`, `overview`, `doctor`, and two domain verbs can pass. A tool with dozens of verbs also passes if it satisfies the seven bundles. agentfront's own `cli cite` is NOT a rubric requirement.

CI configuration, pre-commit hooks, and agent-workflow tooling are deliberately out of scope — those belong to the sibling project `agex-cli` (Agent Experience).

## See also

- [`agent-first.md`](./agent-first.md) — the paradigm behind the rubric.
- [`../agentfront/rubric/`](../agentfront/rubric/) — implementation.
- [`../agentfront/cite/references/python-cli/AGENT.md`](../agentfront/cite/references/python-cli/AGENT.md) — integration guide for the reference tree that `agentfront cli cite` emits.
