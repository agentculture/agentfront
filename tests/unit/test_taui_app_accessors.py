"""Unit tests for App.taui() / App.taui_mirror() / App.taui_driver() accessors."""

from __future__ import annotations

import sys

from agentfront import App


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
    # Ensure the module is not pre-loaded.
    for mod in list(sys.modules.keys()):
        if mod.startswith("agentfront.taui"):
            del sys.modules[mod]

    app = App(name="Lazy", version="0.0.1")
    assert "agentfront.taui.derive" not in sys.modules

    app.taui()

    assert "agentfront.taui.derive" in sys.modules


def test_taui_mirror_accessor_is_lazy() -> None:
    """agentfront.taui.mirror must NOT be imported until app.taui_mirror() is called."""
    for mod in list(sys.modules.keys()):
        if mod.startswith("agentfront.taui"):
            del sys.modules[mod]

    app = App(name="LazyMirror", version="0.0.1")
    assert "agentfront.taui.mirror" not in sys.modules

    app.taui_mirror()

    assert "agentfront.taui.mirror" in sys.modules


def test_taui_driver_accessor_is_lazy() -> None:
    """agentfront.taui.driver must NOT be imported until app.taui_driver() is called."""
    for mod in list(sys.modules.keys()):
        if mod.startswith("agentfront.taui"):
            del sys.modules[mod]

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
