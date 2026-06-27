"""Unit tests for agentfront.taui.reducer — the single pure fold."""

from __future__ import annotations

from agentfront.taui.events import Dismiss, KeyPress, SelectorAction, Tick, UserInput
from agentfront.taui.reducer import focus_order, reduce
from agentfront.taui.state import Panel, PanelItem, Popup, TAUIState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state_with_items(
    items: list[tuple[str, str]],
    visible: list[bool] | None = None,
    focused: str = "input.prompt",
) -> TAUIState:
    """Build a TAUIState with the given panel items.

    Each tuple is (panel_id, item_id). If *visible* is provided, it controls
    panel visibility; otherwise all panels are visible.
    """
    seen: dict[str, list[PanelItem]] = {}
    vis: dict[str, bool] = {}
    panel_order: list[str] = []
    for panel_id, item_id in items:
        if panel_id not in seen:
            seen[panel_id] = []
            panel_order.append(panel_id)
            vis[panel_id] = True
        seen[panel_id].append(PanelItem(id=item_id, label=item_id))

    if visible is not None:
        for i, pid in enumerate(panel_order):
            if i < len(visible):
                vis[pid] = visible[i]

    panels = [Panel(id=pid, visible=vis[pid], items=items) for pid, items in seen.items()]
    return TAUIState(panels=panels, focused=focused)


def _state_with_three_items() -> TAUIState:
    """State with three focusable items across two panels."""
    return TAUIState(
        panels=[
            Panel(
                id="panel.a",
                visible=True,
                items=[
                    PanelItem(id="a.1", label="A1"),
                    PanelItem(id="a.2", label="A2"),
                ],
            ),
            Panel(
                id="panel.b",
                visible=True,
                items=[PanelItem(id="b.1", label="B1")],
            ),
        ],
        focused="a.1",
    )


# ---------------------------------------------------------------------------
# focus_order
# ---------------------------------------------------------------------------


def test_focus_order_basic() -> None:
    state = _state_with_three_items()
    assert focus_order(state) == ["a.1", "a.2", "b.1", "input.prompt"]


def test_focus_order_respects_visibility() -> None:
    state = TAUIState(
        panels=[
            Panel(id="p1", visible=True, items=[PanelItem(id="x", label="X")]),
            Panel(id="p2", visible=False, items=[PanelItem(id="y", label="Y")]),
        ],
    )
    assert focus_order(state) == ["x", "input.prompt"]


def test_focus_order_empty_panels() -> None:
    state = TAUIState(panels=[])
    assert focus_order(state) == ["input.prompt"]


def test_focus_order_empty_items() -> None:
    state = TAUIState(panels=[Panel(id="p", visible=True, items=[])])
    assert focus_order(state) == ["input.prompt"]


# ---------------------------------------------------------------------------
# KeyPress("down")
# ---------------------------------------------------------------------------


def test_keypress_down_navigates_forward() -> None:
    state = _state_with_three_items()
    result = reduce(state, KeyPress("down"))
    assert result.focused == "a.2"


def test_keypress_down_clamps_at_end() -> None:
    state = _state_with_three_items()
    # Navigate to end: a.1 -> a.2 -> b.1 -> input.prompt
    s1 = reduce(state, KeyPress("down"))
    s2 = reduce(s1, KeyPress("down"))
    s3 = reduce(s2, KeyPress("down"))
    assert s3.focused == "input.prompt"
    # Further down stays at end
    s4 = reduce(s3, KeyPress("down"))
    assert s4.focused == "input.prompt"


# ---------------------------------------------------------------------------
# KeyPress("up")
# ---------------------------------------------------------------------------


def test_keypress_up_navigates_backward() -> None:
    state = _state_with_three_items()
    # Start at a.1, go down to a.2, then up back to a.1
    s1 = reduce(state, KeyPress("down"))
    assert s1.focused == "a.2"
    s2 = reduce(s1, KeyPress("up"))
    assert s2.focused == "a.1"


def test_keypress_up_clamps_at_start() -> None:
    state = _state_with_three_items()
    result = reduce(state, KeyPress("up"))
    assert result.focused == "a.1"


# ---------------------------------------------------------------------------
# KeyPress("enter") — no-op for v1
# ---------------------------------------------------------------------------


def test_keypress_enter_noop() -> None:
    state = _state_with_three_items()
    result = reduce(state, KeyPress("enter"))
    assert result == state


# ---------------------------------------------------------------------------
# KeyPress("esc") — dismiss topmost visible popup
# ---------------------------------------------------------------------------


