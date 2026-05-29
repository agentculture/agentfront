# teken — deprecated alias for `agentfront`

`teken` was renamed to **[`agentfront`](https://pypi.org/project/agentfront/)**.
This package is a thin compatibility wrapper: installing it pulls in
`agentfront`, which provides the canonical `agentfront` command and a deprecated
`teken` alias.

```bash
uv tool install teken       # still works — installs agentfront under the hood
uv tool install agentfront  # preferred going forward
```

New code should depend on `agentfront` directly. This wrapper is published in
lockstep with `agentfront` and will be retired once the migration window closes.
