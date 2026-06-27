"""Unit tests for agentfront.taui.mirror — serialize(state) -> JSON mirror dict."""

from __future__ import annotations

import json

import pytest

from agentfront.taui.mirror import SCHEMA_VERSION, serialize
from agentfront.taui.render.ansi import render_ansi
from agentfront.taui.selectors import resolve
from agentfront.taui.state import (
    Action,
    Header,
    Panel,
    PanelItem,
    Popup,
    Status,
    TAUIState,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _baseline_state() -> TAUIState:
    """A minimal state with one visible panel and no popups."""
    return TAUIState(
        header=Header(title="TestApp"),
        panels=[
            Panel(
                id="panel.tools",
                title="Tools",
                visible=True,
                items=[
                    PanelItem(id="tools.search", label="Search", status="available"),
                    PanelItem(id="tools.deploy", label="Deploy", status="available"),
                ],
            ),
        ],
        status=Status(severity="info", message="Ready"),
    )


def _extended_state() -> TAUIState:
    """State with a visible popup, a hidden panel, and a visible panel."""
    return TAUIState(
        header=Header(title="TestApp"),
        panels=[
            Panel(
                id="panel.tools",
                title="Tools",
                visible=True,
                items=[
                    PanelItem(id="tools.search", label="Search", status="available"),
                ],
            ),
            Panel(
                id="panel.hidden",
                title="Hidden",
                visible=False,
                items=[
                    PanelItem(id="hidden.action", label="Hidden Action", status="available"),
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
        status=Status(severity="info", message="Ready"),
    )


# ---------------------------------------------------------------------------
# Test 1: available_actions derived from state tree; JSON-serializable
# ---------------------------------------------------------------------------


class TestAvailableActionsDerived:
    """Every available_actions selector resolves; mirror is JSON-serializable."""

    @pytest.mark.parametrize(
        "state_factory",
        [_baseline_state, _extended_state],
    )
    def test_every_selector_resolves(self, state_factory: callable) -> None:
        """Every selector in available_actions resolves via selectors.resolve()."""
        state = state_factory()
        mirror = serialize(state)
        for entry in mirror["available_actions"]:
            # Must not raise.
            resolve(state, entry["selector"])

    @pytest.mark.parametrize(
        "state_factory",
        [_baseline_state, _extended_state],
    )
    def test_json_serializable(self, state_factory: callable) -> None:
        """json.dumps(serialize(state)) never raises."""
        state = state_factory()
        payload = json.dumps(serialize(state))
        assert isinstance(payload, str)
        assert len(payload) > 0


# ---------------------------------------------------------------------------
# Test 2: mirror and render_ansi describe the same screen
# ---------------------------------------------------------------------------


class TestMirrorAndRenderCoEqual:
    """Mirror and render_ansi agree on visible items for one state."""

    def test_visible_items_appear_in_both(self) -> None:
        """Every visible panel item's label appears in both outputs."""
        state = _extended_state()
        mirror = serialize(state)
        ansi = render_ansi(state)

        # Collect labels from visible panels.
        visible_labels: list[str] = []
        for panel in state.panels:
            if panel.visible:
                for item in panel.items:
                    visible_labels.append(item.label)

        # Each visible label must appear in available_actions descriptions.
        action_descriptions = {entry["description"] for entry in mirror["available_actions"]}
        for label in visible_labels:
            assert (
                label in action_descriptions
            ), f"Visible label {label!r} missing from available_actions"

        # Each visible label must appear in render_ansi output.
        for label in visible_labels:
            assert label in ansi, f"Visible label {label!r} missing from render_ansi"

    def test_hidden_items_appear_in_neither(self) -> None:
        """Hidden panel items appear in neither mirror nor render_ansi."""
        state = _extended_state()
        mirror = serialize(state)
        ansi = render_ansi(state)

        # Collect labels from hidden panels.
        hidden_labels: list[str] = []
        for panel in state.panels:
            if not panel.visible:
                for item in panel.items:
                    hidden_labels.append(item.label)

        # Hidden labels must NOT appear in available_actions descriptions.
        action_descriptions = {entry["description"] for entry in mirror["available_actions"]}
        for label in hidden_labels:
            assert (
                label not in action_descriptions
            ), f"Hidden label {label!r} leaked into available_actions"

        # Hidden labels must NOT appear in render_ansi output.
        for label in hidden_labels:
            assert label not in ansi, f"Hidden label {label!r} leaked into render_ansi"


# ---------------------------------------------------------------------------
# Additional structural checks
# ---------------------------------------------------------------------------


class TestMirrorStructure:
    """Mirror dict has the expected keys and schema version."""

    def test_taui_version_present(self) -> None:
        state = _baseline_state()
        mirror = serialize(state)
        assert mirror["taui_version"] == SCHEMA_VERSION

    def test_contains_to_dict_keys(self) -> None:
        """All keys from state.to_dict() are present in the mirror."""
        state = _baseline_state()
        mirror = serialize(state)
        for key in state.to_dict():
            assert key in mirror, f"Missing key {key!r} from mirror"

    def test_available_actions_is_list(self) -> None:
        state = _baseline_state()
        mirror = serialize(state)
        assert isinstance(mirror["available_actions"], list)

    def test_standing_action_always_present(self) -> None:
        """The input.prompt standing action is always in available_actions."""
        state = TAUIState()  # empty state
        mirror = serialize(state)
        selectors = [entry["selector"] for entry in mirror["available_actions"]]
        assert "input.prompt" in selectors
