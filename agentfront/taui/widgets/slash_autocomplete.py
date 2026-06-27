"""Slash-autocomplete widget — a live, filtered, **grouped** popup of slash commands.

Rendered below the input frame while an agent or human is typing a ``/…`` command
on a colour TTY. The popup lays the matching slash commands out as a small **tree**:
one icon per top-level group (``📁 Controls`` / ``📁 Inspect`` / ``📁 Session``)
with each command shown under its group as ``/name <arg>  <tag badges>``. The
**selected** row is shown in reverse video with a ``›`` marker and its one-line
summary on a dim sub-line. An empty match list renders nothing — the popup
"disappears" (the vanish case).

This module also owns the shared **tag vocabulary** and group display constants so
the popup, the ``/help`` text, and the cockpit tiers all format tags identically and
cannot drift. By invariant this widget **never imports the state module** — it only
reads duck-typed attributes from its ``matches`` items (``.name`` / ``.arg_hint`` /
``.description`` / ``.group`` / ``.tags``). Both the group ordering/titles and the
tag vocabulary are overridable parameters, defaulting to the module-level constants,
so a consumer can supply its own command groups and tag set as data rather than being
bound to the shipped set.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from agentfront.taui.render.layout import DEFAULT_WIDTH

_RESET = "\x1b[0m"
_REVERSE = "\x1b[7m"
_BOLD = "\x1b[1m"
_DIM = "\x1b[2m"


class SlashSpec(Protocol):
    """The duck-typed contract a ``matches`` item must satisfy.

    Declared as a :class:`typing.Protocol` (structural typing) so this widget
    documents exactly what it reads — ``.name`` / ``.arg_hint`` /
    ``.description`` / ``.group`` / ``.tags`` — without importing any concrete
    spec class.  A consumer's own command objects satisfy it by shape alone, so
    the widget stays fully decoupled from the state/consumer layer.
    """

    name: str
    arg_hint: str
    description: str
    group: str
    tags: Sequence[str]


# ---------------------------------------------------------------------------
# Shared tag vocabulary + group display
# ---------------------------------------------------------------------------

#: Display order + heading for each intent group. The popup tree, the ``/help``
#: text, and the cockpit slash panels all iterate this so a command always lands
#: under the same group label.
SLASH_GROUPS: list[tuple[str, str]] = [
    ("controls", "Controls"),
    ("inspect", "Inspect"),
    ("session", "Session"),
]

#: One visual anchor per top-level group (design rule: group = one icon).
GROUP_ICON = "📁"

#: Tag → compact text badge. Only the sanctioned tags the catalog uses
#: (a stable subset of the shared vocabulary).
TAG_TEXT: dict[str, str] = {
    "read-only": "[read-only]",
    "writes": "[writes]",
    "git": "[git]",
    "pr": "[pr]",
    "audit": "[audit]",
    "human-loop": "[human-loop]",
    "interactive": "[interactive]",
    "memory": "[memory]",
    "config": "[config]",
    "telemetry": "[telemetry]",
    "model": "[model]",
    "safe": "[safe]",
}

#: Tag → emoji badge for the optional compact display mode.
TAG_ICON: dict[str, str] = {
    "read-only": "👁",
    "writes": "✍",
    "git": "🌿",
    "pr": "🚀",
    "audit": "🔎",
    "human-loop": "🧑",
    "interactive": "💬",
    "memory": "🧠",
    "config": "⚙",
    "telemetry": "📡",
    "model": "🧬",
    "safe": "🛡",
}


def format_tags(
    tags: Sequence[str],
    style: str = "text",
    *,
    tag_text: dict[str, str] | None = None,
    tag_icon: dict[str, str] | None = None,
) -> str:
    """Render *tags* as a space-joined badge string. Never raises.

    ``style="text"`` (default) yields ``[read-only] [config]``; ``style="icons"``
    yields the emoji compact form. An unknown tag falls back to ``[tag]`` (text)
    or the bare word (icons), so a new catalog tag is shown, not dropped.

    *tag_text* and *tag_icon* default to the module constants but can be
    overridden so a consumer can supply its own tag vocabulary.
    """
    _tag_text = tag_text if tag_text is not None else TAG_TEXT
    _tag_icon = tag_icon if tag_icon is not None else TAG_ICON
    if not tags:
        return ""
    if style == "icons":
        return " ".join(_tag_icon.get(t, t) for t in tags)
    return " ".join(_tag_text.get(t, f"[{t}]") for t in tags)


def _clip(text: str, width: int) -> str:
    """Truncate *text* to *width* display columns (approximate; borderless)."""
    if width > 0 and len(text) > width:
        return text[: max(1, width - 1)] + "…"
    return text


def _line(text: str, width: int, *, sgr: str = "") -> str:
    """One borderless popup line: *text* clipped to *width*, optionally wrapped in
    an SGR code (reverse for the selection, bold for a header, dim for a summary)."""
    clipped = _clip(text, width)
    return f"{sgr}{clipped}{_RESET}" if sgr else clipped


def _group_order(
    matches: Sequence[SlashSpec],
    groups: list[tuple[str, str]],
    default_group: str,
) -> list[str]:
    """Group keys in display order: the known groups first (from *groups*), then any
    unexpected group seen in *matches* (so a mis-tagged command is still shown, last).

    A match with no ``group`` falls into *default_group* rather than a hard-coded
    bucket, so a consumer's own group taxonomy is honored."""
    order = [key for key, _ in groups]
    for spec in matches:
        key = getattr(spec, "group", "") or default_group
        if key not in order:
            order.append(key)
    return order


