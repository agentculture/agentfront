"""Unit tests for the five boxed TAUI widget renderers.

Covers: status_bar, skill_panel, conversation, command_palette, popup_layer.
Each renderer is a pure function of TAUIState — same state → same output.
"""

from __future__ import annotations

from agentfront.taui.state import (
    Action,
    ConversationLine,
    Panel,
    PanelItem,
    Popup,
    Status,
    TAUIState,
)
from agentfront.taui.widgets.command_palette import render_command_palette
from agentfront.taui.widgets.conversation import render_conversation
from agentfront.taui.widgets.popup_layer import render_popup_layer
from agentfront.taui.widgets.skill_panel import render_skill_panel
from agentfront.taui.widgets.status_bar import render_status_bar

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(**kwargs) -> TAUIState:
    """Return a TAUIState with keyword overrides applied."""
    return TAUIState(**kwargs)


# ---------------------------------------------------------------------------
# status_bar
# ---------------------------------------------------------------------------


def test_status_bar_error_has_red_sgr() -> None:
    """Error severity → red SGR escape ``\\x1b[31m``."""
    state = _state(status=Status(severity="error", message="boom"))
    out = render_status_bar(state)
    assert "\x1b[31m" in out


def test_status_bar_error_label() -> None:
    """Error severity → ``[ERR]`` label in the bar."""
    state = _state(status=Status(severity="error", message="boom"))
    out = render_status_bar(state)
    assert "[ERR]" in out


def test_status_bar_message_verbatim() -> None:
    """The message text appears verbatim in the status bar."""
    state = _state(status=Status(severity="error", message="disk full"))
    out = render_status_bar(state)
    assert "disk full" in out


def test_status_bar_warn_yellow() -> None:
    """Warn severity → yellow SGR ``\\x1b[33m``."""
    state = _state(status=Status(severity="warn", message="low mem"))
    out = render_status_bar(state)
    assert "\x1b[33m" in out
    assert "[WRN]" in out


def test_status_bar_success_green() -> None:
    """Success severity → green SGR ``\\x1b[32m``."""
    state = _state(status=Status(severity="success", message="done"))
    out = render_status_bar(state)
    assert "\x1b[32m" in out
    assert "[OK " in out


def test_status_bar_info_cyan() -> None:
    """Info severity → cyan SGR ``\\x1b[36m``."""
    state = _state(status=Status(severity="info", message="ready"))
    out = render_status_bar(state)
    assert "\x1b[36m" in out
    assert "[INF]" in out


def test_status_bar_unknown_severity_falls_back_to_cyan_inf() -> None:
    """An unrecognised severity falls back to cyan SGR and INF label."""
    state = _state(status=Status(severity="banana", message="odd"))
    out = render_status_bar(state)
    assert "\x1b[36m" in out
    assert "[INF]" in out
    assert "odd" in out


def test_status_bar_deterministic() -> None:
    """Same state produces identical output on repeated calls."""
    state = _state(status=Status(severity="error", message="repeat"))
    assert render_status_bar(state) == render_status_bar(state)


# ---------------------------------------------------------------------------
# skill_panel
# ---------------------------------------------------------------------------


def test_skill_panel_absent_returns_empty() -> None:
    """No 'skills' panel → empty string."""
    state = _state(panels=[])
    assert render_skill_panel(state) == ""


def test_skill_panel_hidden_returns_empty() -> None:
    """A 'skills' panel with visible=False → empty string."""
    state = _state(panels=[Panel(id="skills", title="Skills", visible=False, items=[])])
    assert render_skill_panel(state) == ""


def test_skill_panel_visible_renders_box() -> None:
    """A visible 'skills' panel renders a box containing the panel title."""
    state = _state(
        panels=[
            Panel(
                id="skills",
                title="My Skills",
                visible=True,
                items=[],
            )
        ]
    )
    out = render_skill_panel(state)
    assert "My Skills" in out
    assert "┌" in out
    assert "└" in out


def test_skill_panel_active_glyph() -> None:
    """An item with status='active' renders with the '●' glyph."""
    state = _state(
        panels=[
            Panel(
                id="skills",
                visible=True,
                items=[PanelItem(id="s1", label="Runner", status="active")],
            )
        ]
    )
    out = render_skill_panel(state)
    assert "●" in out
    assert "Runner" in out


def test_skill_panel_available_glyph() -> None:
    """An item with status='available' renders with the '○' glyph."""
    state = _state(
        panels=[
            Panel(
                id="skills",
                visible=True,
                items=[PanelItem(id="s2", label="Linter", status="available")],
            )
        ]
    )
    out = render_skill_panel(state)
    assert "○" in out
    assert "Linter" in out


