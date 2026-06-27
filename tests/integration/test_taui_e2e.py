"""End-to-end TAUI flow test (t14).

Proves that the agent path (mirror + selector dispatch) and the human path
(keyboard navigation) reach identical state, and that the mirror's
available_actions is sufficient at every step of a multi-step flow.
"""

from __future__ import annotations

from dataclasses import replace

from agentfront import App
from agentfront.taui.events import Dismiss, KeyPress, SelectorAction
from agentfront.taui.mirror import serialize
from agentfront.taui.reducer import focus_order, reduce
from agentfront.taui.state import Action, Popup


def _make_app() -> App:
    """Return an App with grouped tools for the e2e test."""
    app = App(name="E2ETest", version="0.1.0")

    @app.tool(group=("search",))
    def query(text: str) -> str:
        """Search the corpus."""
        return text

    @app.tool(group=("search",))
    def index() -> str:
        """Rebuild the index."""
        return "ok"

    @app.tool(group=("deploy",))
    def release() -> str:
        """Release to production."""
        return "ok"

    @app.tool
    def status() -> str:
        """Check status."""
        return "ok"

    return app


def test_agent_and_human_reach_identical_state() -> None:
    """Agent path (SelectorAction) and human path (KeyPress) reach identical state."""
    app = _make_app()
    state0 = app.taui()

    # Set initial focus to the first item in focus order.
    order = focus_order(state0)
    state0 = replace(state0, focused=order[0])

    # Pick a target at index k >= 2.
    k = 2
    target = order[k]

    # --- Agent path: learn target from mirror, then dispatch ---
    mirror = serialize(state0)
    available = {entry["selector"] for entry in mirror["available_actions"]}
    assert target in available, f"Target {target!r} not in mirror available_actions"
    state_agent = reduce(state0, SelectorAction(selector=target))

    # --- Human path: navigate with KeyPress("down") ---
    state_human = state0
    for _ in range(k):
        state_human = reduce(state_human, KeyPress("down"))

    assert state_agent.to_dict() == state_human.to_dict()


def test_multi_step_flow_mirror_sufficient() -> None:
    """At each step, the mirror's available_actions is sufficient to pick the next action."""
    app = _make_app()
    state0 = app.taui()

    # Inject a visible popup with a dismiss action.
    popup = Popup(
        id="popup.alert",
        kind="alert",
        visible=True,
        actions=[
            Action(
                selector="popup.alert.dismiss",
                input="esc",
                description="Dismiss alert",
            ),
        ],
    )
    state0 = replace(state0, popups=[popup])

    # Set initial focus to the first item in focus order.
    order = focus_order(state0)
    state0 = replace(state0, focused=order[0])

    # --- Step 1: focus an item via SelectorAction ---
    target1 = order[2]
    mirror_1 = serialize(state0)
    available_1 = {entry["selector"] for entry in mirror_1["available_actions"]}
    assert target1 in available_1, f"Step 1: {target1!r} not in mirror"
    state1 = reduce(state0, SelectorAction(selector=target1))

    # --- Step 2: dismiss the popup ---
    # The popup's action selector must be in the mirror before dispatch.
    mirror_2 = serialize(state1)
    available_2 = {entry["selector"] for entry in mirror_2["available_actions"]}
    dismiss_selector = "popup.alert.dismiss"
    assert dismiss_selector in available_2, f"Step 2: {dismiss_selector!r} not in mirror"
    state2 = reduce(state1, Dismiss())

    # Verify the popup is now hidden.
    assert not state2.popups[0].visible
