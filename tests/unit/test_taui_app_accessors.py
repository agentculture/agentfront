"""Unit tests for App.taui() / App.taui_mirror() / App.taui_driver() accessors."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import Iterator

from agentfront import App


@contextmanager
def _evicted_taui_modules() -> Iterator[None]:
    """Evict every loaded ``agentfront.taui*`` module, restoring originals on exit.

    The lazy-import tests need the taui submodules genuinely absent from
    ``sys.modules`` so they can assert the accessor triggers the import. But if
    a freshly re-imported module were left behind, the rest of the suite would
    see a SECOND copy of e.g. ``PanelItem`` (a new class object) — breaking
    ``isinstance`` checks in unrelated tests, since modules imported at
    collection time (``make_baseline``) still reference the original class.
    Snapshot the evicted modules and restore the originals on exit so module
    identity stays stable suite-wide.
    """
    saved = {name: mod for name, mod in sys.modules.items() if name.startswith("agentfront.taui")}
    for name in saved:
        del sys.modules[name]
    try:
        yield
    finally:
        # Drop any freshly re-imported taui modules, then restore the originals.
        for name in [n for n in sys.modules if n.startswith("agentfront.taui")]:
            del sys.modules[name]
        sys.modules.update(saved)


def _make_fixture() -> App:
    """Return an App with a grouped tool and a host command."""
    app = App(name="TestApp", version="0.1.0", description="A test app")

    @app.tool(group=("search",))
    def query(text: str) -> str:
        """Search the corpus."""
        return text

    def _deploy_handler() -> None:
        pass

    app.add_command("deploy", _deploy_handler, help="Deploy the app")

    return app


# ---------------------------------------------------------------------------
# Lazy-import checks
# ---------------------------------------------------------------------------


def test_taui_accessor_is_lazy() -> None:
    """agentfront.taui.derive must NOT be imported until app.taui() is called."""
    with _evicted_taui_modules():
        app = App(name="Lazy", version="0.0.1")
        assert "agentfront.taui.derive" not in sys.modules

        app.taui()

        assert "agentfront.taui.derive" in sys.modules


def test_taui_mirror_accessor_is_lazy() -> None:
    """agentfront.taui.mirror must NOT be imported until app.taui_mirror() is called."""
    with _evicted_taui_modules():
        app = App(name="LazyMirror", version="0.0.1")
        assert "agentfront.taui.mirror" not in sys.modules

        app.taui_mirror()

        assert "agentfront.taui.mirror" in sys.modules


def test_taui_driver_accessor_is_lazy() -> None:
    """agentfront.taui.driver must NOT be imported until app.taui_driver() is called."""
    with _evicted_taui_modules():
        app = App(name="LazyDriver", version="0.0.1")
        assert "agentfront.taui.driver" not in sys.modules

        app.taui_driver()

        assert "agentfront.taui.driver" in sys.modules


# ---------------------------------------------------------------------------
# Functional checks
# ---------------------------------------------------------------------------


def test_taui_returns_taui_state_with_panels() -> None:
    app = _make_fixture()
    state = app.taui()

    from agentfront.taui.state import TAUIState

    assert isinstance(state, TAUIState)
    # The grouped tool should appear as a dotted-path PanelItem.
    item_ids = [i.id for p in state.panels for i in p.items]
    assert "search.query" in item_ids


def test_taui_mirror_returns_dict_with_expected_keys() -> None:
    app = _make_fixture()
    mirror = app.taui_mirror()

    assert isinstance(mirror, dict)
    assert "taui_version" in mirror
    assert "available_actions" in mirror
    assert len(mirror["available_actions"]) > 0


def test_taui_driver_returns_driver_with_state() -> None:
    app = _make_fixture()
    driver = app.taui_driver()

    assert hasattr(driver, "state")
    # The driver's state must match the baseline state.
    assert driver.state.to_dict() == app.taui().to_dict()
