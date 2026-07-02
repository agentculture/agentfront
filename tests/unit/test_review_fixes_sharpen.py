"""Regression tests for the adversarial-review findings on the sharpen branch.

Each test pins a fix from the pre-PR review of feat/sharpen-testable-collab:

1. ``Session.dispatch`` must degrade malformed ``SelectorAction.args`` to the
   canonical error/result payload instead of raising (parity with
   ``call_mcp``).
2. The MCP surface must treat an explicit JSON ``null`` ``args`` as "no args",
   exactly like ``call_mcp``.
3. ``ToolInvoked``/``ToolResult``/``SelectorAction`` ``from_dict`` must accept
   an explicit JSON ``null`` for their dict fields (hand-edited trails).
4. ``LiveDriver.feed_key`` must hold the session lock across its
   scan-then-act popup routing (no act-on-stale-popup race).
5. ``assert_agent_human_parity`` must reject a registered-tool selector with
   a purpose-built message instead of a confusing generic mismatch.
"""

from __future__ import annotations

import pytest

from agentfront import App
from agentfront.errors import AgentfrontError
from agentfront.taui.driver import LiveDriver
from agentfront.taui.events import SelectorAction, ToolResult, event_from_dict
from agentfront.taui.session import Session
from agentfront.testing import call_mcp
from agentfront.testing.taui import assert_agent_human_parity


def _build_app() -> App:
    app = App(name="review-fix-app", version="0.1.0", description="review fixes")

    @app.tool()
    def add(x: str = "1", y: str = "2") -> str:
        """Add two stringified ints."""
        return str(int(x) + int(y))

    @app.tool()
    def fail_structured() -> str:
        """Raise a structured error."""
        raise AgentfrontError(code=3, message="bad input", remediation="fix it")

    app.add_command("status", lambda: "ok", help="Show status")
    return app


# --- finding 1: Session.dispatch on malformed args ------------------------


def test_dispatch_args_none_matches_call_mcp() -> None:
    app = _build_app()
    session = Session(app)
    session.dispatch(SelectorAction(selector="add", args=None))  # type: ignore[arg-type]
    assert session.last_result == call_mcp(app, ["add"], args=None)
    assert session.last_result == {"result": "3"}


def test_dispatch_args_non_dict_degrades_to_error_payload() -> None:
    app = _build_app()
    session = Session(app)
    bad = SelectorAction(selector="add", args=["x", "y"])  # type: ignore[arg-type]
    state = session.dispatch(bad)
    assert session.last_result is not None
    assert "error" in session.last_result
    # The fold still happened (ToolInvoked + failing ToolResult), never a crash.
    assert any(isinstance(ev, ToolResult) and not ev.ok for ev in session.events)
    assert any(p.id == "popup.tool-error" and p.visible for p in state.popups)


# --- finding 2: MCP surface explicit JSON null args ------------------------


def test_mcp_surface_null_args_matches_call_mcp() -> None:
    pytest.importorskip("mcp")
    import anyio

    from agentfront.mcp_surface import make_mcp_server
    from tests.unit.test_testing_mcp import _call_run

    app = _build_app()
    server = make_mcp_server(app)
    mcp_payload = anyio.run(_call_run, server, {"command": ["add"], "args": None})
    assert mcp_payload == call_mcp(app, ["add"], args=None)
    assert mcp_payload == {"result": "3"}


# --- finding 3: from_dict tolerates explicit JSON null ---------------------


def test_events_from_dict_tolerate_explicit_null() -> None:
    invoked = event_from_dict({"type": "tool_invoked", "selector": "a.b", "args": None})
    assert invoked.args == {}
    result = event_from_dict({"type": "tool_result", "selector": "a.b", "ok": False, "error": None})
    assert result.error == {}
    action = event_from_dict({"type": "selector_action", "selector": "a.b", "args": None})
    assert action.args == {}


# --- finding 4: LiveDriver scan-then-act holds the session lock ------------


def test_feed_key_popup_scan_runs_under_session_lock(monkeypatch) -> None:
    app = _build_app()
    session = Session(app)
    session.dispatch(SelectorAction(selector="fail_structured", args={}))
    driver = LiveDriver(session)

    seen: list[bool] = []
    original = LiveDriver._matching_popup_action

    def probe(self, key):  # noqa: ANN001
        seen.append(self.session.locked()._is_owned())
        return original(self, key)

    monkeypatch.setattr(LiveDriver, "_matching_popup_action", probe)
    driver.feed_key("esc")
    assert seen == [True]
    assert all(not p.visible for p in session.state.popups)


# --- finding 5: parity helper rejects tool selectors up front ---------------


def test_parity_helper_rejects_registered_tool_selector() -> None:
    app = _build_app()
    with pytest.raises(AssertionError, match="resolves to a registered tool"):
        assert_agent_human_parity(app, "add")


def test_parity_helper_still_passes_for_host_command_selector() -> None:
    app = _build_app()
    assert_agent_human_parity(app, "cmd.status")
