"""Public consumer testing harness for apps built on ``agentfront``.

A host app built with :class:`agentfront.App` gets its CLI, MCP, and HTTP
surfaces generated for free — this package is the matching harness for
*testing* that app: in-process CLI invocation (no subprocess), in-process MCP
dispatch (no ``mcp`` package import required), a cross-surface agreement
assertion, and TAUI drive/parity/replay helpers, so a consumer's own test
suite can prove its surfaces never drift apart and that its agent and human
audiences see the same world.

Everything is imported eagerly — one import line serves a consumer's whole
test suite.
"""

from __future__ import annotations

from agentfront.testing.agreement import assert_surfaces_agree
from agentfront.testing.cli import CliResult, run_cli
from agentfront.testing.mcp import call_mcp
from agentfront.testing.taui import (
    Snapshot,
    assert_agent_human_parity,
    assert_replay_equivalent,
    drive,
    read_snapshot,
    replay,
    resume,
    write_snapshot,
)

__all__ = [
    "CliResult",
    "run_cli",
    "assert_surfaces_agree",
    "call_mcp",
    "drive",
    "assert_agent_human_parity",
    "assert_replay_equivalent",
    "write_snapshot",
    "read_snapshot",
    "replay",
    "Snapshot",
    "resume",
]
