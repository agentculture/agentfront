"""Unit tests for agentfront.taui.selectors — selector resolution."""

from __future__ import annotations

import pytest

from agentfront.errors import EXIT_USER_ERROR, AgentfrontError
from agentfront.taui.selectors import (
    advertised_selectors,
    all_selectors_resolve,
    resolve,
)
from agentfront.taui.state import (
    Action,
    Panel,
    PanelItem,
    Popup,
    TAUIState,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _build_state() -> TAUIState:
    """Return a representative TAUIState with panels, items, aliases, popups."""
    return TAUIState(
        panels=[
            Panel(
                id="panel.feedback",
                title="Feedback",
                visible=True,
                items=[
                    PanelItem(
                        id="feedback.record",
                        label="Record",
                        status="available",
                        tags=["alias:record"],
                    ),
                    PanelItem(
                        id="feedback.delete",
                        label="Delete",
                        status="available",
                    ),
                ],
            ),
            Panel(
                id="panel.search",
                title="Search",
                visible=True,
                items=[
                    PanelItem(id="search.query", label="Query", status="available"),
                ],
            ),
        ],
        popups=[
            Popup(
                id="popup.confirm",
                kind="confirm",
                visible=True,
                blocking=True,
                actions=[
                    Action(selector="confirm.yes", input="y", description="Confirm"),
                    Action(selector="confirm.no", input="n", description="Cancel"),
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# resolve() — correct node for every advertised selector
# ---------------------------------------------------------------------------


class TestResolve:
    """resolve() returns the correct node for every selector type."""

    def test_panel_id(self) -> None:
        state = _build_state()
        node = resolve(state, "panel.feedback")
        assert isinstance(node, Panel)
        assert node.id == "panel.feedback"

    def test_panel_item_id(self) -> None:
        state = _build_state()
        node = resolve(state, "feedback.record")
        assert isinstance(node, PanelItem)
        assert node.id == "feedback.record"

    def test_alias_path(self) -> None:
        """An alias tag 'alias:record' resolves the bare path 'record'."""
        state = _build_state()
        node = resolve(state, "record")
        assert isinstance(node, PanelItem)
        assert node.id == "feedback.record"

    def test_popup_id(self) -> None:
        state = _build_state()
        node = resolve(state, "popup.confirm")
        assert isinstance(node, Popup)
        assert node.id == "popup.confirm"

    def test_popup_action_selector(self) -> None:
        state = _build_state()
        node = resolve(state, "confirm.yes")
        assert isinstance(node, Action)
        assert node.selector == "confirm.yes"

    def test_input_prompt_sentinel(self) -> None:
        state = _build_state()
        node = resolve(state, "input.prompt")
        assert node == {"kind": "input", "selector": "input.prompt"}

    def test_unknown_selector_raises(self) -> None:
        state = _build_state()
        with pytest.raises(AgentfrontError) as exc_info:
            resolve(state, "nonexistent.selector")
        err = exc_info.value
        assert err.code == EXIT_USER_ERROR
        assert "nonexistent.selector" in err.message


# ---------------------------------------------------------------------------
# advertised_selectors()
# ---------------------------------------------------------------------------


class TestAdvertisedSelectors:
    """advertised_selectors() lists every resolvable selector."""

    def test_contains_panel_ids(self) -> None:
        state = _build_state()
        sels = advertised_selectors(state)
        assert "panel.feedback" in sels
        assert "panel.search" in sels

    def test_contains_item_ids(self) -> None:
        state = _build_state()
        sels = advertised_selectors(state)
        assert "feedback.record" in sels
        assert "feedback.delete" in sels
        assert "search.query" in sels

    def test_contains_alias_paths(self) -> None:
        state = _build_state()
        sels = advertised_selectors(state)
        assert "record" in sels

    def test_contains_popup_ids(self) -> None:
        state = _build_state()
        sels = advertised_selectors(state)
        assert "popup.confirm" in sels

    def test_contains_action_selectors(self) -> None:
        state = _build_state()
        sels = advertised_selectors(state)
        assert "confirm.yes" in sels
        assert "confirm.no" in sels

    def test_contains_input_prompt(self) -> None:
        state = _build_state()
        sels = advertised_selectors(state)
        assert "input.prompt" in sels

    def test_empty_state(self) -> None:
        state = TAUIState()
        sels = advertised_selectors(state)
        assert sels == ["input.prompt"]


# ---------------------------------------------------------------------------
# all_selectors_resolve()
# ---------------------------------------------------------------------------


class TestAllSelectorsResolve:
    """all_selectors_resolve() is True for a populated state."""

    def test_populated_state(self) -> None:
        state = _build_state()
        assert all_selectors_resolve(state) is True

    def test_empty_state(self) -> None:
        state = TAUIState()
        assert all_selectors_resolve(state) is True
