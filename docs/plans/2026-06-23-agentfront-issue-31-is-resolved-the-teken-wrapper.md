# Build Plan — agentfront issue #31 is resolved: the teken wrapper gains an mcp extra at full parity with agentfront[mcp] (kept in version-lockstep), and the downstream audit is closed as a no-op

slug: `agentfront-issue-31-is-resolved-the-teken-wrapper` · status: `exported` · from frame: `agentfront-issue-31-is-resolved-the-teken-wrapper`

> agentfront issue #31 is resolved: the teken wrapper gains an mcp extra at full parity with agentfront[mcp] (kept in version-lockstep), and the downstream audit is closed as a no-op.

## Tasks

### t1 — Add a [project.optional-dependencies] mcp = ['agentfront[mcp]==VER'] extra to packaging/teken/pyproject.toml

- covers: c2, c4, h2
- acceptance:
  - uv tool install 'teken[mcp]' resolves agentfront[mcp]; the teken wheel METADATA shows Provides-Extra: mcp and Requires-Dist agentfront[mcp]==VER; extra=='mcp'

### t2 — Extend the version-lockstep machinery for the new extra pin: bump.py 3rd replace, tests.yml guard, publish.yml dev-version sed

- depends on: t1
- covers: h4
- acceptance:
  - bump.py updates agentfront[mcp]==OLD -> NEW; tests.yml lockstep step asserts the mcp pin == agentfront[mcp]==ROOT; publish.yml seds the mcp pin to the dev version

### t3 — Add tests/unit/test_wrapper_lockstep.py asserting version + both pins track root and the wheel stays metadata-only

- depends on: t1
- covers: c7, h7
- acceptance:
  - pytest asserts wrapper version == root, agentfront== pin, agentfront[mcp]== pin, and bypass-selection is True; full suite green

### t4 — Document teken[mcp] parity in packaging/teken/README.md (no MCP-specific deprecation message) and update the CHANGELOG entry

- depends on: t1
- covers: c5, c6, h5, h6
- acceptance:
  - README shows both 'agentfront[mcp]' and 'teken[mcp]' installs as parity with no MCP deprecation note; CHANGELOG [0.11.1] describes the added extra; agentfront's own mcp extra and the rename-deprecation framing are unchanged; no sibling repo modified

### t5 — Close issue #31: comment recording the parity decision + downstream-audit result, check both boxes

- depends on: t1, t2, t3, t4
- covers: c1, c3, h1, h3
- acceptance:
  - issue #31 closing comment records the parity decision and the zero-affected-consumers audit; both checkboxes checked; PR Closes #31
