# agentfront issue #31 is resolved: the teken wrapper gains an mcp extra at full parity with agentfront[mcp] (kept in version-lockstep), and the downstream audit is closed as a no-op

> agentfront issue #31 is resolved: the teken wrapper gains an mcp extra at full parity with agentfront[mcp] (kept in version-lockstep), and the downstream audit is closed as a no-op.

## Audience

- agentfront maintainers, plus anyone installing the teken wrapper who wants agentfront's MCP server surface

## Before → After

- Before: issue #31 left two follow-ups after PR #30 made mcp optional: an undecided teken[mcp] parity question and an un-run downstream audit
- After: uv tool install 'teken[mcp]' pulls agentfront[mcp]==VER; the new extra pin is kept in lockstep by bump.py, the tests.yml CI guard, publish.yml, and a pytest regression; issue #31 closed

## Why it matters

- teken stays at full feature parity with agentfront so the rename is transparent — anything installable on agentfront is installable on teken (including the mcp extra)

## Honesty conditions

- both issue #31 checkboxes are resolved (parity added; audit done) and the issue can be closed
- the audience can install the MCP surface via either agentfront[mcp] or teken[mcp], both documented
- the two follow-ups named in issue #31 (teken[mcp] parity; downstream audit) are exactly the two this work resolves
- packaging/teken/pyproject.toml has a [project.optional-dependencies] mcp = ['agentfront[mcp]==VER'], and bump.py/tests.yml/publish.yml + a pytest all keep that pin in lockstep
- the README documents teken[mcp] as parity (no MCP-specific deprecation message), and the teken wheel METADATA carries Provides-Extra: mcp
- git diff does not change agentfront's own [project.optional-dependencies] mcp, modifies no sibling repo, and leaves the rename-deprecation framing intact
- after the change: uv build packaging/teken yields a metadata-only wheel whose METADATA shows Requires-Dist agentfront[mcp]==VER; extra=='mcp', and the lockstep guard checks all three pins

## Success signals

- teken wheel METADATA shows Provides-Extra: mcp and Requires-Dist agentfront[mcp]==VER; the CI lockstep guard checks all three pins; uv build still yields a metadata-only wheel; issue #31 closed

## Scope / boundaries

- non-goal: changing whether mcp is optional on agentfront itself; remediating sibling repos (the audit found none affected); or removing teken's deprecation framing for the rename
