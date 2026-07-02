"""Public consumer testing harness for apps built on ``agentfront``.

A host app built with :class:`agentfront.App` gets its CLI, MCP, and HTTP
surfaces generated for free — this package is the matching harness for
*testing* that app: in-process CLI invocation (no subprocess), in-process MCP
dispatch (no ``mcp`` package import required), and a cross-surface agreement
assertion, so a consumer's own test suite can prove its surfaces never drift
apart.

This is where later additions land as the harness grows: TAUI drive/replay
helpers join this same public surface in a later wave without restructuring
what is exported here.
"""

from __future__ import annotations

from agentfront.testing.agreement import assert_surfaces_agree
from agentfront.testing.cli import CliResult, run_cli
from agentfront.testing.mcp import call_mcp

__all__ = ["CliResult", "run_cli", "assert_surfaces_agree", "call_mcp"]
