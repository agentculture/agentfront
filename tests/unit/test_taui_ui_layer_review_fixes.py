"""Regression guards for the TAUI UI-layer review fixes (issue #45).

These tests pin the behaviours surfaced by the post-implementation review:

- ``render_flat`` renders the header zone (it must not silently drop the tool
  name / version the boxed and Markdown tiers both show).
- ``render_flat`` genericity: ``skip_panel_prefixes`` and the tag vocabulary are
  overridable, so a second consumer is not bound to the shipped conventions.
- ``render_slash_autocomplete`` genericity: ``default_group`` and ``group_icon``
  are overridable.
- ``render_skill_panel`` rows align flush to ``width`` (the off-by-one fix).
- ``render_conversation`` preserves long-line content at a tiny width (it wraps,
  not truncates/loses).
"""

from __future__ import annotations

import types

from agentfront.taui.render.ansi_flat import render_flat
from agentfront.taui.state import (
    ConversationLine,
    Header,
    Panel,
    PanelItem,
    TAUIState,
)
from agentfront.taui.widgets.skill_panel import render_skill_panel
from agentfront.taui.widgets.slash_autocomplete import render_slash_autocomplete

# ---------------------------------------------------------------------------
# render_flat — header zone (no silent drop)
# ---------------------------------------------------------------------------


def test_flat_renders_header_title_version_subtitle():
    state = TAUIState(header=Header(title="agentfront", version="0.19.0", subtitle="cockpit"))
    out = render_flat(state, include_prompt=False)
    assert "agentfront" in out
    assert "0.19.0" in out
    assert "cockpit" in out


def test_flat_omits_header_block_when_title_empty():
    # A bare state has Header("") — no title, so no header line is emitted, but
    # the state line (glyph + status) is still present.
    out = render_flat(TAUIState(), include_prompt=False)
    first_line = out.splitlines()[0]
    # The first line is the state line (starts with a glyph), not a header.
    assert "agentfront" not in out
    assert first_line  # non-empty state line


# ---------------------------------------------------------------------------
# render_flat — genericity overrides
# ---------------------------------------------------------------------------


def test_flat_skip_panel_prefixes_default_hides_slash_panels():
    state = TAUIState(
        panels=[
            Panel(
                id="slash.controls",
                title="SlashTree",
                visible=True,
                items=[PanelItem(id="x", label="hidden-item")],
            )
        ]
    )
    out = render_flat(state, include_prompt=False)
    assert "SlashTree" not in out
    assert "hidden-item" not in out


def test_flat_skip_panel_prefixes_override_can_render_everything():
    state = TAUIState(
        panels=[
            Panel(
                id="slash.controls",
                title="SlashTree",
                visible=True,
                items=[PanelItem(id="x", label="now-shown")],
            )
        ]
    )
    out = render_flat(state, include_prompt=False, skip_panel_prefixes=())
    assert "SlashTree" in out
    assert "now-shown" in out


def test_flat_tag_text_override_is_threaded_to_panel_items():
    state = TAUIState(
        panels=[
            Panel(
                id="skills",
                title="Skills",
                visible=True,
                items=[PanelItem(id="s1", label="recall", tags=["zzz"])],
            )
        ]
    )
    out = render_flat(state, include_prompt=False, tag_text={"zzz": "<<ZZZ>>"})
    assert "<<ZZZ>>" in out


# ---------------------------------------------------------------------------
# render_slash_autocomplete — genericity overrides
# ---------------------------------------------------------------------------


def _spec(group: str = "controls") -> object:
    return types.SimpleNamespace(name="cmd", arg_hint="", description="d", group=group, tags=[])


def test_slash_default_group_override_buckets_groupless_matches():
    # A match whose group is empty falls into default_group, not a hard-coded one.
    match = types.SimpleNamespace(name="cmd", arg_hint="", description="d", group="", tags=[])
    out = render_slash_autocomplete([match], default_group="misc", groups=[("misc", "Misc")])
    assert "Misc" in out


def test_slash_group_icon_override():
    out = render_slash_autocomplete([_spec(group="controls")], group_icon="»")
    assert "»" in out
    assert "📁" not in out


# ---------------------------------------------------------------------------
# render_skill_panel — box rows align flush to width (off-by-one fix)
# ---------------------------------------------------------------------------


