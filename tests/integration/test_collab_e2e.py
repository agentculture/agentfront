"""E2E agent-human collaboration round-trip (t14).

This is the spec's success-signal artifact: an agent drives a task through
the TAUI JSON mirror, a human reviews/replays the identical session in the
TUI, states match.

The story reads top-to-bottom as the three audiences this plan exists to
serve, all sharing ONE ``App`` built once by ``_build_app`` below:

1. AUTHOR — builds a real app (grouped tools, one of which fails with a
   structured ``AgentfrontError``, plus docs) and proves it once with the
   public harness: ``assert_surfaces_agree(app)``.
2. AGENT — drives the app purely through the JSON mirror: reads
   ``mirror()["available_actions"]``, locates the target tool's selector
   from the mirror (never hardcoding it — the dotted path is matched, not
   assumed), dispatches a successful call and a failing one, then PAUSES the
   session by writing a snapshot.
3. HUMAN — reviews the recorded artifact (the snapshot IS the truth: its
   events replay to its own state), then RESUMES the paused session live in
   the TUI via ``LiveDriver``: dismisses the blocking error popup left by
   the agent's failing call, navigates with the arrow keys, and quits.
4. PARITY CODA — proves the agent's selector-dispatch path and the human's
   arrow-key navigation path land on the identical state for a reachable
   panel item, closing the loop this whole plan was built to prove.
"""

from __future__ import annotations

import pytest

from agentfront import App
from agentfront.errors import AgentfrontError
from agentfront.taui.derive import make_baseline
from agentfront.taui.driver import LiveDriver
from agentfront.taui.events import SelectorAction
from agentfront.taui.reducer import replay
from agentfront.taui.session import Session
from agentfront.taui.snapshot import read_snapshot, resume, write_snapshot
from agentfront.testing import (
    assert_agent_human_parity,
    assert_replay_equivalent,
    assert_surfaces_agree,
)

_TASK_GROUP = ("tasks",)
_COMPLETE_NAME = "complete"
_VANISH_NAME = "vanish"
_FAIL_TASK_ID = "t-404"


# ---------------------------------------------------------------------------
# AUTHOR — the one app all three audiences share.
# ---------------------------------------------------------------------------


def _build_app() -> App:
    """A tiny task-tracking app: two grouped tools (one always fails), docs."""
    app = App(
        name="collab-demo",
        version="1.0.0",
        description="Tiny task tracker used to prove the agent/human collaboration round-trip",
    )

    app.add_doc(
        slug="overview",
        title="Overview",
        text=(
            "# Overview\n\n"
            "A tiny task-tracking demo used by the e2e collaboration story: "
            "one tool that succeeds, one that always fails.\n"
        ),
    )
    app.add_doc(
        slug="usage",
        title="Usage",
        text=("# Usage\n\n" "Call `tasks complete <task_id>` to mark a task done.\n"),
    )

    @app.tool(group=_TASK_GROUP)
    def complete(task_id: str) -> dict:
        """Mark a task complete."""
        return {"task_id": task_id, "status": "done"}

    @app.tool(group=_TASK_GROUP)
    def vanish(task_id: str) -> None:
        """Always fails: the task can never be found."""
        raise AgentfrontError(
            code=3,
            message=f"task {task_id!r} not found",
            remediation="check the task id and retry",
        )

    def _status(**kwargs: object) -> str:
        return "ok"

    app.add_command("status", _status, help="Show demo app status")

    return app


@pytest.fixture
def app() -> App:
    return _build_app()


# ---------------------------------------------------------------------------
# Helpers — locating a tool's selector FROM the mirror, not hardcoding it.
# ---------------------------------------------------------------------------


def _selector_for(group: tuple[str, ...], name: str) -> str:
    """The dotted path a tool registered under *group*/*name* is expected at."""
    return ".".join(group + (name,))


def _find_action(mirror: dict, selector: str) -> dict:
    """Locate *selector* inside ``mirror["available_actions"]`` by dotted path.

    Raises ``AssertionError`` (naming every selector the mirror DID offer) if
    it is absent — the agent never assumes an index or hardcodes the mirror's
    shape, it matches on the selector it expects a registered tool to expose.
    """
    for action in mirror["available_actions"]:
        if action["selector"] == selector:
            return action
    offered = [a["selector"] for a in mirror["available_actions"]]
    raise AssertionError(
        f"selector {selector!r} not found in mirror available_actions: {offered!r}"
    )


