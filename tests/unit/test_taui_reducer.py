"""Unit tests for agentfront.taui.reducer — the single pure fold."""

from __future__ import annotations

from agentfront.taui.events import (
    Dismiss,
    KeyPress,
    SelectorAction,
    SkillSuggested,
    Tick,
    UserInput,
    WorkStep,
)
from agentfront.taui.reducer import focus_order, reduce, replay
from agentfront.taui.selectors import resolve
from agentfront.taui.state import Panel, PanelItem, Popup, TAUIState, WorkItem

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
# Tick — advances background.frame
# ---------------------------------------------------------------------------


def test_tick_advances_background_frame() -> None:
    state = TAUIState()
    result = reduce(state, Tick(delta=3))
    assert result.background.frame == 3


def test_tick_delta_accumulates() -> None:
    state = TAUIState()
    s1 = reduce(state, Tick(delta=1))
    s2 = reduce(s1, Tick(delta=2))
    assert s2.background.frame == 3


def test_tick_default_delta_is_one() -> None:
    state = TAUIState()
    result = reduce(state, Tick())
    assert result.background.frame == 1


# ---------------------------------------------------------------------------
# UserInput — appends to conversation with duplicate collapse
# ---------------------------------------------------------------------------


def test_user_input_appends_conversation() -> None:
    state = TAUIState()
    result = reduce(state, UserInput(text="hello"))
    assert len(result.conversation) == 1
    assert result.conversation[0].text == "hello"
    assert result.conversation[0].count == 1


def test_user_input_consecutive_duplicate_collapse() -> None:
    """Same text twice → one ConversationLine with count==2 and render()=='text ×2'."""
    state = TAUIState()
    s1 = reduce(state, UserInput(text="text"))
    s2 = reduce(s1, UserInput(text="text"))
    assert len(s2.conversation) == 1
    assert s2.conversation[0].count == 2
    assert s2.conversation[0].render() == "text ×2"


def test_user_input_non_consecutive_does_not_collapse() -> None:
    state = TAUIState()
    s1 = reduce(state, UserInput(text="first"))
    s2 = reduce(s1, UserInput(text="second"))
    assert len(s2.conversation) == 2


def test_user_input_triple_collapse() -> None:
    """Three consecutive identical inputs → one line, count==3."""
    state = TAUIState()
    s = reduce(state, UserInput(text="x"))
    s = reduce(s, UserInput(text="x"))
    s = reduce(s, UserInput(text="x"))
    assert len(s.conversation) == 1
    assert s.conversation[0].count == 3


# ---------------------------------------------------------------------------
# SkillSuggested — opens popup + sets background
# ---------------------------------------------------------------------------


def test_skill_suggested_opens_visible_non_blocking_popup() -> None:
    state = TAUIState()
    result = reduce(state, SkillSuggested(skill="myskill", reason="it is better"))
    assert len(result.popups) == 1
    popup = result.popups[0]
    assert popup.id == "popup.skill-suggested"
    assert popup.visible is True
    assert popup.blocking is False


def test_skill_suggested_sets_background_theme_and_semantic() -> None:
    state = TAUIState()
    result = reduce(state, SkillSuggested(skill="myskill", theme="custom_theme", semantic="s"))
    assert result.background.theme == "custom_theme"
    assert result.background.semantic == "s"


def test_skill_suggested_popup_message_with_skill() -> None:
    state = TAUIState()
    result = reduce(state, SkillSuggested(skill="myskill"))
    assert result.popups[0].message == "Suggested skill: myskill"


def test_skill_suggested_popup_message_without_skill() -> None:
    state = TAUIState()
    result = reduce(state, SkillSuggested(skill=""))
    assert result.popups[0].message == "Skill suggested"


def test_skill_suggested_default_theme_and_semantic() -> None:
    """SkillSuggested defaults propagate to background correctly."""
    state = TAUIState()
    result = reduce(state, SkillSuggested())
    assert result.background.theme == "skill_suggested"
    assert result.background.semantic == "stronger_agent_recommended"


def test_skill_suggested_popup_actions_resolve() -> None:
    """Both popup action selectors must be resolvable via selectors.resolve()."""
    state = TAUIState()
    result = reduce(state, SkillSuggested(skill="myskill", reason="better fit"))
    popup = result.popups[0]
    assert len(popup.actions) == 2
    for action in popup.actions:
        node = resolve(result, action.selector)
        assert node is not None


def test_skill_suggested_popup_reason_stored() -> None:
    state = TAUIState()
    result = reduce(state, SkillSuggested(skill="myskill", reason="specialist required"))
    assert result.popups[0].reason == "specialist required"


def test_skill_suggested_pure_input_unchanged() -> None:
    """SkillSuggested does not mutate the input state."""
    state = TAUIState()
    original = state.to_dict()
    reduce(state, SkillSuggested(skill="myskill"))
    assert state.to_dict() == original


# ---------------------------------------------------------------------------
# WorkStep — appends conversation, increments step_count, error popup
# ---------------------------------------------------------------------------


def test_work_step_appends_conversation() -> None:
    state = TAUIState()
    result = reduce(state, WorkStep(label="Doing thing"))
    assert len(result.conversation) == 1
    assert result.conversation[0].text == "Doing thing"


