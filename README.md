# afi-cli

**Agent First Interface** — scaffold tools whose primary consumer is an AI agent, not a human.

From a single source of truth, afi-cli generates three interface surfaces, each shaped by a different agent-ergonomic principle:

- **CLI** — with a `learn` affordance so an agent can introspect the tool and author its own usage skill (not just read `--help`).
- **MCP server** — a deliberately minimal menu, tuned for low surface area over maximal API coverage.
- **HTTP site** — markdown pages plus a sitemap, navigable by any agent with a fetch tool.

Part of the [AgentCulture](https://github.com/agentculture) OSS org — see [`docs/agentculture.md`](./docs/agentculture.md) for the org, its paradigm, and how afi-cli is foundational to it. The design brief is in [`docs/agent-first.md`](./docs/agent-first.md); the concrete rubric that `afi cli verify` enforces is in [`docs/rubric.md`](./docs/rubric.md).

## Install

```bash
uv tool install afi-cli
```

Then `afi --version` should work on your PATH. `uv tool install` is the supported path — not `pip install`.

## Usage

Every afi command supports `--json` where it produces a listing or report, and respects the [exit-code policy](./docs/rubric.md#exit-code-policy) (`0` success / `1` user error / `2` env error).

### Introspect

```bash
afi learn                         # structured self-teaching prompt for an agent
afi learn --json                  # same, as a JSON payload
afi explain cli cite              # markdown docs for any noun/verb path
afi explain afi                   # top-level map
```

### CLI scaffolding

```bash
afi cli cite [path]               # emit the agent-first reference tree into
                                  # <path>/.afi/reference/python-cli/ (tokens left literal,
                                  # adds `.afi/` to .gitignore)
afi cli verify [path]             # audit a CLI at <path> against the five-bundle rubric
afi cli verify . --json           # full structured report
afi cli verify . --strict         # treat warnings as failures
```

`afi cli cite` writes only under `.afi/` plus one line in `.gitignore` — it never modifies the rest of the target project. The emitted tree has literal `{{project_name}}`, `{{slug}}`, `{{module}}` tokens; an agent reads the accompanying `AGENT.md` and applies the pattern to the host project on its own terms.

`afi cli verify` is a **hybrid** auditor: static checks for repo structure (`pyproject.toml`, `tests/`) and black-box subprocess probes for behavior (`learn`, `--json`, error discipline, `explain`). Every failure includes a concrete `remediation` pointer.

### MCP / HTTP

Not implemented yet. Planned for v0.4 / v0.5.

## Develop

```bash
uv sync                          # install + dev deps
uv run pytest -n auto -v         # tests (includes the self-verify acceptance gate)
uv run afi cli verify .          # same gate, interactive
uv run pre-commit install        # enable lint hooks
```

The `tests/test_self_verify.py` acceptance gate runs the rubric in-process against the repo root; any regression that breaks a bundle blocks the commit.

See [`CLAUDE.md`](./CLAUDE.md) for design intent and full command reference.

## License

MIT. © 2026 Ori Nachum / AgentCulture.