# ---------------------------------------------------------------------------
# 1. AUTHOR — build the app, prove every surface agrees.
# ---------------------------------------------------------------------------


def test_author_builds_app_and_all_surfaces_agree(app: App) -> None:
    """AUTHOR's proof: the CLI, MCP, HTTP, and TAUI surfaces never drifted."""
    assert_surfaces_agree(app)  # must not raise


# ---------------------------------------------------------------------------
# 2 + 3. AGENT drives via the mirror and pauses; HUMAN reviews the recorded
# artifact, replays it, then resumes the SAME session live in the TUI.
# ---------------------------------------------------------------------------


def test_agent_drives_and_human_reviews_resumes_the_same_session(app: App, tmp_path) -> None:
    # --- AGENT: read the mirror, locate the target tool's selector, dispatch ---
    session = Session(app)
    mirror = session.mirror()

    success_selector = _selector_for(_TASK_GROUP, _COMPLETE_NAME)
    success_action = _find_action(mirror, success_selector)
    assert success_action["input"] == "select"

    session.dispatch(SelectorAction(selector=success_action["selector"], args={"task_id": "t-1"}))

    assert any(
        "✓" in line.text and success_selector in line.text for line in session.state.conversation
    )
    assert session.last_result == {"result": {"task_id": "t-1", "status": "done"}}

    fail_selector = _selector_for(_TASK_GROUP, _VANISH_NAME)
    fail_action = _find_action(mirror, fail_selector)
    assert fail_action["input"] == "select"

    session.dispatch(
        SelectorAction(selector=fail_action["selector"], args={"task_id": _FAIL_TASK_ID})
    )

    mirror_after_failure = session.mirror()
    popup = next(p for p in mirror_after_failure["popups"] if p["id"] == "popup.tool-error")
    assert popup["visible"] is True
    assert popup["blocking"] is True

    problem = mirror_after_failure["problems"][-1]
    assert problem["selector"] == fail_selector
    assert problem["code"] == 3
    assert problem["message"] == f"task {_FAIL_TASK_ID!r} not found"
    assert problem["remediation"] == "check the task id and retry"

    # --- AGENT pauses: hand the live session off as a snapshot ---------------
    stem = str(tmp_path / "collab-session")
    write_snapshot(stem, session.state, session.events)

    # --- HUMAN reviews: the recorded artifact IS the truth --------------------
    snapshot = read_snapshot(stem)
    assert replay(snapshot.events, initial=make_baseline(app)) == snapshot.state

    # --- HUMAN resumes: pick the paused session back up, live, in the TUI ----
    resumed_session = resume(stem, app)
    driver = LiveDriver(resumed_session)

    popup_before = next(p for p in resumed_session.state.popups if p.id == "popup.tool-error")
    assert popup_before.visible is True
    assert popup_before.blocking is True

    driver.feed_key("esc")  # dismisses the blocking error popup left by the agent

    popup_after = next(p for p in resumed_session.state.popups if p.id == "popup.tool-error")
    assert popup_after.visible is False
    assert popup_after.blocking is False

    # Navigate with the arrow keys — focus actually moves and moves back.
    focus_at_rest = resumed_session.state.focused
    driver.feed_key("up")
    assert resumed_session.state.focused != focus_at_rest
    driver.feed_key("down")
    assert resumed_session.state.focused == focus_at_rest

    # "q" quits — no quit-trap, the driver simply stops.
    assert driver.running is True
    driver.feed_key("q")
    assert driver.running is False

    assert_replay_equivalent(resumed_session)


# ---------------------------------------------------------------------------
# 4. PARITY CODA — agent dispatch and human navigation land on identical
# state for a reachable panel item, closing the loop.
# ---------------------------------------------------------------------------


def test_parity_coda_agent_dispatch_and_human_navigation_agree(app: App) -> None:
    baseline = make_baseline(app)
    # A host-command panel item is reachable by both paths but is not itself
    # a registered tool, so the agent's dispatch degrades to pure navigation
    # — exactly what parity with the human's arrow-key path requires.
    selector = next(
        item.id for panel in baseline.panels for item in panel.items if item.id.startswith("cmd.")
    )

    assert_agent_human_parity(app, selector)  # must not raise