def test_skill_panel_disabled_glyph() -> None:
    """An item with status='disabled' renders with the '–' glyph."""
    state = _state(
        panels=[
            Panel(
                id="skills",
                visible=True,
                items=[PanelItem(id="s3", label="Archiver", status="disabled")],
            )
        ]
    )
    out = render_skill_panel(state)
    assert "–" in out


def test_skill_panel_unknown_status_defaults_to_circle() -> None:
    """An item with an unknown status falls back to '○'."""
    state = _state(
        panels=[
            Panel(
                id="skills",
                visible=True,
                items=[PanelItem(id="s4", label="Weird", status="exotic")],
            )
        ]
    )
    out = render_skill_panel(state)
    assert "○" in out


def test_skill_panel_title_fallback() -> None:
    """A panel with no title renders 'Skills' as the fallback title."""
    state = _state(panels=[Panel(id="skills", title="", visible=True, items=[])])
    out = render_skill_panel(state)
    assert "Skills" in out


def test_skill_panel_multiple_items() -> None:
    """Multiple items all appear in the rendered box."""
    state = _state(
        panels=[
            Panel(
                id="skills",
                visible=True,
                items=[
                    PanelItem(id="a", label="Alpha", status="active"),
                    PanelItem(id="b", label="Beta", status="available"),
                ],
            )
        ]
    )
    out = render_skill_panel(state)
    assert "Alpha" in out
    assert "Beta" in out


# ---------------------------------------------------------------------------
# conversation
# ---------------------------------------------------------------------------


def test_conversation_empty_returns_empty() -> None:
    """Empty state.conversation → empty string."""
    state = _state(conversation=[])
    assert render_conversation(state) == ""


def test_conversation_renders_box() -> None:
    """Non-empty conversation renders a box with '╔' and '╚' borders."""
    state = _state(conversation=[ConversationLine(text="hello")])
    out = render_conversation(state)
    assert "╔" in out
    assert "╚" in out
    assert "Conversation" in out


def test_conversation_two_lines_in_order() -> None:
    """Two conversation lines both appear, in order."""
    state = _state(
        conversation=[
            ConversationLine(text="first"),
            ConversationLine(text="second"),
        ]
    )
    out = render_conversation(state)
    assert "first" in out
    assert "second" in out
    # 'first' appears before 'second'
    assert out.index("first") < out.index("second")


def test_conversation_collapsed_duplicate_renders_count() -> None:
    """A ConversationLine with count=3 renders as 'text ×3'."""
    state = _state(conversation=[ConversationLine(text="x", count=3)])
    out = render_conversation(state)
    assert "x ×3" in out


def test_conversation_count_one_no_multiplier() -> None:
    """A ConversationLine with count=1 renders as plain text (no ×N)."""
    state = _state(conversation=[ConversationLine(text="plain", count=1)])
    out = render_conversation(state)
    assert "plain" in out
    assert "×" not in out


def test_conversation_small_width_no_crash() -> None:
    """A pathologically small width=5 does not raise."""
    state = _state(conversation=[ConversationLine(text="hello world this is a long line")])
    out = render_conversation(state, width=5)
    assert isinstance(out, str)
    assert len(out) > 0


def test_conversation_deterministic() -> None:
    """Same state yields identical output on repeated calls."""
    state = _state(conversation=[ConversationLine(text="A"), ConversationLine(text="B", count=2)])
    assert render_conversation(state) == render_conversation(state)


# ---------------------------------------------------------------------------
# command_palette
# ---------------------------------------------------------------------------


def test_command_palette_absent_returns_empty() -> None:
    """No 'commands' panel → empty string."""
    state = _state(panels=[])
    assert render_command_palette(state) == ""


def test_command_palette_hidden_returns_empty() -> None:
    """A 'commands' panel with visible=False → empty string."""
    state = _state(panels=[Panel(id="commands", visible=False, items=[])])
    assert render_command_palette(state) == ""


def test_command_palette_items_numbered() -> None:
    """Items render with 1-based numbers '1.', '2.'."""
    state = _state(
        panels=[
            Panel(
                id="commands",
                visible=True,
                items=[
                    PanelItem(id="c1", label="Deploy"),
                    PanelItem(id="c2", label="Rollback"),
                ],
            )
        ]
    )
    out = render_command_palette(state)
    assert "1." in out
    assert "2." in out
    assert "Deploy" in out
    assert "Rollback" in out


def test_command_palette_title_fallback() -> None:
    """A panel with no title falls back to 'Work templates'."""
    state = _state(panels=[Panel(id="commands", title="", visible=True, items=[])])
    out = render_command_palette(state)
    assert "Work templates" in out


def test_command_palette_custom_title() -> None:
    """A panel with a custom title renders that title."""
    state = _state(panels=[Panel(id="commands", title="My Commands", visible=True, items=[])])
    out = render_command_palette(state)
    assert "My Commands" in out


