"""Tests for ``agentfront.doctor_live`` — the runtime doctor.

The doctor audits an App's live surfaces and returns a list of :class:`Check`
results.  Warnings are allowed; only ``"fail"`` makes the app unhealthy.
"""

from __future__ import annotations

import sys
from io import StringIO

import pytest

from agentfront import App
from agentfront.doctor_live import Check, healthy, run_doctor

# --- helpers -----------------------------------------------------------------


def _make_populated_app() -> App:
    """App with one doc and a few tools (well under threshold)."""
    app = App(name="mytool", version="1.0.0")
    app.add_doc(slug="intro", title="Introduction", text="# Intro\nbody")

    @app.tool
    def search(query: str) -> str:  # noqa: ARG001
        """Search the corpus."""
        return query

    @app.tool
    def index(path: str) -> str:  # noqa: ARG001
        """Index a file."""
        return path

    return app


def _make_big_app() -> App:
    """App with more tools than THRESHOLD (12)."""
    app = App(name="big")
    app.add_doc(slug="a", title="A", text="x")

    for i in range(15):

        def _tool(idx: int = i) -> str:  # noqa: ARG001
            """A tool."""
            return str(idx)

        _tool.__name__ = f"tool_{i}"
        app.tool(_tool)

    return app


# --- happy path --------------------------------------------------------------


def test_populated_app_all_checks_ok() -> None:
    app = _make_populated_app()
    checks = run_doctor(app)
    names = {c.name for c in checks}
    assert "sitemap" in names
    assert "mcp_menu_size" in names
    assert "learn" in names
    for c in checks:
        assert c.status == "ok", f"{c.name} expected ok, got {c.status}"


def test_populated_app_healthy() -> None:
    app = _make_populated_app()
    checks = run_doctor(app)
    assert healthy(checks) is True


# --- mcp_menu_size warn path -------------------------------------------------


def test_exceeding_threshold_warns() -> None:
    app = _make_big_app()
    checks = run_doctor(app)
    menu_check = next(c for c in checks if c.name == "mcp_menu_size")
    assert menu_check.status == "warn"
    assert menu_check.remediation != ""


def test_warn_still_healthy() -> None:
    app = _make_big_app()
    checks = run_doctor(app)
    assert healthy(checks) is True


# --- remediation on non-ok checks -------------------------------------------


def test_non_ok_checks_have_remediation() -> None:
    """Every non-ok check must carry a non-empty remediation string."""
    app = App(name="broken")
    # no docs → sitemap will fail
    checks = run_doctor(app)
    for c in checks:
        if c.status != "ok":
            assert c.remediation != "", f"{c.name} has empty remediation"


# --- Check dataclass shape --------------------------------------------------


def test_check_is_frozen() -> None:
    c = Check(name="x", status="ok", remediation="")
    with pytest.raises(Exception, match="cannot assign"):
        c.status = "fail"  # type: ignore[attr-defined]


def test_check_status_values() -> None:
    for status in ("ok", "warn", "fail"):
        c = Check(name="x", status=status, remediation="")
        assert c.status == status


# --- healthy edge cases ---------------------------------------------------


def test_healthy_empty_list() -> None:
    assert healthy([]) is True


def test_healthy_with_warn_only() -> None:
    checks = [Check(name="a", status="warn", remediation="fix me")]
    assert healthy(checks) is True


def test_unhealthy_with_fail() -> None:
    checks = [Check(name="a", status="fail", remediation="fix me")]
    assert healthy(checks) is False


# --- sitemap check details --------------------------------------------------


def test_sitemap_ok_when_docs_registered() -> None:
    app = _make_populated_app()
    checks = run_doctor(app)
    sitemap = next(c for c in checks if c.name == "sitemap")
    assert sitemap.status == "ok"


def test_sitemap_fail_when_no_docs() -> None:
    app = App(name="empty")
    checks = run_doctor(app)
    sitemap = next(c for c in checks if c.name == "sitemap")
    assert sitemap.status == "fail"
    assert sitemap.remediation != ""


# --- learn check details --------------------------------------------------


def test_learn_ok_on_populated_app() -> None:
    app = _make_populated_app()
    checks = run_doctor(app)
    learn = next(c for c in checks if c.name == "learn")
    assert learn.status == "ok"


def test_learn_check_exercises_run_cli() -> None:
    """Ensure the learn check actually exercises run_cli, not just make_cli."""
    app = _make_populated_app()
    # Capture stdout to confirm run_cli was invoked
    captured = StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        checks = run_doctor(app)
    finally:
        sys.stdout = old_stdout
    learn = next(c for c in checks if c.name == "learn")
    assert learn.status == "ok"
    # run_cli prints to stdout, so there should be output
    assert captured.getvalue() != ""