def test_keypress_esc_hides_topmost_popup() -> None:
    state = TAUIState(
        popups=[
            Popup(id="p1", kind="alert", visible=True),
            Popup(id="p2", kind="confirm", visible=True),
        ],
    )
    result = reduce(state, KeyPress("esc"))
    assert result.popups[0].visible is True
    assert result.popups[1].visible is False


def test_keypress_esc_no_visible_popup_is_noop() -> None:
    state = TAUIState(popups=[Popup(id="p1", kind="alert", visible=False)])
    result = reduce(state, KeyPress("esc"))
    assert result == state


def test_keypress_esc_no_popups_is_noop() -> None:
    state = TAUIState()
    result = reduce(state, KeyPress("esc"))
    assert result == state


# ---------------------------------------------------------------------------
# Dismiss — hide topmost visible popup
# ---------------------------------------------------------------------------


def test_dismiss_hides_topmost_popup() -> None:
    state = TAUIState(
        popups=[
            Popup(id="p1", kind="alert", visible=True),
            Popup(id="p2", kind="confirm", visible=True),
        ],
    )
    result = reduce(state, Dismiss(target="p2"))
    assert result.popups[0].visible is True
    assert result.popups[1].visible is False


def test_dismiss_no_visible_popup_is_noop() -> None:
    state = TAUIState(popups=[Popup(id="p1", kind="alert", visible=False)])
    result = reduce(state, Dismiss())
    assert result == state


# ---------------------------------------------------------------------------
# SelectorAction
# ---------------------------------------------------------------------------


def test_selector_action_sets_focus() -> None:
    state = _state_with_three_items()
    result = reduce(state, SelectorAction(selector="b.1"))
    assert result.focused == "b.1"


def test_selector_action_invalid_selector_is_noop() -> None:
    state = _state_with_three_items()
    result = reduce(state, SelectorAction(selector="nonexistent"))
    assert result == state


# ---------------------------------------------------------------------------
# Tick / UserInput — no-op
# ---------------------------------------------------------------------------


def test_tick_is_noop() -> None:
    state = _state_with_three_items()
    result = reduce(state, Tick())
    assert result == state


def test_user_input_is_noop() -> None:
    state = _state_with_three_items()
    result = reduce(state, UserInput(text="hello"))
    assert result == state


# ---------------------------------------------------------------------------
# Unknown key — no-op
# ---------------------------------------------------------------------------


def test_unknown_key_is_noop() -> None:
    state = _state_with_three_items()
    result = reduce(state, KeyPress("tab"))
    assert result == state


# ---------------------------------------------------------------------------
# Acceptance #1: agent-path == human-path equality
# ---------------------------------------------------------------------------


def test_agent_human_path_equality() -> None:
    """SelectorAction(sel) == KeyPress("down") sequence for the same target."""
    state = _state_with_three_items()
    order = focus_order(state)
    # Target: focus_order[2] == "b.1"
    target = order[2]

    # Agent path: direct SelectorAction
    agent_result = reduce(state, SelectorAction(selector=target))

    # Human path: two KeyPress("down") from initial focus (order[0] == "a.1")
    human_result = reduce(state, KeyPress("down"))
    human_result = reduce(human_result, KeyPress("down"))

    assert agent_result.to_dict() == human_result.to_dict()


# ---------------------------------------------------------------------------
# Acceptance #2: purity
# ---------------------------------------------------------------------------


def test_reduce_is_pure_input_unchanged() -> None:
    """The input state is not mutated by reduce."""
    state = _state_with_three_items()
    original = state.to_dict()
    reduce(state, KeyPress("down"))
    assert state.to_dict() == original


def test_reduce_is_deterministic() -> None:
    """Same (state, event) → equal next state on repeated calls."""
    state = _state_with_three_items()
    event = KeyPress("down")
    r1 = reduce(state, event)
    r2 = reduce(state, event)
    assert r1.to_dict() == r2.to_dict()


def test_reduce_pure_with_selector_action() -> None:
    """SelectorAction does not mutate the input state."""
    state = _state_with_three_items()
    original = state.to_dict()
    reduce(state, SelectorAction(selector="b.1"))
    assert state.to_dict() == original


def test_reduce_pure_with_dismiss() -> None:
    """Dismiss does not mutate the input state."""
    state = TAUIState(
        popups=[Popup(id="p1", kind="alert", visible=True)],
    )
    original = state.to_dict()
    reduce(state, Dismiss())
    assert state.to_dict() == original