def test_skill_panel_rows_align_to_width():
    width = 30
    state = TAUIState(
        panels=[
            Panel(
                id="skills",
                title="Skills",
                visible=True,
                items=[
                    PanelItem(id="a", label="think", status="active"),
                    PanelItem(id="b", label="recall", status="available"),
                ],
            )
        ]
    )
    out = render_skill_panel(state, width=width)
    lines = out.splitlines()
    assert lines, "expected a rendered skills box"
    # Every line (top border, item rows, bottom border) is exactly `width`
    # codepoints wide, so the right border aligns with the corners.
    assert all(len(line) == width for line in lines), {len(line) for line in lines}


# ---------------------------------------------------------------------------
# render_conversation — small width preserves content (wraps, not loses)
# ---------------------------------------------------------------------------


def test_conversation_small_width_preserves_long_line_content():
    from agentfront.taui.widgets.conversation import render_conversation

    long_text = "abcdefghijklmnopqrstuvwxyz0123456789"
    state = TAUIState(conversation=[ConversationLine(text=long_text)])
    out = render_conversation(state, width=12)
    # Wrapping (not truncation) keeps every character of the source line.
    stripped = "".join(ch for ch in out if ch.isalnum())
    for chunk_char in long_text:
        assert chunk_char in stripped


# ---------------------------------------------------------------------------
# Boxed widgets — pathological width does not crash (degraded-but-valid)
# ---------------------------------------------------------------------------


def test_boxed_widgets_pathological_width_no_crash():
    from agentfront.taui.state import Action, Popup
    from agentfront.taui.widgets.command_palette import render_command_palette
    from agentfront.taui.widgets.popup_layer import render_popup_layer
    from agentfront.taui.widgets.skill_panel import render_skill_panel

    state = TAUIState(
        panels=[
            Panel(id="skills", title="S", visible=True, items=[PanelItem(id="a", label="x")]),
            Panel(id="commands", title="C", visible=True, items=[PanelItem(id="t", label="y")]),
        ],
        popups=[
            Popup(
                id="p",
                kind="error",
                visible=True,
                message="boom",
                actions=[Action("p.dismiss", "key", "Dismiss")],
            ),
        ],
    )
    # width=1 is below MIN_WIDTH and never hit in normal use, but each renderer
    # must degrade gracefully (return a str) rather than crash or hang.
    for width in (1, 2):
        assert isinstance(render_skill_panel(state, width=width), str)
        assert isinstance(render_command_palette(state, width=width), str)
        assert isinstance(render_popup_layer(state, width=width), str)


# ---------------------------------------------------------------------------
# Shared clip() helper (deduplicated into render.layout)
# ---------------------------------------------------------------------------


def test_clip_shared_helper():
    from agentfront.taui.render.layout import clip

    assert clip("hello", 80) == "hello"  # fits → unchanged
    assert clip("hello", 3) == "he…"  # truncated with ellipsis
    assert clip("hello", 0) == "hello"  # width <= 0 → no truncation
    assert clip("hello", -5) == "hello"


# ---------------------------------------------------------------------------
# Box title never overflows width (Qodo finding: "Box title exceeds width")
# ---------------------------------------------------------------------------


def test_clip_title_helper():
    from agentfront.taui.render.layout import clip_title

    assert clip_title("Skills", 30) == "Skills"  # fits in width - 4
    # A long title is clipped to the title field budget (width - 4) with ellipsis.
    long = "work-error-deploy-step-7-permission-denied"
    assert len(clip_title(long, 40)) <= 40 - 4
    assert clip_title(long, 40).endswith("…")
    assert clip_title("anything", 3) == ""  # too narrow to frame a title


def test_boxed_widget_titles_never_exceed_width():
    from agentfront.taui.colors import strip_ansi
    from agentfront.taui.state import Popup
    from agentfront.taui.widgets.command_palette import render_command_palette
    from agentfront.taui.widgets.conversation import render_conversation
    from agentfront.taui.widgets.popup_layer import render_popup_layer

    width = 40
    long_id = "work-error-deploy-step-7-permission-denied-and-then-some"

    # popup title is built from kind + popup.id, the worst case for overflow.
    popup_state = TAUIState(popups=[Popup(id=long_id, kind="error", visible=True, message="boom")])
    cmd_state = TAUIState(
        panels=[
            Panel(
                id="commands", title=long_id, visible=True, items=[PanelItem(id="t", label="ship")]
            )
        ]
    )
    conv_state = TAUIState(conversation=[ConversationLine(text="hello")])

    renders = [
        render_popup_layer(popup_state, width=width),
        render_command_palette(cmd_state, width=width),
        render_conversation(conv_state, width=width),
    ]
    for out in renders:
        for line in out.splitlines():
            assert len(strip_ansi(line)) <= width, (len(strip_ansi(line)), line)
