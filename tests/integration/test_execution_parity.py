"""Cross-surface execution parity integration test (t12).

Proves the honesty condition at the center of this plan: the SAME tool,
invoked through the three consumer-facing surfaces —

* a live TAUI session (:meth:`agentfront.taui.session.Session.dispatch`),
* the in-process CLI harness (:func:`agentfront.testing.run_cli`), and
* the in-process MCP harness (:func:`agentfront.testing.call_mcp`),

— yields the SAME result, or the SAME structured
:class:`agentfront.errors.AgentfrontError`, everywhere. All three dispatch
paths are ultimately built from the shared helpers in
``agentfront._run_dispatch`` (t7); this test is the consumer-facing proof
that the sharing actually holds end to end, not a re-test of the helpers
themselves (those already have unit coverage in ``tests/unit/test_taui_session.py``
and ``tests/unit/test_testing_mcp.py``).

One module-level fixture app exercises the four honesty-condition cases the
design contract calls for:

* ``status``            — a tool returning a JSON-able value (a dict).
* ``data.echo``          — a grouped tool (``group=("data",)``) echoing its args.
* ``fail_structured``    — a tool raising ``AgentfrontError(code=3, ...)``.
* ``fail_generic``       — a tool raising a plain ``ValueError("boom")``.

A note on the one place the three surfaces are *not* byte-identical: the CLI
wraps an *unexpected* (non-``AgentfrontError``) exception in a friendlier
``"unexpected: <ClassName>: <message>"`` shape with its own remediation
(``agentfront/cli_surface.py``'s ``_dispatch``, pre-existing and independent
of the t7 refactor) rather than emitting the bare MCP-shape message/remediation
pair. This is a deliberate, pre-existing CLI ergonomics choice (never leak a
bare exception string without a "here's what happened" prefix), not a parity
regression introduced by this plan — the design contract's own spec for this
task only requires the ValueError case to "surface its message with a
nonzero exit" on the CLI (weaker than the exact-triple check it requires for
the ``AgentfrontError`` case). ``test_value_error_cli_surfaces_message_with_nonzero_exit``
below asserts exactly that, and documents the divergence inline rather than
asserting an equality that does not hold by design.
"""

from __future__ import annotations

import json

import pytest

from agentfront import App
from agentfront.errors import AgentfrontError
from agentfront.taui.events import SelectorAction
from agentfront.taui.session import Session
from agentfront.testing import call_mcp, run_cli

_STRUCTURED_MESSAGE = "invalid input"
_STRUCTURED_REMEDIATION = "check the value and retry"


def _build_app() -> App:
    """The one fixture app shared by every case in this module."""
    app = App(name="parity-app", version="0.1.0")

    @app.tool
    def status() -> dict:
        """Return a JSON-able status value."""
        return {"ok": True, "count": 3}

    @app.tool(group=("data",))
    def echo(text: str) -> dict:
        """Echo the given text back."""
        return {"text": text}

    @app.tool
    def fail_structured() -> None:
        """Always raise a structured AgentfrontError."""
        raise AgentfrontError(
            code=3, message=_STRUCTURED_MESSAGE, remediation=_STRUCTURED_REMEDIATION
        )

    @app.tool
    def fail_generic() -> None:
        """Always raise a plain ValueError."""
        raise ValueError("boom")

    return app


@pytest.fixture
def app() -> App:
    return _build_app()


# ---------------------------------------------------------------------------
# 1. Session.dispatch(...).last_result == call_mcp(...) — exact payload
#    equality for all three cases (success, AgentfrontError, ValueError).
# ---------------------------------------------------------------------------


def test_success_session_last_result_matches_call_mcp(app: App) -> None:
    session = Session(app)
    session.dispatch(SelectorAction(selector="status", args={}))
    assert session.last_result == call_mcp(app, ["status"], {})
    assert session.last_result == {"result": {"ok": True, "count": 3}}


def test_success_grouped_session_last_result_matches_call_mcp(app: App) -> None:
    session = Session(app)
    session.dispatch(SelectorAction(selector="data.echo", args={"text": "hi"}))
    assert session.last_result == call_mcp(app, ["data", "echo"], {"text": "hi"})
    assert session.last_result == {"result": {"text": "hi"}}


def test_agentfront_error_session_last_result_matches_call_mcp(app: App) -> None:
    session = Session(app)
    session.dispatch(SelectorAction(selector="fail_structured", args={}))
    mcp_result = call_mcp(app, ["fail_structured"], {})
    assert session.last_result == mcp_result
    assert mcp_result == {
        "error": {
            "code": 3,
            "message": _STRUCTURED_MESSAGE,
            "remediation": _STRUCTURED_REMEDIATION,
        }
    }