def _command_lines(
    index: int,
    spec: SlashSpec,
    *,
    selected: int,
    width: int,
    style: str,
    tag_text: dict[str, str],
    tag_icon: dict[str, str],
) -> list[str]:
    """The borderless line(s) for one command: an indented ``/name <arg>  <tags>``
    row, reverse-highlighted with a ``›`` (plus a dim summary sub-line) when it is
    the *selected* row."""
    left = f"/{spec.name}" + (f" {spec.arg_hint}" if spec.arg_hint else "")
    tags_str = format_tags(
        getattr(spec, "tags", ()),
        style,
        tag_text=tag_text,
        tag_icon=tag_icon,
    )
    text = f"{left}  {tags_str}".rstrip()
    if index != selected:
        return [_line(f"  {text}", width)]
    rows = [_line(f"› {text}", width, sgr=_REVERSE)]
    summary = str(getattr(spec, "description", "") or "")
    if summary:
        rows.append(_line(f"    {summary}", width, sgr=_DIM))
    return rows


def render_slash_autocomplete(
    matches: Sequence[SlashSpec],
    selected: int = 0,
    *,
    width: int = DEFAULT_WIDTH,
    style: str = "text",
    groups: list[tuple[str, str]] | None = None,
    group_icon: str = GROUP_ICON,
    default_group: str = "session",
    tag_text: dict[str, str] | None = None,
    tag_icon: dict[str, str] | None = None,
) -> str:
    """Return a **borderless, grouped** popup of *matches*, or ``""`` when empty.

    No box frame — hierarchy comes from a ``📁`` heading per group and indented
    command rows. *matches* is the flat, catalog-ordered filter result, bucketed by
    ``spec.group`` so filtering preserves group context. Each command renders as
    ``/<name> <arg_hint>  <tags>``; the row at *selected* (a flat index into
    *matches*, clamped) is reverse-highlighted with a ``›`` and gains a dim
    summary sub-line. *style* selects the tag badge form (``"text"`` default |
    ``"icons"``).

    *matches* items are duck-typed spec objects accessed via ``.name``,
    ``.arg_hint``, ``.description``, ``.group``, ``.tags`` — this widget never
    imports the state module or any session/consumer module.

    *groups* controls the heading order and labels (default: :data:`SLASH_GROUPS`),
    *group_icon* the per-group anchor glyph (default: :data:`GROUP_ICON`),
    *default_group* the bucket a group-less match falls into (default ``"session"``),
    and *tag_text* / *tag_icon* the tag badge vocabularies (default: module
    constants) — so a consumer can supply its own command groups, icon, and tag
    set as data rather than being bound to the shipped set.
    """
    _groups = groups if groups is not None else SLASH_GROUPS
    _tag_text = tag_text if tag_text is not None else TAG_TEXT
    _tag_icon = tag_icon if tag_icon is not None else TAG_ICON

    if not matches:
        return ""
    sel = max(0, min(selected, len(matches) - 1))

    # Bucket the flat matches by group, remembering each match's flat index so
    # the selection highlight maps back to the (group-agnostic) navigation model.
    buckets: dict[str, list[tuple[int, SlashSpec]]] = {}
    for i, spec in enumerate(matches):
        key = getattr(spec, "group", "") or default_group
        buckets.setdefault(key, []).append((i, spec))
    titles = dict(_groups)

    lines: list[str] = []
    for key in _group_order(matches, _groups, default_group):
        members = buckets.get(key)
        if not members:
            continue
        lines.append(_line(f"{group_icon} {titles.get(key, key.title())}", width, sgr=_BOLD))
        for i, spec in members:
            lines.extend(
                _command_lines(
                    i,
                    spec,
                    selected=sel,
                    width=width,
                    style=style,
                    tag_text=_tag_text,
                    tag_icon=_tag_icon,
                )
            )
    return "\n".join(lines)
