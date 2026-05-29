# agentfront

**Agent First Interface** — scaffold tools whose primary consumer is an AI agent, not a human.

> Formerly `teken` (and `afi-cli` before that). The project was renamed to **agentfront** — the agent-facing front a tool presents. The `teken` package and the `teken` command still work as deprecated aliases — see [Install](#install).

From a single source of truth, agentfront generates three interface surfaces, each shaped by a different agent-ergonomic principle:

- **CLI** — with a `learn` affordance so an agent can introspect the tool and author its own usage skill (not just read `--help`).
- **MCP server** — a deliberately minimal menu, tuned for low surface area over maximal API coverage.
- **HTTP site** — markdown pages plus a sitemap, navigable by any agent with a fetch tool.

Part of the [AgentCulture](https://github.com/agentculture) OSS org — see [`docs/agentculture.md`](./docs/agentculture.md) for the org, its paradigm, and how agentfront is foundational to it. The design brief is in [`docs/agent-first.md`](./docs/agent-first.md); the concrete rubric that `agentfront cli doctor` enforces is in [`docs/rubric.md`](./docs/rubric.md).

## Install

```bash
uv tool install agentfront
```

Then `agentfront --version` should work on your PATH. `uv tool install` is the supported path — not `pip install`.

```bash
uv tool install teken   # still works: a thin wrapper that installs agentfront
```

The `teken` command is retained as a deprecated alias for `agentfront` (it prints a one-line notice to stderr and forwards). New usage should prefer `agentfront`.

## Usage

Every agentfront command supports `--json` where it produces a listing or report, and respects the [exit-code policy](./docs/rubric.md#exit-code-policy) (`0` success / `1` user error / `2` env error).

### Introspect

```bash
agentfront learn                       # structured self-teaching prompt for an agent
agentfront learn --json                # same, as a JSON payload
agentfront explain cli cite            # markdown docs for any noun/verb path
agentfront explain agentfront          # top-level map
```

### CLI scaffolding

```bash
agentfront cli cite [path]             # emit the agent-first reference tree into
                                       # <path>/.agentfront/reference/python-cli/ (tokens left literal,
                                       # adds `.agentfront/` to .gitignore)
agentfront cli doctor [path]           # audit a CLI at <path> against the seven-bundle rubric
agentfront cli doctor . --json         # full structured report
agentfront cli doctor . --strict       # treat warnings as failures
```

`agentfront cli cite` writes only under `.agentfront/` plus one line in `.gitignore` — it never modifies the rest of the target project. The emitted tree has literal `{{project_name}}`, `{{slug}}`, `{{module}}` tokens; an agent reads the accompanying `AGENT.md` and applies the pattern to the host project on its own terms. Reference trees cited before the rename (under `.teken/`) are still detected.

`agentfront cli doctor` is a **hybrid** auditor: static checks for repo structure (`pyproject.toml`, `tests/`) and black-box subprocess probes for behavior (`learn`, `--json`, error discipline, `explain`). Every failure includes a concrete `remediation` pointer. (`agentfront cli verify` remains as a deprecated alias for `cli doctor`.)

### MCP / HTTP

Not implemented yet. Planned for v0.4 / v0.5.

## Develop

```bash
uv sync                          # install + dev deps
uv run pytest -n auto -v         # tests (includes the self-doctor acceptance gate)
uv run agentfront cli doctor .   # same gate, interactive
uv run pre-commit install        # enable lint hooks
```

The `tests/test_self_doctor.py` acceptance gate runs the rubric and self-doctor in-process against the repo root; any regression that breaks a bundle blocks the commit.

See [`CLAUDE.md`](./CLAUDE.md) for design intent and full command reference.

## License

MIT. © 2026 Ori Nachum / AgentCulture.
