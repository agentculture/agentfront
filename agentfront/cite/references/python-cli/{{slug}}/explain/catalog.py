"""Markdown catalog for ``{{project_name}} explain <path>``.

Each entry is verbatim markdown. Keys are command-path tuples. The empty
tuple and ``("{{project_name}}",)`` both resolve to the root entry.

Keep bodies self-contained: an agent reading one entry should get enough
context without chaining reads.
"""

from __future__ import annotations

_ROOT = """\
# {{project_name}}

<One-paragraph description of {{project_name}} aimed at an agent reader.>

## Verbs

- `{{project_name}} learn` — structured self-teaching prompt.
- `{{project_name}} explain <path>` — markdown docs for any noun/verb.

## Exit-code policy

- `0` success
- `1` user-input error
- `2` environment / setup error
- `3+` reserved

## See also

- `{{project_name}} explain learn`
- `{{project_name}} explain explain`
"""

_LEARN = """\
# {{project_name}} learn

Prints a structured self-teaching prompt covering {{project_name}}'s purpose,
command map, exit-code policy, `--json` support, and `explain` pointer.

## Usage

    {{project_name}} learn
    {{project_name}} learn --json
"""

_EXPLAIN = """\
# {{project_name}} explain <path>

Prints markdown documentation for any noun/verb path. Unlike `--help`
(terse, positional), `explain` is global and addressable by path.

## Usage

    {{project_name}} explain {{project_name}}
    {{project_name}} explain learn
    {{project_name}} explain --json <path>
"""


ENTRIES: dict[tuple[str, ...], str] = {
    (): _ROOT,
    ("{{project_name}}",): _ROOT,
    ("learn",): _LEARN,
    ("explain",): _EXPLAIN,
}