def test_value_error_session_last_result_matches_call_mcp(app: App) -> None:
    session = Session(app)
    session.dispatch(SelectorAction(selector="fail_generic", args={}))
    mcp_result = call_mcp(app, ["fail_generic"], {})
    assert session.last_result == mcp_result
    assert mcp_result == {
        "error": {
            "code": 1,
            "message": "ValueError: boom",
            "remediation": "check command arguments",
        }
    }


# ---------------------------------------------------------------------------
# 2. TAUI state reflects each outcome.
# ---------------------------------------------------------------------------


def test_success_taui_state_shows_check_line(app: App) -> None:
    session = Session(app)
    state = session.dispatch(SelectorAction(selector="status", args={}))
    assert state.conversation[-1].text.startswith("✓ status")


def test_success_grouped_taui_state_shows_check_line(app: App) -> None:
    session = Session(app)
    state = session.dispatch(SelectorAction(selector="data.echo", args={"text": "hi"}))
    assert state.conversation[-1].text.startswith("✓ data.echo")


def test_agentfront_error_taui_state_opens_blocking_popup_with_problem_entry(app: App) -> None:
    session = Session(app)
    state = session.dispatch(SelectorAction(selector="fail_structured", args={}))

    popup = next(p for p in state.popups if p.id == "popup.tool-error")
    assert popup.visible is True
    assert popup.blocking is True
    assert popup.message == _STRUCTURED_MESSAGE

    assert state.problems[-1] == {
        "selector": "fail_structured",
        "code": 3,
        "message": _STRUCTURED_MESSAGE,
        "remediation": _STRUCTURED_REMEDIATION,
    }
    assert state.conversation[-1].text == "✗ fail_structured"


def test_value_error_taui_state_opens_blocking_popup_with_problem_entry(app: App) -> None:
    session = Session(app)
    state = session.dispatch(SelectorAction(selector="fail_generic", args={}))

    popup = next(p for p in state.popups if p.id == "popup.tool-error")
    assert popup.visible is True
    assert popup.blocking is True

    assert state.problems[-1] == {
        "selector": "fail_generic",
        "code": 1,
        "message": "ValueError: boom",
        "remediation": "check command arguments",
    }
    assert state.conversation[-1].text == "✗ fail_generic"


# ---------------------------------------------------------------------------
# 3. CLI parity — run_cli(...) observable behavior.
# ---------------------------------------------------------------------------


def test_success_cli_prints_result_and_exits_zero(app: App) -> None:
    result = run_cli(app, ["status", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"ok": True, "count": 3}


def test_success_grouped_cli_prints_result_and_exits_zero(app: App) -> None:
    result = run_cli(app, ["data", "echo", "hi", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"text": "hi"}


def test_agentfront_error_cli_exits_with_its_code_and_carries_message_and_remediation(
    app: App,
) -> None:
    result = run_cli(app, ["fail_structured"])
    assert result.exit_code == 3
    assert f"error: {_STRUCTURED_MESSAGE}" in result.stderr
    assert f"hint: {_STRUCTURED_REMEDIATION}" in result.stderr


def test_value_error_cli_surfaces_message_with_nonzero_exit(app: App) -> None:
    result = run_cli(app, ["fail_generic"])
    assert result.exit_code != 0
    # See the module docstring: cli_surface wraps unexpected exceptions in a
    # friendlier "unexpected: <ClassName>: <message>" shape rather than the
    # bare MCP-shape message/remediation pair, so only the ORIGINAL
    # exception's message text is asserted here (content, not formatting) —
    # this is what the contract's spec for this case calls for.
    assert "boom" in result.stderr


# ---------------------------------------------------------------------------
# 4. Cross-check: for the AgentfrontError case, the three error payloads'
#    {code, message, remediation} triples are IDENTICAL across
#    session.last_result["error"], call_mcp(...)["error"], and the CLI's
#    observable (--json) error output.
# ---------------------------------------------------------------------------


def test_agentfront_error_triple_identical_across_all_three_surfaces(app: App) -> None:
    session = Session(app)
    session.dispatch(SelectorAction(selector="fail_structured", args={}))
    session_error = session.last_result["error"]

    mcp_error = call_mcp(app, ["fail_structured"], {})["error"]

    cli_result = run_cli(app, ["fail_structured", "--json"])
    assert cli_result.exit_code == 3
    cli_error = json.loads(cli_result.stderr)

    assert session_error == mcp_error == cli_error
    assert session_error == {
        "code": 3,
        "message": _STRUCTURED_MESSAGE,
        "remediation": _STRUCTURED_REMEDIATION,
    }
