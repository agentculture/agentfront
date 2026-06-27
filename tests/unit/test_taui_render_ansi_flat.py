"""Unit tests for agentfront.taui.render.ansi_flat — the borderless ANSI renderer.

Covers: return type, determinism, borderless output, moving work glyph,
idle severity glyphs, include_prompt flag, slash-panel filtering,
conversation zone, popup rendering, status message propagation, and clip.
"""

from __future__ import annotations

from agentfront.taui.render.ansi_flat import _IDLE_GLYPH, _WORK_FRAMES, render_flat
from agentfront.taui.state import (
    Action,
    Background,
    ConversationLine,
    Header,
    Panel,
    PanelItem,
    Popup,
    Status,
    TAUIState,
    WorkItem,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BOX_CHARS = "╔╚║│┌└┐┘─"


def _make_state(**kwargs) -> TAUIState:
    """Build a minimal valid TAUIState, overriding fields via *kwargs*."""
    defaults: dict = {
        "header": Header(title="test"),
        "status": Status(severity="info", message="idle"),
        "panels": [],
        "popups": [],
        "conversation": [],
        "work_item": None,
        "background": Background(),
    }
    defaults.update(kwargs)
    return TAUIState(**defaults)


# ---------------------------------------------------------------------------
# Basic contract
# ---------------------------------------------------------------------------


def test_returns_str():
    """render_flat always returns a str."""
    state = _make_state()
    result = render_flat(state)
    assert isinstance(result, str)


def test_determinism():
    """Calling render_flat twice on the same state yields identical output."""
    state = _make_state(status=Status(severity="info", message="stable"))
    assert render_flat(state) == render_flat(state)


def test_determinism_with_work():
    """Determinism holds even when a work item is present."""
    state = _make_state(work_item=WorkItem(running=True, step_count=3))
    assert render_flat(state) == render_flat(state)


# ---------------------------------------------------------------------------
# Borderless invariant
# ---------------------------------------------------------------------------


def test_borderless_no_box_drawing_chars():
    """Output must contain none of the box-drawing characters used by render_ansi."""
    state = _make_state(
        panels=[Panel(id="skills", title="Skills", visible=True)],
        status=Status(severity="warn", message="check"),
    )
    out = render_flat(state)
    assert not any(
        c in out for c in _BOX_CHARS
    ), f"Box-drawing character found in flat output:\n{out}"


# ---------------------------------------------------------------------------
# Moving glyph — frame-driven from real state
# ---------------------------------------------------------------------------


def test_work_glyph_step0():
    """step_count=0 → first moon-phase frame."""
    state = _make_state(work_item=WorkItem(running=True, step_count=0))
    out = render_flat(state, include_prompt=False)
    assert _WORK_FRAMES[0] in out


def test_work_glyph_step4():
    """step_count=4 → fifth moon-phase frame."""
    state = _make_state(work_item=WorkItem(running=True, step_count=4))
    out = render_flat(state, include_prompt=False)
    assert _WORK_FRAMES[4] in out


def test_work_glyph_changes_with_step_count():
    """Different step_count values produce different glyphs."""
    s0 = _make_state(work_item=WorkItem(running=True, step_count=0))
    s4 = _make_state(work_item=WorkItem(running=True, step_count=4))
    out0 = render_flat(s0, include_prompt=False)
    out4 = render_flat(s4, include_prompt=False)
    # The work glyph is frame-driven by step_count, so the two renders differ.
    assert _WORK_FRAMES[0] in out0
    assert _WORK_FRAMES[4] in out4
    assert out0 != out4


def test_idle_glyph_error():
    """No running work + severity='error' → 🔴."""
    state = _make_state(
        status=Status(severity="error", message="something went wrong"),
        work_item=None,
    )
    out = render_flat(state, include_prompt=False)
    assert _IDLE_GLYPH["error"] in out
    assert "🔴" in out


def test_idle_glyph_warn():
    """No running work + severity='warn' → 🟡."""
    state = _make_state(
        status=Status(severity="warn", message="watch out"),
        work_item=None,
    )
    out = render_flat(state, include_prompt=False)
    assert "🟡" in out


def test_idle_glyph_success():
    """No running work + severity='success' → 🟢."""
    state = _make_state(
        status=Status(severity="success", message="done"),
        work_item=None,
    )
    out = render_flat(state, include_prompt=False)
    assert "🟢" in out


def test_not_running_work_uses_idle_glyph():
    """A work item that is not running does not cycle moon-phase frames."""
    state = _make_state(
        work_item=WorkItem(running=False, step_count=0),
        status=Status(severity="info", message="idle"),
    )
    out = render_flat(state, include_prompt=False)
    # None of the moon-phase frames should appear when not running.
    assert not any(frame in out for frame in _WORK_FRAMES)
    assert "🟢" in out


# ---------------------------------------------------------------------------
# include_prompt flag
# ---------------------------------------------------------------------------


def test_include_prompt_true_contains_chevron():
    """include_prompt=True → prompt chevron ❯ is present."""
    state = _make_state()
    out = render_flat(state, include_prompt=True)
    assert "❯" in out


def test_include_prompt_false_no_chevron():
    """include_prompt=False → prompt chevron ❯ is absent."""
    state = _make_state()
    out = render_flat(state, include_prompt=False)
    assert "❯" not in out


# ---------------------------------------------------------------------------
# slash.* panels are skipped
# ---------------------------------------------------------------------------


def test_slash_panels_skipped():
    """Panels whose id starts with 'slash.' must not appear in the output."""
    slash_panel = Panel(
        id="slash.controls",
        title="Slash",
        visible=True,
        items=[PanelItem(id="slash.controls.help", label="/help")],
    )
    state = _make_state(panels=[slash_panel])
    out = render_flat(state, include_prompt=False)
    assert "Slash" not in out
    assert "/help" not in out


def test_normal_panel_rendered():
    """A normal (non-slash) visible panel appears with its title and items."""
    normal_panel = Panel(
        id="skills",
        title="Skills",
        visible=True,
        items=[PanelItem(id="s1", label="recall")],
    )
    state = _make_state(panels=[normal_panel])
    out = render_flat(state, include_prompt=False)
    assert "Skills" in out
    assert "recall" in out


def test_slash_skipped_normal_kept():
    """A slash panel is skipped while a co-existing normal panel is shown."""
    slash_panel = Panel(id="slash.inspect", title="SlashInspect", visible=True)
    normal_panel = Panel(
        id="skills",
        title="SkillsPanel",
        visible=True,
        items=[PanelItem(id="s1", label="think")],
    )
    state = _make_state(panels=[slash_panel, normal_panel])
    out = render_flat(state, include_prompt=False)
    assert "SlashInspect" not in out
    assert "SkillsPanel" in out
    assert "think" in out


def test_invisible_panel_skipped():
    """A visible=False panel is not rendered."""
    hidden = Panel(id="hidden", title="HiddenPanel", visible=False)
    state = _make_state(panels=[hidden])
    out = render_flat(state, include_prompt=False)
    assert "HiddenPanel" not in out


# ---------------------------------------------------------------------------
# Conversation zone
# ---------------------------------------------------------------------------


def test_conversation_rendered_with_multiplier():
    """A ConversationLine with count > 1 renders as 'text ×N'."""
    state = _make_state(conversation=[ConversationLine("hello", 2)])
    out = render_flat(state, include_prompt=False)
    assert "hello ×2" in out


def test_conversation_heading_present():
    """When conversation is non-empty, the 'Conversation' heading appears."""
    state = _make_state(conversation=[ConversationLine("hi", 1)])
    out = render_flat(state, include_prompt=False)
    assert "Conversation" in out


def test_conversation_single_count_no_multiplier():
    """A ConversationLine with count=1 renders as plain text, no ×1."""
    state = _make_state(conversation=[ConversationLine("just once", 1)])
    out = render_flat(state, include_prompt=False)
    assert "just once" in out
    assert "×1" not in out


def test_conversation_absent_when_empty():
    """No 'Conversation' heading appears when the conversation list is empty."""
    state = _make_state(conversation=[])
    out = render_flat(state, include_prompt=False)
    assert "Conversation" not in out


def test_conversation_multiple_lines():
    """Multiple conversation lines all appear in the output."""
    state = _make_state(
        conversation=[
            ConversationLine("first", 1),
            ConversationLine("second", 3),
        ]
    )
    out = render_flat(state, include_prompt=False)
    assert "first" in out
    assert "second ×3" in out


# ---------------------------------------------------------------------------
# Popup rendering
# ---------------------------------------------------------------------------


def test_visible_popup_message_and_action():
    """A visible popup renders its message and dismiss action."""
    popup = Popup(
        id="p",
        kind="error",
        visible=True,
        message="boom",
        actions=[Action("popup.p.dismiss", "key", "Dismiss")],
    )
    state = _make_state(popups=[popup])
    out = render_flat(state, include_prompt=False)
    assert "boom" in out
    assert "popup.p.dismiss" in out
    assert "Dismiss" in out


def test_popup_uses_warning_flag():
    """A visible popup is prefixed with the ⚠️ flag."""
    popup = Popup(id="p2", kind="info", visible=True, message="note")
    state = _make_state(popups=[popup])
    out = render_flat(state, include_prompt=False)
    assert "⚠️" in out


def test_invisible_popup_not_rendered():
    """A popup with visible=False does not appear."""
    popup = Popup(id="hidden-popup", kind="error", visible=False, message="secret")
    state = _make_state(popups=[popup])
    out = render_flat(state, include_prompt=False)
    assert "secret" not in out


def test_popup_action_falls_back_to_input_when_no_description():
    """When action.description is empty, the 'input' field is used instead."""
    popup = Popup(
        id="p3",
        kind="confirm",
        visible=True,
        message="sure?",
        actions=[Action("p3.ok", "Enter", "")],
    )
    state = _make_state(popups=[popup])
    out = render_flat(state, include_prompt=False)
    # The fallback should show the input value.
    assert "Enter" in out


# ---------------------------------------------------------------------------
# Status message from the mirror
# ---------------------------------------------------------------------------


def test_status_message_in_output():
    """The status message from serialize() appears in the rendered output."""
    state = _make_state(status=Status(severity="info", message="all systems go"))
    out = render_flat(state, include_prompt=False)
    assert "all systems go" in out


# ---------------------------------------------------------------------------
# commands panel uses numbered bullets
# ---------------------------------------------------------------------------


def test_commands_panel_numbered():
    """A panel with id='commands' uses numbered bullets (1. 2. ...)."""
    panel = Panel(
        id="commands",
        title="Commands",
        visible=True,
        items=[
            PanelItem(id="c1", label="run"),
            PanelItem(id="c2", label="stop"),
        ],
    )
    state = _make_state(panels=[panel])
    out = render_flat(state, include_prompt=False)
    assert "1." in out
    assert "2." in out


def test_non_commands_panel_bullet():
    """A normal panel uses • bullets (not numbered)."""
    panel = Panel(
        id="skills",
        title="Skills",
        visible=True,
        items=[PanelItem(id="s1", label="think")],
    )
    state = _make_state(panels=[panel])
    out = render_flat(state, include_prompt=False)
    assert "•" in out


# ---------------------------------------------------------------------------
# Item status rendering
# ---------------------------------------------------------------------------


def test_item_status_shown_when_not_available():
    """Item label and non-'available' status both appear in the output."""
    panel = Panel(
        id="tasks",
        title="Tasks",
        visible=True,
        items=[PanelItem(id="t1", label="deploy", status="running")],
    )
    state = _make_state(panels=[panel])
    out = render_flat(state, include_prompt=False)
    assert "deploy" in out
    assert "running" in out


def test_item_status_omitted_when_available():
    """When item status is 'available', it is not shown in the output."""
    panel = Panel(
        id="tasks",
        title="Tasks",
        visible=True,
        items=[PanelItem(id="t1", label="think", status="available")],
    )
    state = _make_state(panels=[panel])
    out = render_flat(state, include_prompt=False)
    assert "think" in out
    # The word "available" should not appear as a status suffix.
    assert "— available" not in out


# ---------------------------------------------------------------------------
# _clip — truncation at small width
# ---------------------------------------------------------------------------


def test_clip_long_label_truncated():
    """A panel item with a label longer than width is truncated with '…'."""
    long_label = "A" * 40  # definitely exceeds width=20
    panel = Panel(
        id="skills",
        title="Skills",
        visible=True,
        items=[PanelItem(id="x", label=long_label)],
    )
    state = _make_state(panels=[panel])
    out = render_flat(state, width=20, include_prompt=False)
    assert "…" in out
    # The full label must not appear verbatim.
    assert long_label not in out


def test_clip_short_label_not_truncated():
    """A label shorter than width is kept verbatim."""
    short_label = "ok"
    panel = Panel(
        id="skills",
        title="Skills",
        visible=True,
        items=[PanelItem(id="y", label=short_label)],
    )
    state = _make_state(panels=[panel])
    out = render_flat(state, width=80, include_prompt=False)
    assert short_label in out
    assert "…" not in out


# ---------------------------------------------------------------------------
# content_summary rendering
# ---------------------------------------------------------------------------


def test_panel_summary_rendered():
    """A panel with a content_summary shows the summary text."""
    panel = Panel(
        id="context",
        title="Context",
        visible=True,
        content_summary="watching 3 files",
    )
    state = _make_state(panels=[panel])
    out = render_flat(state, include_prompt=False)
    assert "watching 3 files" in out


def test_panel_multiline_summary():
    """A multi-line content_summary is rendered line-by-line."""
    panel = Panel(
        id="ctx",
        title="Ctx",
        visible=True,
        content_summary="line one\nline two",
    )
    state = _make_state(panels=[panel])
    out = render_flat(state, include_prompt=False)
    assert "line one" in out
    assert "line two" in out