def test_command_palette_box_borders() -> None:
    """The palette renders with '┌' and '└' box borders."""
    state = _state(panels=[Panel(id="commands", visible=True, items=[])])
    out = render_command_palette(state)
    assert "┌" in out
    assert "└" in out


def test_command_palette_deterministic() -> None:
    """Same state yields identical output on repeated calls."""
    state = _state(
        panels=[
            Panel(
                id="commands",
                visible=True,
                items=[PanelItem(id="x", label="X")],
            )
        ]
    )
    assert render_command_palette(state) == render_command_palette(state)


# ---------------------------------------------------------------------------
# popup_layer
# ---------------------------------------------------------------------------


def test_popup_layer_no_popups_returns_empty() -> None:
    """No popups → empty string."""
    state = _state(popups=[])
    assert render_popup_layer(state) == ""


def test_popup_layer_all_hidden_returns_empty() -> None:
    """All popups visible=False → empty string."""
    state = _state(popups=[Popup(id="p1", kind="error", visible=False, message="oops")])
    assert render_popup_layer(state) == ""


def test_popup_layer_visible_error_renders_title() -> None:
    """A visible 'error' kind popup renders an 'Error' titled box."""
    state = _state(popups=[Popup(id="err1", kind="error", visible=True, message="disk full")])
    out = render_popup_layer(state)
    assert "Error" in out
    assert "disk full" in out


def test_popup_layer_visible_renders_box_borders() -> None:
    """A visible popup renders with '╔' and '╚' box borders."""
    state = _state(popups=[Popup(id="p2", kind="confirmation", visible=True, message="Sure?")])
    out = render_popup_layer(state)
    assert "╔" in out
    assert "╚" in out


def test_popup_layer_hidden_popup_skipped() -> None:
    """A hidden popup does not appear in the output."""
    state = _state(
        popups=[
            Popup(id="hidden", kind="error", visible=False, message="invisible"),
            Popup(id="shown", kind="info", visible=True, message="visible"),
        ]
    )
    out = render_popup_layer(state)
    assert "invisible" not in out
    assert "visible" in out


def test_popup_layer_unknown_kind_title_cases() -> None:
    """An unrecognised kind is title-cased (underscores → spaces)."""
    state = _state(popups=[Popup(id="u1", kind="my_custom_kind", visible=True, message="hi")])
    out = render_popup_layer(state)
    assert "My Custom Kind" in out


def test_popup_layer_known_kinds() -> None:
    """Known kinds map to their human-readable titles."""
    known = {
        "skill_suggestion": "Skill Suggestion",
        "confirmation": "Confirmation",
        "error": "Error",
        "progress": "Progress",
        "diff": "Diff",
        "help": "Help",
    }
    for kind, expected_title in known.items():
        state = _state(popups=[Popup(id="k1", kind=kind, visible=True, message="msg")])
        out = render_popup_layer(state)
        assert expected_title in out, f"Expected {expected_title!r} for kind={kind!r}"


def test_popup_layer_actions_rendered() -> None:
    """Actions appear in the popup as ``[description]`` labels."""
    state = _state(
        popups=[
            Popup(
                id="a1",
                kind="confirmation",
                visible=True,
                message="Delete?",
                actions=[
                    Action(selector="yes", input="y", description="Yes"),
                    Action(selector="no", input="n", description="No"),
                ],
            )
        ]
    )
    out = render_popup_layer(state)
    assert "[Yes]" in out
    assert "[No]" in out


def test_popup_layer_action_falls_back_to_input() -> None:
    """When an action has no description, its ``input`` is shown instead."""
    state = _state(
        popups=[
            Popup(
                id="a2",
                kind="confirmation",
                visible=True,
                message="Proceed?",
                actions=[Action(selector="ok", input="ok", description="")],
            )
        ]
    )
    out = render_popup_layer(state)
    assert "[ok]" in out


def test_popup_layer_yellow_sgr() -> None:
    """Popup box borders use yellow SGR ``\\x1b[33m``."""
    state = _state(popups=[Popup(id="y1", kind="error", visible=True, message="x")])
    out = render_popup_layer(state)
    assert "\x1b[33m" in out


def test_popup_layer_multiple_visible_separated() -> None:
    """Multiple visible popups are present in the output."""
    state = _state(
        popups=[
            Popup(id="p1", kind="error", visible=True, message="first"),
            Popup(id="p2", kind="help", visible=True, message="second"),
        ]
    )
    out = render_popup_layer(state)
    assert "first" in out
    assert "second" in out


def test_popup_layer_deterministic() -> None:
    """Same state produces identical output on repeated calls."""
    state = _state(popups=[Popup(id="d1", kind="error", visible=True, message="err")])
    assert render_popup_layer(state) == render_popup_layer(state)
