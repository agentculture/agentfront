# agentfront issue #31 is resolved: the teken[mcp] parity follow-up is formally declined and documented, and the downstream-audit follow-up is closed as a no-op.

> agentfront issue #31 is resolved: the teken[mcp] parity follow-up is formally declined and documented, and the downstream-audit follow-up is closed as a no-op.

## Audience

- agentfront maintainers, plus anyone installing the deprecated teken wrapper who wants agentfront's MCP surface

## Before → After

- Before: issue #31 left two open follow-ups after PR #30 made mcp optional: an undecided teken[mcp] parity question and an un-run downstream audit
- After: the teken wrapper README documents that MCP users install agentfront[mcp] directly (teken exposes no [mcp] extra); issue #31's two checkboxes are both resolved and the issue is closed

## Why it matters

- keeps the deprecated wrapper truly metadata-only, avoids growing the version-lockstep machinery (bump.py / tests.yml / publish.yml), and gives MCP users one clear migration path

## Honesty conditions

- both issue #31 checkboxes are resolved in a way that needs no further follow-up, and the issue can be closed
- the audience's only MCP path via the wrapper is documented (install agentfront[mcp]); maintainers can see why parity was declined
- the two follow-ups named in issue #31 (teken[mcp] parity; downstream audit) are exactly the two this work resolves
- packaging/teken/README.md contains a note pointing MCP users to agentfront[mcp] and stating teken has no [mcp] extra
- no change is made to bump.py, tests.yml, or publish.yml; the wrapper stays metadata-only (no optional-dependencies added)
- git diff touches only docs/the wrapper README + version/changelog; no sibling repo is modified; no [mcp] extra appears in packaging/teken/pyproject.toml
- after the change: uv build packaging/teken produces a metadata-only wheel and the CI lockstep guard (wrapper version + agentfront== pin) still passes

## Success signals

- wrapper README states the agentfront[mcp] migration path; 'uv build packaging/teken' still yields a metadata-only wheel; version-bump skill + CI lockstep guard still pass; issue #31 closed

## Scope / boundaries

- non-goal: adding any teken[mcp] extra; touching the bump.py/tests.yml/publish.yml lockstep machinery; or remediating any sibling repo (the audit found none affected)
