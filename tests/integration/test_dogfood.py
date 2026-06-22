"""Dogfood integration tests (t9 — covers c1, h4, c8).

agentfront serves its OWN three surfaces from its own config, and they agree —
the full import -> config -> live round-trip, proven against agentfront itself.
"""

from agentfront import __version__
from agentfront._dogfood import app, build_app, main
from agentfront.doctor_live import healthy, run_doctor
from agentfront.serve import surfaces_agree


def test_dogfood_app_has_docs_and_version_tool():
    a = build_app()
    assert a.name == "agentfront"
    assert a.version == __version__
    assert len(a.list_docs()) >= 1
    assert any(t.name == "version" for t in a.list_tools())


def test_module_level_app_is_built():
    # `from agentfront._dogfood import app` works like any host package
    assert app.name == "agentfront"
    assert len(app.list_docs()) >= 1


def test_dogfood_three_surfaces_build():
    a = build_app()
    assert a.http_app() is not None
    assert a.mcp_server() is not None
    assert a.cli() is not None


def test_dogfood_surfaces_agree():
    assert surfaces_agree(build_app()) is True


def test_dogfood_doctor_healthy():
    assert healthy(run_doctor(build_app())) is True


def test_dogfood_version_tool_returns_version():
    tool = build_app().get_tool("version")
    assert tool is not None
    assert tool.func() == __version__


def test_dogfood_main_gate_passes(capsys):
    rc = main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "DOGFOOD OK" in out
