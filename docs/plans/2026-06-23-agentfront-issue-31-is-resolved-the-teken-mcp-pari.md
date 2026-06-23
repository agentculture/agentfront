# Build Plan — agentfront issue #31 is resolved: the teken[mcp] parity follow-up is formally declined and documented, and the downstream-audit follow-up is closed as a no-op.

slug: `agentfront-issue-31-is-resolved-the-teken-mcp-pari` · status: `exported` · from frame: `agentfront-issue-31-is-resolved-the-teken-mcp-pari`

> agentfront issue #31 is resolved: the teken[mcp] parity follow-up is formally declined and documented, and the downstream-audit follow-up is closed as a no-op.

## Tasks

### t1 — Add an 'MCP surface' note to packaging/teken/README.md: MCP users install agentfront[mcp] directly; the teken wrapper exposes no [mcp] extra (deprecated, zero demand)

- covers: c2, c4, c5, h2, h4
- acceptance:
  - packaging/teken/README.md contains a section that (a) tells MCP users to install agentfront[mcp], (b) states the teken wrapper has no [mcp] extra, and (c) gives the why (deprecated alias; minimalism; no demand)

### t2 — Hold scope: wrapper stays metadata-only and no lockstep machinery changes

- depends on: t1
- covers: c6, h5, h6
- acceptance:
  - git diff touches no .github/workflows/*.yml and no .claude/skills/version-bump/scripts/bump.py
  - packaging/teken/pyproject.toml has NO [project.optional-dependencies] section and no agentfront[mcp] string
  - no file outside agentfront repo is modified (no sibling remediation)

### t3 — Version bump + CHANGELOG entry for the docs change (required on every PR)

- depends on: t1
- covers: c7, h7
- acceptance:
  - version-bump skill bumps the version; packaging/teken/pyproject.toml version + agentfront== pin stay in lockstep with root
  - uv build packaging/teken produces a metadata-only wheel (no importable modules)
  - the CI teken-wrapper-lockstep check passes locally (wrapper version == root AND dependencies[0] == agentfront==<root>)

### t4 — Close issue #31: post a closing comment recording the decline rationale and the downstream-audit result (zero affected consumers), check both checkboxes, close

- depends on: t1, t2, t3
- covers: c1, c3, h1, h3
- acceptance:
  - issue #31 closing comment names both follow-ups (teken[mcp] parity; downstream audit), states parity is declined with rationale, and states the audit found no sibling imports/depends-on agentfront or uses its MCP surface
  - both checkboxes in issue #31 are checked and the issue is closed
