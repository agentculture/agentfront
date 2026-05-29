"""``agentfront learn`` — the learnability affordance.

Prints a structured self-teaching prompt with enough shape that an agent can
author its own usage skill without scraping ``--help``. Also supports
``--json`` for agents that would rather parse structure than text.

Content satisfies rubric bundle 2: ≥200 chars and mentions purpose, command
map, exit codes, ``--json``, and ``explain``.
"""

from __future__ import annotations

import argparse

from agentfront import __version__, _brand
from agentfront.cli._output import emit_result

_TEXT = """\
agentfront — Agent First Interface scaffolder.

Purpose
-------
Generate and verify agent-first interfaces for CLIs (and, later, MCP
servers and HTTP sites). agentfront itself demonstrates the patterns it checks:
learn, explain, overview, doctor, --json output, structured errors.

Commands
--------
  agentfront learn              Print this self-teaching prompt. Supports --json.
  agentfront explain <path>...  Print markdown docs for any noun/verb path; the
                         primary way for an agent to introspect agentfront's
                         grammar. Supports --json.
  agentfront overview [path]    Read-only rollup across interface surfaces. (v0.3)
  agentfront doctor [path]      Diagnose agentfront's own install (no path) or audit a
                         target CLI against the rubric (with path). With
                         --fix, applies auto-fixable remediations. (v0.5)
  agentfront cli cite [path]    Emit the Python agent-first CLI reference tree
                         into <path>/.agentfront/reference/python-cli/ for the
                         agent to apply. (v0.2)
  agentfront cli doctor [path]  Audit the CLI at <path> against the seven-bundle
                         rubric; --fix applies auto-fixable remediations.
                         (v0.5; replaces `cli verify`.)
  agentfront cli overview [path] Read-only descriptive snapshot of a CLI. (v0.3)

Universal verb tier (agent-first)
---------------------------------
Every agent-first CLI exposes the four universal verbs:

  - learn     — what is this tool?
  - explain   — what does this command do?
  - overview  — what is *present* in the subject?
  - doctor    — what is wrong, and how do I fix it?

Machine-readable output
-----------------------
Every command that produces a listing or report supports --json. Errors in
JSON mode emit {"code", "message", "remediation"} to stderr. Stdout and
stderr are never mixed.

Exit-code policy
----------------
  0 success
  1 user-input error (bad flag, bad path, missing arg)
  2 environment / setup error (tool not installed, unreadable file)
  3+ reserved

More detail
-----------
  agentfront explain agentfront
  agentfront explain doctor
  agentfront explain cli cite
  agentfront explain cli doctor

Homepage: https://github.com/agentculture/agentfront
"""


def _as_json_payload() -> dict[str, object]:
    return {
        "tool": _brand.PROG,
        "version": __version__,
        "purpose": ("Generate and verify agent-first interfaces for CLIs (and later MCP + HTTP)."),
        "commands": [
            {"path": ["learn"], "summary": "Self-teaching prompt."},
            {"path": ["explain"], "summary": "Markdown docs by noun/verb path."},
            {"path": ["overview"], "summary": "Rollup across interface surfaces."},
            {
                "path": ["doctor"],
                "summary": (
                    "Self-diagnose agentfront's install or audit a target CLI; "
                    "--fix applies auto-fixable remediations."
                ),
            },
            {"path": ["cli", "cite"], "summary": "Emit CLI reference drop."},
            {
                "path": ["cli", "doctor"],
                "summary": "Audit a CLI against the rubric (replaces `cli verify`).",
            },
            {
                "path": ["cli", "verify"],
                "summary": "Deprecated alias for `cli doctor` (removed in v0.6.0).",
            },
            {"path": ["cli", "overview"], "summary": "Read-only snapshot of a target CLI."},
        ],
        "exit_codes": {
            "0": "success",
            "1": "user-input error",
            "2": "environment/setup error",
        },
        "json_support": True,
        "explain_pointer": "agentfront explain <path> (e.g. 'agentfront explain cli doctor')",
    }


def cmd_learn(args: argparse.Namespace) -> int:
    json_mode = bool(getattr(args, "json", False))
    if json_mode:
        emit_result(_as_json_payload(), json_mode=True)
    else:
        emit_result(_TEXT, json_mode=False)
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "learn",
        help="Print a structured self-teaching prompt for agent consumers.",
    )
    p.add_argument("--json", action="store_true", help="Emit structured JSON.")
    p.set_defaults(func=cmd_learn)
