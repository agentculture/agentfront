"""``{{project_name}} learn`` — the learnability affordance (shape-adapt).

Update the text to describe {{project_name}} specifically. Must satisfy the
agent-first rubric: >=200 chars and mention purpose, command map, exit
codes, --json, explain.
"""

from __future__ import annotations

import argparse

from {{module}} import __version__
from {{module}}.cli._output import emit_result

_TEXT = """\
{{project_name}} — <one-line tagline>.

Purpose
-------
<Describe the tool's job. Write for an agent reader: concrete and terse.>

Commands
--------
  {{project_name}} learn              Print this self-teaching prompt. Supports --json.
  {{project_name}} explain <path>...  Print markdown docs for any noun/verb path.
                              Supports --json.
  # Add your noun-verb entries here.

Machine-readable output
-----------------------
Every command that produces a listing or report supports --json. Errors in
JSON mode emit {"code", "message", "remediation"} to stderr. Stdout and
stderr are never mixed.

Exit-code policy
----------------
  0 success
  1 user-input error (bad flag, bad path, missing arg)
  2 environment / setup error
  3+ reserved

More detail
-----------
  {{project_name}} explain {{project_name}}
"""


def _as_json_payload() -> dict[str, object]:
    return {
        "tool": "{{project_name}}",
        "version": __version__,
        "purpose": "<describe purpose>",
        "commands": [
            {"path": ["learn"], "summary": "Self-teaching prompt."},
            {"path": ["explain"], "summary": "Markdown docs by path."},
        ],
        "exit_codes": {
            "0": "success",
            "1": "user-input error",
            "2": "environment/setup error",
        },
        "json_support": True,
        "explain_pointer": "{{project_name}} explain <path>",
    }


def cmd_learn(args: argparse.Namespace) -> int:
    if getattr(args, "json", False):
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
