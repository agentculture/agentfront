# Skill provenance ledger

This repo vendors a handful of skills from sibling AgentCulture
projects under `.claude/skills/`. This ledger tracks the upstream
source for each vendored skill so future re-syncs (and the auto-broadcast
issues like #17 / #18 that triggered the initial vendoring) know where
to pull from and what was adapted locally.

The AgentCulture skills-portability rule: each skill is self-contained,
nothing reaches across skill boundaries at runtime, and a vendoring repo
adapts identifier-only details (consumer name, signature literal) without
forking the script logic.

| Skill | Upstream | Local path | Vendored since | Local divergence |
|-------|----------|------------|----------------|------------------|
| `cicd` (overlap verbs: `lint`, `open`, `read`, `reply`, `delta`) | [`agentculture/agex-cli`](https://github.com/agentculture/agex-cli) — `agex pr <verb>` is the upstream as of steward 0.12.0; `workflow.sh` is a thin delegate | `.claude/skills/cicd/scripts/workflow.sh` (entry points) | teken 0.7.0 (issue [#17](https://github.com/agentculture/agentfront/issues/17)) | No script logic changed. `workflow.sh` calls `agex pr` directly. |
| `cicd` (steward extensions: `status`, `await`) | [`agentculture/steward`](https://github.com/agentculture/steward/tree/main/.claude/skills/cicd) (local: `../steward/.claude/skills/cicd/`) — to migrate into `agex pr` per [agex-cli#41](https://github.com/agentculture/agex-cli/issues/41) when that lands | `.claude/skills/cicd/scripts/pr-status.sh`, `pr-reply.sh`, `portability-lint.sh`, `_resolve-nick.sh`; `workflow.sh status`/`await` subcommands | teken 0.7.0 (issue [#17](https://github.com/agentculture/agentfront/issues/17)) | Identifier-only adapted: SKILL.md prose reframed as the agentfront edition; environment-variable names (`STEWARD_PR_AWAIT_*`, `STEWARD_AGEX_AGENT`) kept verbatim for interface stability. Four known upstream bugs filed at [steward#33](https://github.com/agentculture/steward/issues/33) — picked up on next resync; not patched locally to keep this PR vendor-pristine. |
| `communicate` | [`agentculture/steward`](https://github.com/agentculture/steward/tree/main/.claude/skills/communicate) (local: `../steward/.claude/skills/communicate/`) | `.claude/skills/communicate/` | teken 0.7.0 (issue [#18](https://github.com/agentculture/agentfront/issues/18)) | Identifier-only adapted: SKILL.md prose reframed as a downstream consumer; broadcast section reduced (agentfront does not broadcast); example issue titles rewritten. agtag resolves signature `<nick>` from `culture.yaml`. |
| `think` (idea→spec leg) | [`agentculture/devague`](https://github.com/agentculture/devague) — author (origin = devague); cited via [`agentculture/guildmaster`](https://github.com/agentculture/guildmaster/tree/main/.claude/skills/think) (local: `../guildmaster/.claude/skills/think/`), guildmaster's mesh-broadcast copy is the citation point | `.claude/skills/think/` | agentfront 0.10.0 (issue [#23](https://github.com/agentculture/agentfront/issues/23)) | No script logic changed; SKILL.md kept **verbatim**. Upstream already carries `type: command` — load-bearing on the culture/agex backend (`culture.yaml` declares an agent; a SKILL.md without `type:` is silently skipped by `probe.py`). The guildmaster-vantage provenance prose in the description tail ("steward pulls this skill from here…") is kept as-is by decision. Runtime dep: `uv tool install devague`. |
| `spec-to-plan` (spec→plan leg) | [`agentculture/devague`](https://github.com/agentculture/devague) — author (origin = devague); cited via [`agentculture/guildmaster`](https://github.com/agentculture/guildmaster/tree/main/.claude/skills/spec-to-plan) (local: `../guildmaster/.claude/skills/spec-to-plan/`) | `.claude/skills/spec-to-plan/` | agentfront 0.10.0 (issue [#23](https://github.com/agentculture/agentfront/issues/23)) | No script logic changed; SKILL.md kept **verbatim** (incl. `type: command`, see `think` row). Drives the `devague plan` CLI group. Runtime dep: `uv tool install devague`. |
| `assign-to-workforce` (plan→parallel impl leg) | [`agentculture/devague`](https://github.com/agentculture/devague) — author (origin = devague); cited via [`agentculture/guildmaster`](https://github.com/agentculture/guildmaster/tree/main/.claude/skills/assign-to-workforce) (local: `../guildmaster/.claude/skills/assign-to-workforce/`) | `.claude/skills/assign-to-workforce/` | agentfront 0.10.0 (issue [#23](https://github.com/agentculture/agentfront/issues/23)) | No script logic changed; SKILL.md kept **verbatim** (incl. `type: command`, see `think` row). Reads `devague plan waves` (read-only) and fans out tasks to per-task agents in isolated git worktrees. Extra runtime deps beyond `uv tool install devague`: `git worktree`, `python3` (the `split-plan` subcommand renders the split-plan table via an inline `python3` program — flagged by Qodo on PR [#25](https://github.com/agentculture/agentfront/pull/25)), and the vendored `cicd` skill (gate-3 `agex pr open`) — present at `.claude/skills/cicd/`. A preflight `python3` guard with a clear error belongs in the upstream script (devague), not a local fork, per the skills-portability rule; pick it up on next resync. |
| `ask-colleague` (delegate scoped work to a different backend) | [`agentculture/colleague`](https://github.com/agentculture/colleague) — author (origin = colleague); copied from the local checkout `../colleague/.claude/skills/ask-colleague/` | `.claude/skills/ask-colleague/` | agentfront (this PR) | No script logic changed; copied **verbatim** (`diff -r` clean, incl. `prompts/` + `type: command`). Runtime dep: `uv tool install colleague` (or `colleague` on PATH) + a reachable backend (default: local vLLM Qwen on `:8001`). Writes run artifacts under `.colleague/` (gitignored). |
| `lint-markdown` | Local-only | `.claude/skills/lint-markdown/` | n/a | Repo-local skill (not vendored). |
| `version-bump` | Local-only | `.claude/skills/version-bump/` | n/a | Repo-local skill (not vendored). |

## Re-sync recipe

When the upstream steward releases a new version of a vendored skill
(broadcast lands as a new GitHub issue on this repo), follow the
recipe in that issue body. The short form:

```bash
git checkout -b skill/<name>-resync
git rm -r .claude/skills/<name>
cp -R ../steward/.claude/skills/<name> .claude/skills/
chmod +x .claude/skills/<name>/scripts/*.sh
# Re-apply the local adaptations listed above for the skill.
# Update this ledger row's "Vendored since" cell.
# Bump version + CHANGELOG. Open PR.
```

The **devague workflow trio** (`think`, `spec-to-plan`, `assign-to-workforce`)
is the exception to the steward source above: it is cited from
`../guildmaster/.claude/skills/<name>/` (guildmaster's mesh-broadcast copy of
devague's operators), not from `../steward/`. Re-sync the three **as a set** —
they are one operator chain (idea→spec→plan→parallel implementation) whose
SKILL.md descriptions cross-reference one another, so a partial re-sync can
leave dangling `/think`→`/spec-to-plan`→`/assign-to-workforce` hand-offs.

## Why a ledger

The `steward announce-skill-update` verb parses this file's "Downstream
copies" cell when broadcasting. agentfront is not listed as a ledger consumer
upstream (the issues that initially vendored these skills were one-off
`--to agentculture/agentfront` broadcasts), but keeping a local ledger makes
re-syncs predictable and the divergence column explicit.