def test_work_step_increments_step_count_with_work_item() -> None:
    state = TAUIState(work_item=WorkItem(task_id="t1"))
    result = reduce(state, WorkStep(label="step"))
    assert result.work_item is not None
    assert result.work_item.step_count == 1


def test_work_step_no_crash_without_work_item() -> None:
    """WorkStep with work_item=None must not crash and leaves work_item None."""
    state = TAUIState(work_item=None)
    result = reduce(state, WorkStep(label="step"))
    assert result.work_item is None


def test_work_step_ok_does_not_open_error_popup() -> None:
    state = TAUIState()
    result = reduce(state, WorkStep(label="step", ok=True))
    assert len(result.popups) == 0


def test_work_step_not_ok_opens_visible_blocking_error_popup() -> None:
    state = TAUIState()
    result = reduce(state, WorkStep(label="step", ok=False, error="Something went wrong"))
    assert len(result.popups) == 1
    popup = result.popups[0]
    assert popup.id == "popup.work-error"
    assert popup.visible is True
    assert popup.blocking is True
    assert popup.message == "Something went wrong"


def test_work_step_not_ok_uses_label_when_no_error() -> None:
    state = TAUIState()
    result = reduce(state, WorkStep(label="the step", ok=False, error=""))
    assert result.popups[0].message == "the step"


def test_work_step_not_ok_default_message_when_no_label_or_error() -> None:
    state = TAUIState()
    result = reduce(state, WorkStep(label="", ok=False, error=""))
    assert result.popups[0].message == "Work step failed"


def test_work_step_conversation_collapse() -> None:
    """Consecutive identical WorkStep labels also collapse."""
    state = TAUIState()
    s1 = reduce(state, WorkStep(label="ping"))
    s2 = reduce(s1, WorkStep(label="ping"))
    assert len(s2.conversation) == 1
    assert s2.conversation[0].count == 2


def test_work_step_pure_input_unchanged() -> None:
    """WorkStep does not mutate the input state."""
    state = TAUIState(work_item=WorkItem(task_id="t1"))
    original = state.to_dict()
    reduce(state, WorkStep(label="step", ok=False, error="err"))
    assert state.to_dict() == original


# ---------------------------------------------------------------------------
# replay() — fold an event list into a TAUIState
# ---------------------------------------------------------------------------


def test_replay_empty_events_none_initial_returns_default() -> None:
    result = replay([], None)
    assert result == TAUIState()


def test_replay_empty_events_with_initial() -> None:
    initial = TAUIState(mode="executing")
    result = replay([], initial)
    assert result == initial


def test_replay_matches_manual_reduction() -> None:
    """replay() folds events into the same state as manual sequential reduce()."""
    events = [Tick(delta=2), UserInput(text="hello"), UserInput(text="world")]
    s = TAUIState()
    for ev in events:
        s = reduce(s, ev)
    replayed = replay(events, TAUIState())
    assert replayed.to_dict() == s.to_dict()


def test_replay_with_skill_suggested_and_work_step() -> None:
    events = [
        SkillSuggested(skill="fast-path"),
        WorkStep(label="step 1"),
        WorkStep(label="step 2"),
    ]
    result = replay(events)
    assert len(result.popups) == 1
    assert len(result.conversation) == 2


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


# ---------------------------------------------------------------------------
# Review-driven regression tests (issue #43 SHOULD-FIX items)
# ---------------------------------------------------------------------------


def test_dismiss_clears_blocking_so_diagnose_stays_ok():
    """Dismissing a blocking error popup must not leave a blocking+invisible
    popup that diagnose_structured would flag as a POPUP_LIFECYCLE bug."""
    from agentfront.taui.diagnose import diagnose_structured

    state = TAUIState(work_item=WorkItem(task_id="t1", engine="mock", running=True))
    failed = reduce(state, WorkStep(label="call tool", ok=False, error="boom"))
    err = next(p for p in failed.popups if p.id == "popup.work-error")
    assert err.visible is True and err.blocking is True
    assert diagnose_structured(failed).ok is True

    dismissed = reduce(failed, Dismiss())
    err2 = next(p for p in dismissed.popups if p.id == "popup.work-error")
    assert err2.visible is False
    assert err2.blocking is False  # dismissed modal no longer blocks
    assert diagnose_structured(dismissed).ok is True


def test_repeated_failed_work_step_keeps_single_error_popup():
    """Repeated failed steps refresh one work-error popup rather than appending
    duplicate ids (which diagnose_structured would flag as a LAYOUT bug)."""
    from agentfront.taui.diagnose import diagnose_structured

    state = TAUIState(work_item=WorkItem(task_id="t1", engine="mock", running=True))
    s1 = reduce(state, WorkStep(label="step one", ok=False, error="first"))
    s2 = reduce(s1, WorkStep(label="step two", ok=False, error="second"))
    work_errors = [p for p in s2.popups if p.id == "popup.work-error"]
    assert len(work_errors) == 1  # one live error popup, not two
    assert work_errors[0].message == "second"  # reflects the latest failure
    assert s2.work_item.step_count == 2
    assert diagnose_structured(s2).ok is True
